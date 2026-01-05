"""Core battle simulator engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Iterator
from enum import Enum
import random
import numpy as np
from copy import deepcopy

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
    base_dot_damage: float = 0.0  # Pre-calculated base DOT damage (source_damage * mult + bonus)


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

    # Cooldowns: ability_id -> turns remaining (ability-specific)
    ability_cooldowns: dict[int, int] = field(default_factory=dict)
    # Global cooldowns: weapon_id -> turns remaining (weapon-specific, applies to all abilities on that weapon)
    global_cooldowns: dict[int, int] = field(default_factory=dict)

    # Ammo tracking: weapon_id -> current ammo
    ammo: dict[int, int] = field(default_factory=dict)

    # Status effects
    status_effects: list[ActiveStatusEffect] = field(default_factory=list)

    # Charging ability (if any)
    charging_weapon: Optional[int] = None
    charge_turns_remaining: int = 0

    # Track when unit entered the field (for charge_time/prep time)
    # This is the turn number when the unit entered the current wave/field
    turn_entered_field: int = 0
    
    # Track when each ability became available (for ability-specific charge_time)
    # Key: ability_id, Value: turn number when ability becomes available
    ability_available_turn: dict[int, int] = field(default_factory=dict)

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
        # Map all damage types to their string names used in damage_mods dict
        dtype_name = {
            DamageType.PIERCING: "piercing",
            DamageType.COLD: "cold",
            DamageType.CRUSHING: "crushing",
            DamageType.EXPLOSIVE: "explosive",
            DamageType.FIRE: "fire",
            DamageType.TORPEDO: "torpedo",
            DamageType.DEPTH_CHARGE: "depth_charge",
            DamageType.MELEE: "melee",
            DamageType.PROJECTILE: "projectile",
            DamageType.SHELL: "shell",
        }.get(damage_type)  # Default to piercing if unknown type

        # Apply damage modifiers
        damage_mod = self.template.stats.damage_mods.get(dtype_name, 1.0)
        modified_damage = int(damage * damage_mod)

        # Apply to armor first (if present)
        if self.current_armor > 0 and armor_piercing < 1.0:
            armor_damage = int(modified_damage * (1 - armor_piercing))
            armor_mod = self.template.stats.armor_damage_mods.get(dtype_name, 1.0)
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
        available = []
        for weapon_id, weapon in self.template.weapons.items():
            # Check weapon-specific global cooldown (blocks all abilities on this weapon)
            if self.global_cooldowns.get(weapon_id, 0) > 0:
                continue

            # Check if any ability on this weapon is available
            has_available_ability = False
            for ability_id in weapon.abilities:
                # Check ability-specific cooldown
                if self.ability_cooldowns.get(ability_id, 0) > 0:
                    continue
                # If we get here, at least one ability is available
                has_available_ability = True
                break

            if not has_available_ability:
                continue

            # Check ammo - need to check if any ability has sufficient ammo
            # For now, check if weapon has any ammo (detailed check happens in validator)
            if weapon.stats.ammo >= 0 and self.ammo.get(weapon_id, 0) <= 0:
                continue

            available.append(weapon_id)

        return available

    def tick_cooldowns(self) -> None:
        """Reduce all cooldowns by 1 at end of turn."""
        # Reduce weapon-specific global cooldowns
        for weapon_id in list(self.global_cooldowns.keys()):
            if self.global_cooldowns[weapon_id] > 0:
                self.global_cooldowns[weapon_id] -= 1
                # Remove cooldown if it reaches 0
                if self.global_cooldowns[weapon_id] == 0:
                    del self.global_cooldowns[weapon_id]

        # Reduce ability-specific cooldowns
        for ability_id in list(self.ability_cooldowns.keys()):
            if self.ability_cooldowns[ability_id] > 0:
                self.ability_cooldowns[ability_id] -= 1
                # Remove cooldown if it reaches 0
                if self.ability_cooldowns[ability_id] == 0:
                    del self.ability_cooldowns[ability_id]

    def tick_status_effects(self) -> int:
        """Process status effects. Returns DOT damage taken."""
        dot_damage = 0
        remaining_effects = []

        for status in self.status_effects:
            if status.effect.effect_type == StatusEffectType.DOT:
                # Use pre-calculated base DOT damage
                dot_damage += int(status.base_dot_damage)

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
    unit_position: Position  # Position of the unit performing the action
    ability_id: int
    target_position: Position


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    damage_dealt: dict[Position, int] = field(default_factory=dict)  # unit_position -> damage
    kills: list[Position] = field(default_factory=list)  # positions of killed units
    status_applied: list[tuple[Position, int]] = field(default_factory=list)  # (unit_position, effect_id)
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
        self.player_is_attacker = player_is_attacker

        # Store original copies as dictionaries (immutable reference from battle start)
        # Key: Position, Value: BattleUnit
        self._original_player_units: dict[Position, BattleUnit] = {
            unit.position: unit for unit in player_units
        }
        self._original_enemy_units: dict[Position, BattleUnit] = {
            unit.position: unit for unit in enemy_units
        }

        # Create deep copies for working copies (where changes are applied)
        # Use dictionaries keyed by position for efficient lookup and removal
        self.player_units: dict[Position, BattleUnit] = {
            unit.position: deepcopy(unit) for unit in player_units
        }
        self.enemy_units: dict[Position, BattleUnit] = {
            unit.position: deepcopy(unit) for unit in enemy_units
        }
        
        # Initialize ability availability for all units based on charge_time
        self._initialize_ability_availability()

        # Turn tracking
        self.turn_number = 0
        self.is_player_turn = True  # Player always goes first

        # Row collapse tracking (how many rows have been collapsed for each side)
        # Only collapses 1 row per turn, so this counts how many times collapse occurred
        self.player_rows_collapsed = 0
        self.enemy_rows_collapsed = 0

        # Battle result
        self.result = BattleResult.IN_PROGRESS

        # Action history for replay
        self.action_history: list[tuple[Action, ActionResult]] = []

        # RNG state (for reproducibility)
        self.rng = random.Random()

    def _initialize_ability_availability(self) -> None:
        """
        Initialize ability availability for all units based on charge_time.
        
        For each unit, for each weapon, for each ability:
        - Set ability_available_turn[ability_id] = turn_entered_field + ability.charge_time
        - If ability has no charge_time (0), it's available immediately (turn_entered_field)
        """
        for unit in list(self.player_units.values()) + list(self.enemy_units.values()):
            for weapon_id, weapon in unit.template.weapons.items():
                for ability_id in weapon.abilities:
                    ability = self.data_loader.get_ability(ability_id)
                    if ability:
                        charge_time = ability.stats.charge_time
                        # Ability becomes available at turn_entered_field + charge_time
                        # If charge_time is 0, available immediately (turn_entered_field)
                        unit.ability_available_turn[ability_id] = unit.turn_entered_field + charge_time

    def seed(self, seed: int) -> None:
        """Set RNG seed for reproducibility."""
        self.rng.seed(seed)

    @property
    def current_side_units(self) -> dict[Position, BattleUnit]:
        """Get units for the current turn's side."""
        return self.player_units if self.is_player_turn else self.enemy_units

    @property
    def opposing_side_units(self) -> dict[Position, BattleUnit]:
        """Get units for the opposing side."""
        return self.enemy_units if self.is_player_turn else self.player_units

    @property
    def original_player_units(self) -> dict[Position, BattleUnit]:
        """Get the original player units from battle start (immutable reference)."""
        return self._original_player_units

    @property
    def original_enemy_units(self) -> dict[Position, BattleUnit]:
        """Get the original enemy units from battle start (immutable reference)."""
        return self._original_enemy_units

    def get_unit_at_position(self, pos: Position, side: BattleSide) -> Optional[BattleUnit]:
        """Get unit at a specific position.
        
        Args:
            pos: The position to check
            side: The side to check (BattleSide.PLAYER_TEAM for player_units, BattleSide.ENEMY_TEAM for enemy_units)
        
        Returns:
            The unit at that position on the specified side, or None if not found
        """
        if side == Side.PLAYER_TEAM:
            return self.player_units.get(pos)
        else:
            return self.enemy_units.get(pos)
    
    def get_weapon_id_for_ability(self, unit: BattleUnit, ability_id: int) -> Optional[int]:
        """
        Find the weapon_id that contains the given ability_id.
        
        Args:
            unit: The unit to search
            ability_id: The ability ID to find
            
        Returns:
            The weapon_id that contains the ability, or None if not found
        """
        for weapon_id, weapon in unit.template.weapons.items():
            if ability_id in weapon.abilities:
                return weapon_id
        return None

    def get_legal_actions(self) -> list[Action]:
        """
        Get all legal actions for the current turn.
        
        Uses the new PlayerTargetValidator to check action validity.
        Only returns actions for player turns (enemy actions are selected internally).
        """
        from .battle_engine.player_target_validator import PlayerTargetValidator
        
        if not self.is_player_turn:
            return []  # Enemy turns don't use this method
        
        actions = []
        
        # Iterate through all player units
        for unit_position, unit in self.player_units.items():
            # Skip if unit is stunned
            from .battle_engine.status_effect_handler import StatusEffectHandler
            if StatusEffectHandler.is_unit_stunned(unit):
                continue
            
            # Iterate through all weapons
            for weapon_id, weapon in unit.template.weapons.items():
                # Check all possible target positions in the grid
                for x in range(self.layout.width):
                    for y in range(self.layout.height):
                        target_pos = Position(x, y)
                        
                        # Create action to check validity
                        temp_action = Action(
                            unit_position=unit_position,
                            weapon_id=weapon_id,
                            target_position=target_pos
                        )
                        
                        # Check if this action is valid
                        if PlayerTargetValidator.is_action_valid(temp_action, self):
                            actions.append(temp_action)
        
        return actions

    def execute_turn(self, action: Optional[Action] = None):
        """
        Execute a single turn using the new battle engine executors.
        
        This method delegates to PlayerTurnExecutor or EnemyTurnExecutor
        depending on whose turn it is.
        
        Args:
            action: The action to execute (required for player turns, ignored for enemy turns)
            
        Returns:
            TurnResult indicating the outcome of the turn
        """
        from .battle_engine.player_turn_executor import PlayerTurnExecutor
        from .battle_engine.enemy_turn_executor import EnemyTurnExecutor
        from .battle_engine.battle_types import TurnResult
        
        # Create executor based on current turn
        if self.is_player_turn:
            if action is None:
                return TurnResult.INVALID_ACTION
            executor = PlayerTurnExecutor(self)
            turn_result = executor.execute_player_turn(action)
        else:
            # Enemy turn - executor selects action internally
            executor = EnemyTurnExecutor(self)
            turn_result = executor.execute_enemy_turn()
        
        return turn_result

    def execute_action(self, action: Optional[Action] = None) -> ActionResult:
        """
        Execute a battle action (backward compatibility wrapper).
        
        This method wraps execute_turn() and converts TurnResult to ActionResult
        for backward compatibility with existing code.
        
        Args:
            action: The action to execute (required for player turns, ignored for enemy turns)
        """
        from .battle_engine.battle_types import TurnResult
        
        turn_result = self.execute_turn(action)
        
        # Convert TurnResult to ActionResult for backward compatibility
        success = turn_result in (TurnResult.SUCCESS, TurnResult.BATTLE_ENDED, TurnResult.PASSED)
        message = turn_result.value if not success else ""
        
        # Create ActionResult
        result = ActionResult(success=success, message=message)
        
        # Record action (only for player turns where we have the action)
        if action is not None:
            self.action_history.append((action, result))
        
        return result

    def run_battle_loop(self, player_action_selector=None) -> BattleResult:
        """
        Run the complete battle loop until one side wins.
        
        Structure:
        - Outer loop: Continue until battle ends
        - Player turn loop: Keep executing until SUCCESS, PASSED, or BATTLE_ENDED
        - Enemy turn loop: Keep executing until SUCCESS, PASSED, or BATTLE_ENDED
        - Increment turn counter after both sides complete
        
        Args:
            player_action_selector: Optional callable that takes BattleState and returns Action
                                   for player turns. If None, will use executor's action_selector.
        
        Returns:
            BattleResult indicating the final outcome
        """
        from .battle_engine.player_turn_executor import PlayerTurnExecutor
        from .battle_engine.enemy_turn_executor import EnemyTurnExecutor
        from .battle_engine.battle_types import TurnResult
        
        player_executor = PlayerTurnExecutor(self)
        enemy_executor = EnemyTurnExecutor(self)
        
        # Set action selector if provided
        if player_action_selector:
            player_executor.action_selector = player_action_selector
        
        # Outer loop: Continue until battle ends
        while self.result == BattleResult.IN_PROGRESS:
            # Player turn loop: Keep executing until SUCCESS, PASSED, or BATTLE_ENDED
            turn_result = TurnResult.INVALID_ACTION
            while turn_result not in (TurnResult.SUCCESS, TurnResult.PASSED, TurnResult.BATTLE_ENDED):
                turn_result = player_executor.execute_player_turn(None)
                
                if turn_result == TurnResult.BATTLE_ENDED:
                    break
            
            # Check if battle ended during player turn
            if self.result != BattleResult.IN_PROGRESS:
                break
            
            # Enemy turn loop: Keep executing until SUCCESS, PASSED, or BATTLE_ENDED
            turn_result = TurnResult.INVALID_ACTION
            while turn_result not in (TurnResult.SUCCESS, TurnResult.PASSED, TurnResult.BATTLE_ENDED):
                turn_result = enemy_executor.execute_enemy_turn()
                
                if turn_result == TurnResult.BATTLE_ENDED:
                    break
            
            # Check if battle ended during enemy turn
            if self.result != BattleResult.IN_PROGRESS:
                break
            
            # Increment turn counter after both sides complete
            self.turn_number += 1
        
        return self.result


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
        for i, unit in enumerate(list(self.player_units.values())[:MAX_UNITS]):
            state[idx] = unit.current_hp / max(1, unit.template.stats.hp)
            state[idx + 1] = unit.current_armor / max(1, unit.template.stats.armor_hp) if unit.template.stats.armor_hp > 0 else 0
            state[idx + 2] = unit.position.x / 5
            state[idx + 3] = unit.position.y / 3
            state[idx + 4] = unit.template.class_type.value / 15
            state[idx + 5] = 1.0  # Unit exists in dict, so it's alive
            state[idx + 6] = 1.0 if unit.can_act() else 0.0
            state[idx + 7] = len(unit.get_available_weapons()) / 2
            # Use max global cooldown across all weapons (for state representation)
            max_global_cooldown = max(unit.global_cooldowns.values()) if unit.global_cooldowns else 0
            state[idx + 8] = max_global_cooldown / 5
            state[idx + 9] = len(unit.status_effects) / 3
            idx += UNIT_FEATURES

        idx = MAX_UNITS * UNIT_FEATURES

        # Enemy units
        for i, unit in enumerate(list(self.enemy_units.values())[:MAX_UNITS]):
            state[idx] = unit.current_hp / max(1, unit.template.stats.hp)
            state[idx + 1] = unit.current_armor / max(1, unit.template.stats.armor_hp) if unit.template.stats.armor_hp > 0 else 0
            state[idx + 2] = unit.position.x / 5
            state[idx + 3] = unit.position.y / 3
            state[idx + 4] = unit.template.class_type.value / 15
            state[idx + 5] = 1.0  # Unit exists in dict, so it's alive
            state[idx + 6] = 1.0 if unit.can_act() else 0.0
            state[idx + 7] = len(unit.get_available_weapons()) / 2
            # Use max global cooldown across all weapons (for state representation)
            max_global_cooldown = max(unit.global_cooldowns.values()) if unit.global_cooldowns else 0
            state[idx + 8] = max_global_cooldown / 5
            state[idx + 9] = len(unit.status_effects) / 3
            idx += UNIT_FEATURES

        # Global state
        idx = MAX_UNITS * UNIT_FEATURES * 2
        state[idx] = self.turn_number / 50
        state[idx + 1] = 1.0 if self.is_player_turn else 0.0
        state[idx + 2] = len(self.player_units) / MAX_UNITS
        state[idx + 3] = len(self.enemy_units) / MAX_UNITS
        state[idx + 4] = sum(u.current_hp for u in self.player_units.values()) / max(1, sum(u.template.stats.hp for u in self.player_units.values()))
        state[idx + 5] = sum(u.current_hp for u in self.enemy_units.values()) / max(1, sum(u.template.stats.hp for u in self.enemy_units.values()))

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
                    battle_side=BattleSide.PLAYER_TEAM,
                    turn_entered_field=0  # Units start at turn 0
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
                    battle_side=BattleSide.ENEMY_TEAM,
                    turn_entered_field=0  # Units start at turn 0
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
                    battle_side=BattleSide.PLAYER_TEAM,
                    turn_entered_field=0  # Units start at turn 0
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
                    battle_side=BattleSide.ENEMY_TEAM,
                    turn_entered_field=0  # Units start at turn 0
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
        """
        Run a complete battle with given policies.
        
        This method now uses the new battle engine's run_battle_loop() method.
        """
        # Create action selector wrapper for player policy
        def player_action_selector(battle_state: BattleState):
            """Select action using player policy."""
            return player_policy(battle_state)
        
        # Run the battle loop with both policies
        return battle.run_battle_loop(
            player_action_selector=player_action_selector,
            enemy_policy=enemy_policy,
            max_turns=max_turns
        )

    def _action_matches_legal(self, action: Action, legal_actions: list[Action]) -> bool:
        """Check if action matches any legal action."""
        for legal in legal_actions:
            if (action.unit_position == legal.unit_position and
                action.ability_id == legal.ability_id and
                action.target_position == legal.target_position):
                return True
        return False
