"""Combat mechanics for battle simulator - targeting, damage, and status effects."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import random

from .enums import (
    DamageType, UnitClass, BattleSide, TargetType, LineOfFire,
    StatusEffectType, DAMAGE_TYPE_NAMES
)
from .models import Position, Ability, Weapon, StatusEffect

if TYPE_CHECKING:
    from .battle import BattleUnit, BattleState


@dataclass
class DamageResult:
    """Result of a single damage application."""
    target_idx: int
    damage_dealt: int
    was_critical: bool = False
    was_dodged: bool = False
    killed: bool = False
    status_applied: list[int] = field(default_factory=list)


class TagResolver:
    """Resolves tag hierarchy for targeting."""

    def __init__(self, tag_hierarchy: dict[int, list[int]]):
        """
        Initialize with tag hierarchy from battle_config.json.

        Args:
            tag_hierarchy: Dict mapping parent tag -> list of child tags
        """
        self.hierarchy = tag_hierarchy
        self._expanded_cache: dict[int, set[int]] = {}

    def expand_tag(self, tag: int) -> set[int]:
        """
        Expand a tag to include all its descendants in the hierarchy.

        If ability targets tag 24, it can hit units with tag 24 or any child tag.
        """
        if tag in self._expanded_cache:
            return self._expanded_cache[tag]

        result = {tag}
        children = self.hierarchy.get(str(tag), [])
        for child in children:
            result.update(self.expand_tag(child))

        self._expanded_cache[tag] = result
        return result

    def can_target(self, ability_targets: list[int], unit_tags: list[int]) -> bool:
        """
        Check if an ability with given target tags can hit a unit with given tags.

        Args:
            ability_targets: Tags the ability can target
            unit_tags: Tags the unit has
        """
        if not ability_targets:
            return True  # No restrictions = can target anything

        # Expand all ability target tags
        valid_tags = set()
        for tag in ability_targets:
            valid_tags.update(self.expand_tag(tag))

        # Check if unit has any valid tag
        return bool(valid_tags.intersection(unit_tags))


class TargetingSystem:
    """Handles target selection and validation."""

    def __init__(self, tag_resolver: TagResolver):
        self.tag_resolver = tag_resolver

    def get_valid_targets(
        self,
        attacker: "BattleUnit",
        weapon: Weapon,
        ability: Ability,
        battle: "BattleState"
    ) -> list[Position]:
        """Get all valid target positions for an ability."""
        stats = ability.stats
        targets = []

        # Get opposing units
        if attacker.battle_side == BattleSide.PLAYER_TEAM:
            target_units = battle.enemy_units
        else:
            target_units = battle.player_units

        for target_unit in target_units:
            if not target_unit.is_alive:
                continue

            # Check tag-based targeting
            if not self.tag_resolver.can_target(stats.targets, target_unit.template.tags):
                continue

            # Check range
            distance = self._calculate_distance(attacker.position, target_unit.position)
            if distance < stats.min_range or distance > stats.max_range:
                continue

            # Check line of fire
            if stats.line_of_fire == LineOfFire.DIRECT:
                if not self._has_line_of_sight(attacker, target_unit, battle):
                    continue

            targets.append(target_unit.position)

        return targets

    def _calculate_distance(self, attacker_pos: Position, target_pos: Position) -> int:
        """
        Calculate cross-grid distance.

        Player and enemy grids face each other:
        - Row 0 (front) is closest to enemy
        - Row 2 (back) is furthest
        - Distance = attacker_row + target_row + 1
        """
        base_distance = attacker_pos.y + target_pos.y + 1
        col_diff = abs(attacker_pos.x - target_pos.x)
        return base_distance + col_diff // 2

    def _has_line_of_sight(
        self,
        attacker: "BattleUnit",
        target: "BattleUnit",
        battle: "BattleState"
    ) -> bool:
        """
        Check if there's a clear line of sight.

        Front row units block attacks to back row units in same column.
        """
        if attacker.position.x != target.position.x:
            return True  # Different columns, no blocking

        # Check for blocking units in front of target
        target_units = battle.enemy_units if attacker.battle_side == BattleSide.PLAYER_TEAM else battle.player_units

        for unit in target_units:
            if unit == target or not unit.is_alive:
                continue
            # Unit blocks if in same column and closer to attacker
            if unit.position.x == target.position.x and unit.position.y < target.position.y:
                return False

        return True

    def resolve_target_area(
        self,
        ability: Ability,
        primary_target: Position,
        battle: "BattleState",
        rng: random.Random
    ) -> list[tuple[Position, float]]:
        """
        Resolve target area pattern to actual positions with damage percentages.

        Returns: List of (position, damage_percent) tuples
        """
        stats = ability.stats
        target_area = stats.target_area

        if target_area is None:
            # No target area = just primary target
            return [(primary_target, 100.0)]

        target_type = target_area.target_type

        if target_type == TargetType.ALL_ENEMIES:
            # Hit all positions in the pattern
            results = []
            for entry in target_area.data:
                pos = Position(
                    primary_target.x + entry.pos.x,
                    primary_target.y + entry.pos.y
                )
                results.append((pos, entry.damage_percent))
            return results

        elif target_type == TargetType.SINGLE:
            if target_area.random and target_area.data:
                # Weighted random selection
                weights = [getattr(entry, 'weight', 100) for entry in target_area.data]
                total_weight = sum(weights)

                if total_weight > 0:
                    roll = rng.random() * total_weight
                    cumulative = 0
                    for entry, weight in zip(target_area.data, weights):
                        cumulative += weight
                        if roll <= cumulative:
                            pos = Position(
                                primary_target.x + entry.pos.x,
                                primary_target.y + entry.pos.y
                            )
                            return [(pos, entry.damage_percent)]

            # Default: just primary target
            return [(primary_target, 100.0)]

        else:
            # ROW, COLUMN, etc - hit all in pattern
            results = []
            for entry in target_area.data:
                pos = Position(
                    primary_target.x + entry.pos.x,
                    primary_target.y + entry.pos.y
                )
                results.append((pos, entry.damage_percent))
            return results

    def resolve_damage_area(
        self,
        ability: Ability,
        primary_target: Position
    ) -> list[tuple[Position, float]]:
        """
        Resolve damage area (splash) pattern.

        Damage area is splash damage around each target hit.
        Returns: List of (position, damage_percent) tuples
        """
        stats = ability.stats

        if not stats.damage_area:
            return [(primary_target, 100.0)]

        results = []
        for entry in stats.damage_area:
            pos = Position(
                primary_target.x + entry.pos.x,
                primary_target.y + entry.pos.y
            )
            results.append((pos, entry.damage_percent))

        return results


class DamageCalculator:
    """Calculates damage for attacks."""

    def __init__(self, class_damage_mods: dict[int, dict[int, float]]):
        """
        Initialize with class damage modifiers from battle_config.json.

        Args:
            class_damage_mods: Dict mapping attacker_class -> {defender_class -> multiplier}
        """
        self.class_damage_mods = class_damage_mods

    def calculate_damage(
        self,
        attacker: "BattleUnit",
        defender: "BattleUnit",
        weapon: Weapon,
        ability: Ability,
        damage_percent: float,
        rng: random.Random
    ) -> tuple[int, bool, bool]:
        """
        Calculate damage for an attack.

        Returns: (damage, is_critical, was_dodged)
        """
        stats = ability.stats
        weapon_stats = weapon.stats

        # Check dodge first
        dodge_chance = defender.template.stats.dodge - attacker.template.stats.accuracy
        dodge_chance = max(0, min(95, dodge_chance))  # Cap at 0-95%

        if rng.random() * 100 < dodge_chance:
            return (0, False, True)

        # Base damage from weapon (random within range)
        if weapon_stats.base_damage_max > weapon_stats.base_damage_min:
            base_damage = rng.randint(weapon_stats.base_damage_min, weapon_stats.base_damage_max)
        else:
            base_damage = weapon_stats.base_damage_min

        # Add ability damage and attack stat contribution
        damage = base_damage + stats.damage

        # Attack stat contribution (attack vs defense)
        attack_bonus = (
            stats.attack * stats.attack_from_weapon +
            weapon_stats.base_atk * stats.attack_from_unit +
            attacker.template.stats.power
        )
        defense = defender.template.stats.defense
        damage += max(0, attack_bonus - defense)

        # Critical hit check
        crit_chance = (
            attacker.template.stats.critical +
            weapon_stats.base_crit_percent +
            stats.critical_hit_percent
        )

        # Add tag-specific crit bonuses
        for tag, bonus in stats.critical_bonuses.items():
            if tag in defender.template.tags:
                crit_chance += bonus

        is_critical = rng.random() * 100 < crit_chance
        if is_critical:
            damage = int(damage * 1.5)

        # Class-based damage modifier
        attacker_class = attacker.template.class_type.value
        defender_class = defender.template.class_type.value
        class_mod = self.class_damage_mods.get(attacker_class, {}).get(defender_class, 1.0)
        damage = int(damage * class_mod)

        # Apply damage percentage (for AOE falloff)
        damage = int(damage * damage_percent / 100)

        # Minimum damage
        damage = max(1, damage)

        return (damage, is_critical, False)

    def apply_damage(
        self,
        target: "BattleUnit",
        damage: int,
        damage_type: DamageType,
        armor_piercing: float = 0.0
    ) -> int:
        """
        Apply damage to a unit.

        Returns actual damage dealt.
        """
        if not target.is_alive:
            return 0

        # Get damage type modifier
        dtype_name = {
            DamageType.PIERCING: "piercing",
            DamageType.CRUSHING: "crushing",
            DamageType.SLASHING: "slashing",
            DamageType.EXPLOSIVE: "explosive",
            DamageType.FIRE: "fire",
            DamageType.COLD: "cold",
            DamageType.ELECTRIC: "electric",
        }.get(damage_type, "piercing")

        # Apply damage modifiers from template
        damage_mod = target.template.stats.damage_mods.get(dtype_name, 1.0)

        # Apply status effect damage modifiers (e.g., firemod)
        for status in target.status_effects:
            if status.effect.effect_type == StatusEffectType.STUN:
                # Check if this status effect modifies this damage type
                dtype_int = damage_type.value
                if dtype_int in status.effect.stun_damage_mods:
                    damage_mod *= status.effect.stun_damage_mods[dtype_int]

        modified_damage = int(damage * damage_mod)

        # Apply to armor first if present
        if target.current_armor > 0 and armor_piercing < 1.0:
            armor_damage = int(modified_damage * (1 - armor_piercing))
            armor_mod = target.template.stats.armor_damage_mods.get(dtype_name, 1.0)

            # Apply status effect armor damage modifiers
            for status in target.status_effects:
                if status.effect.effect_type == StatusEffectType.STUN:
                    dtype_int = damage_type.value
                    if dtype_int in status.effect.stun_armor_damage_mods:
                        armor_mod *= status.effect.stun_armor_damage_mods[dtype_int]

            armor_damage = int(armor_damage * armor_mod)

            if armor_damage >= target.current_armor:
                overflow = armor_damage - target.current_armor
                target.current_armor = 0
                target.current_hp -= overflow
            else:
                target.current_armor -= armor_damage
                return armor_damage
        else:
            target.current_hp -= modified_damage

        # Check death
        if target.current_hp <= 0:
            target.current_hp = 0
            target.is_alive = False

        return modified_damage


class StatusEffectSystem:
    """Handles status effect application and processing."""

    def __init__(self, status_effects: dict[int, StatusEffect]):
        """
        Initialize with status effect definitions.

        Args:
            status_effects: Dict mapping effect_id -> StatusEffect
        """
        self.effects = status_effects

    def try_apply_effect(
        self,
        target: "BattleUnit",
        effect_id: int,
        apply_chance: float,
        source_damage: float,
        rng: random.Random
    ) -> bool:
        """
        Try to apply a status effect to a unit.

        Returns True if effect was applied.
        """
        # Check if unit is immune
        if effect_id in target.template.stats.status_effect_immunities:
            return False

        effect = self.effects.get(effect_id)
        if not effect:
            return False

        # Roll for application
        if rng.random() * 100 >= apply_chance:
            return False

        # Check if effect already exists (refresh duration)
        from .battle import ActiveStatusEffect

        for existing in target.status_effects:
            if existing.effect.id == effect_id:
                # Refresh duration
                existing.remaining_turns = effect.duration
                existing.source_damage = max(existing.source_damage, source_damage)
                return True

        # Apply new effect
        target.status_effects.append(ActiveStatusEffect(
            effect=effect,
            remaining_turns=effect.duration,
            source_damage=source_damage
        ))
        return True

    def process_effects(self, unit: "BattleUnit", damage_calculator: DamageCalculator) -> int:
        """
        Process all status effects on a unit at end of turn.

        Returns total DOT damage dealt.
        """
        if not unit.is_alive:
            return 0

        total_dot = 0
        remaining_effects = []

        for status in unit.status_effects:
            effect = status.effect

            if effect.effect_type == StatusEffectType.DOT:
                # Calculate DOT damage
                dot_damage = int(status.source_damage * effect.dot_ability_damage_mult)
                dot_damage += effect.dot_bonus_damage

                if dot_damage > 0:
                    # Apply DOT damage
                    actual = damage_calculator.apply_damage(
                        unit, dot_damage, effect.dot_damage_type, effect.dot_ap_percent
                    )
                    total_dot += actual

            # Decrement duration
            status.remaining_turns -= 1
            if status.remaining_turns > 0:
                remaining_effects.append(status)

        unit.status_effects = remaining_effects
        return total_dot

    def is_stunned(self, unit: "BattleUnit") -> bool:
        """Check if unit is stunned and cannot act."""
        for status in unit.status_effects:
            if (status.effect.effect_type == StatusEffectType.STUN and
                    status.effect.stun_block_action):
                return True
        return False

    def get_damage_modifiers(self, unit: "BattleUnit") -> dict[int, float]:
        """Get any damage modifiers from status effects."""
        mods = {}
        for status in unit.status_effects:
            if status.effect.effect_type == StatusEffectType.STUN:
                for dtype, mult in status.effect.stun_damage_mods.items():
                    if dtype in mods:
                        mods[dtype] *= mult
                    else:
                        mods[dtype] = mult
        return mods
