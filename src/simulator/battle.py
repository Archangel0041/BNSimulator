"""Core battle simulator engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Iterator
from enum import Enum
import random
import numpy as np

from .enums import (
    DamageType, UnitClass, Side, BattleSide, CellType, TargetType,
    LineOfFire, AttackDirection, StatusEffectType,
    DAMAGE_TYPE_NAMES, TARGETABLE_ALL
)
from .models import (
    Position, UnitTemplate, Ability, Weapon, StatusEffect,
    GridLayout, Encounter, GameConfig
)
from .data_loader import GameDataLoader


class BattleResult(Enum):
    """Battle outcome."""
    IN_PROGRESS = 0
    PLAYER_WIN = 1
    ENEMY_WIN = 2
    SURRENDER = 3


@dataclass
class ActiveStatusEffect:
    """An active status effect on a unit."""
    effect: StatusEffect
    remaining_turns: int
    source_damage: float = 0.0  # For DOT calculation


@dataclass
class BattleUnit:
    """A unit instance in battle."""
    template: UnitTemplate
    position: Position
    battle_side: BattleSide  # Which team the unit fights for (not inherent faction)

    # Current state
    current_hp: int = 0
    current_armor: int = 0
    is_alive: bool = True

    # Cooldowns: weapon_id -> turns remaining
    weapon_cooldowns: dict[int, int] = field(default_factory=dict)
    global_cooldown: int = 0

    # Ammo tracking: weapon_id -> current ammo
    ammo: dict[int, int] = field(default_factory=dict)

    # Status effects
    status_effects: list[ActiveStatusEffect] = field(default_factory=list)

    # Charging ability (if any)
    charging_weapon: Optional[int] = None
    charge_turns_remaining: int = 0

    def __post_init__(self):
        self.current_hp = self.template.stats.hp
        self.current_armor = self.template.stats.armor_hp
        # Initialize ammo for weapons
        for weapon_id, weapon in self.template.weapons.items():
            if weapon.stats.ammo >= 0:
                self.ammo[weapon_id] = weapon.stats.ammo

    @property
    def hp_percent(self) -> float:
        """Get current HP as percentage."""
        max_hp = self.template.stats.hp
        return (self.current_hp / max_hp * 100) if max_hp > 0 else 0

    def take_damage(self, damage: int, damage_type: DamageType, armor_piercing: float = 0.0) -> int:
        """Apply damage to unit. Returns actual damage dealt."""
        if not self.is_alive:
            return 0

        # Get damage type name for modifier lookup
        dtype_name = {
            DamageType.PIERCING: "piercing",
            DamageType.CRUSHING: "crushing",
            DamageType.EXPLOSIVE: "explosive",
            DamageType.FIRE: "fire",
            DamageType.COLD: "cold",
        }.get(damage_type, "piercing")

        # Apply damage modifiers from template
        damage_mod = self.template.stats.damage_mods.get(dtype_name, 1.0)

        # Apply status effect damage modifiers (e.g., firemod)
        # Pick the highest modifier from all active status effects
        status_mod = 1.0
        for status in self.status_effects:
            if status.effect.effect_type == StatusEffectType.STUN:
                dtype_int = damage_type.value
                if dtype_int in status.effect.stun_damage_mods:
                    status_mod = max(status_mod, status.effect.stun_damage_mods[dtype_int])

        # Apply status modifier after template modifier
        damage_mod *= status_mod
        modified_damage = int(damage * damage_mod)

        # Apply to armor first (if present)
        if self.current_armor > 0 and armor_piercing < 1.0:
            armor_damage = int(modified_damage * (1 - armor_piercing))
            armor_mod = self.template.stats.armor_damage_mods.get(dtype_name, 1.0)

            # Apply status effect armor damage modifiers
            # Pick the highest modifier from all active status effects
            armor_status_mod = 1.0
            for status in self.status_effects:
                if status.effect.effect_type == StatusEffectType.STUN:
                    dtype_int = damage_type.value
                    if dtype_int in status.effect.stun_armor_damage_mods:
                        armor_status_mod = max(armor_status_mod, status.effect.stun_armor_damage_mods[dtype_int])

            # Apply status modifier after template modifier
            armor_mod *= armor_status_mod
            armor_damage = int(armor_damage * armor_mod)

            if armor_damage >= self.current_armor:
                # Armor broken, remaining damage goes to HP
                overflow = armor_damage - self.current_armor
                self.current_armor = 0
                self.current_hp -= overflow
            else:
                self.current_armor -= armor_damage
        else:
            self.current_hp -= modified_damage

        # Check death
        if self.current_hp <= 0:
            self.current_hp = 0
            self.is_alive = False

        return modified_damage

    def heal(self, amount: int) -> int:
        """Heal the unit. Returns actual healing done."""
        if not self.is_alive:
            return 0

        max_hp = self.template.stats.hp
        old_hp = self.current_hp
        self.current_hp = min(self.current_hp + amount, max_hp)
        return self.current_hp - old_hp

    def can_act(self) -> bool:
        """Check if unit can take an action this turn."""
        if not self.is_alive:
            return False

        # Check for stun effects
        for status in self.status_effects:
            if (status.effect.effect_type == StatusEffectType.STUN and
                    status.effect.stun_block_action):
                return False

        return True

    def get_available_weapons(self) -> list[int]:
        """Get list of weapon IDs that can be used this turn."""
        if self.global_cooldown > 0:
            return []

        available = []
        for weapon_id, weapon in self.template.weapons.items():
            # Check cooldown
            if self.weapon_cooldowns.get(weapon_id, 0) > 0:
                continue

            # Check ammo
            if weapon.stats.ammo >= 0 and self.ammo.get(weapon_id, 0) <= 0:
                continue

            available.append(weapon_id)

        return available

    def tick_cooldowns(self) -> None:
        """Reduce all cooldowns by 1 at end of turn."""
        if self.global_cooldown > 0:
            self.global_cooldown -= 1

        for weapon_id in self.weapon_cooldowns:
            if self.weapon_cooldowns[weapon_id] > 0:
                self.weapon_cooldowns[weapon_id] -= 1

    def tick_status_effects(self) -> int:
        """Process status effects. Returns DOT damage taken."""
        dot_damage = 0
        remaining_effects = []

        for status in self.status_effects:
            if status.effect.effect_type == StatusEffectType.DOT:
                # Calculate DOT damage
                base_damage = status.source_damage * status.effect.dot_ability_damage_mult
                base_damage += status.effect.dot_bonus_damage
                dot_damage += int(base_damage)

            status.remaining_turns -= 1
            if status.remaining_turns > 0:
                remaining_effects.append(status)

        self.status_effects = remaining_effects

        if dot_damage > 0:
            self.take_damage(dot_damage, DamageType.FIRE)  # DOT is typically fire

        return dot_damage


@dataclass
class Action:
    """A battle action (unit uses ability on target)."""
    unit_index: int
    weapon_id: int
    target_position: Position


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    damage_dealt: dict[int, int] = field(default_factory=dict)  # unit_index -> damage
    kills: list[int] = field(default_factory=list)  # indices of killed units
    status_applied: list[tuple[int, int]] = field(default_factory=list)  # (unit_idx, effect_id)
    message: str = ""


class BattleState:
    """Complete state of a battle."""

    def __init__(
        self,
        data_loader: GameDataLoader,
        layout: GridLayout,
        player_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        player_is_attacker: bool = True
    ):
        self.data_loader = data_loader
        self.layout = layout
        self.player_units = player_units
        self.enemy_units = enemy_units
        self.player_is_attacker = player_is_attacker

        # Turn tracking
        self.turn_number = 0
        self.is_player_turn = True  # Player always goes first

        # Battle result
        self.result = BattleResult.IN_PROGRESS

        # Action history for replay
        self.action_history: list[tuple[Action, ActionResult]] = []

        # RNG state (for reproducibility)
        self.rng = random.Random()

    def seed(self, seed: int) -> None:
        """Set RNG seed for reproducibility."""
        self.rng.seed(seed)

    @property
    def current_side_units(self) -> list[BattleUnit]:
        """Get units for the current turn's side."""
        return self.player_units if self.is_player_turn else self.enemy_units

    @property
    def opposing_side_units(self) -> list[BattleUnit]:
        """Get units for the opposing side."""
        return self.enemy_units if self.is_player_turn else self.player_units

    def get_unit_at_position(self, pos: Position, side: Optional[Side] = None) -> Optional[BattleUnit]:
        """Get unit at a specific position."""
        units = (self.player_units + self.enemy_units) if side is None else (
            self.player_units if side == Side.PLAYER else self.enemy_units
        )
        for unit in units:
            if unit.is_alive and unit.position == pos:
                return unit
        return None

    def get_valid_targets(self, attacker: BattleUnit, weapon_id: int) -> list[Position]:
        """Get all valid target positions for a weapon."""
        weapon = attacker.template.weapons.get(weapon_id)
        if not weapon or not weapon.abilities:
            return []

        # Get ability stats (use first ability)
        ability_id = weapon.abilities[0]
        ability = self.data_loader.get_ability(ability_id)
        if not ability:
            return []

        stats = ability.stats
        valid_targets = []

        # Determine which side to target
        target_units = self.opposing_side_units

        for target_unit in target_units:
            if not target_unit.is_alive:
                continue

            # Check if unit can be targeted by this ability
            if not self._can_target_unit(attacker, target_unit, stats):
                continue

            valid_targets.append(target_unit.position)

        return valid_targets

    def _can_target_unit(self, attacker: BattleUnit, target: BattleUnit, stats) -> bool:
        """Check if attacker can target this unit with given ability stats."""
        # Check target tags
        if stats.targets:
            has_valid_tag = False

            # Check if target has any of the required tags (or child tags via hierarchy)
            for ability_tag in stats.targets:
                # Direct tag match
                if ability_tag in target.template.tags:
                    has_valid_tag = True
                    break

                # Check tag hierarchy - does this ability tag include any of the target's tags?
                child_tags = self.data_loader.config.tag_hierarchy.get(ability_tag, [])
                if any(target_tag in child_tags for target_tag in target.template.tags):
                    has_valid_tag = True
                    break

            # TARGETABLE_ALL (39) is a special tag that matches most units
            if TARGETABLE_ALL in stats.targets:
                has_valid_tag = True

            if not has_valid_tag:
                return False

        # Check range
        distance = self._calculate_distance(attacker.position, target.position)
        if distance < stats.min_range or distance > stats.max_range:
            return False

        # Check line of fire
        if stats.line_of_fire == LineOfFire.DIRECT:
            if not self._has_line_of_sight(attacker.position, target.position):
                return False

        return True

    def _calculate_distance(
        self,
        attacker_pos: Position,
        target_pos: Position,
        cross_grid: bool = True
    ) -> int:
        """
        Calculate grid distance between positions.

        In this game, player and enemy grids face each other. Distance is:
        - Within same grid: based on y-coordinate (row) difference
        - Cross-grid (attacking enemy): row-based with front rows being closest

        The front row (y=0) is closest to the enemy, back row (y=2) is furthest.
        Cross-grid distance = (attacker_row + target_row + 1)
        """
        if cross_grid:
            # Distance across grids: front rows are closest
            # Row 0 (front) attacking row 0 (front) = distance 1
            # Row 2 (back) attacking row 2 (back) = distance 5
            base_distance = attacker_pos.y + target_pos.y + 1
            # Add horizontal offset for diagonal targeting
            col_diff = abs(attacker_pos.x - target_pos.x)
            return base_distance + col_diff // 2
        else:
            # Same-grid distance (e.g., healing allies)
            return abs(attacker_pos.y - target_pos.y) + abs(attacker_pos.x - target_pos.x) // 2

    def _has_line_of_sight(self, attacker_pos: Position, target_pos: Position) -> bool:
        """Check if there's a clear line of sight (no blocking units in between)."""
        # Simplified: check if any unit is directly in the path
        # In this game, front row units typically block back row
        if attacker_pos.x == target_pos.x:
            # Same column - check for blockers
            min_y = min(attacker_pos.y, target_pos.y)
            max_y = max(attacker_pos.y, target_pos.y)
            for y in range(min_y + 1, max_y):
                blocking_pos = Position(attacker_pos.x, y)
                blocking_unit = self.get_unit_at_position(blocking_pos)
                if blocking_unit and blocking_unit.is_alive:
                    return False
        return True

    def get_legal_actions(self) -> list[Action]:
        """Get all legal actions for the current turn."""
        actions = []
        units = self.current_side_units

        for unit_idx, unit in enumerate(units):
            if not unit.can_act():
                continue

            for weapon_id in unit.get_available_weapons():
                valid_targets = self.get_valid_targets(unit, weapon_id)
                for target_pos in valid_targets:
                    actions.append(Action(
                        unit_index=unit_idx,
                        weapon_id=weapon_id,
                        target_position=target_pos
                    ))

        return actions

    def execute_action(self, action: Action) -> ActionResult:
        """Execute a battle action."""
        units = self.current_side_units
        if action.unit_index >= len(units):
            return ActionResult(success=False, message="Invalid unit index")

        unit = units[action.unit_index]
        if not unit.can_act():
            return ActionResult(success=False, message="Unit cannot act")

        weapon = unit.template.weapons.get(action.weapon_id)
        if not weapon:
            return ActionResult(success=False, message="Invalid weapon")

        # Get ability
        ability_id = weapon.abilities[0] if weapon.abilities else None
        if not ability_id:
            return ActionResult(success=False, message="No ability for weapon")

        ability = self.data_loader.get_ability(ability_id)
        if not ability:
            return ActionResult(success=False, message="Ability not found")

        # Execute the attack
        result = self._execute_attack(unit, weapon, ability, action.target_position)

        # Apply cooldowns
        unit.weapon_cooldowns[action.weapon_id] = ability.stats.ability_cooldown
        if ability.stats.global_cooldown > 0:
            unit.global_cooldown = ability.stats.global_cooldown

        # Consume ammo
        if weapon.stats.ammo >= 0:
            unit.ammo[action.weapon_id] = unit.ammo.get(action.weapon_id, 0) - 1

        # Record action
        self.action_history.append((action, result))

        return result

    def _execute_attack(
        self,
        attacker: BattleUnit,
        weapon: Weapon,
        ability: Ability,
        target_pos: Position
    ) -> ActionResult:
        """Execute an attack and calculate damage."""
        result = ActionResult(success=True)
        stats = ability.stats

        # Get target unit(s) based on AOE pattern
        targets = self._get_aoe_targets(target_pos, stats)

        for target_unit, damage_percent in targets:
            if not target_unit.is_alive:
                continue

            # Calculate damage
            damage = self._calculate_damage(attacker, target_unit, weapon, ability, damage_percent)

            # Roll for hit/miss
            hit_chance = self._calculate_hit_chance(attacker, target_unit)
            if self.rng.random() * 100 > hit_chance:
                continue  # Miss

            # Roll for crit
            crit_chance = self._calculate_crit_chance(attacker, target_unit, ability)
            is_crit = self.rng.random() * 100 < crit_chance
            if is_crit:
                damage = int(damage * 1.5)  # 50% crit bonus

            # Apply damage
            actual_damage = target_unit.take_damage(
                damage,
                stats.damage_type,
                stats.armor_piercing_percent
            )

            # Track in result
            target_idx = self._get_unit_index(target_unit)
            result.damage_dealt[target_idx] = result.damage_dealt.get(target_idx, 0) + actual_damage

            if not target_unit.is_alive:
                result.kills.append(target_idx)

            # Apply status effects
            for effect_id, apply_chance in stats.status_effects.items():
                if self.rng.random() * 100 < apply_chance:
                    effect = self.data_loader.status_effects.get(effect_id)
                    if effect and effect_id not in target_unit.template.stats.status_effect_immunities:
                        target_unit.status_effects.append(ActiveStatusEffect(
                            effect=effect,
                            remaining_turns=effect.duration,
                            source_damage=damage
                        ))
                        result.status_applied.append((target_idx, effect_id))

        return result

    def _get_aoe_targets(self, target_pos: Position, stats) -> list[tuple[BattleUnit, float]]:
        """Get all units affected by an AOE attack."""
        targets = []

        # Primary target
        primary = self.get_unit_at_position(target_pos)
        if primary and primary.is_alive:
            targets.append((primary, 100.0))

        # AOE splash from damage_area
        for area in stats.damage_area:
            if area.pos.x == 0 and area.pos.y == 0:
                continue  # Skip primary target position

            splash_pos = Position(
                target_pos.x + area.pos.x,
                target_pos.y + area.pos.y
            )
            splash_unit = self.get_unit_at_position(splash_pos)
            if splash_unit and splash_unit.is_alive:
                targets.append((splash_unit, area.damage_percent))

        return targets

    def _calculate_damage(
        self,
        attacker: BattleUnit,
        defender: BattleUnit,
        weapon: Weapon,
        ability: Ability,
        damage_percent: float = 100.0
    ) -> int:
        """Calculate damage dealt by an attack."""
        stats = ability.stats
        weapon_stats = weapon.stats

        # Base damage from weapon
        base_damage = self.rng.randint(weapon_stats.base_damage_min, weapon_stats.base_damage_max)

        # Attack stat contribution
        attack = (
            stats.attack * stats.attack_from_weapon +
            weapon_stats.base_atk * stats.attack_from_unit +
            attacker.template.stats.power
        )

        # Defense reduction
        defense = defender.template.stats.defense

        # Class-based damage modifier
        class_mod = self.data_loader.get_class_damage_mod(
            attacker.template.class_type.value,
            defender.template.class_type.value
        )

        # Calculate final damage
        damage = base_damage + attack - defense
        damage = max(1, damage)  # Minimum 1 damage
        damage = int(damage * class_mod)
        damage = int(damage * damage_percent / 100)

        return max(1, damage)

    def _calculate_hit_chance(self, attacker: BattleUnit, defender: BattleUnit) -> float:
        """Calculate chance to hit."""
        accuracy = attacker.template.stats.accuracy
        dodge = defender.template.stats.dodge
        base_hit = 80.0  # Base hit chance

        hit_chance = base_hit + accuracy - dodge
        return max(5.0, min(95.0, hit_chance))  # Clamp to 5-95%

    def _calculate_crit_chance(
        self,
        attacker: BattleUnit,
        defender: BattleUnit,
        ability: Ability
    ) -> float:
        """Calculate critical hit chance."""
        base_crit = attacker.template.stats.critical
        ability_crit = ability.stats.critical_hit_percent

        # Check for tag-based crit bonuses
        bonus_crit = 0.0
        for tag, bonus in ability.stats.critical_bonuses.items():
            if tag in defender.template.tags:
                bonus_crit += bonus

        return base_crit + ability_crit + bonus_crit

    def _get_unit_index(self, unit: BattleUnit) -> int:
        """Get the index of a unit in its team list."""
        if unit.battle_side == BattleSide.PLAYER_TEAM:
            return self.player_units.index(unit) if self.player_is_attacker else self.enemy_units.index(unit)
        else:
            return self.enemy_units.index(unit) if self.player_is_attacker else self.player_units.index(unit)

    def end_turn(self) -> None:
        """End the current turn and switch sides."""
        # Tick cooldowns for current side
        for unit in self.current_side_units:
            unit.tick_cooldowns()
            unit.tick_status_effects()

        # Switch turns
        self.is_player_turn = not self.is_player_turn

        # If switching back to player, increment turn counter
        if self.is_player_turn:
            self.turn_number += 1

        # Check win/loss conditions
        self._check_battle_end()

    def _check_battle_end(self) -> None:
        """Check if battle has ended."""
        player_alive = any(u.is_alive and not u.template.unimportant for u in self.player_units)
        enemy_alive = any(u.is_alive and not u.template.unimportant for u in self.enemy_units)

        if not enemy_alive:
            self.result = BattleResult.PLAYER_WIN
        elif not player_alive:
            self.result = BattleResult.ENEMY_WIN

    def surrender(self) -> None:
        """Player surrenders the battle."""
        self.result = BattleResult.SURRENDER

    def get_state_vector(self) -> np.ndarray:
        """Get a numerical representation of the battle state for ML."""
        # This creates a fixed-size observation vector
        # Max units per side assumed to be 8
        MAX_UNITS = 8
        UNIT_FEATURES = 10  # hp%, armor%, position, class, etc.

        state = np.zeros(MAX_UNITS * UNIT_FEATURES * 2 + 10, dtype=np.float32)

        idx = 0

        # Player units
        for i, unit in enumerate(self.player_units[:MAX_UNITS]):
            state[idx] = unit.current_hp / max(1, unit.template.stats.hp)
            state[idx + 1] = unit.current_armor / max(1, unit.template.stats.armor_hp) if unit.template.stats.armor_hp > 0 else 0
            state[idx + 2] = unit.position.x / 5
            state[idx + 3] = unit.position.y / 3
            state[idx + 4] = unit.template.class_type.value / 15
            state[idx + 5] = 1.0 if unit.is_alive else 0.0
            state[idx + 6] = 1.0 if unit.can_act() else 0.0
            state[idx + 7] = len(unit.get_available_weapons()) / 2
            state[idx + 8] = unit.global_cooldown / 5
            state[idx + 9] = len(unit.status_effects) / 3
            idx += UNIT_FEATURES

        idx = MAX_UNITS * UNIT_FEATURES

        # Enemy units
        for i, unit in enumerate(self.enemy_units[:MAX_UNITS]):
            state[idx] = unit.current_hp / max(1, unit.template.stats.hp)
            state[idx + 1] = unit.current_armor / max(1, unit.template.stats.armor_hp) if unit.template.stats.armor_hp > 0 else 0
            state[idx + 2] = unit.position.x / 5
            state[idx + 3] = unit.position.y / 3
            state[idx + 4] = unit.template.class_type.value / 15
            state[idx + 5] = 1.0 if unit.is_alive else 0.0
            state[idx + 6] = 1.0 if unit.can_act() else 0.0
            state[idx + 7] = len(unit.get_available_weapons()) / 2
            state[idx + 8] = unit.global_cooldown / 5
            state[idx + 9] = len(unit.status_effects) / 3
            idx += UNIT_FEATURES

        # Global state
        idx = MAX_UNITS * UNIT_FEATURES * 2
        state[idx] = self.turn_number / 50
        state[idx + 1] = 1.0 if self.is_player_turn else 0.0
        state[idx + 2] = sum(1 for u in self.player_units if u.is_alive) / MAX_UNITS
        state[idx + 3] = sum(1 for u in self.enemy_units if u.is_alive) / MAX_UNITS
        state[idx + 4] = sum(u.current_hp for u in self.player_units) / max(1, sum(u.template.stats.hp for u in self.player_units))
        state[idx + 5] = sum(u.current_hp for u in self.enemy_units) / max(1, sum(u.template.stats.hp for u in self.enemy_units))

        return state


