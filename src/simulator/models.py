"""Data models for battle simulator."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .enums import (
    DamageType, UnitClass, StatusEffectType, StatusEffectFamily,
    TargetType, AttackDirection, LineOfFire, Side, BattleSide, CellType
)


@dataclass
class Position:
    """Grid position (x=column, y=row)."""
    x: int
    y: int

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        if isinstance(other, Position):
            return self.x == other.x and self.y == other.y
        return False

    def to_grid_id(self, width: int = 5) -> int:
        """Convert to linear grid ID."""
        return self.y * width + self.x

    @classmethod
    def from_grid_id(cls, grid_id: int, width: int = 5) -> "Position":
        """Create from linear grid ID."""
        return cls(x=grid_id % width, y=grid_id // width)


@dataclass
class DamageArea:
    """AOE damage pattern relative to target."""
    pos: Position
    damage_percent: float = 100.0
    order: int = 1


@dataclass
class TargetArea:
    """Targeting pattern configuration."""
    target_type: TargetType
    data: list[DamageArea]
    random: bool = False
    aoe_order_delay: float = 0.0


@dataclass
class AbilityStats:
    """Combat statistics for an ability."""
    # Cooldown and ammo
    ability_cooldown: int = 0
    global_cooldown: int = 0
    ammo_required: int = 0
    charge_time: int = 0

    # Attack modifiers
    attack: int = 0
    attacks_per_use: int = 1
    shots_per_attack: int = 1

    # Damage configuration
    damage: int = 0
    damage_type: DamageType = DamageType.PIERCING
    secondary_damage_percent: float = 0.0
    armor_piercing_percent: float = 0.0

    # Scaling multipliers
    attack_from_unit: float = 1.0
    attack_from_weapon: float = 1.0
    damage_from_unit: float = 1.0
    damage_from_weapon: float = 1.0
    crit_from_unit: float = 1.0
    crit_from_weapon: float = 1.0

    # Crit
    critical_hit_percent: float = 0.0
    critical_bonuses: dict[int, float] = field(default_factory=dict)  # Tag -> bonus crit

    # Range and targeting
    min_range: int = 1
    max_range: int = 5
    max_range_mod_atk: float = 0.0
    line_of_fire: LineOfFire = LineOfFire.ANY
    attack_direction: AttackDirection = AttackDirection.ANY

    # AOE
    damage_area: list[DamageArea] = field(default_factory=list)
    target_area: Optional[TargetArea] = None

    # Valid targets (unit tags)
    targets: list[int] = field(default_factory=list)

    # Status effects: effect_id -> apply_chance
    status_effects: dict[int, float] = field(default_factory=dict)

    # Distraction (aggro manipulation)
    damage_distraction: float = 0.0
    damage_distraction_bonus: float = 0.0

    # Capture mechanics
    capture: bool = False
    min_hp_percent: float = 0.0


@dataclass
class Ability:
    """A combat ability/attack."""
    id: int
    name: str
    icon: str = ""
    damage_animation_type: str = ""
    stats: AbilityStats = field(default_factory=AbilityStats)


@dataclass
class WeaponStats:
    """Weapon statistics."""
    ammo: int = -1  # -1 means unlimited
    base_atk: int = 0
    base_damage_min: int = 0
    base_damage_max: int = 0
    base_crit_percent: float = 0.0
    range_bonus: int = 0


@dataclass
class Weapon:
    """A unit's weapon."""
    id: int
    name: str
    abilities: list[int]  # Ability IDs
    stats: WeaponStats = field(default_factory=WeaponStats)


@dataclass
class UnitStats:
    """Combat statistics for a unit at a specific level."""
    hp: int = 100
    defense: int = 0
    accuracy: int = 0
    dodge: int = 0
    critical: float = 0.0
    bravery: int = 0
    power: int = 0
    blocking: int = 0

    # Armor system
    armor_hp: int = 0
    armor_def_style: int = 0

    # Damage modifiers by type (incoming damage multipliers)
    damage_mods: dict[str, float] = field(default_factory=dict)
    armor_damage_mods: dict[str, float] = field(default_factory=dict)

    # Status effect immunities
    status_effect_immunities: list[int] = field(default_factory=list)

    # Size for targeting
    size: int = 1
    ability_slots: int = 2
    preferred_row: int = 1

    # Power value (for matchmaking/balancing)
    pv: int = 0


