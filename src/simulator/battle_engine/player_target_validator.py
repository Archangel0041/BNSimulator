"""
Player Target Validator.

Handles target validation logic for player-side attacks.
"""

from typing import TYPE_CHECKING, List, Dict
from ..battle import BattleState, BattleUnit, Action
from ..models import Ability, Position
from ..enums import TargetType, LineOfFire, AttackDirection, UnitBlocking


class PlayerTargetValidator:
    """Validates if a player can legally target a specific position for an attack."""

    @staticmethod
    def is_action_valid(action: 'Action', battle: 'BattleState') -> bool:
        """
        Check if the action is valid (cooldowns, ammo, charge time, target validation).

        Validates:
        - Ability and global cooldowns are ready
        - Sufficient ammo available
        - Charge time (prep time) has elapsed
        - Target is in range
        - Target location has a unit (if required)
        - Target unit is alive (if required)
        - Line of fire and blocking are clear
        - Target type requirements are met
        - Tag hierarchy matching

        Args:
            action: The action being validated
            battle: The battle state

        Returns:
            True if the action is valid, False otherwise
        """
        # Get the attacking unit
        attacker = battle.player_units.get(action.unit_position)
        if attacker is None:
            return False

        # Get the weapon and ability
        weapon = attacker.template.weapons.get(action.weapon_id)
        if weapon is None or not weapon.abilities:
            return False

        # Use first ability (could be extended to support multiple abilities per weapon)
        ability_id = weapon.abilities[0]
        ability = battle.data_loader.get_ability(ability_id)
        if ability is None:
            return False

        stats = ability.stats
        target_area = ability.stats.target_area

        # Check ability-specific cooldown
        if attacker.ability_cooldowns.get(ability_id, 0) > 0:
            return False

        # Check weapon-specific global cooldown
        if attacker.global_cooldowns.get(action.weapon_id, 0) > 0:
            return False

        # Check ammo
        if weapon.stats.ammo >= 0:  # -1 means unlimited ammo
            current_ammo = attacker.ammo.get(action.weapon_id, 0)
            ammo_required = stats.ammo_required
            if current_ammo < ammo_required:
                return False

        # Check charge time (prep time) - ability-specific
        if stats.charge_time > 0:
            # Each ability has its own charge_time and tracks when it became available
            # Check if this specific ability is available yet
            ability_available_turn = attacker.ability_available_turn.get(ability_id)
            if ability_available_turn is None:
                # Ability not initialized - shouldn't happen, but fail safe
                return False
            if battle.turn_number < ability_available_turn:
                return False

        # Determine target type (default to NONE if not specified)
        target_type = TargetType.NONE
        if target_area:
            target_type = target_area.target_type
        else:
            # No target_area means target_type 0 (NONE)
            target_type = TargetType.NONE

        # Check if target position has alive unit (only for NONE type)
        target_unit = None
        if target_type == TargetType.NONE:
            target_unit = battle.get_unit_at_position(action.target_position)
            if target_unit is None or target_unit.current_hp <= 0:
                return False

        # Check range (using attack direction to determine effective range)
        range_distance = PlayerTargetValidator._calculate_range_distance(
            attacker.position, action.target_position, stats.attack_direction, battle
        )
        if range_distance < stats.min_range or range_distance > stats.max_range:
            return False

        # Check target type and apply appropriate validation
        if target_type == TargetType.NONE:
            # Type 0: Non-reticle - only base position needs blocking check
            return PlayerTargetValidator._check_line_of_fire_and_blocking(
                attacker.position, action.target_position,
                stats.line_of_fire, stats.attack_direction, battle
            )

        elif target_type == TargetType.WEAPON:
            # Type 1: Non-reticle hitting all positions - can fire at any point
            # No line of fire or blocking checks needed for WEAPON type
            if not target_area or not target_area.data:
                return False

            # Check if any position in the attack pattern is in range
            # (WEAPON type can be fired at any point, so we just need to verify
            # at least one position in the pattern would be in range)
            has_valid_range = False
            for damage_area in target_area.data:
                pattern_pos = Position(
                    x=action.target_position.x + damage_area.pos.x,
                    y=action.target_position.y + damage_area.pos.y
                )
                # Check if this position is in range
                pattern_range = PlayerTargetValidator._calculate_range_distance(
                    attacker.position, pattern_pos, stats.attack_direction, battle
                )
                if stats.min_range <= pattern_range <= stats.max_range:
                    has_valid_range = True
                    break

            return has_valid_range

        elif target_type == TargetType.TARGET:
            # Type 2: Reticle-based - only base position needs blocking check
            return PlayerTargetValidator._check_line_of_fire_and_blocking(
                attacker.position, action.target_position,
                stats.line_of_fire, stats.attack_direction, battle
            )

        return False

    @staticmethod
    def _calculate_range_distance(
        attacker_pos: 'Position', 
        target_pos: 'Position',
        attack_direction: 'AttackDirection',
        battle: 'BattleState'
    ) -> int:
        """
        Calculate range distance between two positions.

        Player and enemy grids face each other. Both use the same y-coordinate system:
        - y=0 is the front row (closest to enemy)
        - y=1, y=2, etc. are back rows

        For cross-grid attacks (player attacking enemy or vice versa):
        - FORWARD/ANY: Distance = attacker_row + target_row + 1
        - BACKWARD: Use back-most row of attacker's side for calculation
          Distance = (max_row_on_attacker_side) + target_row + 1

        Range counts all rows (friendly + enemy). For example:
        - Unit on row 0 with range 1 → can hit enemy row 0
        - Unit on row 1 with range 2 → can only hit enemy row 0 (needs 1 range to cross)
        - Unit on row 2 with range 5 → can hit back-most enemy row

        Args:
            attacker_pos: Position of the attacker
            target_pos: Position of the target
            attack_direction: Direction of the attack (FORWARD, BACKWARD, ANY)
            battle: The battle state

        Returns:
            Number of rows between positions
        """
        from ..enums import AttackDirection
        
        # For BACKWARD attacks, use the back-most row of the attacker's side
        if attack_direction == AttackDirection.BACKWARD:
            # Find the back-most row (max y) on player side
            max_y = max(pos.y for pos in battle.player_units.keys()) if battle.player_units else attacker_pos.y
            # Distance from back-most row
            return max_y + target_pos.y + 1
        
        # FORWARD or ANY: use actual attacker position
        # Cross-grid distance: both sides use same y-coordinate system (0=front, 1,2=back)
        # Distance = attacker_row + target_row + 1
        return attacker_pos.y + target_pos.y + 1

    @staticmethod
    def _check_line_of_fire_and_blocking(
        attacker_pos: 'Position',
        target_pos: 'Position',
        line_of_fire: 'LineOfFire',
        attack_direction: 'AttackDirection',
        battle: 'BattleState'
    ) -> bool:
        """
        Check if line of fire and blocking allow targeting.

        Args:
            attacker_pos: Effective position of the attacker
            target_pos: Position of the target
            line_of_fire: Line of fire type
            battle: The battle state

        Returns:
            True if line of fire and blocking allow the attack
        """
        from ..enums import LineOfFire

        if line_of_fire == LineOfFire.INDIRECT:
            # Indirect: Can hit any unit within range (no blocking check)
            return True

        elif line_of_fire == LineOfFire.CONTACT:
            # Contact: Can only hit first valid target in range, units behind blocked
            return PlayerTargetValidator._check_contact_line_of_fire(
                attacker_pos, target_pos, attack_direction, battle
            )

        elif line_of_fire == LineOfFire.DIRECT:
            # Direct: Can hit past units with None (0) blocking
            return PlayerTargetValidator._check_direct_line_of_fire(
                attacker_pos, target_pos, attack_direction, battle
            )

        elif line_of_fire == LineOfFire.PRECISE:
            # Precise: Can target any units unless Full (2) or God (3) blocking in front
            return PlayerTargetValidator._check_precise_line_of_fire(
                attacker_pos, target_pos, attack_direction, battle
            )

        return False

    @staticmethod
    def _check_contact_line_of_fire(
        attacker_pos: 'Position',
        target_pos: 'Position',
        attack_direction: 'AttackDirection',
        battle: 'BattleState'
    ) -> bool:
        """
        Check Contact line of fire: only first valid target in range.

        Units in front of the target (closer to attacker) block the target.

        Args:
            attacker_pos: Position of the attacker (player side)
            target_pos: Position of the target (enemy side)
            battle: The battle state

        Returns:
            True if target is the first valid target (no units in front of it)
        """
        # Check if target position has a unit
        target_unit = battle.get_unit_at_position(target_pos)
        if target_unit is None:
            return False

        # Get units in path (enemy units in front of target)
        units_in_path = PlayerTargetValidator._get_units_in_path(
            attacker_pos, target_pos, attack_direction, battle
        )

        # If there are any units in the path, target is blocked
        return len(units_in_path) == 0

    @staticmethod
    def _check_direct_line_of_fire(
        attacker_pos: 'Position',
        target_pos: 'Position',
        attack_direction: 'AttackDirection',
        battle: 'BattleState'
    ) -> bool:
        """
        Check Direct line of fire: can hit past units with None blocking.

        Args:
            attacker_pos: Position of the attacker
            target_pos: Position of the target
            battle: The battle state

        Returns:
            True if no units with blocking > None are in the path
        """
        from ..enums import UnitBlocking

        units_in_path = PlayerTargetValidator._get_units_in_path(
            attacker_pos, target_pos, attack_direction, battle
        )

        # Check if any unit in path has blocking > None (0)
        for unit in units_in_path:
            blocking = unit.template.stats.blocking
            if blocking > UnitBlocking.NONE:
                return False

        return True

    @staticmethod
    def _check_precise_line_of_fire(
        attacker_pos: 'Position',
        target_pos: 'Position',
        attack_direction: 'AttackDirection',
        battle: 'BattleState'
    ) -> bool:
        """
        Check Precise line of fire: can target unless Full or God blocking in front.

        Args:
            attacker_pos: Position of the attacker
            target_pos: Position of the target
            battle: The battle state

        Returns:
            True if no Full (2) or God (3) blocking units are in front of target
        """
        from ..enums import UnitBlocking

        units_in_path = PlayerTargetValidator._get_units_in_path(
            attacker_pos, target_pos, attack_direction, battle
        )

        # Check if any unit in path has Full (2) or God (3) blocking
        for unit in units_in_path:
            blocking = unit.template.stats.blocking
            if blocking >= UnitBlocking.FULL:
                return False

        return True

    @staticmethod
    def _get_units_in_path(
        attacker_pos: 'Position',
        target_pos: 'Position',
        attack_direction: 'AttackDirection',
        battle: 'BattleState'
    ) -> List['BattleUnit']:
        """
        Get all units that could block the line of fire to the target.

        For cross-grid attacks (player attacking enemy), we only check units on the
        target's side that are in the same column and in front of the target.

        For BACKWARD attacks, we check from the back-most row (y=2) down to target.
        For FORWARD/ANY attacks, we check from front row (y=0) up to target.

        Args:
            attacker_pos: Position of the attacker (player side)
            target_pos: Position of the target (enemy side)
            attack_direction: Direction of the attack (FORWARD, BACKWARD, ANY)
            battle: The battle state

        Returns:
            List of blocking units, ordered by distance from attacker (closest first)
        """
        from ..enums import AttackDirection
        
        units_in_path = []

        # Only check units in the same column
        if attacker_pos.x != target_pos.x:
            # Different columns - no units can block (assuming straight-line targeting)
            return units_in_path

        # For BACKWARD attacks, check from back-most row (y=2) down to target
        # For FORWARD/ANY attacks, check from front row (y=0) up to target
        if attack_direction == AttackDirection.BACKWARD:
            # Check units from back-most row down to target (y=2, y=1, y=0 if target is at y=0)
            # Find back-most row on player side
            max_y = max(pos.y for pos in battle.player_units.keys()) if battle.player_units else attacker_pos.y
            # Check enemy units from max_y down to target_pos.y
            # Units that are in front of target (lower y) block
            for unit in battle.enemy_units.values():
                if (unit.position.x == target_pos.x and 
                    unit.position.y < target_pos.y and 
                    unit.current_hp > 0):
                    units_in_path.append(unit)
            # Sort by distance from back-most row (closest first)
            units_in_path.sort(key=lambda u: max_y + u.position.y + 1)
        else:
            # FORWARD or ANY: check units in front of target (lower y = closer to attacker)
            for unit in battle.enemy_units.values():
                if (unit.position.x == target_pos.x and 
                    unit.position.y < target_pos.y and 
                    unit.current_hp > 0):
                    units_in_path.append(unit)
            # Sort by distance from attacker (closest first)
            # For cross-grid, distance = attacker_y + unit_y + 1
            units_in_path.sort(key=lambda u: attacker_pos.y + u.position.y + 1)

        return units_in_path

    @staticmethod
    def _can_target_by_tags(
        ability_targets: List[int],
        unit_tags: List[int],
        battle: 'BattleState'
    ) -> bool:
        """
        Check if an ability with given target tags can hit a unit with given tags.

        Uses tag hierarchy: if ability targets a parent tag, it can target all
        descendants. If ability only targets a child tag, it cannot target parents.

        Example:
        - Ability targeting tag 24 (Ground) can hit units with 24, 41, 38, 48, 50, 55, 51, etc.
        - Ability targeting tag 46 (Sniper) can ONLY hit units with 46, not 6 or 24

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

        # TARGETABLE_ALL (51) is a special tag that matches most units
        if UnitTag.UNIT in ability_targets:
            return True

        # Expand all ability target tags to include all descendants recursively
        valid_tags = set()
        for tag in ability_targets:
            valid_tags.add(tag)
            PlayerTargetValidator._expand_tag_recursive(
                tag, valid_tags, battle.data_loader.config.tag_hierarchy
            )

        # Check if unit has any valid tag (direct match)
        return bool(valid_tags.intersection(set(unit_tags)))

    @staticmethod
    def _expand_tag_recursive(
        tag: int,
        result_set: set,
        tag_hierarchy: Dict[int, List[int]]
    ) -> None:
        """
        Recursively expand a tag to include all its descendants in the hierarchy.

        If ability targets tag 24, it can hit units with tag 24 or any child tag
        (recursively, so children of children are included too).

        Args:
            tag: The tag to expand
            result_set: Set to add expanded tags to (modified in place)
            tag_hierarchy: The tag hierarchy dictionary (parent -> list of children)
        """
        children = tag_hierarchy.get(tag, [])
        for child in children:
            if child not in result_set:
                result_set.add(child)
                # Recursively expand children
                PlayerTargetValidator._expand_tag_recursive(
                    child, result_set, tag_hierarchy
                )

