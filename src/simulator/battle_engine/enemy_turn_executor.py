"""
Enemy Turn Executor.

Handles all enemy turn step execution with explicit, ordered steps.
"""

from typing import TYPE_CHECKING, Optional, List, Callable
import random

from .battle_types import (
    TurnResult, BattleResult, HitResult, DamageResult,
    Position, ActionCandidate
)
from ..enums import DamageType

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
        # Step 1: Apply DOT to enemy units
        self._step_apply_dot_to_enemy()

        # Step 2: Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED

        # Step 3: Collapse 1 row if no units on front row
        self._step_collapse_enemy_front_row()

        # Step 4: Reduce cooldowns (unit must not be stunned)
        self._step_reduce_enemy_cooldowns()

        # Step 5: Make list of all alive units and abilities
        all_possible_actions = self._step_list_all_alive_units_and_abilities()

        # Step 6: Filter all units which are stunned/frozen
        filtered_actions = self._step_filter_stunned_units(all_possible_actions)

        # Step 7: Filter abilities on cooldown
        filtered_actions = self._step_filter_cooldown_abilities(filtered_actions)

        # Step 8: Calculate valid targets for each ability
        # (empty locations & targets that will not take damage are not valid)
        actions_with_targets = self._step_calculate_valid_targets(filtered_actions)

        # Step 9: Filter abilities with no valid target
        valid_actions = self._step_filter_no_valid_targets(actions_with_targets)

        # No valid actions - skip turn
        if not valid_actions:
            return TurnResult.NO_VALID_ACTIONS

        # Select action using AI policy
        action = self._step_select_action(valid_actions)

        # Step 10: Calculate base damage
        base_damage = self._step_calculate_base_damage(action)

        # Step 11: Check for dodges/misses/etc
        hit_result = self._step_check_hit(action)
        if not hit_result.hit:
            self._step_update_cooldown_and_ammo(action)
            return TurnResult.ATTACK_MISSED

        # Apply critical hit if rolled
        if hit_result.is_critical:
            base_damage *= 1.5

        # Step 12: Apply modifiers & armor
        final_damage = self._step_apply_modifiers_and_armor(action, base_damage)

        # Step 13: Deal damage
        self._step_deal_damage(action, final_damage)

        # Step 14: Check for dead units
        self._step_check_for_dead_units()

        # Check if all player units dead -> end battle with loss
        if self._step_check_all_player_units_dead():
            self.battle.result = BattleResult.ENEMY_WIN
            return TurnResult.BATTLE_ENDED

        # Step 15: Apply DOT status effects
        self._step_apply_status_effects(action, final_damage)

        # Step 16: Update cooldown and ammo
        self._step_update_cooldown_and_ammo(action)

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
        from ..enums import StatusEffectType

        for unit in self.battle.enemy_units:
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

        If effect.dot_diminishing is True:
            Formula: actual_damage = base_damage * (d - r_t + 1) / d
            Where:
            - base_damage = source_damage * dot_ability_damage_mult + dot_bonus_damage
            - d = effect.duration (from config)
            - r_t = remaining_turns
            This makes DOT stronger as it progresses (builds up over time).

        If effect.dot_diminishing is False:
            Formula: actual_damage = base_damage (constant each turn)

        Args:
            status: The active status effect

        Returns:
            Actual DOT damage for this turn (before armor/modifiers)
        """
        # Calculate base DOT damage from source damage
        base_damage = status.source_damage * status.effect.dot_ability_damage_mult
        base_damage += status.effect.dot_bonus_damage

        # Check if this DOT diminishes (decays) or stays constant
        if status.effect.dot_diminishing:
            # Apply decay formula - damage builds up over time
            duration = status.effect.duration
            if duration > 0:
                decay_factor = (duration - status.remaining_turns + 1) / duration
                return base_damage * decay_factor
            else:
                # Invalid duration, use constant damage
                return base_damage
        else:
            # Constant DOT damage each turn
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
    # Step 2: Check if all enemy units dead
    # =========================================================================

    def _step_check_all_enemy_units_dead(self) -> bool:
        """
        Step 2: Check if all enemy units are dead.

        Returns:
            True if all enemy units are dead (ignoring unimportant units)
        """
        # TODO: Implement death check
        return False

    # =========================================================================
    # Step 3: Collapse enemy front row
    # =========================================================================

    def _step_collapse_enemy_front_row(self) -> None:
        """
        Step 3: Collapse 1 row if front row is empty.

        If row 0 (front row) has no alive units, move all units forward
        by one row. Only collapses ONE row per turn.
        """
        # TODO: Implement row collapse
        pass

    # =========================================================================
    # Step 4: Reduce enemy cooldowns
    # =========================================================================

    def _step_reduce_enemy_cooldowns(self) -> None:
        """
        Step 4: Reduce cooldowns for non-stunned units.

        For each alive enemy unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement status effect durations
        """
        # TODO: Implement cooldown reduction
        pass

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
        # TODO: Implement stunned filtering
        return actions

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

    def _step_calculate_base_damage(self, action: 'Action') -> float:
        """
        Step 10: Calculate base damage.

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
    # Step 12: Check for hit/miss
    # =========================================================================

    def _step_check_hit(self, action: 'Action') -> HitResult:
        """
        Step 11: Check for dodges/misses/etc.

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
    # Step 13: Apply modifiers and armor
    # =========================================================================

    def _step_apply_modifiers_and_armor(
        self, action: 'Action', base_damage: float
    ) -> float:
        """
        Step 12: Apply modifiers & armor.

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
        # TODO: Implement modifiers and armor
        return base_damage

    # =========================================================================
    # Step 14: Deal damage
    # =========================================================================

    def _step_deal_damage(self, action: 'Action', damage: float) -> None:
        """
        Step 13: Deal damage.

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
    # Step 15: Check for dead units
    # =========================================================================

    def _step_check_for_dead_units(self) -> None:
        """
        Step 14: Check for dead units.

        Updates is_alive status for any units that have 0 HP.
        """
        # TODO: Implement death check
        pass

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
    # Step 17: Update cooldown and ammo
    # =========================================================================

    def _step_update_cooldown_and_ammo(self, action: 'Action') -> None:
        """
        Step 16: Update cooldown and ammo.

        Sets weapon on cooldown and consumes ammo if applicable.

        Args:
            action: The action that was executed
        """
        # TODO: Implement cooldown and ammo update
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
        # TODO: Implement death check
        return False
