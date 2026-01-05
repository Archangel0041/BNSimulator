"""
Damage Handler.

Handles damage calculation, including crit multipliers, modifiers, armor penetration, and resistance.
"""

import math
from typing import TYPE_CHECKING

from ..battle import BattleState, BattleUnit
from ..enums import BattleSide, DamageType
from .battle_types import HitResult
from ..models import Action, Position
from .armor_handler import ArmorHandler
from .status_effect_handler import StatusEffectHandler


class DamageHandler:
    """Handles damage calculation and application."""

    @staticmethod
    def process_all_hits(
        battle: 'BattleState',
        action: 'Action',
        hits_by_position: dict['Position', list[HitResult]],
        side: 'BattleSide'
    ) -> None:
        """
        Process all collected hits: apply damage, status effects, etc.
        """
        for position, hit_results in hits_by_position.items():
            for hit_result in hit_results:
                if not hit_result.hit:
                    continue  # Skip this hit if it missed
                
                target_side = BattleSide.ENEMY_TEAM if side == BattleSide.PLAYER_TEAM else BattleSide.PLAYER_TEAM

                # Calculate final damage: applies crit multiplier, modifier, multipliers, and armor
                final_hp_damage, final_armor_damage = DamageHandler.apply_multipliers_and_armor(
                    battle, action, hit_result, position, target_side
                )
                
                # Apply damage from this hit to the target
                DamageHandler.apply_damage_to_unit(
                    battle.get_unit_at_position(position, target_side), 
                    final_hp_damage, 
                    final_armor_damage
                )

                # Apply status effects for this hit
                status_effect_base_damage = final_hp_damage + final_armor_damage
                StatusEffectHandler.try_apply_status_effects_for_hit(
                    battle, action, position, hit_result, status_effect_base_damage
                )
        

    @staticmethod
    def apply_multipliers_and_armor(
        battle: 'BattleState',
        action: 'Action',
        hit_result: 'HitResult',
        target_position: 'Position',
        side: 'BattleSide'
    ) -> tuple[int, int]:
        """
        Calculate final damage by applying crit multiplier, modifier, multipliers, and armor.

        Calculates damage in this order:
        1. Start with damage_roll
        2. Apply crit multiplier (1.85x if critical)
        3. Apply modifier percentage (from target_area/damage_area)
        4. Apply armor penetration and resistance calculations
        5. Apply damage to armor and HP separately
        6. Return total HP damage (for status effect base damage)

        Args:
            battle: The battle state
            action: The action being executed
            hit_result: The HitResult containing damage_roll, modifier, and crit status
            target_position: Position of the target unit
            side: The side performing the action (BattleSide.PLAYER_TEAM or BattleSide.ENEMY_TEAM)

        Returns:
            Tuple of (total_hp_damage, actual_armor_damage)
        """
        from .armor_handler import ArmorHandler
        
        # Get the attacking unit and ability
        units = battle.player_units if side == BattleSide.PLAYER_TEAM else battle.enemy_units
        attacker = units.get(action.unit_position)
        if attacker is None:
            return (0, 0)
        
        # Get the ability
        ability = battle.data_loader.get_ability(action.ability_id)
        if ability is None:
            return (0, 0)
        
        stats = ability.stats
        
        # Get the target unit (opposite side of attacker)
        target_side = BattleSide.ENEMY_TEAM if side == BattleSide.PLAYER_TEAM else BattleSide.PLAYER_TEAM
        target_unit = battle.get_unit_at_position(target_position, target_side)
        if target_unit is None:
            return (0, 0)
        
        # Step 1: Start with damage_roll
        base_damage = hit_result.damage_roll
        
        # Step 2: Apply crit multiplier if critical
        if hit_result.is_critical:
            base_damage = math.floor(base_damage * 1.85)
        
        # Step 3: Apply modifier percentage (from target_area/damage_area)
        modified_damage = math.floor(base_damage * hit_result.modifier / 100.0)
        
        # Step 4: Apply armor penetration and resistance calculations
        # Get damage type and armor piercing from ability
        damage_type = stats.damage_type
        ap_percent = stats.armor_piercing_percent  # e.g., 0.85 = 85% armor penetration
        
        # Get damage type name for modifier lookup
        # Map all damage types to their string names used in damage_mods dict
        dtype_name = {
            DamageType.PIERCING: "piercing",
            DamageType.COLD: "cold",
            DamageType.CRUSHING: "crushing",
            DamageType.EXPLOSIVE: "explosive",
            DamageType.FIRE: "fire",
            DamageType.TORPEDO: "torpedo",
            DamageType.DEPTH_CHARGE: "depth_charge",
            DamageType.MELEE: "melee",
            DamageType.PROJECTILE: "projectile",
            DamageType.SHELL: "shell",
        }.get(damage_type, "piercing")  # Default to piercing if unknown type
        
        # Get resistances (check for status effect modifications like firemod)
        armor_resist = ArmorHandler.get_armor_resistance(target_unit, damage_type, dtype_name)
        hp_resist = ArmorHandler.get_hp_resistance(target_unit, damage_type, dtype_name)
        
        # Split damage: armor piercing goes to HP, rest goes to armor
        ap_damage = math.floor(modified_damage * ap_percent)  # Damage that bypasses armor
        armor_damage = modified_damage - ap_damage  # Damage that hits armor first
        
        # Apply HP resistance to armor-piercing damage
        hp_damage_from_ap = ap_damage * hp_resist
        
        # Apply armor resistance to armor damage
        armor_damage_after_resist = math.floor(armor_damage * armor_resist)
        
        # Armor can only absorb up to its current capacity
        armor_capacity = target_unit.current_armor
        actual_armor_damage = min(armor_damage_after_resist, armor_capacity)
        
        # Remaining damage after armor is depleted goes to HP
        remaining_damage = max(0, armor_damage_after_resist - armor_capacity)
        hp_damage_from_armor_breakthrough = remaining_damage * hp_resist
        
        # Total HP damage (this is the "base damage" for status effects)
        total_hp_damage = math.floor(hp_damage_from_ap + hp_damage_from_armor_breakthrough)
        
        # Apply minimum damage (1) to HP
        total_hp_damage = max(1, total_hp_damage)
        
        return total_hp_damage, actual_armor_damage

    @staticmethod
    def apply_damage_to_unit(
        target_unit: 'BattleUnit',
        total_hp_damage: int,
        actual_armor_damage: int
    ) -> None:
        """
        Apply damage to a unit.
        """
        target_unit.current_armor = max(0, target_unit.current_armor - actual_armor_damage)
        target_unit.current_hp = max(0, target_unit.current_hp - total_hp_damage)