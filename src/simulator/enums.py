"""Game enumerations and constants - aligned with Unity game code (dump.cs)."""
from enum import IntEnum


class DamageType(IntEnum):
    """Damage types in the game (from Unity DamageType enum)."""
    NONE = 0
    PIERCING = 1
    COLD = 2
    CRUSHING = 3
    EXPLOSIVE = 4
    FIRE = 5
    TORPEDO = 6
    DEPTH_CHARGE = 7
    MELEE = 8
    PROJECTILE = 9
    SHELL = 10


class UnitClass(IntEnum):
    """Unit class types (from Unity UnitClass enum)."""
    NONE = 0
    EMPLACEMENT = 1      # Was WEAPON_PLACEMENT
    INVINCIBLE = 2       # Was FORTRESS_INVULN
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


class UnitTag(IntEnum):
    """Unit tags for targeting (from Unity UnitTag enum - 69 values)."""
    NONE = 0
    SEA_DEFENSE = 1
    LEGEND = 2
    ARTILLERY = 3
    BIGFOOT = 4
    VRB = 5
    SOLDIER = 6
    MECH_ARTILLERY = 7
    SUB = 8
    LTA = 9
    ANI = 10
    VEHICLE = 11
    HUNTER = 12
    SUBMERSIBLE = 13
    ANCIENT = 14
    SEA = 15
    SRB = 16
    BATTLESHIP = 17
    DEFENSE = 18
    SOL = 19
    TANK = 20
    SEALIFE = 21
    GROUPER = 22
    HELICOPTER = 23
    GROUND = 24
    FLYING_CRITTER = 25
    METAL = 26
    IGNORABLE = 27
    CROSSOVER2 = 28
    SHIP = 29
    I17_ANCIENT = 30
    WIMP = 31
    FAST = 32
    ZOMBIE = 33
    SPIDERWASP = 34
    INF = 35
    FIGHTER = 36
    DESTROYER = 37
    CRITTER = 38
    AIR = 39
    UNICORN = 40
    CIVILIAN = 41
    ZOMBIE_CANDIDATE = 42
    AIRC = 43
    VEH = 44
    MISSILE_STRIKE = 45
    SNIPER = 46
    GUNBOAT = 47
    CROSSOVER = 48
    HOSPITAL = 49
    PERSONNEL = 50
    UNIT = 51
    AIRCRAFT = 52
    DRONE = 53
    BOMBER = 54
    STRUCTURE = 55
    SEA_STRUCTURE = 56
    NON_COM = 57
    WALL = 58
    SEA_WALL = 59
    ARMORED = 60
    BIOLOGICAL = 61
    ELITE = 62
    IMMOBILE = 63
    MECHANICAL = 64
    RAIDER = 65
    SLOW = 66
    STEALTH = 67
    USES_COVER = 68


class UnitStatusEffect(IntEnum):
    """Status effect IDs (from Unity UnitStatusEffect enum)."""
    NONE = 0
    STUN = 1
    POISON = 2
    FROZEN = 3
    PLAGUE = 4
    FIRE = 5
    FLAMMABLE = 6
    BREACH = 7
    SHELL = 8
    COLD = 9
    SHATTER = 10
    ACID = 11
    QUAKE = 12
    FREEZE = 13
    FIREMOD = 14


class StatusEffectType(IntEnum):
    """Status effect behavior types (internal classification)."""
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
    """Target area types (game logic - for ability targeting patterns)."""
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
    """Unit side/faction identifiers (from Unity UnitSide enum).

    This indicates the inherent faction/type of a unit, NOT which team
    they're on during battle. Use BattleSide for battle team membership.
    """
    NONE = 0
    PLAYER = 1      # Player-owned units
    HOSTILE = 2     # Enemy units
    NEUTRAL = 3     # Neutral NPCs
    HERO = 4        # Main cast heroes
    VILLAIN = 5     # Main cast villains
    TEST = 6        # Test/debug units


