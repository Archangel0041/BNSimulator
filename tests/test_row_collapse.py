"""Tests for Row Collapse functionality."""
import pytest
from unittest.mock import Mock, MagicMock

from src.simulator.battle import BattleUnit, BattleState
from src.simulator.battle_engine.player_turn_executor import PlayerTurnExecutor
from src.simulator.battle_engine.enemy_turn_executor import EnemyTurnExecutor
from src.simulator.models import Position, UnitTemplate, UnitStats, GridLayout
from src.simulator.enums import Side, UnitClass, BattleSide
from src.simulator.data_loader import GameDataLoader


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
def mock_data_loader():
    """Create a mock data loader."""
    loader = Mock(spec=GameDataLoader)
    return loader


@pytest.fixture
def mock_layout():
    """Create a mock grid layout."""
    layout = Mock(spec=GridLayout)
    layout.width = 5
    layout.height = 3
    return layout


@pytest.fixture
def battle_state_with_units(basic_unit_template, mock_data_loader, mock_layout):
    """Create a BattleState with units at specific positions."""
    # Create player units: one in row 1 (y=1), one in row 2 (y=2)
    # Front row (y=0) is empty
    player_unit_1 = BattleUnit(
        template=basic_unit_template,
        position=Position(x=0, y=1),
        battle_side=BattleSide.PLAYER_TEAM
    )
    player_unit_2 = BattleUnit(
        template=basic_unit_template,
        position=Position(x=1, y=2),
        battle_side=BattleSide.PLAYER_TEAM
    )
    
    # Create enemy units: one in row 1 (y=1)
    # Front row (y=0) is empty
    enemy_unit_1 = BattleUnit(
        template=basic_unit_template,
        position=Position(x=0, y=1),
        battle_side=BattleSide.ENEMY_TEAM
    )
    
    battle = BattleState(
        data_loader=mock_data_loader,
        layout=mock_layout,
        player_units=[player_unit_1, player_unit_2],
        enemy_units=[enemy_unit_1],
        player_is_attacker=True
    )
    
    return battle, {
        'player_unit_1': player_unit_1,
        'player_unit_2': player_unit_2,
        'enemy_unit_1': enemy_unit_1,
    }


@pytest.fixture
def battle_state_with_front_row_units(basic_unit_template, mock_data_loader, mock_layout):
    """Create a BattleState with units in the front row (should not collapse)."""
    # Create player unit in front row (y=0)
    player_unit_1 = BattleUnit(
        template=basic_unit_template,
        position=Position(x=0, y=0),
        battle_side=BattleSide.PLAYER_TEAM
    )
    
    # Create enemy unit in front row (y=0)
    enemy_unit_1 = BattleUnit(
        template=basic_unit_template,
        position=Position(x=0, y=0),
        battle_side=BattleSide.ENEMY_TEAM
    )
    
    battle = BattleState(
        data_loader=mock_data_loader,
        layout=mock_layout,
        player_units=[player_unit_1],
        enemy_units=[enemy_unit_1],
        player_is_attacker=True
    )
    
    return battle


