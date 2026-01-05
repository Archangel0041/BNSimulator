"""
Enemy Target Validator.

Handles target validation logic for enemy units.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..battle import BattleState
    from .battle_types import Position, ActionCandidate


class EnemyTargetValidator:
    """Handles target validation for enemy actions."""

    @staticmethod
    def calculate_valid_targets(
        battle: 'BattleState',
        action_candidate: 'ActionCandidate'
    ) -> List['Position']:
        """
        Calculate valid target positions for an action candidate.

        Returns all player unit positions that can be validly targeted by this ability.

        Args:
            battle: The battle state
            action_candidate: The action candidate to calculate targets for

        Returns:
            List of valid target positions
        """
        from ..battle import Action
        from .player_target_validator import PlayerTargetValidator
        from ..enums import BattleSide

        # Get the attacking unit
        unit = battle.enemy_units.get(action_candidate.unit_position)
        if unit is None:
            return []

        # Get the ability
        ability = battle.data_loader.get_ability(action_candidate.ability_id)
        if ability is None:
            return []

        valid_targets = []

        # For enemy AI attacking player units:
        # Try targeting each player unit position
        for target_position in battle.player_units.keys():
            # Create a test action with this target
            test_action = Action(
                unit_position=action_candidate.unit_position,
                ability_id=action_candidate.ability_id,
                target_position=target_position
            )

            # Use PlayerTargetValidator logic but adapted for enemy side
            # We need to check if this target is valid
            if EnemyTargetValidator._is_target_valid_for_enemy(test_action, battle):
                valid_targets.append(target_position)

        return valid_targets

    @staticmethod
    def _is_target_valid_for_enemy(action: 'Action', battle: 'BattleState') -> bool:
        """
        Check if a target is valid for an enemy unit.

        This is similar to PlayerTargetValidator.is_action_valid() but:
        - Targets player units instead of enemy units
        - Assumes cooldowns/ammo already checked in filtering step

        Args:
            action: The action to validate
            battle: The battle state

        Returns:
            True if target is valid, False otherwise
        """
        from ..enums import TargetType, BattleSide

        # Get the attacking enemy unit
        attacker = battle.enemy_units.get(action.unit_position)
        if attacker is None:
            return False

        # Get the ability
        ability = battle.data_loader.get_ability(action.ability_id)
        if ability is None:
            return False

        stats = ability.stats
        target_area = ability.stats.target_area

        # Determine target type
        target_type = TargetType.NONE
        if target_area:
            target_type = target_area.target_type

        # Check if target position has alive unit (only for NONE type)
        if target_type == TargetType.NONE:
            # Enemy is attacking player units
            target_unit = battle.get_unit_at_position(action.target_position, BattleSide.PLAYER_TEAM)
            if target_unit is None or target_unit.current_hp <= 0:
                return False

        # For now, simplified validation - just check if there's a valid target
        # Full validation (range, LOS, blocking) can be added later if needed
        return True

