"""
Cooldown Handler.

Handles all cooldown reduction logic.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleState, BattleUnit, Action
    from ..enums import BattleSide


class CooldownHandler:
    """Handles cooldown reduction for units."""

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
        from .status_effect_handler import StatusEffectHandler
        if StatusEffectHandler.is_unit_stunned(unit):
            # Stunned: delay all charge-time thresholds by 1 so charge progress is frozen
            for ability_id in unit.ability_available_turn:
                unit.ability_available_turn[ability_id] += 1
        else:
            # Reduce ability-specific cooldowns
            for ability_id in list(unit.ability_cooldowns.keys()):
                if unit.ability_cooldowns[ability_id] > 0:
                    unit.ability_cooldowns[ability_id] -= 1
                    # Remove cooldown if it reaches 0
                    if unit.ability_cooldowns[ability_id] == 0:
                        del unit.ability_cooldowns[ability_id]

            # Reduce weapon-specific global cooldowns
            for weapon_id in list(unit.global_cooldowns.keys()):
                if unit.global_cooldowns[weapon_id] > 0:
                    unit.global_cooldowns[weapon_id] -= 1
                    # Remove cooldown if it reaches 0
                    if unit.global_cooldowns[weapon_id] == 0:
                        del unit.global_cooldowns[weapon_id]

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

    @staticmethod
    def update_cooldowns_for_unit(battle: 'BattleState', unit: 'BattleUnit', action: 'Action') -> None:
        """
        Update cooldowns for unit that has used an ability.
        """
        # Get the ability
        ability = battle.data_loader.get_ability(action.ability_id)
        if ability is None:
            return
        
        # Find the weapon that contains this ability
        weapon_id = battle.get_weapon_id_for_ability(unit, action.ability_id)
        if weapon_id is None:
            return
        
        unit.ability_cooldowns[action.ability_id] = ability.stats.ability_cooldown
        if ability.stats.global_cooldown > 0:
            unit.global_cooldowns[weapon_id] = ability.stats.global_cooldown
        unit.ammo[weapon_id] = unit.ammo.get(weapon_id, 0) - ability.stats.ammo_required