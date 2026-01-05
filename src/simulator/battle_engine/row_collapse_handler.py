"""
Row Collapse Handler.

Handles row collapse logic when the front row is empty.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleState
    from ..enums import BattleSide


class RowCollapseHandler:
    """Handles row collapse when front row is empty."""

    @staticmethod
    def collapse_front_row(battle: 'BattleState', side: 'BattleSide') -> None:
        """
        Collapse 1 row if front row is empty for the specified side.

        If row 0 (front row, y=0) has no alive units, move all units forward
        by one row (decrease y by 1). Only collapses ONE row per turn.
        Increments the appropriate collapse counter.

        Args:
            battle: The battle state
            side: The side to collapse rows for (BattleSide.PLAYER_TEAM or BattleSide.ENEMY_TEAM)
        """
        from ..enums import BattleSide
        from ..models import Position
        
        # Get the appropriate units dictionary
        units = battle.player_units if side == BattleSide.PLAYER_TEAM else battle.enemy_units
        
        # Check if row 0 (y=0) has any units
        has_front_row_units = any(
            pos.y == 0 for pos in units.keys()
        )
        
        # If front row has units, no collapse needed
        if has_front_row_units:
            return
        
        # Front row is empty - move all units forward by 1 row
        # Need to collect all units first, then update positions
        # (can't modify dict while iterating)
        units_to_move = list(units.items())
        
        # Clear the dictionary
        units.clear()
        
        # Move each unit forward by 1 row (decrease y by 1)
        for old_pos, unit in units_to_move:
            # Create new position with y decreased by 1
            new_pos = Position(x=old_pos.x, y=old_pos.y - 1)
            
            # Update unit's position attribute
            unit.position = new_pos
            
            # Add to dictionary with new position as key
            units[new_pos] = unit
        
        # Increment collapse counter (tracks how many times collapse occurred)
        if side == BattleSide.PLAYER_TEAM:
            battle.player_rows_collapsed += 1
        else:
            battle.enemy_rows_collapsed += 1