class BattleSimulator:
    """High-level battle simulator that manages game flow."""

    def __init__(self, data_dir: str):
        self.data_loader = GameDataLoader(data_dir)
        self.data_loader.load_all()

    def _apply_rank_to_template(self, template: UnitTemplate, rank: int) -> UnitTemplate:
        """Create a copy of the template with stats from the specified rank."""
        from copy import deepcopy
        template_copy = deepcopy(template)
        template_copy.stats = template.get_stats_at_rank(rank)
        return template_copy

    def create_battle_from_encounter(
        self,
        encounter_id: int,
        player_unit_ids: list[int],
        player_ranks: Optional[list[int]] = None
    ) -> Optional[BattleState]:
        """Create a battle state from an encounter definition."""
        encounter = self.data_loader.get_encounter(encounter_id)
        if not encounter:
            return None

        layout = self.data_loader.get_layout(encounter.layout_id)
        if not layout:
            return None

        # Default to rank 1 for all player units if not specified
        if player_ranks is None:
            player_ranks = [1] * len(player_unit_ids)

        # Create player units
        player_units = []
        for i, (unit_id, rank) in enumerate(zip(player_unit_ids, player_ranks)):
            template = self.data_loader.get_unit(unit_id)
            if template:
                # Apply rank to template stats
                template_with_rank = self._apply_rank_to_template(template, rank)
                # Place in grid (simple row-first placement)
                pos = Position.from_grid_id(i, layout.width)
                player_units.append(BattleUnit(
                    template=template_with_rank,
                    position=pos,
                    battle_side=BattleSide.PLAYER_TEAM
                ))

        # Create enemy units with their ranks from encounter
        enemy_units = []
        for enc_unit in encounter.enemy_units:
            template = self.data_loader.get_unit(enc_unit.unit_id)
            if template:
                # Log if unit has multiple ranks available
                num_ranks = len(template.all_rank_stats)
                if num_ranks > 1:
                    print(f"  ℹ Unit {enc_unit.unit_id} ({template.name}) has {num_ranks} ranks available")

                # Apply rank from encounter (defaults to 1 if not specified)
                template_with_rank = self._apply_rank_to_template(template, enc_unit.rank)
                pos = Position.from_grid_id(enc_unit.grid_id, layout.width)
                enemy_units.append(BattleUnit(
                    template=template_with_rank,
                    position=pos,
                    battle_side=BattleSide.ENEMY_TEAM
                ))

        return BattleState(
            data_loader=self.data_loader,
            layout=layout,
            player_units=player_units,
            enemy_units=enemy_units,
            player_is_attacker=encounter.is_player_attacker
        )

    def create_custom_battle(
        self,
        layout_id: int,
        player_unit_ids: list[int],
        player_positions: list[int],
        enemy_unit_ids: list[int],
        enemy_positions: list[int],
        player_ranks: Optional[list[int]] = None,
        enemy_ranks: Optional[list[int]] = None
    ) -> Optional[BattleState]:
        """Create a custom battle with specified units and positions."""
        layout = self.data_loader.get_layout(layout_id)
        if not layout:
            return None

        # Default to rank 1 if not specified
        if player_ranks is None:
            player_ranks = [1] * len(player_unit_ids)
        if enemy_ranks is None:
            enemy_ranks = [1] * len(enemy_unit_ids)

        # Create player units
        player_units = []
        for unit_id, grid_id, rank in zip(player_unit_ids, player_positions, player_ranks):
            template = self.data_loader.get_unit(unit_id)
            if template:
                template_with_rank = self._apply_rank_to_template(template, rank)
                pos = Position.from_grid_id(grid_id, layout.width)
                player_units.append(BattleUnit(
                    template=template_with_rank,
                    position=pos,
                    battle_side=BattleSide.PLAYER_TEAM
                ))

        # Create enemy units
        enemy_units = []
        for unit_id, grid_id, rank in zip(enemy_unit_ids, enemy_positions, enemy_ranks):
            template = self.data_loader.get_unit(unit_id)
            if template:
                template_with_rank = self._apply_rank_to_template(template, rank)
                pos = Position.from_grid_id(grid_id, layout.width)
                enemy_units.append(BattleUnit(
                    template=template_with_rank,
                    position=pos,
                    battle_side=BattleSide.ENEMY_TEAM
                ))

        return BattleState(
            data_loader=self.data_loader,
            layout=layout,
            player_units=player_units,
            enemy_units=enemy_units,
            player_is_attacker=True
        )

    def run_battle(
        self,
        battle: BattleState,
        player_policy,  # Callable[[BattleState], Action]
        enemy_policy,   # Callable[[BattleState], Action]
        max_turns: int = 100
    ) -> BattleResult:
        """Run a complete battle with given policies."""
        while battle.result == BattleResult.IN_PROGRESS and battle.turn_number < max_turns:
            # Get legal actions
            legal_actions = battle.get_legal_actions()

            if not legal_actions:
                # No actions possible, skip turn
                battle.end_turn()
                continue

            # Get action from appropriate policy
            if battle.is_player_turn:
                action = player_policy(battle)
            else:
                action = enemy_policy(battle)

            # Validate and execute
            if action in legal_actions or self._action_matches_legal(action, legal_actions):
                battle.execute_action(action)

            battle.end_turn()

        return battle.result

    def _action_matches_legal(self, action: Action, legal_actions: list[Action]) -> bool:
        """Check if action matches any legal action."""
        for legal in legal_actions:
            if (action.unit_index == legal.unit_index and
                action.weapon_id == legal.weapon_id and
                action.target_position == legal.target_position):
                return True
        return False
