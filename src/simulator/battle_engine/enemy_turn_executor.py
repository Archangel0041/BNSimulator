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
        # Step 1: Make list of all alive units and abilities (already filters stunned units)
        all_possible_actions = self._step_list_all_alive_units_and_abilities()

        # Step 2: Filter abilities on cooldown
        filtered_actions = self._step_filter_cooldown_abilities(all_possible_actions)

        # Step 3: Calculate valid targets for each ability
        # (empty locations & targets that will not take damage are not valid)
        actions_with_targets = self._step_calculate_valid_targets(filtered_actions)

        # Step 4: Filter abilities with no valid target
        valid_actions = self._step_filter_no_valid_targets(actions_with_targets)

        # No valid actions - skip turn
        if not valid_actions:
            return TurnResult.PASSED

        # Step 6: Select action using AI policy
        action = self._step_select_action(valid_actions)
        if action is None:
            return TurnResult.PASSED

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
    # Step 5: List all alive units and abilities
    # =========================================================================

    def _step_list_all_alive_units_and_abilities(self) -> List[ActionCandidate]:
        """
        Step 1: Make list of all alive units and abilities.

        Creates a unique pairwise list for each unit that's alive, not stunned,
        and its corresponding abilities.

        Returns:
            List of ActionCandidate objects (unit_position, ability_id pairs)
        """
        from .status_effect_handler import StatusEffectHandler
        
        action_candidates = []
        
        # Iterate through all enemy units (dead units are already removed from dictionary)
        for unit_position, unit in self.battle.enemy_units.items():
            # Skip if unit is stunned
            if StatusEffectHandler.is_unit_stunned(unit):
                continue
            
            # Iterate through all weapons for this unit
            for weapon_id, weapon in unit.template.weapons.items():
                # Iterate through all abilities for this weapon
                for ability_id in weapon.abilities:
                    # Create an ActionCandidate for this unit+ability pair
                    action_candidate = ActionCandidate(
                        unit_position=unit_position,
                        ability_id=ability_id
                    )
                    action_candidates.append(action_candidate)
        
        return action_candidates

    # =========================================================================
    # Step 7: Filter abilities on cooldown
    # =========================================================================

    def _step_filter_cooldown_abilities(
        self, actions: List[ActionCandidate]
    ) -> List[ActionCandidate]:
        """
        Step 3: Filter abilities on cooldown.

        Removes actions where:
        - Ability is on cooldown (ability_cooldowns)
        - Weapon global cooldown is active (global_cooldowns)
        - Charge time not ready (ability_available_turn > current turn)
        - Insufficient ammo (current_ammo < ammo_required)

        Args:
            actions: List of action candidates

        Returns:
            Filtered list of action candidates
        """
        filtered = []
        current_turn = self.battle.turn_number
        
        for action_candidate in actions:
            unit = self.battle.enemy_units.get(action_candidate.unit_position)
            if unit is None:
                continue
            
            # Get ability directly
            ability = self.battle.data_loader.get_ability(action_candidate.ability_id)
            if ability is None:
                continue
            
            stats = ability.stats
            
            # Find the weapon that contains this ability
            weapon_id = self.battle.get_weapon_id_for_ability(unit, action_candidate.ability_id)
            if weapon_id is None:
                continue
            
            weapon = unit.template.weapons.get(weapon_id)
            if weapon is None:
                continue
            
            # Check ability cooldown
            if action_candidate.ability_id in unit.ability_cooldowns:
                if unit.ability_cooldowns[action_candidate.ability_id] > 0:
                    continue  # Ability is on cooldown
            
            # Check weapon global cooldown
            if weapon_id in unit.global_cooldowns:
                if unit.global_cooldowns[weapon_id] > 0:
                    continue  # Weapon global cooldown is active
            
            # Check charge time (ability_available_turn)
            if action_candidate.ability_id in unit.ability_available_turn:
                if unit.ability_available_turn[action_candidate.ability_id] > current_turn:
                    continue  # Charge time not ready
            
            # Check ammo
            current_ammo = unit.ammo.get(weapon_id, weapon.stats.ammo)
            if current_ammo < stats.ammo_required:
                continue  # Insufficient ammo
            
            # All checks passed, keep this action
            filtered.append(action_candidate)
        
        return filtered

    # =========================================================================
    # Step 8: Calculate valid targets
    # =========================================================================

    def _step_calculate_valid_targets(
        self, actions: List[ActionCandidate]
    ) -> List[ActionCandidate]:
        """
        Step 4: Calculate valid targets for each ability.

        For each action, calculates which positions are valid targets.
        Empty locations & targets that will not take damage are excluded.

        Args:
            actions: List of action candidates

        Returns:
            Action candidates with valid_targets populated
        """
        from .enemy_target_validator import EnemyTargetValidator
        
        # Calculate valid targets for each action candidate
        for action_candidate in actions:
            action_candidate.valid_targets = EnemyTargetValidator.calculate_valid_targets(
                self.battle, action_candidate
            )
        
        return actions

    # =========================================================================
    # Step 9: Filter actions with no valid targets
    # =========================================================================

    def _step_filter_no_valid_targets(
        self, actions: List[ActionCandidate]
    ) -> List['Action']:
        """
        Step 5: Filter abilities with no valid target.

        Removes ActionCandidates with empty valid_targets.
        Converts remaining ActionCandidates to Action objects by picking
        a target from valid_targets list.

        Args:
            actions: List of action candidates with targets

        Returns:
            List of full Action objects ready for execution
        """
        from ..battle import Action
        
        valid_actions = []
        
        for action_candidate in actions:
            # Skip if no valid targets
            if not action_candidate.valid_targets:
                continue
            
            # Get the unit
            unit = self.battle.enemy_units.get(action_candidate.unit_position)
            if unit is None:
                continue
            
            # Pick a target from valid_targets (for now, random selection)
            # This could be enhanced with AI logic later
            target_position = self.rng.choice(action_candidate.valid_targets)
            
            # Create Action object
            action = Action(
                unit_position=action_candidate.unit_position,
                ability_id=action_candidate.ability_id,
                target_position=target_position
            )
            valid_actions.append(action)
        
        return valid_actions

    # =========================================================================
    # Step 10: Select action
    # =========================================================================

    def _step_select_action(self, valid_actions: List['Action']) -> 'Action':
        """
        Step 6: Select action using AI policy.

        Picks 1 out of all available actions.
        Uses the configured AI policy if available, otherwise selects randomly.

        Args:
            valid_actions: List of valid actions to choose from

        Returns:
            Selected action
        """
        if not valid_actions:
            return None
        
        # Use AI policy if configured, otherwise random selection
        if self.ai_policy is not None:
            return self.ai_policy(valid_actions, self.battle)
        else:
            # Default: random selection
            return self.rng.choice(valid_actions)

    # =========================================================================
    # Step 11: Calculate base damage
    # =========================================================================

    def _step_calculate_base_damage(self, action: 'Action') -> tuple[int, int]:
        """
        Step 7: Calculate base damage range.

        Matches bn_toolkit_2's calculateDamageAtRank formula:
        1. scaled_base = floor(base_damage * damage_from_weapon)  [only floor if != 1]
        2. power_contrib = floor(2 * damage_from_unit * power)    [only floor if != 1]
        3. damage = floor(scaled_base * (1 + power_contrib / 100))

        Args:
            action: The action being executed

        Returns:
            Tuple of (damage_min, damage_max) - both integers
        """
        # Get the attacking unit
        attacker = self.battle.enemy_units.get(action.unit_position)
        if attacker is None:
            return (0, 0)

        # Find the weapon that contains this ability
        weapon_id = self.battle.get_weapon_id_for_ability(attacker, action.ability_id)
        if weapon_id is None:
            return (0, 0)

        weapon = attacker.template.weapons.get(weapon_id)
        if weapon is None:
            return (0, 0)

        ability = self.battle.data_loader.get_ability(action.ability_id)
        if ability is None:
            return (0, 0)

        stats = ability.stats
        power = attacker.template.stats.power

        # Step 1: Apply damage_from_weapon multiplier (floor only if not 1)
        dfw = stats.damage_from_weapon
        scaled_min = math.floor(weapon.stats.base_damage_min * dfw) if dfw != 1.0 else weapon.stats.base_damage_min
        scaled_max = math.floor(weapon.stats.base_damage_max * dfw) if dfw != 1.0 else weapon.stats.base_damage_max

        # Step 2: Power contribution: floor(2 * damage_from_unit * power) if not 1
        dfu = stats.damage_from_unit
        power_contrib = math.floor(2 * dfu * power) if dfu != 1.0 else 2 * power

        # Step 3: Final damage range
        damage_min = math.floor(scaled_min * (1 + power_contrib / 100.0))
        damage_max = math.floor(scaled_max * (1 + power_contrib / 100.0))

        return (damage_min, damage_max)

