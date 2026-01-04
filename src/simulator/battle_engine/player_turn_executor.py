"""
Player Turn Executor.

Handles all player turn step execution with explicit, ordered steps.
"""

from typing import TYPE_CHECKING, Optional, Callable
import random

from .battle_types import TurnResult, BattleResult, HitResult, DamageResult, Position
from .status_effect_handler import StatusEffectHandler
from .death_handler import DeathHandler
from ..enums import DamageType

if TYPE_CHECKING:
    from ..battle import BattleState, BattleUnit, Action


class PlayerTurnExecutor:
    """Executes all steps of a player turn."""

    def __init__(self, battle_state: 'BattleState'):
        """
        Initialize player turn executor.

        Args:
            battle_state: The battle state to operate on
        """
        self.battle = battle_state
        self.rng = battle_state.rng
        self.action_selector: Optional[Callable] = None  # Hook for getting player input

    def execute_player_turn(self, action: Optional['Action'] = None) -> TurnResult:
        """
        Execute complete player turn.

        This is the master function that orchestrates all player turn steps
        in the exact order they should occur.

        Args:
            action: The action selected by the player (optional if action_selector is set)

        Returns:
            TurnResult indicating the outcome of the turn
        """
        # Step 1: Player selects action
        # This is where we wait for/get player input
        action = self._step_get_player_action(action)
        if action is None:
            # No valid action available or player passed
            return TurnResult.NO_VALID_ACTIONS

        # Step 2: Check if unit is stunned/frozen/disabled
        if self._step_is_unit_disabled(action):
            return TurnResult.UNIT_CANNOT_ACT

        # Step 3: Check if targeting location is valid
        if not self._step_is_target_valid(action):
            return TurnResult.INVALID_TARGET

        # Step 4: Calculate base damage
        base_damage = self._step_calculate_base_damage(action)

        # Step 5: Check for dodges/misses/etc
        hit_result = self._step_check_hit(action)
        if not hit_result.hit:
            self._step_update_cooldown_and_ammo(action)
            return TurnResult.ATTACK_MISSED

        # Apply critical hit if rolled
        if hit_result.is_critical:
            base_damage *= 1.5

        # Step 6: Apply multipliers and armor
        final_damage = self._step_apply_multipliers_and_armor(action, base_damage)

        # Step 7: Apply damage
        self._step_apply_damage(action, final_damage)

        # Step 8: Check for dead enemy units (from damage)
        self._step_check_for_dead_enemy_units()

        # Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED

        # Step 9: Apply DOT status effects based on final damage
        self._step_apply_status_effects(action, final_damage)

        # Step 10: Update cooldown and ammo
        self._step_update_cooldown_and_ammo(action)

        # Step 11: Apply DOT to enemy units (opposing side that was attacked)
        self._step_apply_dot_to_enemy_units()

        # Step 12: Check for dead enemy units (from DOT)
        self._step_check_for_dead_enemy_units()

        # Step 13: Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED

        # Step 14: Collapse 1 row if no units on front row (enemy side)
        self._step_collapse_enemy_front_row()

        # Step 15: Reduce cooldowns (unit must not be stunned) (enemy side)
        self._step_reduce_enemy_cooldowns()

        # Step 16: Decay stun/freeze effects (player side) - after turn completes
        self._step_decay_stun_effects_player()

        return TurnResult.SUCCESS

    # =========================================================================
    # Step 1: Apply DOT to player units
    # =========================================================================

    def _step_apply_dot_to_player(self) -> None:
        """
        Step 1: Deal DOT damage to all player units.

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
    # Apply DOT to enemy units (opposing side)
    # =========================================================================

    def _step_apply_dot_to_enemy_units(self) -> None:
        """
        Apply DOT to all enemy units (opposing side that was attacked).

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
    # Step 2: Check for dead player units (from DOT)
    # =========================================================================

    def _step_check_for_dead_player_units(self) -> None:
        """
        Step 2: Check for dead player units after DOT application.

        Removes player units with HP <= 0 from the working copy.
        """
        from ..enums import BattleSide
        DeathHandler.check_for_dead_units(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Step 3: Check if all player units dead
    # =========================================================================

    def _step_check_all_player_units_dead(self) -> bool:
        """
        Step 2: Check if all player units are dead.

        Returns:
            True if all player units are dead (ignoring unimportant units)
        """
        from ..enums import BattleSide
        return DeathHandler.check_all_units_dead(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Collapse enemy front row (opposing side)
    # =========================================================================

    def _step_collapse_enemy_front_row(self) -> None:
        """
        Collapse 1 row if front row is empty (enemy side).

        If row 0 (front row, y=0) has no alive units, move all units forward
        by one row (decrease y by 1). Only collapses ONE row per turn.
        Increments the enemy_rows_collapsed counter.
        """
        from ..enums import BattleSide
        from .row_collapse_handler import RowCollapseHandler
        RowCollapseHandler.collapse_front_row(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Step 4: Collapse player front row
    # =========================================================================

    def _step_collapse_player_front_row(self) -> None:
        """
        Step 4: Collapse 1 row if front row is empty.

        If row 0 (front row, y=0) has no alive units, move all units forward
        by one row (decrease y by 1). Only collapses ONE row per turn.
        Increments the player_rows_collapsed counter.
        """
        from ..enums import BattleSide
        from .row_collapse_handler import RowCollapseHandler
        RowCollapseHandler.collapse_front_row(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Reduce enemy cooldowns (opposing side)
    # =========================================================================

    def _step_reduce_enemy_cooldowns(self) -> None:
        """
        Reduce cooldowns for non-stunned units (enemy side).

        For each alive enemy unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement global cooldown
        """
        from ..enums import BattleSide
        from .cooldown_handler import CooldownHandler
        CooldownHandler.reduce_cooldowns_for_side(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Step 5: Reduce player cooldowns
    # =========================================================================

    def _step_reduce_player_cooldowns(self) -> None:
        """
        Step 4: Reduce cooldowns for non-stunned units.

        For each alive player unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement global cooldown
        """
        from ..enums import BattleSide
        from .cooldown_handler import CooldownHandler
        CooldownHandler.reduce_cooldowns_for_side(self.battle, BattleSide.PLAYER_TEAM)

    # =========================================================================
    # Step 16: Decay stun/freeze effects (player side)
    # =========================================================================

    def _step_decay_stun_effects_player(self) -> None:
        """
        Decay stun/freeze status effects for player units (after turn completes).

        Stun/freeze effects should only decay at the end of the turn, not when
        DOT ticks. This ensures that if a unit is stunned, it remains stunned
        for the full turn and can't act that turn.
        """
        for unit in self.battle.player_units.values():
            StatusEffectHandler.decay_stun_effects(unit)

    # =========================================================================
    # Step 6: Get player action
    # =========================================================================

    def _step_get_player_action(self, action: Optional['Action']) -> Optional['Action']:
        """
        Step 5: Player selects action or Pass/Surrender.

        This is the waiting point for player input. The action can be:
        1. Passed directly as a parameter (for immediate/scripted actions)
        2. Retrieved via action_selector callback (for GUI/CLI waiting)
        3. None if player passes/surrenders

        This method provides a clear hook point for different input methods:
        - CLI: Set action_selector to prompt user and wait for input
        - GUI: Set action_selector to wait for button click
        - AI/Testing: Pass action directly as parameter

        Args:
            action: Pre-selected action (if any)

        Returns:
            The selected action, or None if player passes
        """
        # If action was provided directly, use it
        if action is not None:
            return action

        # Otherwise, use the action selector callback if available
        if self.action_selector is not None:
            return self.action_selector(self.battle)

        # No action provided and no selector - player passes
        return None

    # =========================================================================
    # Step 7: Check if unit is disabled
    # =========================================================================

    def _step_is_unit_disabled(self, action: 'Action') -> bool:
        """
        Step 6: Check if unit is stunned/frozen/disabled.

        Args:
            action: The action to check

        Returns:
            True if the unit cannot act
        """
        # Get the unit performing the action
        unit = self.battle.player_units.get(action.unit_position)
        if unit is None:
            return True  # Unit not found, consider it disabled
        
        # Check if unit is stunned (has status effect that blocks actions)
        from .cooldown_handler import CooldownHandler
        return CooldownHandler.is_unit_stunned(unit)

    # =========================================================================
    # Step 8: Check if target is valid
    # =========================================================================

    def _step_is_target_valid(self, action: 'Action') -> bool:
        """
        Step 7: Check if action is valid.

        Validates:
        - Weapon and global cooldowns
        - Ammo availability
        - Charge time (prep time)
        - Target is in range
        - Target location has a unit (if required)
        - Target unit is alive (if required)
        - Line of fire and blocking are clear
        - Target type requirements are met
        - Tag hierarchy matching

        Args:
            action: The action to validate

        Returns:
            True if action is valid
        """
        from .player_target_validator import PlayerTargetValidator
        return PlayerTargetValidator.is_action_valid(action, self.battle)

    # =========================================================================
    # Step 9: Calculate base damage
    # =========================================================================

    def _step_calculate_base_damage(self, action: 'Action') -> float:
        """
        Step 8: Calculate base damage.

        Calculates damage including:
        1. Base weapon damage roll
        2. Attack vs Defense
        3. Class modifiers
        4. (Critical hit applied later in main function)

        Args:
            action: The action being executed

        Returns:
            Base damage value
        """
        # TODO: Implement damage calculation
        return 0.0

    # =========================================================================
    # Step 10: Check for hit/miss
    # =========================================================================

    def _step_check_hit(self, action: 'Action') -> HitResult:
        """
        Step 9: Check for dodges/misses/etc.

        Calculates hit chance based on:
        - Base hit chance (80%)
        - Attacker accuracy
        - Defender dodge
        - Clamped to 5-95% range

        Also rolls for critical hit.

        Args:
            action: The action being executed

        Returns:
            HitResult with hit/miss and critical hit status
        """
        # TODO: Implement hit check
        return HitResult(hit=True, is_critical=False, hit_chance=80.0)

    # =========================================================================
    # Step 11: Apply multipliers and armor
    # =========================================================================

    def _step_apply_multipliers_and_armor(
        self, action: 'Action', base_damage: float
    ) -> float:
        """
        Step 10: Apply multipliers and armor to damage.

        Applies:
        - Type effectiveness modifiers
        - AOE falloff
        - Armor reduction
        - Minimum damage (1)

        Args:
            action: The action being executed
            base_damage: Base damage before modifiers

        Returns:
            Final damage after all modifiers
        """
        # TODO: Implement multipliers and armor
        return base_damage

    # =========================================================================
    # Step 12: Apply damage
    # =========================================================================

    def _step_apply_damage(self, action: 'Action', damage: float) -> None:
        """
        Step 11: Apply damage to target(s).

        Applies damage to:
        - Primary target
        - AOE targets (if applicable)

        Args:
            action: The action being executed
            damage: Final damage to apply
        """
        # TODO: Implement damage application
        pass

    # =========================================================================
    # Step 13: Check for dead enemy units (from damage)
    # =========================================================================

    def _step_check_for_dead_enemy_units(self) -> None:
        """
        Step 13: Check for dead enemy units after damage application.

        Removes enemy units with HP <= 0 from the working copy.
        """
        from ..enums import BattleSide
        DeathHandler.check_for_dead_units(self.battle, BattleSide.ENEMY_TEAM)

    # =========================================================================
    # Step 14: Apply status effects
    # =========================================================================

    def _step_apply_status_effects(self, action: 'Action', final_damage: float) -> None:
        """
        Step 13: Apply DOT status effects based on final damage.

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
    # Step 15: Update cooldown and ammo
    # =========================================================================

    def _step_update_cooldown_and_ammo(self, action: 'Action') -> None:
        """
        Step 14: Update cooldown and ammo for used ability.

        Sets weapon on cooldown and consumes ammo if applicable.

        Args:
            action: The action that was executed
        """
        # TODO: Implement cooldown and ammo update
        pass

    # =========================================================================
    # Helper: Check if all enemy units dead
    # =========================================================================

    def _step_check_all_enemy_units_dead(self) -> bool:
        """
        Check if all enemy units are dead.

        Returns:
            True if all enemy units are dead (ignoring unimportant units)
        """
        from ..enums import BattleSide
        return DeathHandler.check_all_units_dead(self.battle, BattleSide.ENEMY_TEAM)
