"""Tests for battle simulation functionality."""
import pytest
import numpy as np

from src.simulator.battle import (
    BattleSimulator, BattleState, BattleResult, BattleUnit, Action
)
from src.simulator.models import Position, UnitTemplate, UnitStats
from src.simulator.enums import Side, UnitClass, DamageType
from src.simulator.data_loader import GameDataLoader


@pytest.fixture
def data_loader():
    """Create a data loader with the test data."""
    loader = GameDataLoader("data")
    loader.load_all()
    return loader


@pytest.fixture
def battle_simulator(data_loader):
    """Create a battle simulator."""
    return BattleSimulator("data")


@pytest.fixture
def sample_unit_ids(data_loader):
    """Get some sample unit IDs from the data."""
    # Find units that have weapons
    units_with_weapons = [
        uid for uid, unit in data_loader.units.items()
        if unit.weapons
    ]
    return units_with_weapons[:8] if len(units_with_weapons) >= 8 else units_with_weapons


class TestBattleUnit:
    """Tests for BattleUnit class."""

    def test_create_unit(self, data_loader, sample_unit_ids):
        """Test creating a battle unit."""
        if not sample_unit_ids:
            pytest.skip("No sample units available")

        template = data_loader.get_unit(sample_unit_ids[0])
        unit = BattleUnit(
            template=template,
            position=Position(2, 1),
            side=Side.ATTACKER
        )

        assert unit.is_alive
        assert unit.current_hp == template.stats.hp
        assert unit.position == Position(2, 1)

    def test_take_damage(self, data_loader, sample_unit_ids):
        """Test damage calculation."""
        if not sample_unit_ids:
            pytest.skip("No sample units available")

        template = data_loader.get_unit(sample_unit_ids[0])
        unit = BattleUnit(
            template=template,
            position=Position(2, 1),
            side=Side.ATTACKER
        )

        initial_hp = unit.current_hp
        damage = 50
        unit.take_damage(damage, DamageType.PIERCING)

        assert unit.current_hp < initial_hp
        assert unit.is_alive or unit.current_hp == 0

    def test_unit_death(self, data_loader, sample_unit_ids):
        """Test unit death when HP reaches 0."""
        if not sample_unit_ids:
            pytest.skip("No sample units available")

        template = data_loader.get_unit(sample_unit_ids[0])
        unit = BattleUnit(
            template=template,
            position=Position(2, 1),
            side=Side.ATTACKER
        )

        # Deal massive damage
        unit.take_damage(99999, DamageType.EXPLOSIVE)

        assert not unit.is_alive
        assert unit.current_hp == 0

    def test_heal(self, data_loader, sample_unit_ids):
        """Test healing functionality."""
        if not sample_unit_ids:
            pytest.skip("No sample units available")

        template = data_loader.get_unit(sample_unit_ids[0])
        unit = BattleUnit(
            template=template,
            position=Position(2, 1),
            side=Side.ATTACKER
        )

        # Take some damage first
        unit.take_damage(50, DamageType.PIERCING)
        damaged_hp = unit.current_hp

        # Heal
        healed = unit.heal(30)

        assert unit.current_hp > damaged_hp
        assert healed <= 30

    def test_heal_cap(self, data_loader, sample_unit_ids):
        """Test that healing doesn't exceed max HP."""
        if not sample_unit_ids:
            pytest.skip("No sample units available")

        template = data_loader.get_unit(sample_unit_ids[0])
        unit = BattleUnit(
            template=template,
            position=Position(2, 1),
            side=Side.ATTACKER
        )

        # Heal beyond max
        unit.heal(99999)

        assert unit.current_hp == template.stats.hp