class TestPlayerRowCollapse:
    """Tests for player row collapse."""
    
    def test_collapse_when_front_row_empty(self, battle_state_with_units):
        """Test that row collapses when front row is empty."""
        battle, units = battle_state_with_units
        
        # Verify initial state: units in rows 1 and 2, front row empty
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is False
        assert any(pos.y == 1 for pos in battle.player_units.keys()) is True
        assert any(pos.y == 2 for pos in battle.player_units.keys()) is True
        assert battle.player_rows_collapsed == 0
        
        # Create executor and collapse
        executor = PlayerTurnExecutor(battle)
        executor._step_collapse_player_front_row()
        
        # Verify collapse occurred: units moved forward by 1 row
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is True
        assert any(pos.y == 1 for pos in battle.player_units.keys()) is True
        assert any(pos.y == 2 for pos in battle.player_units.keys()) is False
        assert battle.player_rows_collapsed == 1
        
        # Verify unit positions were updated
        for pos, unit in battle.player_units.items():
            assert unit.position == pos
            assert unit.position.y < 3  # Should not go out of bounds
    
    def test_no_collapse_when_front_row_has_units(self, battle_state_with_front_row_units):
        """Test that row does not collapse when front row has units."""
        battle = battle_state_with_front_row_units
        
        # Verify initial state: unit in front row
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is True
        initial_positions = {pos: unit.position for pos, unit in battle.player_units.items()}
        assert battle.player_rows_collapsed == 0
        
        # Create executor and attempt collapse
        executor = PlayerTurnExecutor(battle)
        executor._step_collapse_player_front_row()
        
        # Verify no collapse occurred
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is True
        assert battle.player_rows_collapsed == 0
        
        # Verify positions unchanged
        for pos, unit in battle.player_units.items():
            assert unit.position == initial_positions[pos]
    
    def test_multiple_collapses(self, battle_state_with_units):
        """Test that multiple collapses increment counter correctly."""
        battle, units = battle_state_with_units
        
        executor = PlayerTurnExecutor(battle)
        
        # First collapse: row 1 -> row 0, row 2 -> row 1
        executor._step_collapse_player_front_row()
        assert battle.player_rows_collapsed == 1
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is True
        
        # Move units back to row 1 and 2 (simulate units moving back)
        # Actually, we need to manually set positions to test multiple collapses
        # Since collapse only happens when front row is empty, we need to clear front row again
        # Let's move all units to row 1 and 2 again
        units_to_move = list(battle.player_units.items())
        battle.player_units.clear()
        for old_pos, unit in units_to_move:
            # Move units to row 1 and 2 (skip row 0)
            new_y = old_pos.y + 1 if old_pos.y < 2 else 2
            new_pos = Position(x=old_pos.x, y=new_y)
            unit.position = new_pos
            battle.player_units[new_pos] = unit
        
        # Second collapse
        executor._step_collapse_player_front_row()
        assert battle.player_rows_collapsed == 2
    
    def test_collapse_updates_unit_positions(self, battle_state_with_units):
        """Test that unit position attributes are updated during collapse."""
        battle, units = battle_state_with_units
        
        # Store original positions
        original_positions = {pos: unit.position for pos, unit in battle.player_units.items()}
        
        executor = PlayerTurnExecutor(battle)
        executor._step_collapse_player_front_row()
        
        # Verify all unit positions were updated
        for pos, unit in battle.player_units.items():
            # Unit's position attribute should match dictionary key
            assert unit.position == pos
            # Position should be one row forward (y decreased by 1)
            original_pos = original_positions.get(pos)
            if original_pos:
                assert unit.position.y == original_pos.y - 1
                assert unit.position.x == original_pos.x


class TestEnemyRowCollapse:
    """Tests for enemy row collapse."""
    
    def test_collapse_when_front_row_empty(self, battle_state_with_units):
        """Test that enemy row collapses when front row is empty."""
        battle, units = battle_state_with_units
        
        # Verify initial state: enemy unit in row 1, front row empty
        assert any(pos.y == 0 for pos in battle.enemy_units.keys()) is False
        assert any(pos.y == 1 for pos in battle.enemy_units.keys()) is True
        assert battle.enemy_rows_collapsed == 0
        
        # Create executor and collapse
        executor = EnemyTurnExecutor(battle)
        executor._step_collapse_enemy_front_row()
        
        # Verify collapse occurred
        assert any(pos.y == 0 for pos in battle.enemy_units.keys()) is True
        assert any(pos.y == 1 for pos in battle.enemy_units.keys()) is False
        assert battle.enemy_rows_collapsed == 1
    
    def test_no_collapse_when_front_row_has_units(self, battle_state_with_front_row_units):
        """Test that enemy row does not collapse when front row has units."""
        battle = battle_state_with_front_row_units
        
        assert any(pos.y == 0 for pos in battle.enemy_units.keys()) is True
        assert battle.enemy_rows_collapsed == 0
        
        executor = EnemyTurnExecutor(battle)
        executor._step_collapse_enemy_front_row()
        
        assert any(pos.y == 0 for pos in battle.enemy_units.keys()) is True
        assert battle.enemy_rows_collapsed == 0


