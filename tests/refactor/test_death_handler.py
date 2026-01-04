"""Tests for Death Handler."""
import pytest
from unittest.mock import Mock

from src.simulator.battle import BattleUnit
from src.simulator.battle_engine.death_handler import DeathHandler
from src.simulator.models import Position, UnitTemplate, UnitStats
from src.simulator.enums import Side, UnitClass, BattleSide


@pytest.fixture
def basic_unit_template():
    """Create a basic unit template for testing."""
    stats = UnitStats(
        hp=100,
        armor_hp=50,
        defense=5,
        dodge=10,
        accuracy=10,
        critical=5.0,
        power=10,
        bravery=5
    )
    return UnitTemplate(
        id=1,
        name="Test Unit",
        class_type=UnitClass.SOLDIER,
        side=Side.PLAYER,
        stats=stats
    )


@pytest.fixture
def unimportant_unit_template():
    """Create an unimportant unit template for testing."""
    stats = UnitStats(
        hp=50,
        armor_hp=0,
        defense=2,
        dodge=5,
        accuracy=5,
        critical=2.0,
        power=5,
        bravery=2
    )
    template = UnitTemplate(
        id=2,
        name="Unimportant Unit",
        class_type=UnitClass.SOLDIER,
        side=Side.PLAYER,
        stats=stats
    )
    template.unimportant = True
    return template


@pytest.fixture
def mock_battle_state(basic_unit_template, unimportant_unit_template):
    """Create a mock BattleState for testing."""
    from copy import deepcopy
    
    # Create player units
    player_unit_1 = BattleUnit(
        template=basic_unit_template,
        position=Position(0, 0),
        battle_side=BattleSide.PLAYER_TEAM
    )
    player_unit_2 = BattleUnit(
        template=basic_unit_template,
        position=Position(1, 0),
        battle_side=BattleSide.PLAYER_TEAM
    )
    player_unit_3 = BattleUnit(
        template=unimportant_unit_template,
        position=Position(2, 0),
        battle_side=BattleSide.PLAYER_TEAM
    )
    
    # Create enemy units
    enemy_unit_1 = BattleUnit(
        template=basic_unit_template,
        position=Position(0, 2),
        battle_side=BattleSide.ENEMY_TEAM
    )
    enemy_unit_2 = BattleUnit(
        template=basic_unit_template,
        position=Position(1, 2),
        battle_side=BattleSide.ENEMY_TEAM
    )
    
    # Create mock battle state
    battle = Mock()
    battle.player_units = {
        player_unit_1.position: player_unit_1,
        player_unit_2.position: player_unit_2,
        player_unit_3.position: player_unit_3,
    }
    battle.enemy_units = {
        enemy_unit_1.position: enemy_unit_1,
        enemy_unit_2.position: enemy_unit_2,
    }
    
    return battle, {
        'player_unit_1': player_unit_1,
        'player_unit_2': player_unit_2,
        'player_unit_3': player_unit_3,
        'enemy_unit_1': enemy_unit_1,
        'enemy_unit_2': enemy_unit_2,
    }


class TestCheckForDeadUnits:
    """Tests for check_for_dead_units method."""

    def test_remove_dead_player_unit(self, mock_battle_state):
        """Test removing a dead player unit."""
        battle, units = mock_battle_state
        
        # Kill one player unit
        units['player_unit_1'].current_hp = 0
        
        initial_count = len(battle.player_units)
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Dead unit should be removed
        assert len(battle.player_units) == initial_count - 1
        assert units['player_unit_1'].position not in battle.player_units
        # Other units should still be there
        assert units['player_unit_2'].position in battle.player_units
        assert units['player_unit_3'].position in battle.player_units

    def test_remove_dead_enemy_unit(self, mock_battle_state):
        """Test removing a dead enemy unit."""
        battle, units = mock_battle_state
        
        # Kill one enemy unit
        units['enemy_unit_1'].current_hp = 0
        
        initial_count = len(battle.enemy_units)
        DeathHandler.check_for_dead_units(battle, BattleSide.ENEMY_TEAM)
        
        # Dead unit should be removed
        assert len(battle.enemy_units) == initial_count - 1
        assert units['enemy_unit_1'].position not in battle.enemy_units
        # Other unit should still be there
        assert units['enemy_unit_2'].position in battle.enemy_units

    def test_remove_multiple_dead_player_units(self, mock_battle_state):
        """Test removing multiple dead player units."""
        battle, units = mock_battle_state
        
        # Kill two player units
        units['player_unit_1'].current_hp = 0
        units['player_unit_2'].current_hp = 0
        
        initial_count = len(battle.player_units)
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Both dead units should be removed
        assert len(battle.player_units) == initial_count - 2
        assert units['player_unit_1'].position not in battle.player_units
        assert units['player_unit_2'].position not in battle.player_units
        # Unimportant unit should still be there
        assert units['player_unit_3'].position in battle.player_units

    def test_remove_unit_with_negative_hp(self, mock_battle_state):
        """Test removing a unit with negative HP."""
        battle, units = mock_battle_state
        
        # Set HP to negative
        units['player_unit_1'].current_hp = -10
        
        initial_count = len(battle.player_units)
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Unit should be removed
        assert len(battle.player_units) == initial_count - 1
        assert units['player_unit_1'].position not in battle.player_units

    def test_no_removal_when_all_alive(self, mock_battle_state):
        """Test that no units are removed when all are alive."""
        battle, units = mock_battle_state
        
        initial_player_count = len(battle.player_units)
        initial_enemy_count = len(battle.enemy_units)
        
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        DeathHandler.check_for_dead_units(battle, BattleSide.ENEMY_TEAM)
        
        # All units should still be there
        assert len(battle.player_units) == initial_player_count
        assert len(battle.enemy_units) == initial_enemy_count

    def test_only_remove_from_specified_side(self, mock_battle_state):
        """Test that only units from the specified side are removed."""
        battle, units = mock_battle_state
        
        # Kill one player and one enemy unit
        units['player_unit_1'].current_hp = 0
        units['enemy_unit_1'].current_hp = 0
        
        initial_player_count = len(battle.player_units)
        initial_enemy_count = len(battle.enemy_units)
        
        # Only remove player units
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Player unit should be removed, enemy unit should remain
        assert len(battle.player_units) == initial_player_count - 1
        assert len(battle.enemy_units) == initial_enemy_count
        assert units['player_unit_1'].position not in battle.player_units
        assert units['enemy_unit_1'].position in battle.enemy_units