class BattleSide(IntEnum):
    """Battle team membership (which team a unit fights for).

    During battle, units are assigned to either the PLAYER_TEAM or ENEMY_TEAM,
    regardless of their inherent Side (faction). For example, a HOSTILE unit
    could be on PLAYER_TEAM if recruited/captured.
    """
    PLAYER_TEAM = 1  # Fighting for the player
    ENEMY_TEAM = 2   # Fighting against the player


class UnitBlocking(IntEnum):
    """Unit blocking types (from Unity UnitBlocking enum)."""
    NONE = 0
    PARTIAL = 1
    FULL = 2
    GOD = 3


# Grid layout constants
class CellType(IntEnum):
    """Grid cell types (from Unity BattleGridTileConfig enum)."""
    NONE = 0
    AVAILABLE = 1   # Was VALID
    UNAVAILABLE = 2  # Was INVALID (dead zone corners)
    WALL = 3

    # Alias for backwards compatibility
    @classmethod
    def VALID(cls):
        return cls.AVAILABLE

    @classmethod
    def INVALID(cls):
        return cls.UNAVAILABLE


# Layout IDs
class LayoutId(IntEnum):
    """Battle layout configurations (from Unity LayoutId enum)."""
    NONE = 0
    EQUAL_3X3 = 1   # Was RAID - 3x3 with dead corners
    EQUAL_5X3 = 2   # Was STANDARD - 5x3 with dead corners
    EQUAL_4X3 = 3   # Was ASSAULT - 4x3 asymmetric

    # Aliases for backwards compatibility
    @classmethod
    def RAID(cls):
        return cls.EQUAL_3X3

    @classmethod
    def STANDARD(cls):
        return cls.EQUAL_5X3

    @classmethod
    def ASSAULT(cls):
        return cls.EQUAL_4X3


# Common unit tags that affect targeting
TARGETABLE_ALL = 51  # UnitTag.UNIT - targets all units
TARGETABLE_GROUND = UnitTag.GROUND
TARGETABLE_AIR = UnitTag.AIR
TARGETABLE_BUILDINGS = UnitTag.STRUCTURE


# Damage type string mapping for JSON parsing
DAMAGE_TYPE_NAMES = {
    "none": DamageType.NONE,
    "piercing": DamageType.PIERCING,
    "cold": DamageType.COLD,
    "crushing": DamageType.CRUSHING,
    "explosive": DamageType.EXPLOSIVE,
    "fire": DamageType.FIRE,
    "torpedo": DamageType.TORPEDO,
    "depthcharge": DamageType.DEPTH_CHARGE,
    "depth_charge": DamageType.DEPTH_CHARGE,
    "melee": DamageType.MELEE,
    "projectile": DamageType.PROJECTILE,
    "shell": DamageType.SHELL,
}


# Status effect string mapping for JSON parsing
STATUS_EFFECT_NAMES = {
    "none": UnitStatusEffect.NONE,
    "stun": UnitStatusEffect.STUN,
    "poison": UnitStatusEffect.POISON,
    "frozen": UnitStatusEffect.FROZEN,
    "plague": UnitStatusEffect.PLAGUE,
    "fire": UnitStatusEffect.FIRE,
    "flammable": UnitStatusEffect.FLAMMABLE,
    "breach": UnitStatusEffect.BREACH,
    "shell": UnitStatusEffect.SHELL,
    "cold": UnitStatusEffect.COLD,
    "shatter": UnitStatusEffect.SHATTER,
    "acid": UnitStatusEffect.ACID,
    "quake": UnitStatusEffect.QUAKE,
    "freeze": UnitStatusEffect.FREEZE,
    "firemod": UnitStatusEffect.FIREMOD,
}