class TestRowCollapseCounters:
    """Tests for row collapse counter tracking."""
    
    def test_counters_initialized_to_zero(self, battle_state_with_units):
        """Test that counters start at zero."""
        battle, _ = battle_state_with_units
        assert battle.player_rows_collapsed == 0
        assert battle.enemy_rows_collapsed == 0
    
    def test_counters_increment_separately(self, battle_state_with_units):
        """Test that player and enemy counters increment independently."""
        battle, _ = battle_state_with_units
        
        player_executor = PlayerTurnExecutor(battle)
        enemy_executor = EnemyTurnExecutor(battle)
        
        # Collapse player row
        player_executor._step_collapse_player_front_row()
        assert battle.player_rows_collapsed == 1
        assert battle.enemy_rows_collapsed == 0
        
        # Collapse enemy row
        enemy_executor._step_collapse_enemy_front_row()
        assert battle.player_rows_collapsed == 1
        assert battle.enemy_rows_collapsed == 1


class TestMultiWaveRowCollapse:
    """Tests for row collapse in multi-wave battles."""
    
    def test_counters_reset_between_waves(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test that row collapse counters reset when a new battle (wave) is created."""
        # Create first battle/wave
        player_unit_1 = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=1),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        battle_wave_1 = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[player_unit_1],
            enemy_units=[],
            player_is_attacker=True
        )
        
        # Collapse in first wave
        executor_1 = PlayerTurnExecutor(battle_wave_1)
        executor_1._step_collapse_player_front_row()
        assert battle_wave_1.player_rows_collapsed == 1
        
        # Create second battle/wave (simulating new wave)
        player_unit_2 = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=1),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        battle_wave_2 = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[player_unit_2],
            enemy_units=[],
            player_is_attacker=True
        )
        
        # Verify counters reset in new wave
        assert battle_wave_2.player_rows_collapsed == 0
        assert battle_wave_2.enemy_rows_collapsed == 0
        
        # First wave counter should still be 1
        assert battle_wave_1.player_rows_collapsed == 1
    
    def test_each_wave_tracks_own_collapses(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test that each wave independently tracks its row collapses."""
        # Wave 1: 2 collapses
        player_unit_1 = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=2),  # Start in row 2
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        battle_wave_1 = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[player_unit_1],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor_1 = PlayerTurnExecutor(battle_wave_1)
        
        # First collapse: row 2 -> row 1
        executor_1._step_collapse_player_front_row()
        assert battle_wave_1.player_rows_collapsed == 1
        
        # Move unit back to row 2 for second collapse test
        # (In real battle, this wouldn't happen, but for testing...)
        units_to_move = list(battle_wave_1.player_units.items())
        battle_wave_1.player_units.clear()
        for old_pos, unit in units_to_move:
            new_pos = Position(x=old_pos.x, y=2)
            unit.position = new_pos
            battle_wave_1.player_units[new_pos] = unit
        
        # Second collapse: row 2 -> row 1 again (front row empty)
        executor_1._step_collapse_player_front_row()
        assert battle_wave_1.player_rows_collapsed == 2
        
        # Wave 2: 1 collapse
        player_unit_2 = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=1),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        battle_wave_2 = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[player_unit_2],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor_2 = PlayerTurnExecutor(battle_wave_2)
        executor_2._step_collapse_player_front_row()
        
        # Each wave has its own counter
        assert battle_wave_1.player_rows_collapsed == 2
        assert battle_wave_2.player_rows_collapsed == 1


