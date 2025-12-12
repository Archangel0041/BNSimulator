"""
Battle Engine for BN Simulator.
Core combat mechanics and battle simulation.
"""

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from .data_loader import GameData, get_game_data
from .models import (
    Ability, Action, ActionResult, BattleState, BattleUnit, DamageResult,
    DamageType, EncounterWave, GridLayout, Side, StatusEffect, StatusEffectType,
    UnitTemplate
)


@dataclass
class BattleConfig:
    """Configuration for battle simulation."""
    # RNG settings
    seed: Optional[int] = None
    deterministic: bool = False  # If True, use average damage instead of random

    # Gameplay options
    allow_surrender: bool = True
    max_turns: int = 100

    # Debug
    verbose: bool = False


class BattleEngine:
    """
    Core battle simulation engine.

    Handles:
    - Turn order and execution
    - Damage calculation
    - Targeting and range validation
    - Status effects
    - Win/loss conditions
    """

    def __init__(self, game_data: Optional[GameData] = None, config: Optional[BattleConfig] = None):
        self.game_data = game_data or get_game_data()
        self.config = config or BattleConfig()
        self.rng = random.Random(self.config.seed)

    def create_battle_unit(
        self,
        template_id: int,
        level: int = 0,
        position: int = -1,
        side: Optional[Side] = None
    ) -> Optional[BattleUnit]:
        """Create a battle unit instance from template."""
        template = self.game_data.get_unit(template_id)
        if not template:
            return None

        # Clamp level to available stats
        max_level = len(template.stats_by_level) - 1
        actual_level = min(max(0, level), max_level) if max_level >= 0 else 0

        unit = BattleUnit(
            template_id=template_id,
            template=template,
            level=actual_level,
            position=position,
            side=side or template.side
        )
        unit.init_battle_state()
        return unit

    def setup_battle_from_encounter(
        self,
        encounter_id: int,
        player_unit_ids: list[tuple[int, int, int]] = None,  # (unit_id, level, position)
        wave_index: int = 0
    ) -> Optional[BattleState]:
        """
        Set up a battle from an encounter definition.

        Args:
            encounter_id: ID of the encounter to load
            player_unit_ids: List of (unit_id, level, position) for player units.
                           If None, uses encounter's player_units if defined.
            wave_index: Which wave to start with (0-indexed)

        Returns:
            BattleState or None if encounter not found
        """
        encounter = self.game_data.get_encounter(encounter_id)
        if not encounter:
            return None

        layout = self.game_data.get_layout(encounter.layout_id)
        if not layout:
            layout = self.game_data.get_layout(2)  # Default layout

        state = BattleState(
            layout=layout,
            total_waves=len(encounter.waves),
            current_wave=wave_index
        )

        # Set up player units
        if player_unit_ids:
            for unit_id, level, pos in player_unit_ids:
                unit = self.create_battle_unit(unit_id, level, pos, Side.PLAYER)
                if unit:
                    state.player_units.append(unit)
        elif encounter.player_units:
            for grid_id, unit_id in encounter.player_units:
                unit = self.create_battle_unit(unit_id, 0, grid_id, Side.PLAYER)
                if unit:
                    state.player_units.append(unit)

        # Set up enemy units from wave
        if wave_index < len(encounter.waves):
            wave = encounter.waves[wave_index]
            self._spawn_wave(state, wave, encounter.level)

        return state

    def setup_custom_battle(
        self,
        player_units: list[tuple[int, int, int]],  # (unit_id, level, position)
        enemy_units: list[tuple[int, int, int]],
        layout_id: int = 2
    ) -> BattleState:
        """Set up a custom battle with specified units."""
        layout = self.game_data.get_layout(layout_id)
        if not layout:
            layout = self.game_data.get_layout(2)

        state = BattleState(layout=layout, total_waves=1)

        for unit_id, level, pos in player_units:
            unit = self.create_battle_unit(unit_id, level, pos, Side.PLAYER)
            if unit:
                state.player_units.append(unit)

        for unit_id, level, pos in enemy_units:
            unit = self.create_battle_unit(unit_id, level, pos, Side.HOSTILE)
            if unit:
                state.enemy_units.append(unit)

        return state

    def _spawn_wave(self, state: BattleState, wave: EncounterWave, encounter_level: int):
        """Spawn units for a wave."""
        for grid_id, unit_id in wave.units:
            template = self.game_data.get_unit(unit_id)
            if not template:
                continue

            # Determine level based on encounter level and unit stats
            level = self._get_unit_level_for_encounter(template, encounter_level)
            unit = self.create_battle_unit(unit_id, level, grid_id, Side.HOSTILE)
            if unit:
                state.enemy_units.append(unit)

    def _get_unit_level_for_encounter(self, template: UnitTemplate, encounter_level: int) -> int:
        """Determine appropriate unit level for encounter."""
        # Find level closest to encounter level based on stats
        for i, stats in enumerate(template.stats_by_level):
            if stats.pv >= encounter_level:
                return max(0, i - 1)
        return len(template.stats_by_level) - 1

    def get_valid_actions(self, state: BattleState) -> list[Action]:
        """Get all valid actions for the current turn."""
        actions = []
        units = state.player_units if state.is_player_turn else state.enemy_units
        target_units = state.enemy_units if state.is_player_turn else state.player_units

        for unit_idx, unit in enumerate(units):
            if not unit.is_alive or unit.has_acted or unit.is_stunned:
                continue

            for weapon_id, weapon in unit.template.weapons.items():
                # Check ammo
                if weapon.stats.ammo > 0:
                    current_ammo = unit.weapon_ammo.get(weapon_id, 0)
                    if current_ammo <= 0:
                        continue

                for ability_id in weapon.abilities:
                    ability = self.game_data.get_ability(ability_id)
                    if not ability:
                        continue

                    # Check cooldown
                    if unit.weapon_cooldowns.get(ability_id, 0) > 0:
                        continue

                    # Get valid targets
                    valid_targets = self._get_valid_targets(state, unit, ability, target_units)
                    for target_pos in valid_targets:
                        actions.append(Action(
                            unit_idx=unit_idx,
                            weapon_id=weapon_id,
                            ability_id=ability_id,
                            target_pos=target_pos
                        ))

        return actions

    def _get_valid_targets(
        self,
        state: BattleState,
        attacker: BattleUnit,
        ability: Ability,
        potential_targets: list[BattleUnit]
    ) -> list[int]:
        """Get valid target positions for an ability."""
        valid = []

        # Get all positions with living targets
        target_positions = set()
        for target in potential_targets:
            if target.is_alive:
                target_positions.add(target.position)

        # Check range for each position
        for pos in target_positions:
            if self._is_in_range(state, attacker.position, pos, ability):
                valid.append(pos)

        return valid

    def _is_in_range(
        self,
        state: BattleState,
        attacker_pos: int,
        target_pos: int,
        ability: Ability
    ) -> bool:
        """Check if target is in range for ability."""
        if not state.layout:
            return True  # No layout = no range restrictions

        # Convert to grid coordinates
        attacker_row, attacker_col = state.layout.pos_to_coords(attacker_pos)
        target_row, target_col = state.layout.pos_to_coords(target_pos)

        # Calculate distance (using row distance as primary range metric)
        # In this game, "range" typically refers to how many rows away
        row_dist = abs(target_row - attacker_row)

        # Also consider column distance for some abilities
        col_dist = abs(target_col - attacker_col)

        # Simple range check
        # Most abilities use row-based range
        distance = row_dist  # Can be modified based on game rules

        return ability.stats.min_range <= distance <= ability.stats.max_range

    def execute_action(self, state: BattleState, action: Action) -> ActionResult:
        """Execute an action and update battle state."""
        result = ActionResult(action=action)

        units = state.player_units if state.is_player_turn else state.enemy_units
        targets = state.enemy_units if state.is_player_turn else state.player_units

        if action.unit_idx >= len(units):
            return result

        attacker = units[action.unit_idx]
        weapon = attacker.template.weapons.get(action.weapon_id)
        ability = self.game_data.get_ability(action.ability_id)

        if not weapon or not ability or not attacker.is_alive:
            return result

        # Consume ammo
        if weapon.stats.ammo > 0:
            attacker.weapon_ammo[action.weapon_id] = attacker.weapon_ammo.get(action.weapon_id, 0) - ability.stats.ammo_required

        # Set cooldowns
        if ability.stats.ability_cooldown > 0:
            attacker.weapon_cooldowns[action.ability_id] = ability.stats.ability_cooldown

        if ability.stats.global_cooldown > 0:
            attacker.global_cooldown = ability.stats.global_cooldown

        # Mark as acted
        attacker.has_acted = True

        # Calculate and apply damage
        affected_positions = self._get_affected_positions(state, action.target_pos, ability)

        for pos in affected_positions:
            # Find target at position
            target = state.get_unit_at_position(pos, Side.HOSTILE if state.is_player_turn else Side.PLAYER)
            if not target:
                continue

            target_idx = targets.index(target) if target in targets else -1
            if target_idx < 0:
                continue

            # Calculate damage
            damage_result = self._calculate_damage(attacker, target, weapon, ability)
            damage_result.target_idx = target_idx

            # Apply damage
            self._apply_damage(target, damage_result)
            result.damage_results.append(damage_result)

            # Update statistics
            if state.is_player_turn:
                state.total_damage_dealt += damage_result.damage
                if damage_result.killed:
                    state.enemies_killed += 1
            else:
                state.total_damage_taken += damage_result.damage
                if damage_result.killed:
                    state.units_lost += 1

            # Apply status effects
            for effect_id, chance in ability.status_effects.items():
                if self.rng.random() * 100 < chance:
                    if self._apply_status_effect(target, effect_id, damage_result.damage):
                        result.status_effects_applied.append((target_idx, effect_id))

        return result

    def _get_affected_positions(
        self,
        state: BattleState,
        target_pos: int,
        ability: Ability
    ) -> list[int]:
        """Get all positions affected by an ability's AOE."""
        positions = [target_pos]

        if not ability.target_area or not ability.target_area.data:
            return positions

        if not state.layout:
            return positions

        target_row, target_col = state.layout.pos_to_coords(target_pos)

        for entry in ability.target_area.data:
            new_row = target_row + entry.pos.y
            new_col = target_col + entry.pos.x

            # Check bounds
            if 0 <= new_row < state.layout.height and 0 <= new_col < state.layout.width:
                new_pos = state.layout.coords_to_pos(new_row, new_col)
                if new_pos not in positions:
                    positions.append(new_pos)

        return positions

    def _calculate_damage(
        self,
        attacker: BattleUnit,
        target: BattleUnit,
        weapon,
        ability: Ability
    ) -> DamageResult:
        """
        Calculate damage for an attack.

        Damage formula: random(base_damage_min, base_damage_max) * (1 + 2 * power / 100)
        Defense, accuracy, offense are only used for dodge calculation.
        """
        result = DamageResult(target_idx=-1, damage=0, is_crit=False, is_dodge=False)

        # Check dodge - uses defense, accuracy, dodge stats
        # TODO: Verify exact dodge formula
        dodge_chance = max(0, target.stats.dodge - attacker.stats.accuracy)
        if not self.config.deterministic and self.rng.random() * 100 < dodge_chance:
            result.is_dodge = True
            return result

        # Base damage calculation: random(min, max) * (1 + 2 * power / 100)
        power_multiplier = 1 + 2 * attacker.stats.power / 100

        if self.config.deterministic:
            base_damage = (weapon.stats.base_damage_min + weapon.stats.base_damage_max) / 2
        else:
            base_damage = self.rng.randint(
                weapon.stats.base_damage_min,
                max(weapon.stats.base_damage_min, weapon.stats.base_damage_max)
            )

        damage = base_damage * power_multiplier

        # Check critical hit
        crit_chance = (
            weapon.stats.base_crit_percent +
            attacker.stats.critical +
            ability.stats.critical_hit_percent
        )

        # Apply critical bonuses for target tags
        for tag in target.template.tags:
            if tag in ability.critical_bonuses:
                crit_chance += ability.critical_bonuses[tag]

        if not self.config.deterministic and self.rng.random() * 100 < crit_chance:
            result.is_crit = True
            damage *= 1.5  # Critical multiplier (TODO: verify)

        # Apply damage type modifiers
        damage_type = ability.stats.damage_type
        damage_type_name = self._get_damage_type_name(damage_type)

        if damage_type_name in target.stats.damage_mods:
            damage *= target.stats.damage_mods[damage_type_name]

        # Apply class damage modifiers
        attacker_class = self.game_data.get_class_config(attacker.template.class_id)
        if attacker_class and target.template.class_id in attacker_class.damage_mods:
            damage *= attacker_class.damage_mods[target.template.class_id]

        # Apply status effect damage modifiers (vulnerability effects)
        for effect in target.status_effects:
            if damage_type in effect.stun_damage_mods:
                damage *= effect.stun_damage_mods[damage_type]

        # Get damage modifiers for this damage type
        armor_mod = target.stats.armor_damage_mods.get(damage_type_name, 1.0)
        hp_mod = target.stats.damage_mods.get(damage_type_name, 1.0)

        # Calculate armor and HP damage
        # Armor absorbs raw damage based on its modifier
        # Overflow damage goes to HP with HP modifier applied
        raw_damage = max(1, damage)

        if target.current_armor > 0 and armor_mod > 0:
            # How much raw damage can armor absorb?
            # armor_absorbed * armor_mod = current_armor (when armor depletes)
            # So: max_raw_absorbed = current_armor / armor_mod
            max_raw_absorbed = target.current_armor / armor_mod

            if raw_damage <= max_raw_absorbed:
                # Armor absorbs all damage
                result.armor_damage = int(raw_damage * armor_mod)
                result.hp_damage = 0
            else:
                # Armor depletes, overflow goes to HP
                result.armor_damage = target.current_armor  # Armor fully depleted
                overflow_raw = raw_damage - max_raw_absorbed
                result.hp_damage = int(overflow_raw * hp_mod)
        else:
            # No armor - all damage goes to HP with HP modifier
            result.hp_damage = int(raw_damage * hp_mod)
            result.armor_damage = 0

        result.damage = result.armor_damage + result.hp_damage
        return result

    def _get_damage_type_name(self, damage_type: int) -> str:
        """Convert damage type ID to name."""
        type_names = {
            1: "piercing",
            2: "crushing",
            3: "cold",
            4: "explosive",
            5: "fire",
            6: "poison"
        }
        return type_names.get(damage_type, "piercing")

    def _apply_damage(self, target: BattleUnit, result: DamageResult):
        """Apply damage to a unit."""
        target.current_armor = max(0, target.current_armor - result.armor_damage)
        target.current_hp = max(0, target.current_hp - result.hp_damage)

        if target.current_hp <= 0:
            result.killed = True

    def _apply_status_effect(
        self,
        target: BattleUnit,
        effect_id: int,
        source_damage: float
    ) -> bool:
        """Apply a status effect to a unit."""
        template = self.game_data.get_status_effect(effect_id)
        if not template:
            return False

        # Check immunity
        if effect_id in target.template.status_effect_immunities:
            return False

        # Check if same family effect exists (replace or stack)
        for i, existing in enumerate(target.status_effects):
            if existing.family == template.family:
                # Replace with longer duration
                if template.duration > existing.remaining_turns:
                    target.status_effects[i] = StatusEffect(
                        id=effect_id,
                        remaining_turns=template.duration,
                        source_damage=source_damage,
                        dot_ability_damage_mult=template.dot_ability_damage_mult,
                        dot_bonus_damage=template.dot_bonus_damage,
                        dot_damage_type=template.dot_damage_type,
                        dot_diminishing=template.dot_diminishing,
                        dot_ap_percent=template.dot_ap_percent,
                        stun_block_action=template.stun_block_action,
                        stun_block_movement=template.stun_block_movement,
                        stun_damage_break=template.stun_damage_break,
                        stun_damage_mods=template.stun_damage_mods.copy(),
                        stun_armor_damage_mods=template.stun_armor_damage_mods.copy(),
                        effect_type=template.effect_type,
                        family=template.family
                    )
                return True

        # Add new effect
        target.status_effects.append(StatusEffect(
            id=effect_id,
            remaining_turns=template.duration,
            source_damage=source_damage,
            dot_ability_damage_mult=template.dot_ability_damage_mult,
            dot_bonus_damage=template.dot_bonus_damage,
            dot_damage_type=template.dot_damage_type,
            dot_diminishing=template.dot_diminishing,
            dot_ap_percent=template.dot_ap_percent,
            stun_block_action=template.stun_block_action,
            stun_block_movement=template.stun_block_movement,
            stun_damage_break=template.stun_damage_break,
            stun_damage_mods=template.stun_damage_mods.copy(),
            stun_armor_damage_mods=template.stun_armor_damage_mods.copy(),
            effect_type=template.effect_type,
            family=template.family
        ))
        return True

    def process_status_effects(self, state: BattleState):
        """Process status effects at end of turn."""
        units = state.player_units if state.is_player_turn else state.enemy_units

        for unit in units:
            if not unit.is_alive:
                continue

            effects_to_remove = []
            for i, effect in enumerate(unit.status_effects):
                # Apply DoT damage
                if effect.effect_type == StatusEffectType.DOT:
                    dot_damage = int(
                        effect.source_damage * effect.dot_ability_damage_mult +
                        effect.dot_bonus_damage
                    )

                    # Apply armor piercing
                    if unit.current_armor > 0:
                        piercing = int(dot_damage * effect.dot_ap_percent)
                        armor_damage = min(dot_damage - piercing, unit.current_armor)
                        hp_damage = piercing + max(0, dot_damage - armor_damage - piercing)
                        unit.current_armor -= armor_damage
                    else:
                        hp_damage = dot_damage

                    unit.current_hp = max(0, unit.current_hp - hp_damage)

                    # Update statistics
                    if unit.side == Side.PLAYER:
                        state.total_damage_taken += dot_damage
                        if unit.current_hp <= 0:
                            state.units_lost += 1
                    else:
                        state.total_damage_dealt += dot_damage
                        if unit.current_hp <= 0:
                            state.enemies_killed += 1

                    # Diminishing damage
                    if effect.dot_diminishing:
                        effect.source_damage *= 0.5

                # Decrement duration
                effect.remaining_turns -= 1
                if effect.remaining_turns <= 0:
                    effects_to_remove.append(i)

            # Remove expired effects
            for i in reversed(effects_to_remove):
                unit.status_effects.pop(i)

    def end_turn(self, state: BattleState):
        """End the current turn and advance to next."""
        # Process status effects
        self.process_status_effects(state)

        # Decrement cooldowns
        units = state.player_units if state.is_player_turn else state.enemy_units
        for unit in units:
            for ability_id in list(unit.weapon_cooldowns.keys()):
                unit.weapon_cooldowns[ability_id] = max(0, unit.weapon_cooldowns[ability_id] - 1)
            unit.global_cooldown = max(0, unit.global_cooldown - 1)
            unit.has_acted = False

        # Check for battle end
        state.check_battle_end()

        # Check for next wave
        if not state.is_finished and state.is_player_turn:
            enemy_alive = any(u.is_alive for u in state.enemy_units)
            if not enemy_alive and state.current_wave < state.total_waves - 1:
                state.current_wave += 1
                # Would need to spawn next wave here

        # Switch turns
        state.is_player_turn = not state.is_player_turn
        state.turn_number += 1

        # Check max turns
        if state.turn_number >= self.config.max_turns:
            state.is_finished = True
            state.player_won = False

    def surrender(self, state: BattleState):
        """Surrender the battle."""
        if self.config.allow_surrender:
            state.is_finished = True
            state.player_won = False
            state.surrendered = True

    def simulate_random_battle(self, state: BattleState) -> BattleState:
        """Simulate a battle with random actions until completion."""
        while not state.is_finished:
            actions = self.get_valid_actions(state)
            if not actions:
                self.end_turn(state)
                continue

            action = self.rng.choice(actions)
            self.execute_action(state, action)
            self.end_turn(state)

        return state

    def clone_state(self, state: BattleState) -> BattleState:
        """Create a deep copy of battle state."""
        return deepcopy(state)


def create_test_battle() -> tuple[BattleEngine, BattleState]:
    """Create a simple test battle for debugging."""
    engine = BattleEngine()

    # Find some player and enemy units
    player_units_templates = engine.game_data.get_player_units()[:3]
    enemy_units_templates = engine.game_data.get_enemy_units()[:3]

    player_units = [(t.id, 0, i) for i, t in enumerate(player_units_templates)]
    enemy_units = [(t.id, 0, i + 5) for i, t in enumerate(enemy_units_templates)]

    state = engine.setup_custom_battle(player_units, enemy_units)
    return engine, state
