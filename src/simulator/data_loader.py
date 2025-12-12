"""Data loader for parsing game JSON files."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
import numpy as np

from .enums import (
    DamageType, UnitClass, StatusEffectType, StatusEffectFamily,
    TargetType, AttackDirection, LineOfFire, Side, CellType,
    DAMAGE_TYPE_NAMES
)
from .models import (
    Position, DamageArea, TargetArea, AbilityStats, Ability,
    WeaponStats, Weapon, UnitStats, UnitTemplate, StatusEffect,
    GridLayout, EncounterUnit, Encounter, GameConfig
)


class GameDataLoader:
    """Loads and parses all game data from JSON files."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.battle_dir = self.data_dir / "Assets" / "Config" / "battle"

        # Loaded data
        self.config: Optional[GameConfig] = None
        self.abilities: dict[int, Ability] = {}
        self.units: dict[int, UnitTemplate] = {}
        self.status_effects: dict[int, StatusEffect] = {}
        self.encounters: dict[int, Encounter] = {}

    def load_all(self) -> None:
        """Load all game data."""
        self._load_config()
        self._load_status_effects()
        self._load_abilities()
        self._load_units()
        self._load_encounters()

    def _load_json(self, filename: str) -> dict:
        """Load a JSON file from the battle config directory."""
        filepath = self.battle_dir / filename
        if not filepath.exists():
            # Try root config dir
            filepath = self.data_dir / "Assets" / "Config" / filename
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_config(self) -> None:
        """Load battle configuration."""
        data = self._load_json("battle_config.json")

        # Parse class damage modifiers
        class_damage_mods = {}
        for class_id, class_data in data.get("classes", {}).get("class_types", {}).items():
            class_id = int(class_id)
            mods = {}
            for target_class, mult in class_data.get("damage_mods", {}).items():
                mods[int(target_class)] = float(mult)
            class_damage_mods[class_id] = mods

        # Parse tag hierarchy
        tag_hierarchy = {}
        for parent_tag, child_tags in data.get("tag_hierarchy", {}).items():
            tag_hierarchy[int(parent_tag)] = [int(t) for t in child_tags]

        # Parse layouts
        layouts = {}
        for layout_id, layout_data in data.get("layouts", {}).items():
            layout_id = int(layout_id)
            base_grids = layout_data.get("base_grids", {})

            attacker_grid = np.array(base_grids.get("attacker", []), dtype=np.int8)
            defender_grid = np.array(base_grids.get("defender", []), dtype=np.int8)
            defender_wall = layout_data.get("defender_wall", [])

            layouts[layout_id] = GridLayout(
                id=layout_id,
                attacker_grid=attacker_grid,
                defender_grid=defender_grid,
                defender_wall=defender_wall
            )

        # Get thresholds
        class_configs = data.get("classes", {}).get("configs", {})

        self.config = GameConfig(
            class_damage_mods=class_damage_mods,
            layouts=layouts,
            tag_hierarchy=tag_hierarchy,
            good_vs_cutoff=class_configs.get("good_vs_cutoff", 1.1),
            weak_vs_cutoff=class_configs.get("weak_vs_cutoff", 0.85)
        )

    def _load_status_effects(self) -> None:
        """Load status effect definitions."""
        data = self._load_json("status_effects.json")

        for effect_id, effect_data in data.items():
            effect_id = int(effect_id)
            effect_type = StatusEffectType(effect_data.get("status_effect_type", 1))

            # Parse DOT damage mods
            stun_damage_mods = {}
            for dtype, mult in effect_data.get("stun_damage_mods", {}).items():
                stun_damage_mods[int(dtype)] = float(mult)

            stun_armor_damage_mods = {}
            for dtype, mult in effect_data.get("stun_armor_damage_mods", {}).items():
                stun_armor_damage_mods[int(dtype)] = float(mult)

            self.status_effects[effect_id] = StatusEffect(
                id=effect_id,
                effect_type=effect_type,
                family=StatusEffectFamily(effect_data.get("family", 5)),
                duration=effect_data.get("duration", 1),
                dot_damage_type=DamageType(effect_data.get("dot_damage_type", 5)),
                dot_ability_damage_mult=effect_data.get("dot_ability_damage_mult", 1.0),
                dot_bonus_damage=effect_data.get("dot_bonus_damage", 0),
                dot_ap_percent=effect_data.get("dot_ap_percent", 0.0),
                dot_diminishing=effect_data.get("dot_diminishing", True),
                stun_block_action=effect_data.get("stun_block_action", False),
                stun_block_movement=effect_data.get("stun_block_movement", False),
                stun_damage_break=effect_data.get("stun_damage_break", False),
                stun_damage_mods=stun_damage_mods,
                stun_armor_damage_mods=stun_armor_damage_mods
            )

    def _parse_damage_area(self, area_data: list[dict]) -> list[DamageArea]:
        """Parse damage area pattern."""
        result = []
        for entry in area_data:
            pos_data = entry.get("pos", {})
            result.append(DamageArea(
                pos=Position(x=pos_data.get("x", 0), y=pos_data.get("y", 0)),
                damage_percent=entry.get("damage_percent", 100.0),
                order=entry.get("order", 1)
            ))
        return result

    def _parse_target_area(self, area_data: dict) -> Optional[TargetArea]:
        """Parse targeting area configuration."""
        if not area_data:
            return None

        data_list = self._parse_damage_area(area_data.get("data", []))

        return TargetArea(
            target_type=TargetType(area_data.get("target_type", 2)),
            data=data_list,
            random=area_data.get("random", False),
            aoe_order_delay=area_data.get("aoe_order_delay", 0.0)
        )

    def _load_abilities(self) -> None:
        """Load ability definitions."""
        data = self._load_json("battle_abilities.json")

        for ability_id, ability_data in data.items():
            ability_id = int(ability_id)
            stats_data = ability_data.get("stats", {})

            # Parse critical bonuses (tag-based crit bonus)
            critical_bonuses = {}
            for tag, bonus in stats_data.get("critical_bonuses", {}).items():
                critical_bonuses[int(tag)] = float(bonus)

            # Parse status effects
            status_effects = {}
            for effect_id, chance in stats_data.get("status_effects", {}).items():
                status_effects[int(effect_id)] = float(chance)

            # Parse damage area
            damage_area = self._parse_damage_area(stats_data.get("damage_area", []))

            # Parse target area
            target_area = self._parse_target_area(stats_data.get("target_area"))

            stats = AbilityStats(
                ability_cooldown=stats_data.get("ability_cooldown", 0),
                global_cooldown=stats_data.get("global_cooldown", 0),
                ammo_required=stats_data.get("ammo_required", 0),
                charge_time=stats_data.get("charge_time", 0),
                attack=stats_data.get("attack", 0),
                attacks_per_use=stats_data.get("attacks_per_use", 1),
                shots_per_attack=stats_data.get("shots_per_attack", 1),
                damage=stats_data.get("damage", 0),
                damage_type=DamageType(stats_data.get("damage_type", 1)),
                secondary_damage_percent=stats_data.get("secondary_damage_percent", 0.0),
                armor_piercing_percent=stats_data.get("armor_piercing_percent", 0.0),
                attack_from_unit=stats_data.get("attack_from_unit", 1.0),
                attack_from_weapon=stats_data.get("attack_from_weapon", 1.0),
                damage_from_unit=stats_data.get("damage_from_unit", 1.0),
                damage_from_weapon=stats_data.get("damage_from_weapon", 1.0),
                crit_from_unit=stats_data.get("crit_from_unit", 1.0),
                crit_from_weapon=stats_data.get("crit_from_weapon", 1.0),
                critical_hit_percent=stats_data.get("critical_hit_percent", 0.0),
                critical_bonuses=critical_bonuses,
                min_range=stats_data.get("min_range", 1),
                max_range=stats_data.get("max_range", 5),
                max_range_mod_atk=stats_data.get("max_range_mod_atk", 0.0),
                line_of_fire=LineOfFire(stats_data.get("line_of_fire", 3)),
                attack_direction=AttackDirection(stats_data.get("attack_direction", 1)),
                damage_area=damage_area,
                target_area=target_area,
                targets=stats_data.get("targets", []),
                status_effects=status_effects,
                damage_distraction=stats_data.get("damage_distraction", 0.0),
                damage_distraction_bonus=stats_data.get("damage_distraction_bonus", 0.0),
                capture=stats_data.get("capture", False),
                min_hp_percent=stats_data.get("min_hp_percent", 0.0)
            )

            self.abilities[ability_id] = Ability(
                id=ability_id,
                name=ability_data.get("name", f"ability_{ability_id}"),
                icon=ability_data.get("icon", ""),
                damage_animation_type=ability_data.get("damage_animation_type", ""),
                stats=stats
            )

    def _parse_damage_mods(self, mods_data: dict) -> dict[str, float]:
        """Parse damage modifier dictionary."""
        result = {}
        for dtype_name, mult in mods_data.items():
            result[dtype_name] = float(mult)
        return result

    def _load_units(self) -> None:
        """Load unit definitions."""
        data = self._load_json("battle_units.json")

        for unit_id, unit_configs in data.items():
            unit_id = int(unit_id)

            # Unit data is a list of config objects
            identity = None
            stats_config = None
            weapons_config = None

            for config in unit_configs:
                config_type = config.get("_t", "")
                if config_type == "battle_unit_identity_config":
                    identity = config
                elif config_type == "battle_unit_stats_config":
                    stats_config = config
                elif config_type == "battle_unit_weapons_config":
                    weapons_config = config

            if not identity:
                continue

            # Store all rank stats for this unit
            all_rank_stats = []
            if stats_config:
                stats_list = stats_config.get("stats", [])
                for rank_idx, s in enumerate(stats_list):
                    rank_stats = UnitStats(
                        hp=s.get("hp", 100),
                        defense=s.get("defense", 0),
                        accuracy=s.get("accuracy", 0),
                        dodge=s.get("dodge", 0),
                        critical=s.get("critical", 0.0),
                        bravery=s.get("bravery", 0),
                        power=s.get("power", 0),
                        blocking=stats_config.get("blocking", 0),
                        armor_hp=s.get("armor_hp", 0),
                        armor_def_style=s.get("armor_def_style", 0),
                        damage_mods=self._parse_damage_mods(s.get("damage_mods", {})),
                        armor_damage_mods=self._parse_damage_mods(s.get("armor_damage_mods", {})),
                        status_effect_immunities=stats_config.get("status_effect_immunities", []),
                        size=s.get("size", 1),
                        ability_slots=s.get("ability_slots", 2),
                        preferred_row=stats_config.get("preferred_row", 1),
                        pv=s.get("pv", 0)
                    )
                    all_rank_stats.append(rank_stats)

            # Default to rank 1 (index 0) if no stats specified
            unit_stats = all_rank_stats[0] if all_rank_stats else UnitStats()

            # Parse weapons
            weapons = {}
            if weapons_config:
                for weapon_id, weapon_data in weapons_config.get("weapons", {}).items():
                    weapon_id = int(weapon_id)
                    w_stats = weapon_data.get("stats", {})
                    weapons[weapon_id] = Weapon(
                        id=weapon_id,
                        name=weapon_data.get("name", f"weapon_{weapon_id}"),
                        abilities=weapon_data.get("abilities", []),
                        stats=WeaponStats(
                            ammo=w_stats.get("ammo", -1),
                            base_atk=w_stats.get("base_atk", 0),
                            base_damage_min=w_stats.get("base_damage_min", 0),
                            base_damage_max=w_stats.get("base_damage_max", 0),
                            base_crit_percent=w_stats.get("base_crit_percent", 0.0),
                            range_bonus=w_stats.get("range_bonus", 0)
                        )
                    )

            self.units[unit_id] = UnitTemplate(
                id=unit_id,
                name=identity.get("name", f"unit_{unit_id}"),
                short_name=identity.get("short_name", ""),
                description=identity.get("description", ""),
                icon=identity.get("icon", ""),
                class_type=UnitClass(identity.get("class_name", 13)),
                side=Side(identity.get("side", 2)),
                tags=identity.get("tags", []),
                stats=unit_stats,
                all_rank_stats=all_rank_stats,  # Store all rank stats
                weapons=weapons,
                unimportant=stats_config.get("unimportant", False) if stats_config else False
            )

    def _load_encounters(self) -> None:
        """Load encounter definitions."""
        data = self._load_json("battle_encounters.json")
        armies = data.get("armies", data)  # Handle both formats

        for enc_id, enc_data in armies.items():
            enc_id = int(enc_id)

            # Parse enemy units
            enemy_units = []
            for unit_data in enc_data.get("units", []):
                enemy_units.append(EncounterUnit(
                    grid_id=unit_data.get("grid_id", 0),
                    unit_id=unit_data.get("unit_id", 0),
                    rank=unit_data.get("rank", 1)  # Default to rank 1 if not specified
                ))

            # Parse player units (for story battles)
            player_units = []
            for unit_data in enc_data.get("player_units", []):
                player_units.append(EncounterUnit(
                    grid_id=unit_data.get("grid_id", 0),
                    unit_id=unit_data.get("unit_id", 0),
                    rank=unit_data.get("rank", 1)  # Default to rank 1 if not specified
                ))

            self.encounters[enc_id] = Encounter(
                id=enc_id,
                name=enc_data.get("name", f"encounter_{enc_id}"),
                level=enc_data.get("level", 1),
                layout_id=enc_data.get("layout_id", 2),
                enemy_units=enemy_units,
                player_units=player_units,
                attacker_slots=enc_data.get("attacker_slots", 8),
                attacker_defense_slots=enc_data.get("attacker_defense_slots", 0),
                is_player_attacker=enc_data.get("is_player_attacker", True),
                regen=enc_data.get("regen", True)
            )

    def get_unit(self, unit_id: int) -> Optional[UnitTemplate]:
        """Get a unit template by ID."""
        return self.units.get(unit_id)

    def get_ability(self, ability_id: int) -> Optional[Ability]:
        """Get an ability by ID."""
        return self.abilities.get(ability_id)

    def get_encounter(self, encounter_id: int) -> Optional[Encounter]:
        """Get an encounter by ID."""
        return self.encounters.get(encounter_id)

    def get_layout(self, layout_id: int) -> Optional[GridLayout]:
        """Get a grid layout by ID."""
        if self.config:
            return self.config.layouts.get(layout_id)
        return None

    def get_class_damage_mod(self, attacker_class: int, defender_class: int) -> float:
        """Get the damage multiplier between two classes."""
        if self.config:
            return self.config.class_damage_mods.get(attacker_class, {}).get(defender_class, 1.0)
        return 1.0
