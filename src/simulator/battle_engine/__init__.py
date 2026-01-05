"""
Battle Engine - Refactored modular battle system.

This package contains the refactored battle engine with clear separation
between player and enemy turn logic.
"""

from .battle_types import (
    TurnResult,
    BattleResult,
    HitResult,
    DamageResult,
)

__all__ = [
    "TurnResult",
    "BattleResult",
    "HitResult",
    "DamageResult",
]
