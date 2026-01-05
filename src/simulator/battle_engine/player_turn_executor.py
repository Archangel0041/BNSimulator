"""
Player Turn Executor.

Handles all player turn step execution with explicit, ordered steps.
"""

from typing import TYPE_CHECKING, Optional, Callable
import random
import math

from .battle_types import TurnResult, BattleResult, HitResult, DamageResult, Position
from .status_effect_handler import StatusEffectHandler
from .death_handler import DeathHandler
from .damage_handler import DamageHandler
from .armor_handler import ArmorHandler
from ..enums import DamageType, BattleSide
from .cooldown_handler import CooldownHandler
from .row_collapse_handler import RowCollapseHandler
from .targeting_handler import TargetingHandler


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
        if CooldownHandler.is_unit_stunned(self.battle.player_units.get(action.unit_position)):
            return TurnResult.UNIT_CANNOT_ACT

        # Step 3: Check if targeting location is valid
        if not self._step_is_target_valid(action):
            return TurnResult.INVALID_TARGET

        # Step 4: Calculate base damage range
        damage_min, damage_max = self._step_calculate_base_damage(action)

        # Step 5: Calculate all hits using TargetingHandler
        # This handles targeting patterns, damage rolls, hit/crit checks, and groups base+splash
        hits_by_position = TargetingHandler.calculate_hits_by_position(
            self.battle, action, damage_min, damage_max, BattleSide.PLAYER_TEAM
        )
        
        # Step 6: Process all collected hits (apply damage, status effects, etc.)
        DamageHandler.process_all_hits(self.battle, action, hits_by_position, BattleSide.PLAYER_TEAM) 

        # Step 7: Check for dead enemy units (from damage)
        DeathHandler.check_for_dead_units(self.battle, BattleSide.ENEMY_TEAM)
        
        # Check if all enemy units dead -> end battle with victory
        if DeathHandler.check_all_units_dead(self.battle, BattleSide.ENEMY_TEAM):
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED
        
        # Step 8: Update cooldown and ammo
        CooldownHandler.update_cooldowns_for_unit(self.battle, self.battle.player_units.get(action.unit_position), action)
        
        # Step 9: Apply DOT to enemy units (opposing side that was attacked)
        StatusEffectHandler.apply_dot_to_all_units_for_side(self.battle, BattleSide.ENEMY_TEAM)
        
        # Step 10: Check for dead enemy units (from DOT)
        DeathHandler.check_for_dead_units(self.battle, BattleSide.ENEMY_TEAM)
        
        # Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED
        
        # Step 11: Collapse 1 row if no units on front row (enemy side)
        RowCollapseHandler.collapse_front_row(self.battle, BattleSide.ENEMY_TEAM)
        
        # Step 12: Reduce cooldowns (unit must not be stunned) (enemy side)
        CooldownHandler.reduce_cooldowns_for_side(self.battle, BattleSide.ENEMY_TEAM)
        
        # Step 13: Decay stun/freeze effects (player side) - after turn completes
        StatusEffectHandler.decay_stun_effects_for_side(self.battle, BattleSide.PLAYER_TEAM)
        
        return TurnResult.SUCCESS


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
    # Step 9: Calculate base damage
    # =========================================================================

    def _step_calculate_base_damage(self, action: 'Action') -> tuple[int, int]:
        """
        Step 4: Calculate base damage range.

        Calculates base damage range from weapon stats and unit power:
        - damage_min = floor(base_damage_min * (1 + (2 * power / 100)))
        - damage_max = floor(base_damage_max * (1 + (2 * power / 100)))

        Args:
            action: The action being executed

        Returns:
            Tuple of (damage_min, damage_max) - both integers
        """
        # Get the attacking unit
        attacker = self.battle.player_units.get(action.unit_position)
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