class TestRowCollapseEdgeCases:
    """Tests for edge cases in row collapse."""
    
    def test_collapse_with_no_units(self, mock_data_loader, mock_layout):
        """Test collapse behavior when there are no units."""
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_collapse_player_front_row()
        
        # Should not crash, counter should increase to 1
        assert battle.player_rows_collapsed == 1
        assert len(battle.player_units) == 0
    
    def test_collapse_only_one_row_per_turn(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test that only one row collapses per turn, even if multiple rows are empty."""
        # Create units starting in row 2 (rows 0 and 1 empty)
        player_unit_1 = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=2),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[player_unit_1],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        
        # First collapse: row 2 -> row 1 (only one row)
        executor._step_collapse_player_front_row()
        assert battle.player_rows_collapsed == 1
        
        # Unit should now be in row 1, not row 0
        unit_positions = list(battle.player_units.keys())
        assert all(pos.y == 1 for pos in unit_positions)
        
        # Second collapse needed to move to row 0
        executor._step_collapse_player_front_row()
        assert battle.player_rows_collapsed == 2
        assert all(pos.y == 0 for pos in battle.player_units.keys())
    
    def test_collapse_after_actions_not_before(self, basic_unit_template, mock_data_loader, mock_layout):
        """
        Test that collapse happens AFTER actions, not before.
        
        Scenario:
        - Both player and enemy have 1 unit on row 1 (y=1), front row (y=0) is empty
        - Initially, no collapse should happen
        - After player executes attack, enemy side should collapse
        - After enemy executes attack, player side should collapse
        """
        from src.simulator.battle import Action
        
        # Create player unit on row 1 (y=1)
        player_unit = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=1),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Create enemy unit on row 1 (y=1)
        enemy_unit = BattleUnit(
            template=basic_unit_template,
            position=Position(x=0, y=1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[player_unit],
            enemy_units=[enemy_unit],
            player_is_attacker=True
        )
        
        # Verify initial state: both units on row 1, front row empty
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is False
        assert any(pos.y == 1 for pos in battle.player_units.keys()) is True
        assert any(pos.y == 0 for pos in battle.enemy_units.keys()) is False
        assert any(pos.y == 1 for pos in battle.enemy_units.keys()) is True
        assert battle.player_rows_collapsed == 0
        assert battle.enemy_rows_collapsed == 0
        
        # Create a mock action for player to attack enemy
        # Note: Since combat steps aren't fully implemented, we'll use a simple action
        # The action will go through the turn flow even if damage is 0
        player_executor = PlayerTurnExecutor(battle)
        
        # Create action: player unit attacks enemy unit
        # We need to get the actual positions from the battle state
        player_pos = next(iter(battle.player_units.keys()))
        enemy_pos = next(iter(battle.enemy_units.keys()))
        
        # Create a simple action (weapon_id=0 is a placeholder)
        # Action uses Position from models (x, y)
        action = Action(
            unit_position=Position(x=player_pos.x, y=player_pos.y),
            weapon_id=0,
            target_position=Position(x=enemy_pos.x, y=enemy_pos.y)
        )
        
        # Execute player turn - this should trigger enemy collapse at the end
        result = player_executor.execute_player_turn(action)
        
        # After player turn, enemy side should have collapsed (moved from row 1 to row 0)
        # Player side should NOT have collapsed yet
        assert any(pos.y == 0 for pos in battle.enemy_units.keys()) is True
        assert any(pos.y == 1 for pos in battle.enemy_units.keys()) is False
        assert battle.enemy_rows_collapsed == 1
        assert battle.player_rows_collapsed == 0  # Player side hasn't collapsed yet
        assert any(pos.y == 1 for pos in battle.player_units.keys()) is True  # Still on row 1
        
        # Now execute enemy turn - this should trigger player collapse at the end
        # Since enemy turn executor selects actions internally and the selection logic
        # isn't fully implemented, we'll need to mock the action selection or test the
        # collapse step directly. For now, let's verify the collapse step works correctly
        # by calling it directly, which simulates what happens after an enemy action.
        enemy_executor = EnemyTurnExecutor(battle)
        
        # Manually trigger the collapse step that would happen after enemy action
        # This simulates the behavior after enemy executes an attack
        enemy_executor._step_collapse_player_front_row()
        
        # After enemy turn collapse step, player side should have collapsed (moved from row 1 to row 0)
        assert any(pos.y == 0 for pos in battle.player_units.keys()) is True
        assert any(pos.y == 1 for pos in battle.player_units.keys()) is False
        assert battle.player_rows_collapsed == 1
        assert battle.enemy_rows_collapsed == 1  # Enemy already collapsed

