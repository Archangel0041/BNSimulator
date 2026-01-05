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

        For enemy AI, stricter rules apply:
        - Must target units that match tag requirements
        - Cannot place reticles on empty spots for TargetType.TARGET
        - The reticle position itself must be a valid target by tags

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

        # Get target unit at the position
        target_unit = battle.get_unit_at_position(action.target_position, BattleSide.PLAYER_TEAM)

        # For TargetType.NONE or TARGET: Enemy AI MUST target a valid unit
        # (cannot place reticle on empty spots)
        if target_type in (TargetType.NONE, TargetType.TARGET):
            if target_unit is None or target_unit.current_hp <= 0:
                return False

            # Validate tag requirements
            if not EnemyTargetValidator._can_target_by_tags(
                ability_targets=stats.targets,
                unit_tags=target_unit.template.tags,
                battle=battle
            ):
                return False

        # For TargetType.WEAPON: Enemy AI can target empty spots,
        # but in practice we still validate if there are any valid targets nearby
        # For now, allow it (simplified)

        return True

    @staticmethod
    def _can_target_by_tags(
        ability_targets: list[int],
        unit_tags: list[int],
        battle: 'BattleState'
    ) -> bool:
        """
        Check if an ability with given target tags can hit a unit with given tags.

        Uses tag hierarchy: if ability targets a parent tag, it can target all
        descendants.

        Args:
            ability_targets: Tags the ability can target
            unit_tags: Tags the unit has
            battle: The battle state (for accessing tag hierarchy)

        Returns:
            True if the unit can be targeted
        """
        from ..enums import UnitTag

        if not ability_targets:
            return True  # No restrictions = can target anything

        # UNIT tag matches everything
        if UnitTag.UNIT in ability_targets:
            return True

        # Expand all ability target tags to include all descendants recursively
        valid_tags = set()
        for tag in ability_targets:
            valid_tags.add(tag)
            EnemyTargetValidator._expand_tag_recursive(
                tag, valid_tags, battle.data_loader.config.tag_hierarchy
            )

        # Check if unit has any valid tag
        return bool(valid_tags.intersection(set(unit_tags)))

    @staticmethod
    def _expand_tag_recursive(
        tag: int,
        result_set: set,
        tag_hierarchy: dict[int, list[int]]
    ) -> None:
        """
        Recursively expand a tag to include all its descendants in the hierarchy.

        Args:
            tag: The tag to expand
            result_set: Set to add expanded tags to (modified in place)
            tag_hierarchy: The tag hierarchy dictionary (parent -> list of children)
        """
        # Get children of this tag
        children = tag_hierarchy.get(tag, [])
        for child in children:
            if child not in result_set:
                result_set.add(child)
                # Recursively expand this child
                EnemyTargetValidator._expand_tag_recursive(child, result_set, tag_hierarchy)

