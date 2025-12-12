"""
Data loader for BN Simulator.
Loads and parses game data from JSON files.
"""

import json
from pathlib import Path
from typing import Optional

from .models import (
    Ability, AbilityStats, ClassConfig, DamageAreaEntry, DamageType,
    Encounter, EncounterWave, GridLayout, Position, Side,
    StatusEffectTemplate, StatusEffectType, TargetArea, TargetAreaEntry,
    UnitStats, UnitTemplate, Weapon, WeaponStats
)


class GameData:
    """Container for all loaded game data."""

    def __init__(self, data_path: str = "data/Assets/Config"):
        self.data_path = Path(data_path)
        self.units: dict[int, UnitTemplate] = {}
        self.abilities: dict[int, Ability] = {}
        self.encounters: dict[int, Encounter] = {}
        self.status_effects: dict[int, StatusEffectTemplate] = {}
        self.class_configs: dict[int, ClassConfig] = {}
        self.layouts: dict[int, GridLayout] = {}

        # Damage type name to enum mapping
        self.damage_type_map = {
            "piercing": DamageType.PIERCING,
            "crushing": DamageType.CRUSHING,
            "cold": DamageType.COLD,
            "explosive": DamageType.EXPLOSIVE,
            "fire": DamageType.FIRE,
            "poison": DamageType.POISON,
        }

    def load_all(self):
        """Load all game data."""
        self._load_battle_config()
        self._load_abilities()
        self._load_status_effects()
        self._load_units()
        self._load_encounters()

    def _load_json(self, relative_path: str) -> dict:
        """Load a JSON file."""
        full_path = self.data_path / relative_path
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_battle_config(self):
        """Load battle configuration (classes, layouts)."""
        data = self._load_json("battle/battle_config.json")

        # Load class types
        class_types = data.get("classes", {}).get("class_types", {})
        for class_id_str, class_data in class_types.items():
            class_id = int(class_id_str)
            damage_mods = {}
            for target_id_str, mod in class_data.get("damage_mods", {}).items():
                damage_mods[int(target_id_str)] = mod

            self.class_configs[class_id] = ClassConfig(
                id=class_id,
                display_name=class_data.get("display_name", ""),
                damage_mods=damage_mods
            )

        # Load layouts
        layouts = data.get("layouts", {})
        for layout_id_str, layout_data in layouts.items():
            layout_id = int(layout_id_str)
            base_grids = layout_data.get("base_grids", {})

            self.layouts[layout_id] = GridLayout(
                id=layout_id,
                attacker_grid=base_grids.get("attacker", []),
                defender_grid=base_grids.get("defender", []),
                defender_wall=layout_data.get("defender_wall", [])
            )

    def _load_abilities(self):
        """Load ability definitions."""
        data = self._load_json("battle/battle_abilities.json")

        for ability_id_str, ability_data in data.items():
            ability_id = int(ability_id_str)
            stats_data = ability_data.get("stats", {})

            # Parse damage area
            damage_area = []
            for entry in stats_data.get("damage_area", []):
                pos_data = entry.get("pos", {})
                damage_area.append(DamageAreaEntry(
                    pos=Position(x=pos_data.get("x", 0), y=pos_data.get("y", 0)),
                    damage_percent=entry.get("damage_percent", 100),
                    order=entry.get("order", 1)
                ))

            # Parse target area
            target_area = None
            target_area_data = stats_data.get("target_area")
            if target_area_data:
                target_entries = []
                for entry in target_area_data.get("data", []):
                    pos_data = entry.get("pos", {})
                    target_entries.append(TargetAreaEntry(
                        pos=Position(x=pos_data.get("x", 0), y=pos_data.get("y", 0)),
                        damage_percent=entry.get("damage_percent", 100),
                        order=entry.get("order", 1),
                        weight=entry.get("weight", 100)
                    ))
                target_area = TargetArea(
                    data=target_entries,
                    target_type=target_area_data.get("target_type", 2),
                    random=target_area_data.get("random", False),
                    aoe_order_delay=target_area_data.get("aoe_order_delay", 0)
                )

            # Parse status effects
            status_effects = {}
            for effect_id_str, chance in stats_data.get("status_effects", {}).items():
                status_effects[int(effect_id_str)] = chance

            # Parse critical bonuses
            critical_bonuses = {}
            for tag_str, bonus in stats_data.get("critical_bonuses", {}).items():
                critical_bonuses[int(tag_str)] = bonus

            ability = Ability(
                id=ability_id,
                name=ability_data.get("name", ""),
                icon=ability_data.get("icon", ""),
                damage_animation_type=ability_data.get("damage_animation_type", ""),
                stats=AbilityStats(
                    attack=stats_data.get("attack", 0),
                    damage_type=stats_data.get("damage_type", 1),
                    min_range=stats_data.get("min_range", 1),
                    max_range=stats_data.get("max_range", 5),
                    line_of_fire=stats_data.get("line_of_fire", 3),
                    critical_hit_percent=stats_data.get("critical_hit_percent", 0),
                    armor_piercing_percent=stats_data.get("armor_piercing_percent", 0.0),
                    shots_per_attack=stats_data.get("shots_per_attack", 1),
                    attacks_per_use=stats_data.get("attacks_per_use", 1),
                    ability_cooldown=stats_data.get("ability_cooldown", 0),
                    global_cooldown=stats_data.get("global_cooldown", 0),
                    charge_time=stats_data.get("charge_time", 0),
                    ammo_required=stats_data.get("ammo_required", 0),
                    secondary_damage_percent=stats_data.get("secondary_damage_percent", 0),
                    damage_distraction=stats_data.get("damage_distraction", 0),
                    damage_distraction_bonus=stats_data.get("damage_distraction_bonus", 0),
                    capture=stats_data.get("capture", False),
                    min_hp_percent=stats_data.get("min_hp_percent", 0),
                    attack_from_unit=stats_data.get("attack_from_unit", 1.0),
                    attack_from_weapon=stats_data.get("attack_from_weapon", 1.0),
                    damage_from_unit=stats_data.get("damage_from_unit", 1.0),
                    damage_from_weapon=stats_data.get("damage_from_weapon", 1.0),
                    crit_from_unit=stats_data.get("crit_from_unit", 1.0),
                    crit_from_weapon=stats_data.get("crit_from_weapon", 1.0),
                ),
                damage_area=damage_area,
                target_area=target_area,
                targets=stats_data.get("targets", []),
                status_effects=status_effects,
                critical_bonuses=critical_bonuses
            )

            self.abilities[ability_id] = ability

    def _load_status_effects(self):
        """Load status effect definitions."""
        data = self._load_json("status_effects.json")

        for effect_id_str, effect_data in data.items():
            effect_id = int(effect_id_str)
            effect_type = StatusEffectType(effect_data.get("status_effect_type", 1))

            # Parse stun damage mods (convert string keys to int)
            stun_damage_mods = {}
            for dtype_str, mod in effect_data.get("stun_damage_mods", {}).items():
                stun_damage_mods[int(dtype_str)] = mod

            stun_armor_damage_mods = {}
            for dtype_str, mod in effect_data.get("stun_armor_damage_mods", {}).items():
                stun_armor_damage_mods[int(dtype_str)] = mod

            self.status_effects[effect_id] = StatusEffectTemplate(
                id=effect_id,
                duration=effect_data.get("duration", 1),
                family=effect_data.get("family", 0),
                effect_type=effect_type,
                dot_ability_damage_mult=effect_data.get("dot_ability_damage_mult", 1.0),
                dot_bonus_damage=effect_data.get("dot_bonus_damage", 0),
                dot_damage_type=effect_data.get("dot_damage_type", 5),
                dot_diminishing=effect_data.get("dot_diminishing", True),
                dot_ap_percent=effect_data.get("dot_ap_percent", 0),
                stun_block_action=effect_data.get("stun_block_action", False),
                stun_block_movement=effect_data.get("stun_block_movement", False),
                stun_damage_break=effect_data.get("stun_damage_break", False),
                stun_damage_mods=stun_damage_mods,
                stun_armor_damage_mods=stun_armor_damage_mods
            )

    def _load_units(self):
        """Load unit definitions."""
        data = self._load_json("battle/battle_units.json")

        for unit_id_str, configs in data.items():
            unit_id = int(unit_id_str)

            # Parse config sections
            identity = None
            stats_config = None
            weapons_config = None

            for config in configs:
                config_type = config.get("_t", "")
                if config_type == "battle_unit_identity_config":
                    identity = config
                elif config_type == "battle_unit_stats_config":
                    stats_config = config
                elif config_type == "battle_unit_weapons_config":
                    weapons_config = config

            if not identity:
                continue

            # Parse stats by level
            stats_by_level = []
            if stats_config:
                for stats_data in stats_config.get("stats", []):
                    # Parse damage mods
                    damage_mods = stats_data.get("damage_mods", {})
                    armor_damage_mods = stats_data.get("armor_damage_mods", {})

                    stats_by_level.append(UnitStats(
                        hp=stats_data.get("hp", 100),
                        power=stats_data.get("power", 0),
                        defense=stats_data.get("defense", 0),
                        accuracy=stats_data.get("accuracy", 0),
                        dodge=stats_data.get("dodge", 0),
                        bravery=stats_data.get("bravery", 0),
                        critical=stats_data.get("critical", 0),
                        ability_slots=stats_data.get("ability_slots", 2),
                        armor_hp=stats_data.get("armor_hp", 0),
                        armor_def_style=stats_data.get("armor_def_style", 0),
                        pv=stats_data.get("pv", 0),
                        damage_mods=damage_mods,
                        armor_damage_mods=armor_damage_mods
                    ))

            # Parse weapons
            weapons = {}
            if weapons_config:
                for weapon_id_str, weapon_data in weapons_config.get("weapons", {}).items():
                    weapon_id = int(weapon_id_str)
                    weapon_stats = weapon_data.get("stats", {})

                    weapons[weapon_id] = Weapon(
                        id=weapon_id,
                        name=weapon_data.get("name", ""),
                        abilities=weapon_data.get("abilities", []),
                        stats=WeaponStats(
                            ammo=weapon_stats.get("ammo", -1),
                            base_atk=weapon_stats.get("base_atk", 0),
                            base_crit_percent=weapon_stats.get("base_crit_percent", 0),
                            base_damage_min=weapon_stats.get("base_damage_min", 0),
                            base_damage_max=weapon_stats.get("base_damage_max", 0),
                            range_bonus=weapon_stats.get("range_bonus", 0)
                        )
                    )

            self.units[unit_id] = UnitTemplate(
                id=unit_id,
                name=identity.get("name", ""),
                class_id=identity.get("class_name", 0),
                side=Side(identity.get("side", 2)),
                tags=identity.get("tags", []),
                stats_by_level=stats_by_level,
                weapons=weapons,
                status_effect_immunities=stats_config.get("status_effect_immunities", []) if stats_config else [],
                preferred_row=stats_config.get("preferred_row", 1) if stats_config else 1,
                size=stats_config.get("size", 1) if stats_config else 1,
                blocking=stats_config.get("blocking", 0) if stats_config else 0,
                unimportant=stats_config.get("unimportant", False) if stats_config else False
            )

    def _load_encounters(self):
        """Load encounter definitions."""
        data = self._load_json("battle/battle_encounters.json")
        armies = data.get("armies", {})

        for encounter_id_str, encounter_data in armies.items():
            encounter_id = int(encounter_id_str)

            # Parse units in encounter
            units = []
            for unit_entry in encounter_data.get("units", []):
                units.append((
                    unit_entry.get("grid_id", 0),
                    unit_entry.get("unit_id", 0)
                ))

            # Parse player units (if any)
            player_units = []
            for unit_entry in encounter_data.get("player_units", []):
                player_units.append((
                    unit_entry.get("grid_id", 0),
                    unit_entry.get("unit_id", 0)
                ))

            # Create single wave for now (multi-wave encounters handled separately)
            waves = [EncounterWave(units=units)] if units else []

            self.encounters[encounter_id] = Encounter(
                id=encounter_id,
                name=encounter_data.get("name", ""),
                level=encounter_data.get("level", 1),
                layout_id=encounter_data.get("layout_id", 2),
                attacker_slots=encounter_data.get("attacker_slots", 5),
                waves=waves,
                player_units=player_units
            )

    def get_unit(self, unit_id: int) -> Optional[UnitTemplate]:
        """Get unit template by ID."""
        return self.units.get(unit_id)

    def get_ability(self, ability_id: int) -> Optional[Ability]:
        """Get ability by ID."""
        return self.abilities.get(ability_id)

    def get_encounter(self, encounter_id: int) -> Optional[Encounter]:
        """Get encounter by ID."""
        return self.encounters.get(encounter_id)

    def get_layout(self, layout_id: int) -> Optional[GridLayout]:
        """Get layout by ID."""
        return self.layouts.get(layout_id)

    def get_status_effect(self, effect_id: int) -> Optional[StatusEffectTemplate]:
        """Get status effect template by ID."""
        return self.status_effects.get(effect_id)

    def get_class_config(self, class_id: int) -> Optional[ClassConfig]:
        """Get class config by ID."""
        return self.class_configs.get(class_id)

    def get_player_units(self) -> list[UnitTemplate]:
        """Get all player-side units."""
        return [u for u in self.units.values() if u.side == Side.PLAYER]

    def get_enemy_units(self) -> list[UnitTemplate]:
        """Get all enemy-side units."""
        return [u for u in self.units.values() if u.side == Side.HOSTILE]


# Global instance for convenience
_game_data: Optional[GameData] = None


def get_game_data(data_path: str = "data/Assets/Config") -> GameData:
    """Get or create the global game data instance."""
    global _game_data
    if _game_data is None:
        _game_data = GameData(data_path)
        _game_data.load_all()
    return _game_data


def reload_game_data(data_path: str = "data/Assets/Config") -> GameData:
    """Force reload of game data."""
    global _game_data
    _game_data = GameData(data_path)
    _game_data.load_all()
    return _game_data