@dataclass
class UnitTemplate:
    """Template for a unit type (from JSON data)."""
    id: int
    name: str
    short_name: str = ""
    description: str = ""
    icon: str = ""
    back_icon: str = ""
    class_type: UnitClass = UnitClass.SOLDIER
    side: Side = Side.HOSTILE
    tags: list[int] = field(default_factory=list)

    # Stats (can vary by level)
    stats: UnitStats = field(default_factory=UnitStats)
    all_rank_stats: list[UnitStats] = field(default_factory=list)  # All rank variations

    # Weapons
    weapons: dict[int, Weapon] = field(default_factory=dict)

    # Flags
    unimportant: bool = False  # For NPCs that don't count for win/loss

    def get_stats_at_rank(self, rank: int) -> UnitStats:
        """
        Get unit stats at a specific rank.

        Args:
            rank: The rank number (1-based, where rank 1 is the first/lowest rank)

        Returns:
            UnitStats for the specified rank
        """
        if not self.all_rank_stats:
            return self.stats
        # Convert rank (1-based) to index (0-based)
        # Rank 1 -> index 0, Rank 6 -> index 5, etc.
        index = rank - 1
        # Clamp index to available range
        index = max(0, min(index, len(self.all_rank_stats) - 1))
        return self.all_rank_stats[index]


@dataclass
class StatusEffect:
    """A status effect definition."""
    id: int
    effect_type: StatusEffectType
    family: StatusEffectFamily
    duration: int

    # DOT specific
    dot_damage_type: DamageType = DamageType.FIRE
    dot_ability_damage_mult: float = 1.0
    dot_bonus_damage: int = 0
    dot_ap_percent: float = 0.0
    dot_diminishing: bool = True

    # Stun specific
    stun_block_action: bool = False
    stun_block_movement: bool = False
    stun_damage_break: bool = False
    stun_damage_mods: dict[int, float] = field(default_factory=dict)
    stun_armor_damage_mods: dict[int, float] = field(default_factory=dict)


@dataclass
class GridLayout:
    """Battle grid layout configuration."""
    id: int
    attacker_grid: np.ndarray  # 2D array of CellType
    defender_grid: np.ndarray
    defender_wall: list[int]  # Wall heights per column

    @property
    def width(self) -> int:
        return self.attacker_grid.shape[1]

    @property
    def height(self) -> int:
        return self.attacker_grid.shape[0]

    def is_valid_cell(self, battle_side: BattleSide, pos: Position) -> bool:
        """Check if position is a valid cell for the given battle side."""
        grid = self.attacker_grid if battle_side == BattleSide.PLAYER_TEAM else self.defender_grid
        if 0 <= pos.y < grid.shape[0] and 0 <= pos.x < grid.shape[1]:
            return grid[pos.y, pos.x] == CellType.AVAILABLE
        return False


@dataclass
class EncounterUnit:
    """Unit placement in an encounter."""
    grid_id: int
    unit_id: int
    rank: int = 1  # Unit rank (1-based: rank 1 is the first/lowest rank)


@dataclass
class Encounter:
    """An enemy encounter definition."""
    id: int
    name: str
    level: int
    layout_id: int

    # Unit placements
    enemy_units: list[EncounterUnit] = field(default_factory=list)
    player_units: list[EncounterUnit] = field(default_factory=list)

    # Slot limits
    attacker_slots: int = 8
    attacker_defense_slots: int = 0

    # Flags
    is_player_attacker: bool = True
    regen: bool = True


@dataclass
class ClassDamageMod:
    """Damage modifiers between unit classes."""
    attacker_class: UnitClass
    defender_class: UnitClass
    multiplier: float


@dataclass
class GameConfig:
    """Global game configuration."""
    # Class-based damage modifiers
    class_damage_mods: dict[int, dict[int, float]] = field(default_factory=dict)

    # Layouts
    layouts: dict[int, GridLayout] = field(default_factory=dict)

    # Tag hierarchy (parent tag -> list of child tags)
    tag_hierarchy: dict[int, list[int]] = field(default_factory=dict)

    # Thresholds for "good vs" / "weak vs" display
    good_vs_cutoff: float = 1.1
    weak_vs_cutoff: float = 0.85
