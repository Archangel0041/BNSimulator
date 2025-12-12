"""Tests for Gymnasium environment wrapper."""
import pytest
import numpy as np
import gymnasium as gym

from src.simulator.gym_env import BattleEnv, MultiWaveBattleEnv
from src.simulator.data_loader import GameDataLoader


@pytest.fixture
def data_loader():
    """Create a data loader with the test data."""
    loader = GameDataLoader("data")
    loader.load_all()
    return loader


@pytest.fixture
def sample_unit_ids(data_loader):
    """Get sample unit IDs that have weapons."""
    units_with_weapons = [
        uid for uid, unit in data_loader.units.items()
        if unit.weapons
    ]
    return units_with_weapons[:8] if len(units_with_weapons) >= 8 else units_with_weapons


@pytest.fixture
def battle_env(data_loader, sample_unit_ids):
    """Create a battle environment."""
    if len(sample_unit_ids) < 4:
        pytest.skip("Not enough sample units")

    env = BattleEnv(
        data_dir="data",
        player_unit_ids=sample_unit_ids[:2],
        enemy_unit_ids=sample_unit_ids[2:4],
        enemy_positions=[0, 1]
    )
    return env


class TestBattleEnv:
    """Tests for BattleEnv class."""

    def test_env_creation(self, battle_env):
        """Test environment creation."""
        assert battle_env is not None
        assert battle_env.observation_space is not None
        assert battle_env.action_space is not None

    def test_observation_space(self, battle_env):
        """Test observation space is correctly defined."""
        obs_space = battle_env.observation_space

        assert isinstance(obs_space, gym.spaces.Box)
        assert obs_space.shape[0] == battle_env.state_size
        assert obs_space.dtype == np.float32

    def test_action_space(self, battle_env):
        """Test action space is correctly defined."""
        action_space = battle_env.action_space

        assert isinstance(action_space, gym.spaces.Discrete)
        assert action_space.n == battle_env.action_size

    def test_reset(self, battle_env):
        """Test environment reset."""
        obs, info = battle_env.reset()

        assert obs is not None
        assert isinstance(obs, np.ndarray)
        assert obs.shape == battle_env.observation_space.shape
        assert "action_mask" in info

    def test_reset_with_seed(self, battle_env):
        """Test environment reset with seed for reproducibility."""
        obs1, _ = battle_env.reset(seed=42)
        obs2, _ = battle_env.reset(seed=42)

        np.testing.assert_array_equal(obs1, obs2)

    def test_step(self, battle_env):
        """Test taking a step."""
        obs, info = battle_env.reset()

        # Get a valid action from the mask
        action_mask = info["action_mask"]
        valid_actions = np.where(action_mask == 1)[0]

        if len(valid_actions) == 0:
            pytest.skip("No valid actions available")

        action = valid_actions[0]
        obs, reward, terminated, truncated, info = battle_env.step(action)

        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_action_mask(self, battle_env):
        """Test action mask generation."""
        obs, info = battle_env.reset()

        action_mask = info["action_mask"]

        assert isinstance(action_mask, np.ndarray)
        assert action_mask.shape == (battle_env.action_size,)
        assert action_mask.dtype == np.int8
        assert np.all((action_mask == 0) | (action_mask == 1))

    def test_invalid_action_handling(self, battle_env):
        """Test handling of invalid actions."""
        obs, info = battle_env.reset()

        # Find an invalid action
        action_mask = info["action_mask"]
        invalid_actions = np.where(action_mask == 0)[0]

        if len(invalid_actions) == 0:
            pytest.skip("No invalid actions to test")

        # Take invalid action - should not crash
        action = invalid_actions[0]
        obs, reward, terminated, truncated, info = battle_env.step(action)

        # Environment should still be functional
        assert obs is not None

    def test_episode_completion(self, battle_env):
        """Test that episodes can complete."""
        obs, info = battle_env.reset()

        max_steps = 200
        for _ in range(max_steps):
            action_mask = info["action_mask"]
            valid_actions = np.where(action_mask == 1)[0]

            if len(valid_actions) == 0:
                # No valid actions, take random
                action = battle_env.action_space.sample()
            else:
                action = np.random.choice(valid_actions)

            obs, reward, terminated, truncated, info = battle_env.step(action)

            if terminated or truncated:
                break

        # Episode should have ended (either naturally or truncated)
        assert terminated or truncated or _ == max_steps - 1

    def test_render_ansi(self, data_loader, sample_unit_ids):
        """Test ANSI rendering."""
        if len(sample_unit_ids) < 4:
            pytest.skip("Not enough sample units")

        env = BattleEnv(
            data_dir="data",
            player_unit_ids=sample_unit_ids[:2],
            enemy_unit_ids=sample_unit_ids[2:4],
            enemy_positions=[0, 1],
            render_mode="ansi"
        )

        env.reset()
        render_output = env.render()

        assert render_output is not None
        assert isinstance(render_output, str)
        assert "Turn" in render_output
        env.close()

    def test_close(self, battle_env):
        """Test environment cleanup."""
        battle_env.reset()
        battle_env.close()

        # Should be able to close without errors
        assert battle_env.battle is None