class TestCheckAllUnitsDead:
    """Tests for check_all_units_dead method."""

    def test_all_player_units_dead(self, mock_battle_state):
        """Test when all player units are dead."""
        battle, units = mock_battle_state
        
        # Kill all player units
        units['player_unit_1'].current_hp = 0
        units['player_unit_2'].current_hp = 0
        units['player_unit_3'].current_hp = 0
        
        # Remove dead units first
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Check if all are dead
        assert DeathHandler.check_all_units_dead(battle, BattleSide.PLAYER_TEAM) is True

    def test_some_player_units_alive(self, mock_battle_state):
        """Test when some player units are still alive."""
        battle, units = mock_battle_state
        
        # Kill only one player unit
        units['player_unit_1'].current_hp = 0
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Not all are dead
        assert DeathHandler.check_all_units_dead(battle, BattleSide.PLAYER_TEAM) is False

    def test_all_enemy_units_dead(self, mock_battle_state):
        """Test when all enemy units are dead."""
        battle, units = mock_battle_state
        
        # Kill all enemy units
        units['enemy_unit_1'].current_hp = 0
        units['enemy_unit_2'].current_hp = 0
        
        # Remove dead units first
        DeathHandler.check_for_dead_units(battle, BattleSide.ENEMY_TEAM)
        
        # Check if all are dead
        assert DeathHandler.check_all_units_dead(battle, BattleSide.ENEMY_TEAM) is True

    def test_unimportant_units_ignored(self, mock_battle_state):
        """Test that unimportant units are ignored when checking if all are dead."""
        battle, units = mock_battle_state
        
        # Kill all important player units, but leave unimportant one alive
        units['player_unit_1'].current_hp = 0
        units['player_unit_2'].current_hp = 0
        # player_unit_3 is unimportant, leave it alive
        
        # Remove dead units
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # All important units are dead, so should return True
        assert DeathHandler.check_all_units_dead(battle, BattleSide.PLAYER_TEAM) is True

    def test_unimportant_unit_only_alive(self, mock_battle_state):
        """Test when only unimportant unit is alive."""
        battle, units = mock_battle_state
        
        # Kill all important units
        units['player_unit_1'].current_hp = 0
        units['player_unit_2'].current_hp = 0
        # player_unit_3 (unimportant) remains alive
        
        # Remove dead units
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # Should return True since all important units are dead
        assert DeathHandler.check_all_units_dead(battle, BattleSide.PLAYER_TEAM) is True

    def test_empty_side_considered_dead(self, mock_battle_state):
        """Test that empty side is considered as all dead."""
        battle, units = mock_battle_state
        
        # Remove all enemy units
        units['enemy_unit_1'].current_hp = 0
        units['enemy_unit_2'].current_hp = 0
        DeathHandler.check_for_dead_units(battle, BattleSide.ENEMY_TEAM)
        
        # Empty side should return True
        assert len(battle.enemy_units) == 0
        assert DeathHandler.check_all_units_dead(battle, BattleSide.ENEMY_TEAM) is True

    def test_mixed_important_and_unimportant_dead(self, mock_battle_state):
        """Test when both important and unimportant units are dead."""
        battle, units = mock_battle_state
        
        # Kill all units including unimportant
        units['player_unit_1'].current_hp = 0
        units['player_unit_2'].current_hp = 0
        units['player_unit_3'].current_hp = 0
        
        # Remove dead units
        DeathHandler.check_for_dead_units(battle, BattleSide.PLAYER_TEAM)
        
        # All units are dead
        assert DeathHandler.check_all_units_dead(battle, BattleSide.PLAYER_TEAM) is True

