"""
DOT (Damage Over Time) Handler.

Handles all DOT-related calculations and application.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleUnit, ActiveStatusEffect


class DOTHandler:
    """Handles DOT damage calculation and application."""

    @staticmethod
    def calculate_dot_damage(status: 'ActiveStatusEffect') -> float:
        """
        Calculate DOT damage for a single status effect.

        If effect.dot_diminishing is True:
            Formula: actual_damage = base_damage * (d - r_t + 1) / d
            Where:
            - base_damage = source_damage * dot_ability_damage_mult + dot_bonus_damage
            - d = effect.duration (from config)
            - r_t = remaining_turns
            This makes DOT stronger as it progresses (builds up over time).

        If effect.dot_diminishing is False:
            Formula: actual_damage = base_damage (constant each turn)

        Args:
            status: The active status effect

        Returns:
            Actual DOT damage for this turn (before armor/modifiers)
        """
        # Calculate base DOT damage from source damage
        base_damage = status.source_damage * status.effect.dot_ability_damage_mult
        base_damage += status.effect.dot_bonus_damage

        # Check if this DOT diminishes (decays) or stays constant
        if status.effect.dot_diminishing:
            # Apply decay formula - damage builds up over time
            duration = status.effect.duration
            if duration > 0:
                decay_factor = (duration - status.remaining_turns + 1) / duration
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
                dot_damage = DOTHandler.calculate_dot_damage(status)

                if dot_damage > 0:
                    # Apply damage with the effect's specific damage type
                    # take_damage handles armor/modifiers automatically
                    unit.take_damage(
                        int(dot_damage),
                        status.effect.dot_damage_type,
                        armor_piercing=status.effect.dot_ap_percent
                    )

    @staticmethod
    def decay_status_effects(unit: 'BattleUnit') -> None:
        """
        Decrement duration of all status effects and remove expired ones.

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
