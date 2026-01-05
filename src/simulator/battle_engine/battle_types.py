"""
Battle engine types and enums.

This module contains all the enums, dataclasses, and type definitions
used by the battle engine.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple

from ..enums import DamageType


class TurnResult(Enum):
    """Result of executing a turn."""
    SUCCESS = "success"
    BATTLE_ENDED = "battle_ended"
    UNIT_CANNOT_ACT = "unit_cannot_act"
    INVALID_TARGET = "invalid_target"
    ATTACK_MISSED = "attack_missed"
    NO_VALID_ACTIONS = "no_valid_actions"


class BattleResult(Enum):
    """Final result of a battle."""
    IN_PROGRESS = "in_progress"
    PLAYER_WIN = "player_win"
    ENEMY_WIN = "enemy_win"
    SURRENDER = "surrender"


@dataclass
class HitResult:
    """Result of a hit/miss check."""
    damage_roll: int  # Base damage roll (before crit multiplier)
    modifier: float  # Percent modifier (e.g., 100.0 for base, 50.0 for 50% splash)
    hit: bool  # Whether the hit connected
    is_critical: bool  # Whether it was a critical hit
    damage: int  # Final damage after crit multiplier (damage_roll * (1.5 if crit else 1.0))


@dataclass
class DamageResult:
    """Result of damage calculation."""
    base_damage: float
    final_damage: float
    damage_type: DamageType
    was_critical: bool = False
    # Additional fields for tracking damage breakdown
    attack_value: float = 0.0
    defense_value: float = 0.0
    class_modifier: float = 1.0
    type_modifier: float = 1.0


@dataclass
class Position:
    """Grid position (row, column)."""
    row: int
    col: int

    def __eq__(self, other):
        if not isinstance(other, Position):
            return False
        return self.row == other.row and self.col == other.col

    def __hash__(self):
        return hash((self.row, self.col))


@dataclass
class ActionCandidate:
    """
    Represents a potential action during enemy turn.
    Used for filtering and target calculation.
    """
    unit_position: Position  # Position of the unit
    ability_index: int
    # Will be populated during target calculation
    valid_targets: List[Position] = None

    def __post_init__(self):
        if self.valid_targets is None:
            self.valid_targets = []


@dataclass
class TargetHitInfo:
    """
    Information about a hit on a target position.
    Contains position and modifier, but not damage/hit/crit (rolled later).
    """
    position: Position  # Target position
    modifier: float  # Damage modifier (100.0 for base, e.g., 50.0 for 50% splash)
