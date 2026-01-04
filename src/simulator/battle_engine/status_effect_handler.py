"""
Status Effect Handler.

Handles all status effect-related calculations, application, and decay.
"""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleUnit, ActiveStatusEffect


class StatusEffectHandler:
    """Handles status effect damage calculation, application, and decay."""

    @staticmethod
    def calculate_dot_damage(status: 'ActiveStatusEffect') -> float:
        """
        Calculate DOT damage for a single status effect.

        If effect.dot_diminishing is True:
            Formula: actual_damage = base_damage * (r_t / d)
            Where:
            - base_damage = pre-calculated (stored in status.base_dot_damage)
            - d = effect.duration (from config)
            - r_t = remaining_turns
            This makes DOT weaker as time progresses (diminishes).

        If effect.dot_diminishing is False:
            Formula: actual_damage = base_damage (constant each turn)

        Args:
            status: The active status effect

        Returns:
            Actual DOT damage for this turn (before armor/modifiers)
        """
        # Use pre-calculated base DOT damage
        base_damage = status.base_dot_damage

        # Check if this DOT diminishes (gets weaker) or stays constant
        if status.effect.dot_diminishing:
            # Apply diminishing formula - damage gets weaker over time
            duration = status.effect.duration
            if duration > 0:
                decay_factor = status.remaining_turns / duration
                return base_damage * decay_factor
            else:
                # Invalid duration, use constant damage
                return base_damage
        else:
            # Constant DOT damage each turn
            return base_damage

    @staticmethod
    def apply_dot_to_unit(unit: 'BattleUnit') -> None:
        """
        Apply DOT damage to a unit from all active DOT effects.

        Each effect is applied separately since they can have different damage types.

        Args:
            unit: The unit to apply DOT damage to
        """
        from ..enums import StatusEffectType

        for status in unit.status_effects:
            if status.effect.effect_type == StatusEffectType.DOT:
                # Calculate DOT damage for this effect
                dot_damage = StatusEffectHandler.calculate_dot_damage(status)

                if dot_damage > 0:
                    # Apply damage with the effect's specific damage type
                    # take_damage handles armor/modifiers automatically
                    unit.take_damage(
                        math.floor(dot_damage),
                        status.effect.dot_damage_type,
                        armor_piercing=status.effect.dot_ap_percent
                    )

    @staticmethod
    def decay_dot_effects(unit: 'BattleUnit') -> None:
        """
        Decrement duration of DOT status effects and remove expired ones.

        Only DOT effects are decayed here. Stun/Freeze effects should be
        decayed at the end of the turn.

        Args:
            unit: The unit whose DOT status effects to decay
        """
        from ..enums import StatusEffectType
        
        remaining_effects = []
        for status in unit.status_effects:
            if status.effect.effect_type == StatusEffectType.DOT:
                # Decrement duration for DOT effects
                status.remaining_turns -= 1
                # Keep effect if still active
                if status.remaining_turns > 0:
                    remaining_effects.append(status)
            else:
                # Keep non-DOT effects as-is (they decay at end of turn)
                remaining_effects.append(status)

        # Update unit's status effects list
        unit.status_effects = remaining_effects
    
    @staticmethod
    def decay_stun_effects(unit: 'BattleUnit') -> None:
        """
        Decrement duration of stun/freeze status effects and remove expired ones.

        Only stun/freeze effects are decayed here. DOT effects should be
        decayed when DOT ticks apply.

        Args:
            unit: The unit whose stun/freeze status effects to decay
        """
        from ..enums import StatusEffectType
        
        remaining_effects = []
        for status in unit.status_effects:
            if status.effect.effect_type == StatusEffectType.STUN:
                # Decrement duration for stun/freeze effects
                status.remaining_turns -= 1
                # Keep effect if still active
                if status.remaining_turns > 0:
                    remaining_effects.append(status)
            else:
                # Keep non-stun effects as-is (DOT effects decay when DOT ticks)
                remaining_effects.append(status)

        # Update unit's status effects list
        unit.status_effects = remaining_effects
    
    @staticmethod
    def decay_status_effects(unit: 'BattleUnit') -> None:
        """
        Decrement duration of all status effects and remove expired ones.

        DEPRECATED: Use decay_dot_effects() for DOT effects and 
        decay_stun_effects() for stun/freeze effects instead.

        Args:
            unit: The unit whose status effects to decay
        """
        remaining_effects = []
        for status in unit.status_effects:
            # Decrement duration
            status.remaining_turns -= 1

            # Keep effect if still active
            if status.remaining_turns > 0:
                remaining_effects.append(status)

        # Update unit's status effects list
        unit.status_effects = remaining_effects

