"""
Data models for BN Simulator.
Pydantic models for units, abilities, encounters, and battle state.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional
import numpy as np


class DamageType(IntEnum):
    """Damage types in the game."""
    PIERCING = 1
    CRUSHING = 2
    COLD = 3
    EXPLOSIVE = 4
    FIRE = 5
    POISON = 6


class Side(IntEnum):
    """Unit sides."""
    ENEMY = 1
    PLAYER = 2
    NEUTRAL = 3
    ALLY_NPC = 4
    SPECIAL_1 = 5
    SPECIAL_2 = 6


class StatusEffectType(IntEnum):
    """Status effect types."""
    DOT = 1  # Damage over time
    MODIFIER = 2  # Stat modifier (stun, vulnerability, etc.)


@dataclass
class Position:
    """Grid position."""
    x: int
    y: int

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        if isinstance(other, Position):
            return self.x == other.x and self.y == other.y
        return False


@dataclass
class DamageAreaEntry:
    """Entry in damage area pattern."""
    pos: Position
    damage_percent: float = 100.0
    order: int = 1
    weight: int = 100


@dataclass
class TargetAreaEntry:
    """Entry in target area pattern."""
    pos: Position
    damage_percent: float = 100.0
    order: int = 1
    weight: int = 100


@dataclass
class TargetArea:
    """Target area configuration."""
    data: list[TargetAreaEntry]
    target_type: int = 2  # 1=friendly, 2=enemy
    random: bool = False
    aoe_order_delay: float = 0.0


@dataclass
class AbilityStats:
    """Stats for an ability."""
    attack: int = 0
    damage_type: int = 1
    min_range: int = 1
    max_range: int = 5
    line_of_fire: int = 3
    critical_hit_percent: int = 0
    armor_piercing_percent: float = 0.0
    shots_per_attack: int = 1
    attacks_per_use: int = 1
    ability_cooldown: int = 0
    global_cooldown: int = 0
    charge_time: int = 0
    ammo_required: int = 0
    secondary_damage_percent: float = 0.0
    damage_distraction: float = 0.0
    damage_distraction_bonus: int = 0
    capture: bool = False
    min_hp_percent: float = 0.0

    # Multipliers
    attack_from_unit: float = 1.0
    attack_from_weapon: float = 1.0
    damage_from_unit: float = 1.0
    damage_from_weapon: float = 1.0
    crit_from_unit: float = 1.0
    crit_from_weapon: float = 1.0


@dataclass
class Ability:
    """Ability definition."""
    id: int
    name: str
    icon: str = ""
    damage_animation_type: str = ""
    stats: AbilityStats = field(default_factory=AbilityStats)
    damage_area: list[DamageAreaEntry] = field(default_factory=list)
    target_area: Optional[TargetArea] = None
    targets: list[int] = field(default_factory=list)  # Valid target tags
    status_effects: dict[int, float] = field(default_factory=dict)  # effect_id -> chance
    critical_bonuses: dict[int, int] = field(default_factory=dict)  # tag -> bonus crit %


@dataclass
class WeaponStats:
    """Stats for a weapon."""
    ammo: int = -1  # -1 = unlimited
    base_atk: int = 0
    base_crit_percent: int = 0
    base_damage_min: int = 0
    base_damage_max: int = 0
    range_bonus: int = 0


@dataclass
class Weapon:
    """Weapon configuration."""
    id: int
    name: str
    abilities: list[int]  # Ability IDs
    stats: WeaponStats = field(default_factory=WeaponStats)


@dataclass
class UnitStats:
    """Combat stats for a unit at a specific level."""
    hp: int = 100
    power: int = 0
    defense: int = 0
    accuracy: int = 0
    dodge: int = 0
    bravery: int = 0
    critical: int = 0
    ability_slots: int = 2
    armor_hp: int = 0
    armor_def_style: int = 0
    pv: int = 0  # Power value (used for matchmaking/balance)

    # Damage modifiers by type name
    damage_mods: dict[str, float] = field(default_factory=dict)
    armor_damage_mods: dict[str, float] = field(default_factory=dict)


@dataclass
class UnitTemplate:
    """Template for a unit type (loaded from JSON)."""
    id: int
    name: str
    class_id: int
    side: Side
    tags: list[int] = field(default_factory=list)
    stats_by_level: list[UnitStats] = field(default_factory=list)
    weapons: dict[int, Weapon] = field(default_factory=dict)
    status_effect_immunities: list[int] = field(default_factory=list)
    preferred_row: int = 1
    size: int = 1
    blocking: int = 0
    unimportant: bool = False


@dataclass
class StatusEffect:
    """Active status effect on a unit."""
    id: int
    remaining_turns: int
    source_damage: float = 0.0  # For DoT calculations

    # DoT properties
    dot_ability_damage_mult: float = 1.0
    dot_bonus_damage: float = 0.0
    dot_damage_type: int = 5
    dot_diminishing: bool = True
    dot_ap_percent: float = 0.0

    # Modifier properties
    stun_block_action: bool = False
    stun_block_movement: bool = False
    stun_damage_break: bool = False
    stun_damage_mods: dict[int, float] = field(default_factory=dict)
    stun_armor_damage_mods: dict[int, float] = field(default_factory=dict)

    effect_type: StatusEffectType = StatusEffectType.DOT
    family: int = 0


@dataclass
class StatusEffectTemplate:
    """Template for status effects (loaded from JSON)."""
    id: int
    duration: int
    family: int
    effect_type: StatusEffectType

    # DoT properties
    dot_ability_damage_mult: float = 1.0
    dot_bonus_damage: float = 0.0
    dot_damage_type: int = 5
    dot_diminishing: bool = True
    dot_ap_percent: float = 0.0

    # Modifier properties
    stun_block_action: bool = False
    stun_block_movement: bool = False
    stun_damage_break: bool = False
    stun_damage_mods: dict[int, float] = field(default_factory=dict)
    stun_armor_damage_mods: dict[int, float] = field(default_factory=dict)


@dataclass
class BattleUnit:
    """A unit instance in battle."""
    template_id: int
    template: UnitTemplate
    level: int = 0

    # Current state
    current_hp: int = 0
    current_armor: int = 0
    position: int = -1  # Grid position ID
    side: Side = Side.PLAYER

    # Weapon state
    weapon_ammo: dict[int, int] = field(default_factory=dict)  # weapon_id -> ammo
    weapon_cooldowns: dict[int, int] = field(default_factory=dict)  # ability_id -> turns remaining

    # Status effects
    status_effects: list[StatusEffect] = field(default_factory=list)

    # Turn state
    has_acted: bool = False
    global_cooldown: int = 0

    @property
    def stats(self) -> UnitStats:
        """Get stats for current level."""
        if self.level < len(self.template.stats_by_level):
            return self.template.stats_by_level[self.level]
        return self.template.stats_by_level[-1] if self.template.stats_by_level else UnitStats()

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def is_stunned(self) -> bool:
        return any(e.stun_block_action for e in self.status_effects)

    def init_battle_state(self):
        """Initialize state at battle start."""
        stats = self.stats
        self.current_hp = stats.hp
        self.current_armor = stats.armor_hp
        self.weapon_ammo = {}
        self.weapon_cooldowns = {}
        self.status_effects = []
        self.has_acted = False
        self.global_cooldown = 0

        # Initialize ammo
        for weapon_id, weapon in self.template.weapons.items():
            if weapon.stats.ammo > 0:
                self.weapon_ammo[weapon_id] = weapon.stats.ammo

    def get_available_abilities(self) -> list[tuple[int, int, Ability]]:
        """Get list of (weapon_id, ability_id, ability) that can be used."""
        if not self.is_alive or self.is_stunned:
            return []

        available = []
        for weapon_id, weapon in self.template.weapons.items():
            # Check ammo
            if weapon.stats.ammo > 0:
                current_ammo = self.weapon_ammo.get(weapon_id, 0)
                if current_ammo <= 0:
                    continue

            for ability_id in weapon.abilities:
                # Check cooldown
                if self.weapon_cooldowns.get(ability_id, 0) > 0:
                    continue
                available.append((weapon_id, ability_id, None))  # Ability filled in by engine

        return available


@dataclass
class GridLayout:
    """Battle grid layout configuration."""
    id: int
    attacker_grid: list[list[int]]  # 2=invalid, 1=valid
    defender_grid: list[list[int]]
    defender_wall: list[int] = field(default_factory=list)

    @property
    def width(self) -> int:
        return len(self.attacker_grid[0]) if self.attacker_grid else 0

    @property
    def height(self) -> int:
        return len(self.attacker_grid)

    def get_valid_positions(self, is_attacker: bool) -> list[int]:
        """Get list of valid grid position IDs."""
        grid = self.attacker_grid if is_attacker else self.defender_grid
        valid = []
        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                if cell == 1:
                    pos_id = row_idx * self.width + col_idx
                    valid.append(pos_id)
        return valid

    def pos_to_coords(self, pos_id: int) -> tuple[int, int]:
        """Convert position ID to (row, col)."""
        return pos_id // self.width, pos_id % self.width

    def coords_to_pos(self, row: int, col: int) -> int:
        """Convert (row, col) to position ID."""
        return row * self.width + col


@dataclass
class EncounterWave:
    """A single wave of enemies in an encounter."""
    units: list[tuple[int, int]]  # (grid_id, unit_id)


@dataclass
class Encounter:
    """Encounter configuration."""
    id: int
    name: str
    level: int
    layout_id: int
    attacker_slots: int
    waves: list[EncounterWave] = field(default_factory=list)
    player_units: list[tuple[int, int]] = field(default_factory=list)  # (grid_id, unit_id)


@dataclass
class ClassConfig:
    """Class type configuration."""
    id: int
    display_name: str
    damage_mods: dict[int, float] = field(default_factory=dict)  # target_class -> modifier


@dataclass
class Action:
    """A combat action."""
    unit_idx: int  # Index of acting unit in battle state
    weapon_id: int
    ability_id: int
    target_pos: int  # Target grid position

    def __hash__(self):
        return hash((self.unit_idx, self.weapon_id, self.ability_id, self.target_pos))


@dataclass
class DamageResult:
    """Result of damage calculation."""
    target_idx: int
    damage: int
    is_crit: bool
    is_dodge: bool
    armor_damage: int = 0
    hp_damage: int = 0
    killed: bool = False


@dataclass
class ActionResult:
    """Result of executing an action."""
    action: Action
    damage_results: list[DamageResult] = field(default_factory=list)
    status_effects_applied: list[tuple[int, int]] = field(default_factory=list)  # (unit_idx, effect_id)


@dataclass
class BattleState:
    """Complete state of a battle."""
    # Units
    player_units: list[BattleUnit] = field(default_factory=list)
    enemy_units: list[BattleUnit] = field(default_factory=list)

    # Grid
    layout: Optional[GridLayout] = None

    # Turn state
    turn_number: int = 0
    is_player_turn: bool = True

    # Wave state (for multi-wave encounters)
    current_wave: int = 0
    total_waves: int = 1

    # Battle outcome
    is_finished: bool = False
    player_won: bool = False
    surrendered: bool = False

    # Statistics
    total_damage_dealt: int = 0
    total_damage_taken: int = 0
    units_lost: int = 0
    enemies_killed: int = 0

    def get_all_units(self) -> list[BattleUnit]:
        """Get all units in battle."""
        return self.player_units + self.enemy_units

    def get_unit_at_position(self, pos: int, side: Optional[Side] = None) -> Optional[BattleUnit]:
        """Get unit at grid position."""
        units = self.player_units if side == Side.PLAYER else (
            self.enemy_units if side == Side.ENEMY else self.get_all_units()
        )
        for unit in units:
            if unit.position == pos and unit.is_alive:
                return unit
        return None

    def get_living_units(self, side: Side) -> list[BattleUnit]:
        """Get all living units for a side."""
        units = self.player_units if side == Side.PLAYER else self.enemy_units
        return [u for u in units if u.is_alive]

    def check_battle_end(self) -> bool:
        """Check if battle has ended."""
        player_alive = any(u.is_alive for u in self.player_units)
        enemy_alive = any(u.is_alive for u in self.enemy_units)

        if not player_alive:
            self.is_finished = True
            self.player_won = False
            return True

        if not enemy_alive:
            # Check for next wave
            if self.current_wave < self.total_waves - 1:
                return False  # More waves to come
            self.is_finished = True
            self.player_won = True
            return True

        return False

    def to_observation(self) -> np.ndarray:
        """Convert battle state to observation array for ML."""
        # Features per unit: hp%, armor%, position, class, status effects, etc.
        max_units = 16  # Max units per side
        features_per_unit = 20

        obs = np.zeros((2, max_units, features_per_unit), dtype=np.float32)

        for side_idx, units in enumerate([self.player_units, self.enemy_units]):
            for unit_idx, unit in enumerate(units[:max_units]):
                if not unit.is_alive:
                    continue

                stats = unit.stats
                obs[side_idx, unit_idx, 0] = unit.current_hp / max(stats.hp, 1)
                obs[side_idx, unit_idx, 1] = unit.current_armor / max(stats.armor_hp, 1) if stats.armor_hp > 0 else 0
                obs[side_idx, unit_idx, 2] = unit.position / 15.0  # Normalized position
                obs[side_idx, unit_idx, 3] = unit.template.class_id / 15.0
                obs[side_idx, unit_idx, 4] = stats.power / 200.0
                obs[side_idx, unit_idx, 5] = stats.defense / 100.0
                obs[side_idx, unit_idx, 6] = stats.accuracy / 100.0
                obs[side_idx, unit_idx, 7] = stats.dodge / 100.0
                obs[side_idx, unit_idx, 8] = stats.critical / 50.0
                obs[side_idx, unit_idx, 9] = 1.0 if unit.is_stunned else 0.0
                obs[side_idx, unit_idx, 10] = len(unit.status_effects) / 5.0
                obs[side_idx, unit_idx, 11] = 1.0  # Unit alive flag

                # Weapon/ability availability
                available = len([1 for w in unit.template.weapons.values()
                               for a in w.abilities
                               if unit.weapon_cooldowns.get(a, 0) == 0])
                obs[side_idx, unit_idx, 12] = available / 6.0

        # Global state
        global_features = np.array([
            self.turn_number / 100.0,
            1.0 if self.is_player_turn else 0.0,
            self.current_wave / max(self.total_waves, 1),
            len(self.get_living_units(Side.PLAYER)) / max(len(self.player_units), 1),
            len(self.get_living_units(Side.ENEMY)) / max(len(self.enemy_units), 1),
        ], dtype=np.float32)

        return np.concatenate([obs.flatten(), global_features])
