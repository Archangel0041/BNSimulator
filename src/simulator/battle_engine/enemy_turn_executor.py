"""
Enemy Turn Executor.

Handles all enemy turn step execution with explicit, ordered steps.
"""

from typing import TYPE_CHECKING, Optional, List, Callable
import random
import math

from .battle_types import (
    TurnResult, BattleResult, HitResult, DamageResult,
    Position, ActionCandidate
)
from ..enums import TargetType, BattleSide
from .status_effect_handler import StatusEffectHandler
from .death_handler import DeathHandler
from .damage_handler import DamageHandler
from .armor_handler import ArmorHandler
from ..enums import DamageType
from .cooldown_handler import CooldownHandler
from .row_collapse_handler import RowCollapseHandler

if TYPE_CHECKING:
    from ..battle import BattleState, BattleUnit, Action


class EnemyTurnExecutor:
    """Executes all steps of an enemy turn."""

    def __init__(self, battle_state: 'BattleState'):
        """
        Initialize enemy turn executor.

        Args:
            battle_state: The battle state to operate on
        """
        self.battle = battle_state
        self.rng = battle_state.rng
        self.ai_policy: Optional[Callable] = None  # Set externally

    def execute_enemy_turn(self) -> TurnResult:
        """
        Execute complete enemy turn.

        This is the master function that orchestrates all enemy turn steps
        in the exact order they should occur.

        Returns:
            TurnResult indicating the outcome of the turn
        """
        # Step 1: Make list of all alive units and abilities
        all_possible_actions = self._step_list_all_alive_units_and_abilities()

        # Step 2: Filter all units which are stunned/frozen
        filtered_actions = self._step_filter_stunned_units(all_possible_actions)

        # Step 3: Filter abilities on cooldown
        filtered_actions = self._step_filter_cooldown_abilities(filtered_actions)

        # Step 4: Calculate valid targets for each ability
        # (empty locations & targets that will not take damage are not valid)
        actions_with_targets = self._step_calculate_valid_targets(filtered_actions)

        # Step 5: Filter abilities with no valid target
        valid_actions = self._step_filter_no_valid_targets(actions_with_targets)

        # No valid actions - skip turn
        if not valid_actions:
            return TurnResult.NO_VALID_ACTIONS

        # Step 6: Select action using AI policy
        action = self._step_select_action(valid_actions)

        # Step 7: Calculate base damage range
        damage_min, damage_max = self._step_calculate_base_damage(action)

        # Step 8: Calculate all hits using TargetingHandler
        # This handles targeting patterns, damage rolls, hit/crit checks, and groups base+splash
        from ..enums import BattleSide
        from .targeting_handler import TargetingHandler
        hits_by_position = TargetingHandler.calculate_hits_by_position(
            self.battle, action, damage_min, damage_max, BattleSide.ENEMY_TEAM
        )
        
        # Step 9: Process all collected hits (apply damage, status effects, etc.)
        DamageHandler.process_all_hits(self.battle, action, hits_by_position, BattleSide.ENEMY_TEAM) 

        # Step 11: Check for dead player units (from damage)
        DeathHandler.check_for_dead_units(self.battle, BattleSide.PLAYER_TEAM)
        
        # Step 13: Update cooldown and ammo
        CooldownHandler.update_cooldowns_for_unit(self.battle, self.battle.enemy_units.get(action.unit_position), action)
 
        # Step 14: Apply DOT to player units (opposing side that was attacked)
        StatusEffectHandler.apply_dot_to_all_units_for_side(self.battle, BattleSide.PLAYER_TEAM)

        # Step 15: Check for dead player units (from DOT)
        DeathHandler.check_for_dead_units(self.battle, BattleSide.PLAYER_TEAM)

        # Step 16: Check if all player units dead -> end battle with loss
        if DeathHandler.check_all_units_dead(self.battle, BattleSide.PLAYER_TEAM):
            self.battle.result = BattleResult.ENEMY_WIN
            return TurnResult.BATTLE_ENDED

        # Step 17: Collapse 1 row if no units on front row (player side)
        RowCollapseHandler.collapse_front_row(self.battle, BattleSide.PLAYER_TEAM)

        # Step 18: Reduce cooldowns (unit must not be stunned) (player side)
        CooldownHandler.reduce_cooldowns_for_side(self.battle, BattleSide.PLAYER_TEAM)

        # Step 19: Decay stun/freeze effects (enemy side) - after turn completes
        StatusEffectHandler.decay_stun_effects_for_side(self.battle, BattleSide.ENEMY_TEAM)

        return TurnResult.SUCCESS

    # =========================================================================
    # Step 1: Apply DOT to enemy units
    # =========================================================================

    def _step_apply_dot_to_enemy(self) -> None:
        """
        Step 1: Apply DOT to all enemy units.

        Iterates through all enemy units and applies DOT damage from
        active status effects.

        Sub-steps for each unit:
        1. Calculate base DOT damage for each valid DOT effect
        2. Decay the status effect duration
        3. Apply armor/modifiers to damage
        4. Apply the final damage to the unit
        """
        for unit in self.battle.enemy_units.values():
            # Sub-step 1 & 3 & 4: Calculate and apply DOT damage for each effect
            # (Must be done per-effect since each can have different damage type)
            StatusEffectHandler.apply_dot_to_unit(unit)

            # Sub-step 2: Decay DOT status effect durations and remove expired effects
            # (Only DOT effects decay here; stun/freeze decay at end of turn)
            StatusEffectHandler.decay_dot_effects(unit)

    # =========================================================================
    # Apply DOT to player units (opposing side)
    # =========================================================================

    def _step_apply_dot_to_player_units(self) -> None:
        """
        Apply DOT to all player units (opposing side that was attacked).

        Iterates through all player units and applies DOT damage from
        active status effects.

        Sub-steps for each unit:
        1. Calculate base DOT damage for each valid DOT effect
        2. Decay the status effect duration
        3. Apply armor/modifiers to damage
        4. Apply the final damage to the unit
        """
        for unit in self.battle.player_units.values():
            # Sub-step 1 & 3 & 4: Calculate and apply DOT damage for each effect
            # (Must be done per-effect since each can have different damage type)
            StatusEffectHandler.apply_dot_to_unit(unit)

            # Sub-step 2: Decay DOT status effect durations and remove expired effects
            # (Only DOT effects decay here; stun/freeze decay at end of turn)
            StatusEffectHandler.decay_dot_effects(unit)

    # =========================================================================
    # Step 2: Check for dead enemy units (from DOT)
    # =========================================================================

    def _step_check_for_dead_enemy_units(self) -> None:
        """
        Step 2: Check for dead enemy units after DOT application.

        Removes enemy units with HP <= 0 from the working copy.
        """
        from ..enums import BattleSide
        DeathHandler.check_for_dead_units(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Step 3: Check if all enemy units dead
    # =========================================================================

    def _step_check_all_enemy_units_dead(self) -> bool:
        """
        Step 2: Check if all enemy units are dead.

        Returns:
            True if all enemy units are dead (ignoring unimportant units)
        """
        from ..enums import BattleSide
        return DeathHandler.check_all_units_dead(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Collapse player front row (opposing side)
    # =========================================================================

    def _step_collapse_player_front_row(self) -> None:
        """
        Collapse 1 row if front row is empty (player side).

        If row 0 (front row, y=0) has no alive units, move all units forward
        by one row (decrease y by 1). Only collapses ONE row per turn.
        Increments the player_rows_collapsed counter.
        """
        from ..enums import BattleSide
        from .row_collapse_handler import RowCollapseHandler
        RowCollapseHandler.collapse_front_row(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Step 4: Collapse enemy front row
    # =========================================================================

    def _step_collapse_enemy_front_row(self) -> None:
        """
        Step 4: Collapse 1 row if front row is empty.

        If row 0 (front row, y=0) has no alive units, move all units forward
        by one row (decrease y by 1). Only collapses ONE row per turn.
        Increments the enemy_rows_collapsed counter.
        """
        from ..enums import BattleSide
        from .row_collapse_handler import RowCollapseHandler
        RowCollapseHandler.collapse_front_row(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Reduce player cooldowns (opposing side)
    # =========================================================================

    def _step_reduce_player_cooldowns(self) -> None:
        """
        Reduce cooldowns for non-stunned units (player side).

        For each alive player unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement global cooldown
        """
        from ..enums import BattleSide
        from .cooldown_handler import CooldownHandler
        CooldownHandler.reduce_cooldowns_for_side(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Step 5: Reduce enemy cooldowns
    # =========================================================================

    def _step_reduce_enemy_cooldowns(self) -> None:
        """
        Step 4: Reduce cooldowns for non-stunned units.

        For each alive enemy unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement global cooldown
        """
        from ..enums import BattleSide
        from .cooldown_handler import CooldownHandler
        CooldownHandler.reduce_cooldowns_for_side(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Step 19: Decay stun/freeze effects (enemy side)
    # =========================================================================

    def _step_decay_stun_effects_enemy(self) -> None:
        """
        Decay stun/freeze status effects for enemy units (after turn completes).

        Stun/freeze effects should only decay at the end of the turn, not when
        DOT ticks. This ensures that if a unit is stunned, it remains stunned
        for the full turn and can't act that turn.
        """
        for unit in self.battle.enemy_units.values():
            StatusEffectHandler.decay_stun_effects(unit)

    # =========================================================================
    # Step 5: List all alive units and abilities
    # =========================================================================

    def _step_list_all_alive_units_and_abilities(self) -> List[ActionCandidate]:
        """
        Step 5: Make list of all alive units and abilities.

        Creates a list of all possible actions from alive enemy units.

        Returns:
            List of ActionCandidate objects
        """
        # TODO: Implement action listing
        return []

    # =========================================================================
    # Step 6: Filter stunned units
    # =========================================================================

    def _step_filter_stunned_units(
        self, actions: List[ActionCandidate]
    ) -> List[ActionCandidate]:
        """
        Step 6: Filter all units which are stunned/frozen.

        Removes actions from units that cannot act due to status effects.

        Args:
            actions: List of action candidates

        Returns:
            Filtered list of action candidates
        """
        from .cooldown_handler import CooldownHandler
        filtered = []
        for action_candidate in actions:
            unit = self.battle.enemy_units.get(action_candidate.unit_position)
            if unit is not None and not CooldownHandler.is_unit_stunned(unit):
                filtered.append(action_candidate)
        return filtered

    # =========================================================================
    # Step 7: Filter abilities on cooldown
    # =========================================================================

    def _step_filter_cooldown_abilities(
        self, actions: List[ActionCandidate]
    ) -> List[ActionCandidate]:
        """
        Step 7: Filter abilities on cooldown.

        Removes actions for abilities that are still on cooldown or
        have no ammo remaining.

        Args:
            actions: List of action candidates

        Returns:
            Filtered list of action candidates
        """
        # TODO: Implement cooldown filtering
        return actions

    # =========================================================================
    # Step 8: Calculate valid targets
    # =========================================================================

    def _step_calculate_valid_targets(
        self, actions: List[ActionCandidate]
    ) -> List[ActionCandidate]:
        """
        Step 8: Calculate valid targets for each ability.

        For each action, calculates which positions are valid targets.
        Empty locations & targets that will not take damage are excluded.

        Args:
            actions: List of action candidates

        Returns:
            Action candidates with valid_targets populated
        """
        # TODO: Implement target calculation
        return actions

    # =========================================================================
    # Step 9: Filter actions with no valid targets
    # =========================================================================

    def _step_filter_no_valid_targets(
        self, actions: List[ActionCandidate]
    ) -> List['Action']:
        """
        Step 9: Filter abilities with no valid target.

        Converts ActionCandidates with valid targets into full Action objects.

        Args:
            actions: List of action candidates with targets

        Returns:
            List of full Action objects ready for execution
        """
        # TODO: Implement filtering and conversion to Action
        return []

    # =========================================================================
    # Step 10: Select action
    # =========================================================================

    def _step_select_action(self, valid_actions: List['Action']) -> 'Action':
        """
        Select action using AI policy.

        Uses the configured AI policy to select which action to execute.

        Args:
            valid_actions: List of valid actions to choose from

        Returns:
            Selected action
        """
        # TODO: Implement action selection
        # For now, just return random action
        return self.rng.choice(valid_actions) if valid_actions else None

    # =========================================================================
    # Step 11: Calculate base damage
    # =========================================================================

    def _step_calculate_base_damage(self, action: 'Action') -> tuple[int, int]:
        """
        Step 7: Calculate base damage range.

        Calculates base damage range from weapon stats and unit power:
        - damage_min = floor(base_damage_min * (1 + (2 * power / 100)))
        - damage_max = floor(base_damage_max * (1 + (2 * power / 100)))

        Args:
            action: The action being executed

        Returns:
            Tuple of (damage_min, damage_max) - both integers
        """
        # Get the attacking unit
        attacker = self.battle.enemy_units.get(action.unit_position)
        if attacker is None:
            return (0, 0)
        
        # Get the weapon
        weapon = attacker.template.weapons.get(action.weapon_id)
        if weapon is None:
            return (0, 0)
        
        # Get unit power
        power = attacker.template.stats.power
        
        # Calculate power multiplier: (1 + (2 * power / 100))
        power_multiplier = 1.0 + (2.0 * power / 100.0)
        
        # Calculate damage range (both floored to integers)
        damage_min = math.floor(weapon.stats.base_damage_min * power_multiplier)
        damage_max = math.floor(weapon.stats.base_damage_max * power_multiplier)
        
        # Return min and max (damage roll will be calculated per target)
        return (damage_min, damage_max)


    # =========================================================================
    # Step 14: Check for dead player units (from damage)
    # =========================================================================

    def _step_check_for_dead_player_units(self) -> None:
        """
        Step 14: Check for dead player units after damage application.

        Removes player units with HP <= 0 from the working copy.
        """
        from ..enums import BattleSide
        DeathHandler.check_for_dead_units(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Step 16: Apply status effects
    # =========================================================================

    def _step_apply_status_effects(self, action: 'Action', final_damage: float) -> None:
        """
        Step 15: Apply DOT status effects.

        For each status effect in the ability:
        - Check immunity
        - Roll for application chance
        - Add to target's status effects list
        - Store source_damage for DOT calculation

        Args:
            action: The action being executed
            final_damage: Final damage dealt (used for DOT calculation)
        """
        # TODO: Implement status effect application
        pass


    # =========================================================================
    # Helper: Check if all player units dead
    # =========================================================================

    def _step_check_all_player_units_dead(self) -> bool:
        """
        Check if all player units are dead.

        Returns:
            True if all player units are dead (ignoring unimportant units)
        """
        from ..enums import BattleSide
        return DeathHandler.check_all_units_dead(self.battle, BattleSide.PLAYER_TEAM)
    
    # =========================================================================
    # Resistance calculation - MOVED TO ArmorHandler
    # =========================================================================
    # This functionality has been moved to ArmorHandler.get_armor_resistance and
    # ArmorHandler.get_hp_resistance