# Unit tag string mapping for JSON parsing
UNIT_TAG_NAMES = {
    "none": UnitTag.NONE,
    "sea_defense": UnitTag.SEA_DEFENSE,
    "legend": UnitTag.LEGEND,
    "artillery": UnitTag.ARTILLERY,
    "bigfoot": UnitTag.BIGFOOT,
    "vrb": UnitTag.VRB,
    "soldier": UnitTag.SOLDIER,
    "mech_artillery": UnitTag.MECH_ARTILLERY,
    "sub": UnitTag.SUB,
    "lta": UnitTag.LTA,
    "ani": UnitTag.ANI,
    "vehicle": UnitTag.VEHICLE,
    "hunter": UnitTag.HUNTER,
    "submersible": UnitTag.SUBMERSIBLE,
    "ancient": UnitTag.ANCIENT,
    "sea": UnitTag.SEA,
    "srb": UnitTag.SRB,
    "battleship": UnitTag.BATTLESHIP,
    "defense": UnitTag.DEFENSE,
    "sol": UnitTag.SOL,
    "tank": UnitTag.TANK,
    "sealife": UnitTag.SEALIFE,
    "grouper": UnitTag.GROUPER,
    "helicopter": UnitTag.HELICOPTER,
    "ground": UnitTag.GROUND,
    "flying_critter": UnitTag.FLYING_CRITTER,
    "metal": UnitTag.METAL,
    "ignorable": UnitTag.IGNORABLE,
    "crossover2": UnitTag.CROSSOVER2,
    "ship": UnitTag.SHIP,
    "i17_ancient": UnitTag.I17_ANCIENT,
    "wimp": UnitTag.WIMP,
    "fast": UnitTag.FAST,
    "zombie": UnitTag.ZOMBIE,
    "spiderwasp": UnitTag.SPIDERWASP,
    "inf": UnitTag.INF,
    "fighter": UnitTag.FIGHTER,
    "destroyer": UnitTag.DESTROYER,
    "critter": UnitTag.CRITTER,
    "air": UnitTag.AIR,
    "unicorn": UnitTag.UNICORN,
    "civilian": UnitTag.CIVILIAN,
    "zombie_candidate": UnitTag.ZOMBIE_CANDIDATE,
    "airc": UnitTag.AIRC,
    "veh": UnitTag.VEH,
    "missile_strike": UnitTag.MISSILE_STRIKE,
    "sniper": UnitTag.SNIPER,
    "gunboat": UnitTag.GUNBOAT,
    "crossover": UnitTag.CROSSOVER,
    "hospital": UnitTag.HOSPITAL,
    "personnel": UnitTag.PERSONNEL,
    "unit": UnitTag.UNIT,
    "aircraft": UnitTag.AIRCRAFT,
    "drone": UnitTag.DRONE,
    "bomber": UnitTag.BOMBER,
    "structure": UnitTag.STRUCTURE,
    "sea_structure": UnitTag.SEA_STRUCTURE,
    "non_com": UnitTag.NON_COM,
    "wall": UnitTag.WALL,
    "sea_wall": UnitTag.SEA_WALL,
    "armored": UnitTag.ARMORED,
    "biological": UnitTag.BIOLOGICAL,
    "elite": UnitTag.ELITE,
    "immobile": UnitTag.IMMOBILE,
    "mechanical": UnitTag.MECHANICAL,
    "raider": UnitTag.RAIDER,
    "slow": UnitTag.SLOW,
    "stealth": UnitTag.STEALTH,
    "uses_cover": UnitTag.USES_COVER,
}


# Unit class string mapping for JSON parsing
UNIT_CLASS_NAMES = {
    "none": UnitClass.NONE,
    "emplacement": UnitClass.EMPLACEMENT,
    "invincible": UnitClass.INVINCIBLE,
    "critter": UnitClass.CRITTER,
    "aircraft": UnitClass.AIRCRAFT,
    "sub": UnitClass.SUB,
    "fortress": UnitClass.FORTRESS,
    "vehicle": UnitClass.VEHICLE,
    "destroyer": UnitClass.DESTROYER,
    "heavy_soldier": UnitClass.HEAVY_SOLDIER,
    "heavysoldier": UnitClass.HEAVY_SOLDIER,
    "artillery": UnitClass.ARTILLERY,
    "battleship": UnitClass.BATTLESHIP,
    "gunboat": UnitClass.GUNBOAT,
    "soldier": UnitClass.SOLDIER,
    "tank": UnitClass.TANK,
    "ship": UnitClass.SHIP,
}
