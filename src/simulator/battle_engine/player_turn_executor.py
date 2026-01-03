"""
Player Turn Executor.

Handles all player turn step execution with explicit, ordered steps.
"""

from typing import TYPE_CHECKING, Optional, Callable
import random

from .battle_types import TurnResult, BattleResult, HitResult, DamageResult, Position
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
        # Step 1: Apply DOT to player units
        self._step_apply_dot_to_player()

        # Step 2: Check if all player units dead -> end battle with loss
        if self._step_check_all_player_units_dead():
            self.battle.result = BattleResult.ENEMY_WIN
            return TurnResult.BATTLE_ENDED

        # Step 3: Collapse 1 row if no units on front row
        self._step_collapse_player_front_row()

        # Step 4: Reduce cooldowns (unit must not be stunned)
        self._step_reduce_player_cooldowns()

        # Step 5: Player selects action
        # This is where we wait for/get player input
        action = self._step_get_player_action(action)
        if action is None:
            # No valid action available or player passed
            return TurnResult.NO_VALID_ACTIONS

        # Step 6: Check if unit is stunned/frozen/disabled
        if self._step_is_unit_disabled(action):
            return TurnResult.UNIT_CANNOT_ACT

        # Step 7: Check if targeting location is valid
        if not self._step_is_target_valid(action):
            return TurnResult.INVALID_TARGET

        # Step 8: Calculate base damage
        base_damage = self._step_calculate_base_damage(action)

        # Step 9: Check for dodges/misses/etc
        hit_result = self._step_check_hit(action)
        if not hit_result.hit:
            self._step_update_cooldown_and_ammo(action)
            return TurnResult.ATTACK_MISSED

        # Apply critical hit if rolled
        if hit_result.is_critical:
            base_damage *= 1.5

        # Step 10: Apply multipliers and armor
        final_damage = self._step_apply_multipliers_and_armor(action, base_damage)

        # Step 11: Apply damage
        self._step_apply_damage(action, final_damage)

        # Step 12: Check for dead units
        self._step_check_for_dead_units()

        # Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED

        # Step 13: Apply DOT status effects based on final damage
        self._step_apply_status_effects(action, final_damage)

        # Step 14: Update cooldown and ammo
        self._step_update_cooldown_and_ammo(action)

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
        from ..enums import StatusEffectType

        for unit in self.battle.player_units:
            if not unit.is_alive:
                continue

            # Sub-step 1 & 3 & 4: Calculate and apply DOT damage for each effect
            # (Must be done per-effect since each can have different damage type)
            self._apply_dot_damage_to_unit(unit)

            # Sub-step 2: Decay status effect durations and remove expired effects
            self._decay_status_effects(unit)

    def _calculate_dot_damage_for_effect(self, status: 'ActiveStatusEffect') -> float:
        """
        Calculate DOT damage for a single status effect.

        Formula: base_damage = source_damage * dot_ability_damage_mult + dot_bonus_damage

        Args:
            status: The active status effect

        Returns:
            Base DOT damage (before armor/modifiers)
        """
        base_damage = status.source_damage * status.effect.dot_ability_damage_mult
        base_damage += status.effect.dot_bonus_damage
        return base_damage

    def _decay_status_effects(self, unit: 'BattleUnit') -> None:
        """
        Decrement duration of all status effects and remove expired ones.

        Args:
            unit: The unit whose status effects to decay
        """
        remaining_effects = []
        for status in unit.status_effects:
            # Decrement duration
            status.remaining_turns -= 1

            # Keep effect if still active
            if status.remaining_turns > 0:
                remaining_effects.append(status)

        # Update unit's status effects list
        unit.status_effects = remaining_effects

    def _apply_dot_damage_to_unit(self, unit: 'BattleUnit') -> None:
        """
        Apply DOT damage to a unit from all active DOT effects.

        Each effect is applied separately since they can have different damage types.

        Args:
            unit: The unit to apply DOT damage to
        """
        from ..enums import StatusEffectType

        for status in unit.status_effects:
            if status.effect.effect_type == StatusEffectType.DOT:
                # Calculate DOT damage for this effect
                dot_damage = self._calculate_dot_damage_for_effect(status)

                if dot_damage > 0:
                    # Apply damage with the effect's specific damage type
                    # take_damage handles armor/modifiers automatically
                    unit.take_damage(
                        int(dot_damage),
                        status.effect.dot_damage_type,  # Use the effect's damage type
                        armor_piercing=status.effect.dot_ap_percent
                    )

    # =========================================================================
    # Step 2: Check if all player units dead
    # =========================================================================

    def _step_check_all_player_units_dead(self) -> bool:
        """
        Step 2: Check if all player units are dead.

        Returns:
            True if all player units are dead (ignoring unimportant units)
        """
        # TODO: Implement death check
        return False

    # =========================================================================
    # Step 3: Collapse player front row
    # =========================================================================

    def _step_collapse_player_front_row(self) -> None:
        """
        Step 3: Collapse 1 row if front row is empty.

        If row 0 (front row) has no alive units, move all units forward
        by one row. Only collapses ONE row per turn.
        """
        # TODO: Implement row collapse
        pass

    # =========================================================================
    # Step 4: Reduce player cooldowns
    # =========================================================================

    def _step_reduce_player_cooldowns(self) -> None:
        """
        Step 4: Reduce cooldowns for non-stunned units.

        For each alive player unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement status effect durations
        """
        # TODO: Implement cooldown reduction
        pass

    # =========================================================================
    # Step 5: Get player action
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
    # Step 6: Check if unit is disabled
    # =========================================================================

    def _step_is_unit_disabled(self, action: 'Action') -> bool:
        """
        Step 6: Check if unit is stunned/frozen/disabled.

        Args:
            action: The action to check

        Returns:
            True if the unit cannot act
        """
        # TODO: Implement disability check
        return False

    # =========================================================================
    # Step 7: Check if target is valid
    # =========================================================================

    def _step_is_target_valid(self, action: 'Action') -> bool:
        """
        Step 7: Check if targeting location is valid.

        Validates:
        - Target is in range
        - Target location has a unit (if required)
        - Target unit is alive (if required)
        - Line of sight is clear

        Args:
            action: The action to validate

        Returns:
            True if target is valid
        """
        # TODO: Implement target validation
        return True

    # =========================================================================
    # Step 8: Calculate base damage
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
    # Step 9: Check for hit/miss
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
    # Step 10: Apply multipliers and armor
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
    # Step 11: Apply damage
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
    # Step 12: Check for dead units
    # =========================================================================

    def _step_check_for_dead_units(self) -> None:
        """
        Step 12: Check for dead units and update states.

        Updates is_alive status for any units that have 0 HP.
        """
        # TODO: Implement death check
        pass

    # =========================================================================
    # Step 13: Apply status effects
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
    # Step 14: Update cooldown and ammo
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
        # TODO: Implement death check
        return False
