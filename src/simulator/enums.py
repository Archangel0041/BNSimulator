"""Game enumerations and constants."""
from enum import IntEnum, auto


class DamageType(IntEnum):
    """Damage types in the game."""
    PIERCING = 1
    CRUSHING = 2
    SLASHING = 3
    EXPLOSIVE = 4
    FIRE = 5
    COLD = 6
    ELECTRIC = 7


class UnitClass(IntEnum):
    """Unit class types (from battle_config.json class_types)."""
    WEAPON_PLACEMENT = 1
    FORTRESS_INVULN = 2  # Invulnerable fortress (all 0 damage mods)
    CRITTER = 3
    AIRCRAFT = 4
    SUB = 5
    FORTRESS = 6
    VEHICLE = 7
    DESTROYER = 8
    HEAVY_SOLDIER = 9
    ARTILLERY = 10
    BATTLESHIP = 11
    GUNBOAT = 12
    SOLDIER = 13
    TANK = 14
    SHIP = 15


class StatusEffectType(IntEnum):
    """Status effect types."""
    DOT = 1  # Damage over time
    STUN = 2  # Stun/debuff effect


class StatusEffectFamily(IntEnum):
    """Status effect families (from status_effects.json)."""
    BLEED = 1
    POISON = 2
    FREEZE = 3
    SHOCK = 4
    FIRE = 5
    WATER = 6
    ACID = 7
    CORROSION = 8
    BURN = 9
    WEAKEN = 10
    SLOW = 11
    STAGGER = 12
    MARKED = 14


class TargetType(IntEnum):
    """Target area types."""
    SELF = 0
    ALL_ENEMIES = 1
    SINGLE = 2
    ROW = 3
    COLUMN = 4


class AttackDirection(IntEnum):
    """Attack direction constraints."""
    ANY = 0
    FORWARD = 1
    BACKWARD = 2


class LineOfFire(IntEnum):
    """Line of fire requirements."""
    NONE = 0
    DIRECT = 1
    INDIRECT = 2
    ANY = 3


class Side(IntEnum):
    """Battle side identifiers."""
    ATTACKER = 1
    DEFENDER = 2
    NEUTRAL = 3
    ALLY = 4
    ENEMY_SPECIAL = 5
    NPC = 6


# Grid layout constants
class CellType(IntEnum):
    """Grid cell types from layout data."""
    VALID = 1
    INVALID = 2  # Dead zone (corners in back row)


# Layout IDs
class LayoutId(IntEnum):
    """Battle layout configurations."""
    RAID = 1      # 3x3 with dead corners
    STANDARD = 2  # 5x3 with dead corners
    ASSAULT = 3   # 4x3 asymmetric


# Common unit tags that affect targeting
TARGETABLE_ALL = 39  # Most common target tag - "all units"
TARGETABLE_GROUND = 24
TARGETABLE_AIR = 15
TARGETABLE_BUILDINGS = 6


# Damage type string mapping for JSON parsing
DAMAGE_TYPE_NAMES = {
    "piercing": DamageType.PIERCING,
    "crushing": DamageType.CRUSHING,
    "explosive": DamageType.EXPLOSIVE,
    "fire": DamageType.FIRE,
    "cold": DamageType.COLD,
}
