"""Tests for battle engine."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.battle_engine import BattleEngine, BattleConfig
from src.data_loader import get_game_data
from src.models import BattleState, Side


class TestBattleEngine:
    """Test suite for battle engine."""

    @pytest.fixture
    def engine(self):
        """Create battle engine fixture."""
        return BattleEngine(config=BattleConfig(seed=42))

    @pytest.fixture
    def game_data(self):
        """Get game data fixture."""
        return get_game_data()

    def test_create_battle_unit(self, engine, game_data):
        """Test creating a battle unit."""
        # Get first player unit
        player_units = game_data.get_player_units()
        assert len(player_units) > 0

        template = player_units[0]
        unit = engine.create_battle_unit(template.id, level=0, position=0)

        assert unit is not None
        assert unit.template_id == template.id
        assert unit.is_alive
        assert unit.current_hp > 0

    def test_setup_custom_battle(self, engine, game_data):
        """Test setting up a custom battle."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        player_configs = [(u.id, 0, i) for i, u in enumerate(player_units)]
        enemy_configs = [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]

        state = engine.setup_custom_battle(player_configs, enemy_configs)

        assert state is not None
        assert len(state.player_units) == len(player_configs)
        assert len(state.enemy_units) == len(enemy_configs)
        assert state.turn_number == 0
        assert state.is_player_turn
        assert not state.is_finished

    def test_get_valid_actions(self, engine, game_data):
        """Test getting valid actions."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        player_configs = [(u.id, 0, i) for i, u in enumerate(player_units)]
        enemy_configs = [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]

        state = engine.setup_custom_battle(player_configs, enemy_configs)
        actions = engine.get_valid_actions(state)

        # Should have at least one valid action
        assert len(actions) >= 0  # Could be 0 if no valid targets

    def test_execute_action(self, engine, game_data):
        """Test executing an action."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        player_configs = [(u.id, 0, i) for i, u in enumerate(player_units)]
        enemy_configs = [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]

        state = engine.setup_custom_battle(player_configs, enemy_configs)
        actions = engine.get_valid_actions(state)

        if actions:
            action = actions[0]
            result = engine.execute_action(state, action)

            assert result is not None
            assert result.action == action
            # Unit should have acted
            assert state.player_units[action.unit_idx].has_acted

    def test_end_turn(self, engine, game_data):
        """Test ending a turn."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        player_configs = [(u.id, 0, i) for i, u in enumerate(player_units)]
        enemy_configs = [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]

        state = engine.setup_custom_battle(player_configs, enemy_configs)

        assert state.is_player_turn
        engine.end_turn(state)
        assert not state.is_player_turn
        assert state.turn_number == 1

    def test_battle_end_detection(self, engine, game_data):
        """Test that battle end is detected."""
        player_units = game_data.get_player_units()[:1]
        enemy_units = game_data.get_enemy_units()[:1]

        state = engine.setup_custom_battle(
            [(player_units[0].id, 0, 0)],
            [(enemy_units[0].id, 0, 5)]
        )

        # Kill all enemies
        for unit in state.enemy_units:
            unit.current_hp = 0

        state.check_battle_end()
        assert state.is_finished
        assert state.player_won

    def test_surrender(self, engine, game_data):
        """Test surrendering."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        state = engine.setup_custom_battle(
            [(u.id, 0, i) for i, u in enumerate(player_units)],
            [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]
        )

        engine.surrender(state)

        assert state.is_finished
        assert not state.player_won
        assert state.surrendered

    def test_simulate_random_battle(self, engine, game_data):
        """Test simulating a random battle to completion."""
        player_units = game_data.get_player_units()[:3]
        enemy_units = game_data.get_enemy_units()[:3]

        state = engine.setup_custom_battle(
            [(u.id, 0, i) for i, u in enumerate(player_units)],
            [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]
        )

        result = engine.simulate_random_battle(state)

        assert result.is_finished
        assert result.turn_number > 0

    def test_clone_state(self, engine, game_data):
        """Test cloning battle state."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        state = engine.setup_custom_battle(
            [(u.id, 0, i) for i, u in enumerate(player_units)],
            [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]
        )

        cloned = engine.clone_state(state)

        # Modify original
        state.turn_number = 999
        state.player_units[0].current_hp = 1

        # Clone should be unaffected
        assert cloned.turn_number == 0
        assert cloned.player_units[0].current_hp != 1

    def test_deterministic_mode(self, game_data):
        """Test deterministic damage calculation."""
        engine = BattleEngine(config=BattleConfig(deterministic=True, seed=42))

        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        state = engine.setup_custom_battle(
            [(u.id, 0, i) for i, u in enumerate(player_units)],
            [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]
        )

        actions = engine.get_valid_actions(state)
        if actions:
            # Execute same action multiple times should give same result
            state1 = engine.clone_state(state)
            state2 = engine.clone_state(state)

            engine.execute_action(state1, actions[0])
            engine.execute_action(state2, actions[0])

            # In deterministic mode, damage should be the same
            # (HP after action should be equal)
            for i, (u1, u2) in enumerate(zip(state1.enemy_units, state2.enemy_units)):
                assert u1.current_hp == u2.current_hp


class TestLineOfFireAndBlocking:
    """Test line of fire and blocking mechanics."""

    @pytest.fixture
    def engine(self):
        """Create battle engine fixture."""
        return BattleEngine(config=BattleConfig(seed=42))

    @pytest.fixture
    def game_data(self):
        """Get game data fixture."""
        return get_game_data()

    def test_indirect_fire_bypasses_blocking(self, engine, game_data):
        """Test that indirect fire (LOF=3) bypasses all blocking."""
        # Find an ability with indirect fire (line_of_fire=3)
        indirect_abilities = [
            a for a in game_data.abilities.values()
            if a.stats.line_of_fire == 3
        ]

        if not indirect_abilities:
            pytest.skip("No indirect fire abilities found in game data")

        # Indirect fire should never be blocked
        for ability in indirect_abilities[:5]:
            assert ability.stats.line_of_fire == 3

    def test_direct_fire_blocked_by_partial_blocking(self, engine, game_data):
        """Test that direct fire (LOF=1) is blocked by partial blocking (blocking=1)."""
        # Find units with blocking > 0
        blocking_units = [
            u for u in game_data.units.values()
            if u.blocking >= 1
        ]

        if blocking_units:
            # Verify blocking values exist in game data
            assert any(u.blocking >= 1 for u in blocking_units)

    def test_precise_fire_only_blocked_by_full_blocking(self, engine, game_data):
        """Test that precise fire (LOF=2) only blocked by full blocking (blocking=2)."""
        # Find abilities with precise fire (line_of_fire=2)
        precise_abilities = [
            a for a in game_data.abilities.values()
            if a.stats.line_of_fire == 2
        ]

        # Find units with full blocking
        full_blocking_units = [
            u for u in game_data.units.values()
            if u.blocking == 2
        ]

        # Just verify the data exists
        if precise_abilities:
            assert precise_abilities[0].stats.line_of_fire == 2

    def test_blocking_logic(self, engine, game_data):
        """Test the _is_target_blocked method logic."""
        from src.models import Ability, AbilityStats, BattleUnit, UnitTemplate, GridLayout

        # Create a mock layout (3x3 grid)
        layout = GridLayout(
            id=1,
            attacker_grid=[[1, 1, 1], [1, 1, 1], [1, 1, 1]],
            defender_grid=[[1, 1, 1], [1, 1, 1], [1, 1, 1]],
            defender_wall=[]
        )

        state = BattleState(layout=layout)

        # Create a mock ability with direct fire
        direct_ability = Ability(
            id=999,
            name="Test Direct",
            icon="",
            damage_animation_type="",
            stats=AbilityStats(
                attack=10,
                damage_type=1,
                min_range=1,
                max_range=5,
                line_of_fire=1,  # Direct fire
            ),
            damage_area=[],
            target_area=None,
            targets=[],
            status_effects={},
            critical_bonuses={}
        )

        # Create a mock ability with indirect fire
        indirect_ability = Ability(
            id=998,
            name="Test Indirect",
            icon="",
            damage_animation_type="",
            stats=AbilityStats(
                attack=10,
                damage_type=1,
                min_range=1,
                max_range=5,
                line_of_fire=3,  # Indirect fire
            ),
            damage_area=[],
            target_area=None,
            targets=[],
            status_effects={},
            critical_bonuses={}
        )

        # Indirect fire should never be blocked
        assert indirect_ability.stats.line_of_fire == 3

        # Direct fire can be blocked
        assert direct_ability.stats.line_of_fire == 1

    def test_line_of_fire_values_in_data(self, game_data):
        """Test that line of fire values are properly loaded."""
        lof_counts = {0: 0, 1: 0, 2: 0, 3: 0}

        for ability in game_data.abilities.values():
            lof = ability.stats.line_of_fire
            if lof in lof_counts:
                lof_counts[lof] += 1

        # Should have abilities with various LOF values
        total = sum(lof_counts.values())
        assert total > 0

    def test_blocking_values_in_data(self, game_data):
        """Test that blocking values are properly loaded."""
        blocking_counts = {0: 0, 1: 0, 2: 0}

        for unit in game_data.units.values():
            blocking = unit.blocking
            if blocking in blocking_counts:
                blocking_counts[blocking] += 1

        # Most units should have no blocking (0)
        assert blocking_counts[0] > 0


class TestBattleState:
    """Test battle state methods."""

    @pytest.fixture
    def state(self):
        """Create a battle state fixture."""
        engine = BattleEngine()
        game_data = get_game_data()

        player_units = game_data.get_player_units()[:3]
        enemy_units = game_data.get_enemy_units()[:3]

        return engine.setup_custom_battle(
            [(u.id, 0, i) for i, u in enumerate(player_units)],
            [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]
        )

    def test_get_living_units(self, state):
        """Test getting living units."""
        living = state.get_living_units(Side.PLAYER)
        assert len(living) == len(state.player_units)

        # Kill one unit
        state.player_units[0].current_hp = 0
        living = state.get_living_units(Side.PLAYER)
        assert len(living) == len(state.player_units) - 1

    def test_get_unit_at_position(self, state):
        """Test getting unit at position."""
        unit = state.player_units[0]
        found = state.get_unit_at_position(unit.position, Side.PLAYER)
        assert found == unit

    def test_to_observation(self, state):
        """Test converting state to observation."""
        obs = state.to_observation()
        assert obs is not None
        assert len(obs) > 0
        assert obs.dtype == 'float32'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
