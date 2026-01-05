"""
Armor Handler.

Handles armor and resistance calculations, including status effect modifications.
"""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleUnit, BattleState, Action
    from ..enums import DamageType
    from .battle_types import HitResult


class ArmorHandler:
    """Handles armor and resistance calculations."""

    @staticmethod
    def get_armor_resistance(unit: 'BattleUnit', damage_type: 'DamageType', dtype_name: str) -> float:
        """
        Get armor resistance for a damage type, accounting for status effect modifications.
        
        Rules:
        - If no effect: keep original value
        - If 1 effect: use that effect's modifier if applicable
        - If more than 1: pick the highest
        
        Args:
            unit: The target unit
            damage_type: The damage type enum
            dtype_name: The damage type name string
            
        Returns:
            Resistance multiplier (e.g., 0.25 = 25% resistance, 2.0 = 200% resistance)
        """
        # Start with base armor resistance
        base_resist = unit.template.stats.armor_damage_mods.get(dtype_name, 1.0)
        
        # Check for status effect modifications (e.g., firemod, freeze)
        # Get all resistance-modifying effects and take the maximum
        max_resist_mod = None
        for active_effect in unit.status_effects:
            # Check if this effect modifies armor resistances for this damage type
            # stun_armor_damage_mods is a dict: damage_type_id -> modifier
            if active_effect.effect.stun_armor_damage_mods:
                damage_type_id = damage_type.value
                if damage_type_id in active_effect.effect.stun_armor_damage_mods:
                    mod_value = active_effect.effect.stun_armor_damage_mods[damage_type_id]
                    if max_resist_mod is None or mod_value > max_resist_mod:
                        max_resist_mod = mod_value
        
        # If we found any resistance modifiers, use the maximum
        if max_resist_mod is not None:
            return max_resist_mod
        
        # Otherwise, return base resistance
        return base_resist
    
    @staticmethod
    def get_hp_resistance(unit: 'BattleUnit', damage_type: 'DamageType', dtype_name: str) -> float:
        """
        Get HP resistance for a damage type, accounting for status effect modifications.
        
        Rules:
        - If no effect: keep original value
        - If 1 effect: use that effect's modifier if applicable
        - If more than 1: pick the highest
        
        Args:
            unit: The target unit
            damage_type: The damage type enum
            dtype_name: The damage type name string
            
        Returns:
            Resistance multiplier (e.g., 0.25 = 25% resistance, 2.0 = 200% resistance)
        """
        # Start with base HP resistance
        base_resist = unit.template.stats.damage_mods.get(dtype_name, 1.0)
        
        # Check for status effect modifications (e.g., firemod, freeze)
        # Get all resistance-modifying effects and take the maximum
        max_resist_mod = None
        for active_effect in unit.status_effects:
            # Check if this effect modifies HP resistances for this damage type
            # stun_damage_mods is a dict: damage_type_id -> modifier
            if active_effect.effect.stun_damage_mods:
                damage_type_id = damage_type.value
                if damage_type_id in active_effect.effect.stun_damage_mods:
                    mod_value = active_effect.effect.stun_damage_mods[damage_type_id]
                    if max_resist_mod is None or mod_value > max_resist_mod:
                        max_resist_mod = mod_value
        
        # If we found any resistance modifiers, use the maximum
        if max_resist_mod is not None:
            return max_resist_mod
        
        # Otherwise, return base resistance
        return base_resist