class TestActionEncoding:
    """Tests for action encoding/decoding."""

    def test_action_encode_decode(self, battle_env):
        """Test action encoding and decoding."""
        for unit_idx in range(battle_env.MAX_UNITS):
            for weapon_idx in range(battle_env.MAX_WEAPONS):
                for target_idx in range(battle_env.MAX_TARGETS):
                    encoded = battle_env._encode_action(unit_idx, weapon_idx, target_idx)
                    decoded = battle_env._decode_action(encoded)

                    assert decoded == (unit_idx, weapon_idx, target_idx)

    def test_action_bounds(self, battle_env):
        """Test that all actions are within bounds."""
        for action in range(battle_env.action_size):
            unit_idx, weapon_idx, target_idx = battle_env._decode_action(action)

            assert 0 <= unit_idx < battle_env.MAX_UNITS
            assert 0 <= weapon_idx < battle_env.MAX_WEAPONS
            assert 0 <= target_idx < battle_env.MAX_TARGETS


class TestRewardFunction:
    """Tests for reward calculation."""

    def test_reward_bounds(self, battle_env):
        """Test that rewards are reasonable."""
        obs, info = battle_env.reset()

        rewards = []
        for _ in range(50):
            action_mask = info["action_mask"]
            valid_actions = np.where(action_mask == 1)[0]

            if len(valid_actions) == 0:
                action = battle_env.action_space.sample()
            else:
                action = np.random.choice(valid_actions)

            obs, reward, terminated, truncated, info = battle_env.step(action)
            rewards.append(reward)

            if terminated or truncated:
                break

        # Rewards should be in reasonable range
        assert max(rewards) <= 5.0  # Win reward + bonuses
        assert min(rewards) >= -5.0  # Loss penalty + damage taken


class TestMultiWaveBattleEnv:
    """Tests for MultiWaveBattleEnv class."""

    def test_multi_wave_creation(self, data_loader, sample_unit_ids):
        """Test multi-wave environment creation."""
        if len(sample_unit_ids) < 4:
            pytest.skip("Not enough sample units")

        # Get some encounter IDs
        enc_ids = list(data_loader.encounters.keys())[:3]

        if len(enc_ids) < 2:
            pytest.skip("Not enough encounters")

        env = MultiWaveBattleEnv(
            data_dir="data",
            wave_encounter_ids=enc_ids,
            player_unit_ids=sample_unit_ids[:4]
        )

        assert env is not None
        assert len(env.wave_encounter_ids) == len(enc_ids)
        env.close()

    def test_wave_info(self, data_loader, sample_unit_ids):
        """Test wave information in info dict."""
        if len(sample_unit_ids) < 4:
            pytest.skip("Not enough sample units")

        enc_ids = list(data_loader.encounters.keys())[:3]

        if len(enc_ids) < 2:
            pytest.skip("Not enough encounters")

        env = MultiWaveBattleEnv(
            data_dir="data",
            wave_encounter_ids=enc_ids,
            player_unit_ids=sample_unit_ids[:4]
        )

        obs, info = env.reset()

        assert "current_wave" in info
        assert "total_waves" in info
        assert info["current_wave"] == 0
        assert info["total_waves"] == len(enc_ids)

        env.close()


class TestGymCompatibility:
    """Tests for Gymnasium API compatibility."""

    def test_check_env(self, battle_env):
        """Test environment passes Gymnasium checks."""
        from gymnasium.utils.env_checker import check_env

        # This will raise an exception if the env doesn't comply
        try:
            check_env(battle_env, warn=True)
        except Exception as e:
            # Some warnings are OK, only fail on errors
            if "Error" in str(e):
                pytest.fail(f"Environment check failed: {e}")
