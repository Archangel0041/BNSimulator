"""
Death Handler.

Handles all death checking and unit removal logic.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleState
    from ..enums import BattleSide


class DeathHandler:
    """Handles death checking and unit removal."""

    @staticmethod
    def check_for_dead_units(battle: 'BattleState', side: 'BattleSide') -> None:
        """
        Check for dead units on the specified side and remove them.

        Removes units with HP <= 0 from the working copy by clearing
        their position in the dictionary.

        Args:
            battle: The battle state
            side: The side to check (BattleSide.PLAYER_TEAM or BattleSide.ENEMY_TEAM)
        """
        from ..enums import BattleSide
        
        if side == BattleSide.PLAYER_TEAM:
            # Remove dead units from player units dict
            dead_positions = [
                pos for pos, unit in battle.player_units.items()
                if unit.current_hp <= 0
            ]
            for pos in dead_positions:
                del battle.player_units[pos]
        elif side == BattleSide.ENEMY_TEAM:
            # Remove dead units from enemy units dict
            dead_positions = [
                pos for pos, unit in battle.enemy_units.items()
                if unit.current_hp <= 0
            ]
            for pos in dead_positions:
                del battle.enemy_units[pos]

    @staticmethod
    def check_all_units_dead(battle: 'BattleState', side: 'BattleSide') -> bool:
        """
        Check if all units on the specified side are dead.

        Args:
            battle: The battle state
            side: The side to check (BattleSide.PLAYER_TEAM or BattleSide.ENEMY_TEAM)

        Returns:
            True if all units on the side are dead (ignoring unimportant units)
        """
        from ..enums import BattleSide
        
        # Get the appropriate units dictionary
        units = battle.player_units if side == BattleSide.PLAYER_TEAM else battle.enemy_units
        
        # Check if any important units are still alive
        # Units in the dict are alive by definition (dead ones are removed)
        return not any(
            not unit.template.unimportant
            for unit in units.values()
        )

