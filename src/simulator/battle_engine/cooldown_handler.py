"""
Cooldown Handler.

Handles all cooldown reduction logic.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleState, BattleUnit
    from ..enums import BattleSide


class CooldownHandler:
    """Handles cooldown reduction for units."""

    @staticmethod
    def is_unit_stunned(unit: 'BattleUnit') -> bool:
        """
        Check if a unit is stunned and cannot act.

        A unit is stunned if it has a status effect with:
        - effect_type == StatusEffectType.STUN
        - stun_block_action == True

        Args:
            unit: The unit to check

        Returns:
            True if the unit is stunned and cannot act
        """
        from ..enums import StatusEffectType
        
        for status in unit.status_effects:
            if (status.effect.effect_type == StatusEffectType.STUN and
                    status.effect.stun_block_action):
                return True
        return False

    @staticmethod
    def reduce_unit_cooldowns(unit: 'BattleUnit') -> None:
        """
        Reduce cooldowns for a single unit (if not stunned).

        For the unit:
        - Decrement weapon cooldowns
        - Decrement global cooldown

        Args:
            unit: The unit whose cooldowns to reduce
        """
        # Only reduce cooldowns if unit is not stunned
        if not CooldownHandler.is_unit_stunned(unit):
            # Reduce weapon cooldowns
            for weapon_id in list(unit.weapon_cooldowns.keys()):
                if unit.weapon_cooldowns[weapon_id] > 0:
                    unit.weapon_cooldowns[weapon_id] -= 1
                    # Remove cooldown if it reaches 0
                    if unit.weapon_cooldowns[weapon_id] == 0:
                        del unit.weapon_cooldowns[weapon_id]
            
            # Reduce global cooldown
            if unit.global_cooldown > 0:
                unit.global_cooldown -= 1

    @staticmethod
    def reduce_cooldowns_for_side(battle: 'BattleState', side: 'BattleSide') -> None:
        """
        Reduce cooldowns for all units on the specified side.

        For each alive unit that can act (not stunned):
        - Decrement weapon cooldowns
        - Decrement global cooldown

        Args:
            battle: The battle state
            side: The side to reduce cooldowns for (BattleSide.PLAYER_TEAM or BattleSide.ENEMY_TEAM)
        """
        from ..enums import BattleSide
        
        # Get the appropriate units dictionary
        units = battle.player_units if side == BattleSide.PLAYER_TEAM else battle.enemy_units
        
        # Reduce cooldowns for each unit
        for unit in units.values():
            CooldownHandler.reduce_unit_cooldowns(unit)

