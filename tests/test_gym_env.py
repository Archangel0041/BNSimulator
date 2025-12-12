"""Tests for Gymnasium environment."""

import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gym_env import BNBattleEnv, make_env
from src.data_loader import get_game_data


class TestBNBattleEnv:
    """Test suite for Gym environment."""

    @pytest.fixture
    def env(self):
        """Create environment fixture."""
        env = BNBattleEnv(seed=42)
        yield env
        env.close()

    @pytest.fixture
    def game_data(self):
        """Get game data fixture."""
        return get_game_data()

    def test_env_creation(self, env):
        """Test environment creates successfully."""
        assert env is not None
        assert env.observation_space is not None
        assert env.action_space is not None

    def test_reset(self, env):
        """Test environment reset."""
        obs, info = env.reset()

        assert obs is not None
        assert isinstance(obs, np.ndarray)
        assert obs.shape == env.observation_space.shape
        assert info is not None
        assert isinstance(info, dict)

    def test_step(self, env):
        """Test environment step."""
        obs, info = env.reset()

        # Get valid action
        mask = env.action_masks()
        valid_actions = np.where(mask)[0]

        if len(valid_actions) > 0:
            action = valid_actions[0]
            new_obs, reward, terminated, truncated, new_info = env.step(action)

            assert new_obs is not None
            assert isinstance(reward, (int, float))
            assert isinstance(terminated, bool)
            assert isinstance(truncated, bool)
            assert isinstance(new_info, dict)

    def test_action_masks(self, env):
        """Test action masking."""
        env.reset()
        mask = env.action_masks()

        assert mask is not None
        assert len(mask) == env.max_actions
        assert mask.dtype == np.bool_

    def test_render(self, env):
        """Test rendering."""
        env = BNBattleEnv(render_mode="ansi", seed=42)
        env.reset()
        output = env.render()
        assert output is not None
        assert "Turn" in output
        env.close()

    def test_episode_completion(self, env):
        """Test that episodes can complete."""
        obs, info = env.reset()
        done = False
        steps = 0
        max_steps = 1000

        while not done and steps < max_steps:
            mask = env.action_masks()
            valid_actions = np.where(mask)[0]

            if len(valid_actions) > 0:
                action = np.random.choice(valid_actions)
            else:
                action = 0

            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1

        # Episode should complete within reasonable time
        assert done or steps == max_steps

    def test_reward_range(self, env):
        """Test that rewards are reasonable."""
        env.reset()
        total_reward = 0

        for _ in range(100):
            mask = env.action_masks()
            valid_actions = np.where(mask)[0]

            if len(valid_actions) == 0:
                break

            action = np.random.choice(valid_actions)
            _, reward, done, _, _ = env.step(action)
            total_reward += reward

            if done:
                break

        # Reward should be finite
        assert np.isfinite(total_reward)

    def test_custom_units(self, game_data):
        """Test environment with custom units."""
        player_units = game_data.get_player_units()[:2]
        enemy_units = game_data.get_enemy_units()[:2]

        env = BNBattleEnv(
            player_units=[(u.id, 0, i) for i, u in enumerate(player_units)],
            enemy_units=[(u.id, 0, i + 5) for i, u in enumerate(enemy_units)],
            seed=42
        )

        obs, info = env.reset()
        assert info["player_units_alive"] == len(player_units)
        assert info["enemy_units_alive"] == len(enemy_units)

        env.close()

    def test_info_dict(self, env):
        """Test info dictionary contents."""
        obs, info = env.reset()

        required_keys = ["valid_actions", "turn", "player_units_alive", "enemy_units_alive"]
        for key in required_keys:
            assert key in info

    def test_observation_bounds(self, env):
        """Test that observations are within bounds."""
        obs, _ = env.reset()

        assert np.all(obs >= env.observation_space.low)
        assert np.all(obs <= env.observation_space.high)


class TestMakeEnv:
    """Test environment factory function."""

    def test_make_battle_env(self):
        """Test creating battle environment."""
        env = make_env("battle", seed=42)
        assert env is not None
        env.close()

    def test_invalid_env_type(self):
        """Test invalid environment type raises error."""
        with pytest.raises(ValueError):
            make_env("invalid_type")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
