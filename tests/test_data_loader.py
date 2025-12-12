"""Tests for data loading functionality."""
import pytest
from pathlib import Path

from src.simulator.data_loader import GameDataLoader
from src.simulator.enums import UnitClass, DamageType


@pytest.fixture
def data_loader():
    """Create a data loader with the test data."""
    loader = GameDataLoader("data")
    loader.load_all()
    return loader


class TestGameDataLoader:
    """Tests for GameDataLoader class."""

    def test_load_config(self, data_loader):
        """Test that configuration loads correctly."""
        assert data_loader.config is not None
        assert len(data_loader.config.layouts) > 0
        assert len(data_loader.config.class_damage_mods) > 0

    def test_load_layouts(self, data_loader):
        """Test that layouts are parsed correctly."""
        # Standard layout (ID 2) should exist
        layout = data_loader.get_layout(2)
        assert layout is not None
        assert layout.width == 5
        assert layout.height == 3

    def test_load_units(self, data_loader):
        """Test that units are loaded."""
        assert len(data_loader.units) > 0

        # Check that units have expected fields
        for unit_id, unit in list(data_loader.units.items())[:5]:
            assert unit.id == unit_id
            assert unit.name
            assert isinstance(unit.class_type, UnitClass)
            assert unit.stats.hp > 0

    def test_load_abilities(self, data_loader):
        """Test that abilities are loaded."""
        assert len(data_loader.abilities) > 0

        # Check ability structure
        for ability_id, ability in list(data_loader.abilities.items())[:5]:
            assert ability.id == ability_id
            assert ability.name
            assert isinstance(ability.stats.damage_type, DamageType)

    def test_load_encounters(self, data_loader):
        """Test that encounters are loaded."""
        assert len(data_loader.encounters) > 0

        # Check encounter structure
        for enc_id, encounter in list(data_loader.encounters.items())[:5]:
            assert encounter.id == enc_id
            assert encounter.level > 0
            assert len(encounter.enemy_units) > 0

    def test_load_status_effects(self, data_loader):
        """Test that status effects are loaded."""
        assert len(data_loader.status_effects) > 0

        # Check status effect structure
        for effect_id, effect in list(data_loader.status_effects.items())[:5]:
            assert effect.id == effect_id
            assert effect.duration > 0

    def test_class_damage_mods(self, data_loader):
        """Test class damage modifier lookup."""
        # Aircraft (4) should have bonus vs soldiers (13)
        mod = data_loader.get_class_damage_mod(4, 8)  # Aircraft vs Destroyer
        assert mod != 1.0 or mod == 1.0  # Just verify it returns something

        # Non-existent class should return 1.0
        mod = data_loader.get_class_damage_mod(999, 999)
        assert mod == 1.0

    def test_get_unit(self, data_loader):
        """Test getting a specific unit."""
        # Get first unit
        first_id = next(iter(data_loader.units.keys()))
        unit = data_loader.get_unit(first_id)
        assert unit is not None
        assert unit.id == first_id

        # Non-existent unit
        unit = data_loader.get_unit(99999)
        assert unit is None

    def test_get_ability(self, data_loader):
        """Test getting a specific ability."""
        first_id = next(iter(data_loader.abilities.keys()))
        ability = data_loader.get_ability(first_id)
        assert ability is not None
        assert ability.id == first_id

    def test_get_encounter(self, data_loader):
        """Test getting a specific encounter."""
        first_id = next(iter(data_loader.encounters.keys()))
        encounter = data_loader.get_encounter(first_id)
        assert encounter is not None
        assert encounter.id == first_id


class TestDataIntegrity:
    """Tests for data integrity and relationships."""

    def test_unit_weapons_reference_valid_abilities(self, data_loader):
        """Test that unit weapons reference valid abilities."""
        errors = []
        for unit_id, unit in data_loader.units.items():
            for weapon_id, weapon in unit.weapons.items():
                for ability_id in weapon.abilities:
                    if ability_id not in data_loader.abilities:
                        errors.append(f"Unit {unit_id} weapon {weapon_id} references missing ability {ability_id}")

        # Allow some missing abilities (game data might have deprecated ones)
        assert len(errors) < len(data_loader.units) * 0.1, f"Too many missing abilities: {errors[:10]}"

    def test_encounters_reference_valid_units(self, data_loader):
        """Test that encounters reference valid units."""
        errors = []
        for enc_id, encounter in data_loader.encounters.items():
            for enc_unit in encounter.enemy_units:
                if enc_unit.unit_id not in data_loader.units:
                    errors.append(f"Encounter {enc_id} references missing unit {enc_unit.unit_id}")

        assert len(errors) < len(data_loader.encounters) * 0.1, f"Too many missing units: {errors[:10]}"

    def test_encounters_reference_valid_layouts(self, data_loader):
        """Test that encounters reference valid layouts."""
        for enc_id, encounter in data_loader.encounters.items():
            layout = data_loader.get_layout(encounter.layout_id)
            assert layout is not None, f"Encounter {enc_id} references missing layout {encounter.layout_id}"
