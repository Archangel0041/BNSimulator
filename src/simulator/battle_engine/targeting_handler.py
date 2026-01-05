"""
Targeting Handler.

Handles all targeting pattern calculation, damage rolls, and hit/crit checks.
Groups base positions with their splash damage for shared hit/crit rolls.
"""

from typing import TYPE_CHECKING, Optional
import random

if TYPE_CHECKING:
    from ..battle import BattleState, BattleUnit, Action
    from ..enums import BattleSide, TargetType
    from .battle_types import HitResult
    from ..models import Position, DamageArea, TargetArea, AbilityStats
    from ..data_loader import Ability


class TargetingHandler:
    """Handles targeting pattern calculation and hit result generation."""

    @staticmethod
    def calculate_hits_by_position(
        battle: 'BattleState',
        action: 'Action',
        damage_min: int,
        damage_max: int,
        side: 'BattleSide'
    ) -> dict['Position', list['HitResult']]:
        """
        Calculate all hits for an action, grouped by position.

        This method:
        1. Calculates targeting patterns (base positions + splash)
        2. Groups base positions with their splash positions
        3. For each group, rolls damage and hit/crit once
        4. Applies modifiers to each position in the group
        5. Returns dictionary of Position -> List[HitResult]

        Args:
            battle: The battle state
            action: The action being executed
            damage_min: Minimum base damage
            damage_max: Maximum base damage
            side: The side performing the action (BattleSide.PLAYER_TEAM or BattleSide.ENEMY_TEAM)

        Returns:
            Dictionary mapping positions to lists of HitResult objects
        """
        from ..enums import BattleSide, TargetType
        from ..models import DamageArea, TargetArea
        from .battle_types import HitResult
        
        # Get the attacking unit and ability
        units = battle.player_units if side == BattleSide.PLAYER_TEAM else battle.enemy_units
        attacker = units.get(action.unit_position)
        if attacker is None:
            return {}
        
        weapon = attacker.template.weapons.get(action.weapon_id)
        if weapon is None or not weapon.abilities:
            return {}
        
        # Use first ability (could be extended to support multiple abilities per weapon)
        ability_id = weapon.abilities[0]
        ability = battle.data_loader.get_ability(ability_id)
        if ability is None:
            return {}
        
        stats = ability.stats
        target_type = stats.target_area.target_type if stats.target_area else None
        
        # Determine target type (default to NONE if not specified)
        if target_type is None:
            # Check if target_area exists - log warning if it does
            if stats.target_area is not None:
                import warnings
                warnings.warn(
                    f"Ability {ability_id} has target_area but no target_type specified. "
                    "Defaulting to TargetType.NONE."
                )
            target_type = TargetType.NONE
        
        # Get number of hits
        num_hits = stats.attacks_per_use * stats.shots_per_attack
        num_hits = max(1, num_hits)
        
        # Check if this is a random attack
        is_random = stats.target_area is not None and stats.target_area.random if stats.target_area else False
        
        # Dictionary to collect all hits: Position -> List[HitResult]
        hits_by_position: dict['Position', list['HitResult']] = {}
        
        # Process each hit
        for hit_num in range(num_hits):
            # Get hit groups for this hit (base position + its splash positions)
            hit_groups = TargetingHandler._get_hit_groups_for_hit(
                battle, action, attacker, stats, target_type, is_random, side
            )
            
            # For each hit group, roll damage and hit/crit once, then apply to all positions in group
            for base_pos, base_modifier, splash_entries in hit_groups:
                # Roll damage once for this group
                base_damage_roll = random.randint(damage_min, damage_max)
                
                # Check hit/miss/crit once for the base position
                hit_result = TargetingHandler._check_hit(
                    battle, action, attacker, ability, stats, base_pos, base_damage_roll, base_modifier, side
                )
                
                if not hit_result.hit:
                    continue  # If base missed, no splash damage either
                
                # Add base position hit with its modifier
                # Final damage will be calculated later when applying modifiers and armor
                if base_pos not in hits_by_position:
                    hits_by_position[base_pos] = []
                hits_by_position[base_pos].append(HitResult(
                    damage_roll=base_damage_roll,
                    modifier=base_modifier,
                    hit=hit_result.hit,
                    is_critical=hit_result.is_critical,
                    damage=0  # Will be calculated later when applying modifiers and armor
                ))
                
                # Add splash positions with their modifiers (using same hit/crit result)
                for splash_entry, splash_pos in splash_entries:
                    # Calculate combined modifier: multiply percentages together
                    # (base_modifier% * splash_modifier%) / 100.0 = combined_modifier%
                    combined_modifier = (base_modifier * splash_entry.damage_percent) / 100.0
                    
                    if splash_pos not in hits_by_position:
                        hits_by_position[splash_pos] = []
                    hits_by_position[splash_pos].append(HitResult(
                        damage_roll=base_damage_roll,  # Same roll
                        modifier=combined_modifier,  # Combined modifier (base * splash)
                        hit=hit_result.hit,  # Same hit status
                        is_critical=hit_result.is_critical,  # Same crit status
                        damage=0  # Will be calculated later when applying modifiers and armor
                    ))
        
        return hits_by_position

    @staticmethod
    def _get_hit_groups_for_hit(
        battle: 'BattleState',
        action: 'Action',
        attacker: 'BattleUnit',
        stats: 'AbilityStats',
        target_type: 'TargetType',
        is_random: bool,
        side: 'BattleSide'
    ) -> list[tuple['Position', float, list[tuple['DamageArea', 'Position']]]]:
        """
        Get hit groups (base position + splash entries) for a single hit.

        Returns:
            List of (base_position, base_modifier, splash_entries) tuples
            Each tuple represents one hit group that shares damage/hit/crit rolls.
            base_modifier is the damage_percent modifier for the base position (from target_area and damage_area).
        """
        from ..enums import TargetType
        from ..models import DamageArea
        
        hit_groups: list[tuple['Position', float, list[tuple['DamageArea', 'Position']]]] = []
        
        if target_type == TargetType.NONE:
            # TargetType.NONE: Attack centered on clicked spot
            center_pos = action.target_position
            
            # Calculate base modifier: check for damage_area entry at (0,0)
            base_modifier = TargetingHandler._get_base_position_modifier(
                stats.damage_area, None
            )
            
            # Get splash entries for this center position (excluding (0,0) entry)
            splash_entries = TargetingHandler._get_splash_entries(
                stats.damage_area, center_pos, exclude_center=True
            )
            
            hit_groups.append((center_pos, base_modifier, splash_entries))
        
        elif target_type == TargetType.TARGET:
            # TargetType.TARGET: Reticle-based with target_area
            center_pos = action.target_position
            
            if stats.target_area is None:
                # No target_area - just use center position
                # Calculate base modifier: check for damage_area entry at (0,0)
                base_modifier = TargetingHandler._get_base_position_modifier(
                    stats.damage_area, None
                )
                splash_entries = TargetingHandler._get_splash_entries(
                    stats.damage_area, center_pos, exclude_center=True
                )
                hit_groups.append((center_pos, base_modifier, splash_entries))
            else:
                target_area = stats.target_area
                
                if is_random:
                    # Random weighted selection - select one base position
                    base_pos, target_entry = TargetingHandler._select_random_base_position_with_entry(
                        center_pos, target_area
                    )
                    if base_pos is not None:
                        # Calculate base modifier: target_area entry * damage_area entry at (0,0)
                        base_modifier = TargetingHandler._get_base_position_modifier(
                            stats.damage_area, target_entry
                        )
                        splash_entries = TargetingHandler._get_splash_entries(
                            stats.damage_area, base_pos, exclude_center=True
                        )
                        hit_groups.append((base_pos, base_modifier, splash_entries))
                else:
                    # All positions in target_area are hit
                    for entry in target_area.data:
                        from ..models import Position
                        base_pos = Position(
                            x=center_pos.x + entry.pos.x,
                            y=center_pos.y + entry.pos.y
                        )
                        # Calculate base modifier: target_area entry * damage_area entry at (0,0)
                        base_modifier = TargetingHandler._get_base_position_modifier(
                            stats.damage_area, entry
                        )
                        splash_entries = TargetingHandler._get_splash_entries(
                            stats.damage_area, base_pos, exclude_center=True
                        )
                        hit_groups.append((base_pos, base_modifier, splash_entries))
        
        elif target_type == TargetType.WEAPON:
            # TargetType.WEAPON: Fixed pattern relative to unit
            # Center is 1 grid ahead of unit
            from ..models import Position
            center_pos = Position(
                x=attacker.position.x,
                y=attacker.position.y - 1
            )
            
            if stats.target_area is None:
                # No target_area - just use center position
                # Calculate base modifier: check for damage_area entry at (0,0)
                base_modifier = TargetingHandler._get_base_position_modifier(
                    stats.damage_area, None
                )
                # WEAPON type typically doesn't have splash, but check anyway
                splash_entries = TargetingHandler._get_splash_entries(
                    stats.damage_area, center_pos, exclude_center=True
                )
                hit_groups.append((center_pos, base_modifier, splash_entries))
            else:
                # All positions in target_area relative to center
                for entry in stats.target_area.data:
                    pattern_pos = Position(
                        x=center_pos.x + entry.pos.x,
                        y=center_pos.y + entry.pos.y
                    )
                    # Calculate base modifier: target_area entry * damage_area entry at (0,0)
                    base_modifier = TargetingHandler._get_base_position_modifier(
                        stats.damage_area, entry
                    )
                    # WEAPON type typically doesn't have splash, but check anyway
                    splash_entries = TargetingHandler._get_splash_entries(
                        stats.damage_area, pattern_pos, exclude_center=True
                    )
                    hit_groups.append((pattern_pos, base_modifier, splash_entries))
        
        return hit_groups

    @staticmethod
    def _get_base_position_modifier(
        damage_area: list['DamageArea'],
        target_area_entry: Optional['DamageArea']
    ) -> float:
        """
        Calculate the base position modifier from target_area and damage_area entries.

        The modifier is calculated by multiplying percentages together:
        - target_area_entry.damage_percent (if exists, default 100%)
        - * damage_area entry at (0,0).damage_percent (if exists, default 100%)
        - Result: (modifier1 * modifier2) / 100.0 (e.g., 25% * 25% = 6.25%)

        Args:
            damage_area: List of DamageArea entries from ability stats
            target_area_entry: The target_area entry for this base position (if any)

        Returns:
            Combined modifier as a percentage (e.g., 100.0 for 100%, 6.25 for 6.25%)
        """
        # Start with target_area modifier (if exists)
        modifier = 100.0
        if target_area_entry is not None:
            modifier = target_area_entry.damage_percent
        
        # Check for damage_area entry at (0,0) - this applies to the base position
        for entry in damage_area:
            if entry.pos.x == 0 and entry.pos.y == 0:
                # Multiply modifiers together as percentages: (mod1 * mod2) / 100.0
                modifier = (modifier * entry.damage_percent) / 100.0
                break
        
        return modifier

    @staticmethod
    def _get_splash_entries(
        damage_area: list['DamageArea'],
        base_position: 'Position',
        exclude_center: bool = False
    ) -> list[tuple['DamageArea', 'Position']]:
        """
        Get all splash damage entries with their positions around a base position.

        Args:
            damage_area: List of DamageArea entries from ability stats
            base_position: The base position to calculate splash around
            exclude_center: If True, exclude the (0,0) entry (used for base position modifier)

        Returns:
            List of (DamageArea entry, Position) tuples for splash damage
        """
        from ..models import Position
        splash_entries = []
        
        for splash_entry in damage_area:
            # Skip (0,0) entry if exclude_center is True (it's used for base modifier)
            if exclude_center and splash_entry.pos.x == 0 and splash_entry.pos.y == 0:
                continue
            
            splash_pos = Position(
                x=base_position.x + splash_entry.pos.x,
                y=base_position.y + splash_entry.pos.y
            )
            splash_entries.append((splash_entry, splash_pos))
        
        return splash_entries

    @staticmethod
    def _select_random_base_position_with_entry(
        center_pos: 'Position',
        target_area: 'TargetArea'
    ) -> tuple[Optional['Position'], Optional['DamageArea']]:
        """
        Select a random base position using weighted selection.

        Args:
            center_pos: Center position (reticle/target position)
            target_area: Target area configuration with random weights

        Returns:
            Tuple of (selected base position, target_area entry), or (None, None) if no valid position
        """
        if not target_area.data:
            return (None, None)
        
        # Get weights for each position (default to 100 if not specified)
        entries_with_weights = []
        for entry in target_area.data:
            weight = getattr(entry, 'weight', 100)
            entries_with_weights.append((entry, weight))
        
        # Calculate total weight
        total_weight = sum(weight for _, weight in entries_with_weights)
        if total_weight == 0:
            return (None, None)
        
        # Roll for weighted random selection
        roll = random.random() * total_weight
        cumulative = 0.0
        
        from ..models import Position
        for entry, weight in entries_with_weights:
            cumulative += weight
            if roll <= cumulative:
                # This entry was selected
                return (
                    Position(
                        x=center_pos.x + entry.pos.x,
                        y=center_pos.y + entry.pos.y
                    ),
                    entry
                )
        
        # Fallback (shouldn't happen, but just in case)
        if entries_with_weights:
            entry, _ = entries_with_weights[0]
            return (
                Position(
                    x=center_pos.x + entry.pos.x,
                    y=center_pos.y + entry.pos.y
                ),
                entry
            )
        
        return (None, None)

    @staticmethod
    def _check_hit(
        battle: 'BattleState',
        action: 'Action',
        attacker: 'BattleUnit',
        ability: 'Ability',
        stats: 'AbilityStats',
        target_position: 'Position',
        base_damage_roll: int,
        modifier: float,
        side: 'BattleSide'
    ) -> 'HitResult':
        """
        Check for hit/miss/crit for a target position.

        Args:
            battle: The battle state
            action: The action being executed
            attacker: The attacking unit
            ability: The ability being used
            stats: The ability stats
            target_position: Position of the target unit to check
            base_damage_roll: Base damage roll for this hit
            modifier: The damage modifier for this position (as percentage, e.g., 100.0 for 100%)
            side: The side performing the action

        Returns:
            HitResult with hit/miss, critical hit status, and damage
        """
        from ..enums import BattleSide
        from .player_target_validator import PlayerTargetValidator
        from .battle_types import HitResult
        
        # Get the target unit - if attacker is on player team, target is on enemy side (ENEMY_TEAM)
        # If attacker is on enemy team, target is on player side (PLAYER_TEAM)
        target_side = BattleSide.ENEMY_TEAM if side == BattleSide.PLAYER_TEAM else BattleSide.PLAYER_TEAM
        target_unit = battle.get_unit_at_position(target_position, target_side)
        if target_unit is None:
            return HitResult(
                damage_roll=base_damage_roll,
                modifier=modifier,
                hit=False,
                is_critical=False,
                damage=0  # Missed, no damage
            )
        
        # Check if target is valid based on tag hierarchy
        if not PlayerTargetValidator._can_target_by_tags(
            stats.targets, target_unit.template.tags, battle
        ):
            return HitResult(
                damage_roll=base_damage_roll,
                modifier=modifier,
                hit=False,
                is_critical=False,
                damage=0  # Invalid target, no damage
            )
        
        # Calculate Offense = ability.attack + unit.accuracy
        offense = stats.attack + attacker.template.stats.accuracy
        
        # Calculate dodge chance = Defense + 5 - Offense (as percentage, clamped 0-100)
        defense = target_unit.template.stats.defense
        dodge_chance = defense + 5 - offense
        dodge_chance = max(0.0, min(100.0, dodge_chance))
        
        # Calculate hit chance (inverse of dodge)
        hit_chance = 100.0 - dodge_chance
        
        # Roll for hit (inside this method)
        hit_roll = random.random() * 100.0
        hit = hit_roll < hit_chance
        
        if not hit:
            # Missed - return early
            return HitResult(
                damage_roll=base_damage_roll,
                modifier=modifier,
                hit=False,
                is_critical=False,
                damage=0  # Missed, no damage
            )
        
        # Calculate crit chance (only if hit)
        # 1) critical_hit_percent from ability
        crit_chance = stats.critical_hit_percent
        
        # 2) Critical chance from unit stats
        crit_chance += attacker.template.stats.critical
        
        # 3) Critical bonuses from ability based on target tags (including hierarchy)
        tag_hierarchy = battle.data_loader.config.tag_hierarchy
        for bonus_tag, bonus_value in stats.critical_bonuses.items():
            # Expand the bonus tag to include all descendants
            valid_tags = {bonus_tag}
            PlayerTargetValidator._expand_tag_recursive(
                bonus_tag, valid_tags, tag_hierarchy
            )
            # Check if target has any of these tags
            if any(tag in valid_tags for tag in target_unit.template.tags):
                crit_chance += bonus_value
        
        # Clamp crit chance to 0-100
        crit_chance = max(0.0, min(100.0, crit_chance))
        
        # Roll for critical hit (only if hit)
        crit_roll = random.random() * 100.0
        is_critical = crit_roll < crit_chance

        # Note: damage field will be calculated later when applying modifiers and armor
        # We just track if it's a crit here
        return HitResult(
            damage_roll=base_damage_roll,
            modifier=modifier,  # Use the provided modifier for this position
            hit=True,
            is_critical=is_critical,
            damage=0  # Will be calculated later when applying modifiers and armor
        )

