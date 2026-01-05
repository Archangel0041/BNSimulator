"""
Status Effect Handler.

Handles all status effect-related calculations, application, and decay.
"""

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import BattleUnit, ActiveStatusEffect, BattleState, Action
    from .battle_types import HitResult
    from ..models import Position, StatusEffect


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
    def apply_dot_to_all_units_for_side(battle: 'BattleState', side: 'BattleSide') -> None:
        """
        Apply DOT damage to all units for a side.
        """
        from ..enums import BattleSide
        units = battle.player_units if side == BattleSide.PLAYER_TEAM else battle.enemy_units
        for unit in units.values():
            StatusEffectHandler.apply_dot_to_unit(unit)

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
    def try_apply_status_effects_for_hit(
        battle: 'BattleState',
        action: 'Action',
        target_position: 'Position',
        hit_result: 'HitResult',
        base_damage: int,
        side: 'BattleSide'
    ) -> None:
        """
        Try to apply status effects for a single hit.

        Rules:
        1. Base chance comes from ability data (status_effects dict: effect_id -> apply_chance)
        2. Base damage for status effect = final_hp_damage + final_armor_damage
        3. Modifier (from hit_result.modifier) modifies the chance: final_chance = base_chance * (modifier / 100.0)
        4. Each hit has its own chance to apply status effects
        5. If status effect already exists, handle replacement

        Args:
            battle: The battle state
            action: The action being executed
            target_position: Position of the target unit
            hit_result: The HitResult containing modifier information
            base_damage: Base damage for status effect calculation (final_hp_damage + final_armor_damage)
        """
        from ..enums import BattleSide
        
        attacker = battle.get_unit_at_position(action.unit_position, side)
        if attacker is None:
            return

        target_side = BattleSide.ENEMY_TEAM if side == BattleSide.PLAYER_TEAM else BattleSide.PLAYER_TEAM

        target_unit = battle.get_unit_at_position(target_position, target_side)

        if target_unit is None:
            return
        
        weapon = attacker.template.weapons.get(action.weapon_id)
        if weapon is None or not weapon.abilities:
            return
        
        ability_id = weapon.abilities[0]
        ability = battle.data_loader.get_ability(ability_id)
        if ability is None:
            return
        
        stats = ability.stats
        
        # Get status effects from ability stats
        # status_effects is a dict: effect_id -> base_apply_chance (percentage)
        for effect_id, base_chance in stats.status_effects.items():
            # Calculate modified chance: base_chance * (modifier / 100.0)
            # e.g., if base_chance is 100% and modifier is 50%, final_chance is 50%
            modified_chance = base_chance * (hit_result.modifier / 100.0)
            
            # Roll for application
            roll = random.random() * 100.0
            if roll >= modified_chance:
                continue  # Status effect did not apply
            
            # Try to apply the status effect
            StatusEffectHandler._apply_status_effect_to_unit(
                battle, target_unit, effect_id, base_damage
            )
    
    @staticmethod
    def _apply_status_effect_to_unit(
        battle: 'BattleState',
        target_unit: 'BattleUnit',
        effect_id: int,
        base_damage: int
    ) -> None:
        """
        Apply a status effect to a unit.

        Args:
            battle: The battle state
            target_unit: The target unit
            effect_id: The status effect ID to apply
            base_damage: Base damage for DOT calculation (final_hp_damage + final_armor_damage)
        """
        from ..battle import ActiveStatusEffect
        
        # Check if unit is immune to this status effect
        if effect_id in target_unit.template.stats.status_effect_immunities:
            return
        
        # Get the status effect definition
        status_effect = battle.data_loader.status_effects.get(effect_id)
        if status_effect is None:
            return
        
        # Check if status effect of the same type AND duration already exists
        # If same type AND duration: replace
        # If same type but different duration: stack (both exist)
        existing_same_type_duration = None
        for active_effect in target_unit.status_effects:
            if (active_effect.effect.id == effect_id and 
                active_effect.effect.duration == status_effect.duration):
                existing_same_type_duration = active_effect
                break
        
        if existing_same_type_duration is not None:
            # Same type AND duration: replace the existing effect
            StatusEffectHandler._handle_existing_status_effect(
                existing_same_type_duration, status_effect, base_damage
            )
        else:
            # Different type OR different duration: stack (add new effect)
            # Calculate base DOT damage: base_damage * mult + bonus
            base_dot_damage = base_damage * status_effect.dot_ability_damage_mult + status_effect.dot_bonus_damage
            
            target_unit.status_effects.append(ActiveStatusEffect(
                effect=status_effect,
                remaining_turns=status_effect.duration,  # All turns remaining (0 turns used)
                base_dot_damage=base_dot_damage
            ))
    
    @staticmethod
    def _handle_existing_status_effect(
        existing_effect: 'ActiveStatusEffect',
        new_effect: 'StatusEffect',
        base_damage: int
    ) -> None:
        """
        Handle replacement of an existing status effect (same type AND duration).

        For DOTs with same duration: Create a new DOT with 0 turns used (all turns remaining),
        and use the new base damage calculated.

        Args:
            existing_effect: The existing active status effect
            new_effect: The new status effect being applied
            base_damage: Base damage for DOT calculation
        """
        # For same type and duration, replace by resetting to full duration
        # Calculate new base DOT damage
        new_base_dot_damage = base_damage * new_effect.dot_ability_damage_mult + new_effect.dot_bonus_damage
        
        # Replace: reset to full duration (0 turns used, all turns remaining)
        existing_effect.remaining_turns = new_effect.duration
        existing_effect.base_dot_damage = new_base_dot_damage