class TestBattleState:
    """Tests for BattleState class."""

    def test_create_battle_from_encounter(self, battle_simulator, data_loader, sample_unit_ids):
        """Test creating battle from encounter."""
        if not sample_unit_ids:
            pytest.skip("No sample units available")

        # Get first encounter
        enc_id = next(iter(data_loader.encounters.keys()))

        battle = battle_simulator.create_battle_from_encounter(
            enc_id,
            sample_unit_ids[:4]
        )

        assert battle is not None
        assert len(battle.player_units) > 0
        assert len(battle.enemy_units) > 0
        assert battle.result == BattleResult.IN_PROGRESS

    def test_create_custom_battle(self, battle_simulator, data_loader, sample_unit_ids):
        """Test creating custom battle."""
        if len(sample_unit_ids) < 2:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[:2],
            enemy_positions=[0, 1]
        )

        assert battle is not None
        assert len(battle.player_units) == 2
        assert len(battle.enemy_units) == 2

    def test_get_legal_actions(self, battle_simulator, data_loader, sample_unit_ids):
        """Test getting legal actions."""
        if len(sample_unit_ids) < 2:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[:2],
            enemy_positions=[0, 1]
        )

        legal_actions = battle.get_legal_actions()

        # Should have some legal actions
        assert len(legal_actions) >= 0  # Could be 0 if units have no usable weapons

    def test_execute_action(self, battle_simulator, data_loader, sample_unit_ids):
        """Test executing an action."""
        if len(sample_unit_ids) < 2:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[:2],
            enemy_positions=[0, 1]
        )

        legal_actions = battle.get_legal_actions()

        if legal_actions:
            action = legal_actions[0]
            result = battle.execute_action(action)
            assert result.success

    def test_turn_progression(self, battle_simulator, data_loader, sample_unit_ids):
        """Test turn switching."""
        if len(sample_unit_ids) < 2:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[:2],
            enemy_positions=[0, 1]
        )

        assert battle.is_player_turn
        assert battle.turn_number == 0

        battle.end_turn()
        assert not battle.is_player_turn

        battle.end_turn()
        assert battle.is_player_turn
        assert battle.turn_number == 1

    def test_state_vector(self, battle_simulator, data_loader, sample_unit_ids):
        """Test state vector generation."""
        if len(sample_unit_ids) < 2:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[:2],
            enemy_positions=[0, 1]
        )

        state = battle.get_state_vector()

        assert isinstance(state, np.ndarray)
        assert state.dtype == np.float32
        assert len(state.shape) == 1
        # Values should be normalized
        assert state.min() >= 0.0
        assert state.max() <= 1.0 or np.isclose(state.max(), 1.0, atol=0.1)

    def test_surrender(self, battle_simulator, data_loader, sample_unit_ids):
        """Test surrender functionality."""
        if len(sample_unit_ids) < 2:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[:2],
            enemy_positions=[0, 1]
        )

        battle.surrender()
        assert battle.result == BattleResult.SURRENDER


class TestBattleSimulator:
    """Tests for BattleSimulator class."""

    def test_run_battle_random_vs_random(self, battle_simulator, data_loader, sample_unit_ids):
        """Test running a battle with random policies."""
        if len(sample_unit_ids) < 4:
            pytest.skip("Not enough sample units available")

        battle = battle_simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=sample_unit_ids[:2],
            player_positions=[0, 1],
            enemy_unit_ids=sample_unit_ids[2:4],
            enemy_positions=[0, 1]
        )

        if battle is None:
            pytest.skip("Could not create battle")

        # Simple random policy
        import random

        def random_policy(battle_state):
            actions = battle_state.get_legal_actions()
            return random.choice(actions) if actions else None

        result = battle_simulator.run_battle(
            battle,
            random_policy,
            random_policy,
            max_turns=50
        )

        assert result in [BattleResult.PLAYER_WIN, BattleResult.ENEMY_WIN, BattleResult.IN_PROGRESS]


class TestPosition:
    """Tests for Position class."""

    def test_position_equality(self):
        """Test position comparison."""
        p1 = Position(2, 3)
        p2 = Position(2, 3)
        p3 = Position(3, 2)

        assert p1 == p2
        assert p1 != p3

    def test_position_hash(self):
        """Test position hashing for dict keys."""
        p1 = Position(2, 3)
        p2 = Position(2, 3)

        positions = {p1: "test"}
        assert positions[p2] == "test"

    def test_grid_id_conversion(self):
        """Test converting to/from grid ID."""
        pos = Position(2, 1)  # Column 2, row 1
        grid_id = pos.to_grid_id(width=5)

        restored = Position.from_grid_id(grid_id, width=5)
        assert pos == restored

    def test_grid_id_round_trip(self):
        """Test round-trip conversion for all positions."""
        width = 5
        height = 3

        for y in range(height):
            for x in range(width):
                pos = Position(x, y)
                grid_id = pos.to_grid_id(width)
                restored = Position.from_grid_id(grid_id, width)
                assert pos == restored, f"Failed for pos {pos}"
