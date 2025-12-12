"""Battle simulator package."""
from .enums import (
    DamageType, UnitClass, StatusEffectType, StatusEffectFamily,
    TargetType, AttackDirection, LineOfFire, Side, CellType, LayoutId
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

__all__ = [
    # Enums
    "DamageType", "UnitClass", "StatusEffectType", "StatusEffectFamily",
    "TargetType", "AttackDirection", "LineOfFire", "Side", "CellType", "LayoutId",
    # Models
    "Position", "DamageArea", "TargetArea", "AbilityStats", "Ability",
    "WeaponStats", "Weapon", "UnitStats", "UnitTemplate", "StatusEffect",
    "GridLayout", "EncounterUnit", "Encounter", "GameConfig",
    # Data loader
    "GameDataLoader",
    # Battle
    "BattleResult", "ActiveStatusEffect", "BattleUnit", "Action", "ActionResult",
    "BattleState", "BattleSimulator",
    # Gym
    "BattleEnv", "MultiWaveBattleEnv", "register_envs"
]
