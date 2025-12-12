"""Battle simulator package."""
from .enums import (
    DamageType, UnitClass, UnitTag, UnitStatusEffect, UnitBlocking,
    StatusEffectType, StatusEffectFamily,
    TargetType, AttackDirection, LineOfFire, Side, CellType, LayoutId,
    DAMAGE_TYPE_NAMES, STATUS_EFFECT_NAMES, UNIT_TAG_NAMES, UNIT_CLASS_NAMES,
    TARGETABLE_ALL, TARGETABLE_GROUND, TARGETABLE_AIR, TARGETABLE_BUILDINGS
)
from .models import (
    Position, DamageArea, TargetArea, AbilityStats, Ability,
    WeaponStats, Weapon, UnitStats, UnitTemplate, StatusEffect,
    GridLayout, EncounterUnit, Encounter, GameConfig
)
from .data_loader import GameDataLoader
from .battle import (
    BattleResult, ActiveStatusEffect, BattleUnit, Action, ActionResult,
    BattleState, BattleSimulator
)
from .gym_env import BattleEnv, MultiWaveBattleEnv, register_envs
from .combat import (
    TagResolver, TargetingSystem, DamageCalculator, StatusEffectSystem,
    DamageResult
)

__all__ = [
    # Enums
    "DamageType", "UnitClass", "UnitTag", "UnitStatusEffect", "UnitBlocking",
    "StatusEffectType", "StatusEffectFamily",
    "TargetType", "AttackDirection", "LineOfFire", "Side", "CellType", "LayoutId",
    # Enum name mappings
    "DAMAGE_TYPE_NAMES", "STATUS_EFFECT_NAMES", "UNIT_TAG_NAMES", "UNIT_CLASS_NAMES",
    "TARGETABLE_ALL", "TARGETABLE_GROUND", "TARGETABLE_AIR", "TARGETABLE_BUILDINGS",
    # Models
    "Position", "DamageArea", "TargetArea", "AbilityStats", "Ability",
    "WeaponStats", "Weapon", "UnitStats", "UnitTemplate", "StatusEffect",
    "GridLayout", "EncounterUnit", "Encounter", "GameConfig",
    # Data loader
    "GameDataLoader",
    # Battle
    "BattleResult", "ActiveStatusEffect", "BattleUnit", "Action", "ActionResult",
    "BattleState", "BattleSimulator",
    # Combat systems
    "TagResolver", "TargetingSystem", "DamageCalculator", "StatusEffectSystem",
    "DamageResult",
    # Gym
    "BattleEnv", "MultiWaveBattleEnv", "register_envs"
]
