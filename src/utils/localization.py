"""Localization support for resolving game string keys to readable names."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


class LocalizationManager:
    """
    Manages game localization strings.

    Loads Unity localization tables and provides key->text lookup.
    """

    def __init__(self, localization_dir: str | Path):
        """
        Initialize localization manager.

        Args:
            localization_dir: Path to Assets/Localization directory
        """
        self.localization_dir = Path(localization_dir)
        self.tables_dir = self.localization_dir / "tables"

        # Key -> ID mapping (from shared data)
        self.key_to_id: dict[str, int] = {}

        # ID -> localized text (per language)
        self.id_to_text: dict[str, dict[int, str]] = {}

        # Direct key -> text cache
        self._cache: dict[str, dict[str, str]] = {}

        # Current language
        self.current_language = "en"

    def load(self, table_name: str = "GameText", language: str = "en") -> None:
        """
        Load a localization table.

        Args:
            table_name: Name of the table (e.g., "GameText", "DynamicUIStrings")
            language: Language code (e.g., "en", "de", "fr")
        """
        self.current_language = language

        # Load shared data (key -> ID mapping)
        shared_file = self.tables_dir / f"{table_name} Shared Data.json"
        if shared_file.exists():
            self._load_shared_data(shared_file, table_name)

        # Load language-specific data (ID -> text mapping)
        lang_file = self.tables_dir / f"{table_name}_{language}.json"
        if lang_file.exists():
            self._load_language_data(lang_file, table_name, language)

    def _load_shared_data(self, filepath: Path, table_name: str) -> None:
        """Load shared data file containing key -> ID mappings."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = data.get("m_Entries", [])
        for entry in entries:
            key = entry.get("m_Key", "")
            entry_id = entry.get("m_Id", 0)
            if key and entry_id:
                self.key_to_id[key] = entry_id

        print(f"Loaded {len(entries)} localization keys from {table_name}")

    def _load_language_data(self, filepath: Path, table_name: str, language: str) -> None:
        """Load language-specific data containing ID -> text mappings."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if language not in self.id_to_text:
            self.id_to_text[language] = {}

        table_data = data.get("m_TableData", [])
        for entry in table_data:
            entry_id = entry.get("m_Id", 0)
            text = entry.get("m_Localized", "")
            if entry_id and text:
                self.id_to_text[language][entry_id] = text

        print(f"Loaded {len(table_data)} translations for {language}")

    def get(self, key: str, language: str = None) -> str:
        """
        Get localized text for a key.

        Args:
            key: The localization key (e.g., "abil_air_agent_orange_name")
            language: Language code (defaults to current_language)

        Returns:
            Localized text, or the key itself if not found
        """
        language = language or self.current_language

        # Check cache first
        cache_key = f"{language}:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Look up ID from key
        entry_id = self.key_to_id.get(key)
        if entry_id is None:
            return key  # Return key as-is if not found

        # Look up text from ID
        lang_data = self.id_to_text.get(language, {})
        text = lang_data.get(entry_id, key)

        # Cache result
        self._cache[cache_key] = text
        return text

    def get_or_default(self, key: str, default: str = None, language: str = None) -> str:
        """
        Get localized text or a default value.

        Args:
            key: The localization key
            default: Default value if key not found (defaults to key itself)
            language: Language code

        Returns:
            Localized text, default, or the key
        """
        result = self.get(key, language)
        if result == key:  # Not found
            return default if default is not None else key
        return result

    def resolve_unit_name(self, name_key: str) -> str:
        """Resolve a unit name key to readable text."""
        return self.get(name_key)

    def resolve_ability_name(self, name_key: str) -> str:
        """Resolve an ability name key to readable text."""
        return self.get(name_key)

    def resolve_description(self, desc_key: str) -> str:
        """Resolve a description key to readable text."""
        return self.get(desc_key)

    def search(self, query: str, limit: int = 20) -> list[tuple[str, str]]:
        """
        Search for localization entries containing the query.

        Args:
            query: Search string (case-insensitive)
            limit: Maximum results to return

        Returns:
            List of (key, text) tuples
        """
        query_lower = query.lower()
        results = []

        lang_data = self.id_to_text.get(self.current_language, {})

        for key, entry_id in self.key_to_id.items():
            text = lang_data.get(entry_id, "")
            if query_lower in key.lower() or query_lower in text.lower():
                results.append((key, text))
                if len(results) >= limit:
                    break

        return results

    def get_all_keys_with_prefix(self, prefix: str) -> list[tuple[str, str]]:
        """
        Get all keys starting with a prefix.

        Useful for finding all abilities (prefix="abil_") or units (prefix="air_", "veh_", etc.)

        Args:
            prefix: Key prefix to search for

        Returns:
            List of (key, text) tuples
        """
        results = []
        lang_data = self.id_to_text.get(self.current_language, {})

        for key, entry_id in self.key_to_id.items():
            if key.startswith(prefix):
                text = lang_data.get(entry_id, key)
                results.append((key, text))

        return sorted(results, key=lambda x: x[0])


class LocalizedDataLoader:
    """
    Wrapper that adds localization support to GameDataLoader.

    Enhances data loading with proper names instead of key strings.
    """

    def __init__(self, data_loader, localization: LocalizationManager):
        """
        Initialize localized data loader.

        Args:
            data_loader: GameDataLoader instance
            localization: LocalizationManager instance
        """
        self.data_loader = data_loader
        self.loc = localization

    def get_unit_display_name(self, unit_id: int) -> str:
        """Get the display name for a unit."""
        unit = self.data_loader.get_unit(unit_id)
        if unit:
            return self.loc.resolve_unit_name(unit.name)
        return f"Unit {unit_id}"

    def get_ability_display_name(self, ability_id: int) -> str:
        """Get the display name for an ability."""
        ability = self.data_loader.get_ability(ability_id)
        if ability:
            return self.loc.resolve_ability_name(ability.name)
        return f"Ability {ability_id}"

    def get_unit_info(self, unit_id: int) -> dict:
        """Get detailed unit info with localized names."""
        unit = self.data_loader.get_unit(unit_id)
        if not unit:
            return {}

        info = {
            "id": unit_id,
            "name": self.loc.resolve_unit_name(unit.name),
            "short_name": self.loc.get(unit.short_name) if unit.short_name else "",
            "description": self.loc.resolve_description(unit.description) if unit.description else "",
            "class": unit.class_type.name,
            "tags": unit.tags,
            "stats": {
                "hp": unit.stats.hp,
                "defense": unit.stats.defense,
                "dodge": unit.stats.dodge,
                "accuracy": unit.stats.accuracy,
                "critical": unit.stats.critical,
                "power": unit.stats.power,
            },
            "weapons": []
        }

        for weapon_id, weapon in unit.weapons.items():
            weapon_info = {
                "id": weapon_id,
                "name": self.loc.get(weapon.name) if weapon.name else f"Weapon {weapon_id}",
                "damage_range": (weapon.stats.base_damage_min, weapon.stats.base_damage_max),
                "abilities": []
            }

            for ability_id in weapon.abilities:
                ability = self.data_loader.get_ability(ability_id)
                if ability:
                    weapon_info["abilities"].append({
                        "id": ability_id,
                        "name": self.loc.resolve_ability_name(ability.name),
                        "range": (ability.stats.min_range, ability.stats.max_range),
                        "targets": ability.stats.targets,
                        "damage_type": ability.stats.damage_type.name,
                    })

            info["weapons"].append(weapon_info)

        return info


def create_localized_loader(data_dir: str) -> tuple:
    """
    Convenience function to create both data loader and localization.

    Args:
        data_dir: Path to data directory

    Returns:
        Tuple of (GameDataLoader, LocalizationManager, LocalizedDataLoader)
    """
    from src.simulator.data_loader import GameDataLoader

    data_path = Path(data_dir)

    # Load game data
    data_loader = GameDataLoader(data_dir)
    data_loader.load_all()

    # Load localization
    loc_dir = data_path / "Assets" / "Localization"
    loc = LocalizationManager(loc_dir)
    loc.load("GameText", "en")

    # Create localized wrapper
    localized = LocalizedDataLoader(data_loader, loc)

    return data_loader, loc, localized
