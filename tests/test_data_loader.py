"""Tests for data loader."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_loader import GameData, get_game_data
from src.models import Side


class TestDataLoader:
    """Test suite for data loading."""

    @pytest.fixture
    def game_data(self):
        """Load game data fixture."""
        return get_game_data()

    def test_load_all_data(self, game_data):
        """Test that all data loads without errors."""
        assert game_data is not None
        assert len(game_data.units) > 0
        assert len(game_data.abilities) > 0
        assert len(game_data.encounters) > 0
        assert len(game_data.status_effects) > 0
        assert len(game_data.class_configs) > 0
        assert len(game_data.layouts) > 0

    def test_unit_count(self, game_data):
        """Test that we have expected number of units."""
        # Should have 700+ units according to docs
        assert len(game_data.units) >= 100  # At least some units

    def test_ability_count(self, game_data):
        """Test that we have expected number of abilities."""
        # Should have 300+ abilities
        assert len(game_data.abilities) >= 100

    def test_unit_has_required_fields(self, game_data):
        """Test that units have required fields."""
        for unit_id, unit in list(game_data.units.items())[:10]:
            assert unit.id == unit_id
            assert unit.name is not None
            assert unit.class_id >= 0
            assert unit.side in [Side.PLAYER, Side.HOSTILE, Side.VILLAIN, Side.HERO, Side.NEUTRAL, Side.TEST]

    def test_unit_has_stats(self, game_data):
        """Test that units have stats."""
        for unit_id, unit in list(game_data.units.items())[:10]:
            assert len(unit.stats_by_level) >= 1
            stats = unit.stats_by_level[0]
            assert stats.hp > 0

    def test_unit_has_weapons(self, game_data):
        """Test that units have weapons."""
        units_with_weapons = [u for u in game_data.units.values() if u.weapons]
        assert len(units_with_weapons) > 0

        for unit in units_with_weapons[:10]:
            for weapon_id, weapon in unit.weapons.items():
                assert len(weapon.abilities) > 0
                assert weapon.stats is not None

    def test_ability_has_stats(self, game_data):
        """Test that abilities have stats."""
        for ability_id, ability in list(game_data.abilities.items())[:10]:
            assert ability.id == ability_id
            assert ability.stats is not None
            assert ability.stats.max_range >= ability.stats.min_range

    def test_encounter_has_units(self, game_data):
        """Test that encounters have unit placements."""
        encounters_with_units = [e for e in game_data.encounters.values() if e.waves]
        assert len(encounters_with_units) > 0

        for encounter in encounters_with_units[:10]:
            assert len(encounter.waves) >= 1
            wave = encounter.waves[0]
            assert len(wave.units) >= 1

    def test_layout_grids(self, game_data):
        """Test that layouts have valid grids."""
        for layout_id, layout in game_data.layouts.items():
            assert layout.attacker_grid is not None
            assert layout.defender_grid is not None
            assert len(layout.attacker_grid) > 0

            # Check that grids have valid cell values (1 or 2)
            for row in layout.attacker_grid:
                for cell in row:
                    assert cell in [1, 2]

    def test_status_effects(self, game_data):
        """Test status effect definitions."""
        for effect_id, effect in game_data.status_effects.items():
            assert effect.id == effect_id
            assert effect.duration >= 1
            assert effect.family >= 0

    def test_class_configs(self, game_data):
        """Test class configurations."""
        for class_id, config in game_data.class_configs.items():
            assert config.id == class_id
            assert config.display_name is not None

    def test_get_player_units(self, game_data):
        """Test getting player-side units."""
        player_units = game_data.get_player_units()
        assert len(player_units) > 0
        for unit in player_units:
            assert unit.side == Side.PLAYER

    def test_get_enemy_units(self, game_data):
        """Test getting enemy-side units."""
        enemy_units = game_data.get_enemy_units()
        assert len(enemy_units) > 0
        for unit in enemy_units:
            assert unit.side == Side.HOSTILE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
