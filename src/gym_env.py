"""
Gymnasium Environment for BN Simulator.
Wraps the battle engine as a standard RL environment.
"""

from typing import Any, Optional, SupportsFloat
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .battle_engine import BattleEngine, BattleConfig
from .data_loader import GameData, get_game_data
from .models import Action, BattleState, Side


class BNBattleEnv(gym.Env):
    """
    Gymnasium environment for Battle Nerds combat simulation.

    Observation Space:
        - Flattened array of unit features + global battle state
        - Shape: (2 * max_units * features_per_unit + global_features,)

    Action Space:
        - Discrete: index into list of valid actions
        - With action masking support for invalid actions

    Rewards:
        - Positive for dealing damage
        - Large positive for winning
        - Negative for taking damage
        - Large negative for losing
        - Time penalty per turn
    """

    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(
        self,
        encounter_id: Optional[int] = None,
        player_units: Optional[list[tuple[int, int, int]]] = None,  # (unit_id, level, pos)
        enemy_units: Optional[list[tuple[int, int, int]]] = None,
        max_units_per_side: int = 16,  # Must match BattleState.to_observation()
        features_per_unit: int = 20,
        global_features: int = 5,
        max_actions: int = 256,
        reward_config: Optional[dict] = None,
        game_data: Optional[GameData] = None,
        seed: Optional[int] = None,
        render_mode: Optional[str] = None,
    ):
        super().__init__()

        self.encounter_id = encounter_id
        self.player_units_config = player_units
        self.enemy_units_config = enemy_units
        self.max_units = max_units_per_side
        self.features_per_unit = features_per_unit
        self.global_features = global_features
        self.max_actions = max_actions
        self.render_mode = render_mode

        # Game data and engine
        self.game_data = game_data or get_game_data()
        self.engine = BattleEngine(self.game_data, BattleConfig(seed=seed))

        # Reward configuration
        self.reward_config = reward_config or {
            "damage_dealt": 0.01,
            "damage_taken": -0.01,
            "kill_enemy": 0.5,
            "lose_unit": -1.0,
            "win": 10.0,
            "lose": -10.0,
            "surrender": -5.0,
            "turn_penalty": -0.01,
            "invalid_action": -0.1,
        }

        # Observation space
        obs_size = 2 * max_units_per_side * features_per_unit + global_features
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(obs_size,), dtype=np.float32
        )

        # Action space (discrete with masking)
        self.action_space = spaces.Discrete(max_actions)

        # State
        self.state: Optional[BattleState] = None
        self.valid_actions: list[Action] = []
        self.action_to_idx: dict[Action, int] = {}
        self.idx_to_action: dict[int, Action] = {}

        # Episode statistics
        self.episode_reward = 0.0
        self.episode_length = 0

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> tuple[np.ndarray, dict]:
        """Reset the environment to initial state."""
        super().reset(seed=seed)

        if seed is not None:
            self.engine.rng.seed(seed)

        # Set up battle
        if self.encounter_id is not None:
            self.state = self.engine.setup_battle_from_encounter(
                self.encounter_id,
                self.player_units_config
            )
        elif self.player_units_config and self.enemy_units_config:
            self.state = self.engine.setup_custom_battle(
                self.player_units_config,
                self.enemy_units_config
            )
        else:
            # Create a default test battle
            self.state = self._create_default_battle()

        # Reset statistics
        self.episode_reward = 0.0
        self.episode_length = 0

        # Update action mapping
        self._update_action_mapping()

        obs = self._get_observation()
        info = self._get_info()

        return obs, info

    def _create_default_battle(self) -> BattleState:
        """Create a default battle for testing."""
        # Get some player and enemy units
        player_templates = self.game_data.get_player_units()[:3]
        enemy_templates = self.game_data.get_enemy_units()[:3]

        player_units = [(t.id, 0, i) for i, t in enumerate(player_templates)]
        enemy_units = [(t.id, 0, i + 5) for i, t in enumerate(enemy_templates)]

        return self.engine.setup_custom_battle(player_units, enemy_units)

    def step(self, action: int) -> tuple[np.ndarray, SupportsFloat, bool, bool, dict]:
        """Execute one step in the environment."""
        reward = 0.0
        terminated = False
        truncated = False

        if self.state is None or self.state.is_finished:
            return self._get_observation(), 0.0, True, False, self._get_info()

        # Check if it's player's turn
        if not self.state.is_player_turn:
            # AI turn - execute random action
            self._execute_ai_turn()
            self._update_action_mapping()
            return self._get_observation(), reward, self.state.is_finished, False, self._get_info()

        # Validate action
        if action < 0 or action >= len(self.valid_actions):
            # Invalid action - small penalty and no-op
            reward += self.reward_config["invalid_action"]
            # Try to find any valid action
            if self.valid_actions:
                action = 0  # Use first valid action
            else:
                # No valid actions - end turn
                self.engine.end_turn(self.state)
                self._update_action_mapping()
                return self._get_observation(), reward, self.state.is_finished, False, self._get_info()

        # Get the actual action
        game_action = self.valid_actions[action]

        # Store pre-action state for reward calculation
        pre_damage_dealt = self.state.total_damage_dealt
        pre_damage_taken = self.state.total_damage_taken
        pre_enemies = self.state.enemies_killed
        pre_units_lost = self.state.units_lost

        # Execute action
        result = self.engine.execute_action(self.state, game_action)

        # Calculate reward from action results
        damage_dealt = self.state.total_damage_dealt - pre_damage_dealt
        damage_taken = self.state.total_damage_taken - pre_damage_taken
        enemies_killed = self.state.enemies_killed - pre_enemies
        units_lost = self.state.units_lost - pre_units_lost

        reward += damage_dealt * self.reward_config["damage_dealt"]
        reward += damage_taken * self.reward_config["damage_taken"]
        reward += enemies_killed * self.reward_config["kill_enemy"]
        reward += units_lost * self.reward_config["lose_unit"]

        # End player turn
        self.engine.end_turn(self.state)

        # Turn penalty
        reward += self.reward_config["turn_penalty"]

        # Check for game end
        if self.state.is_finished:
            if self.state.player_won:
                reward += self.reward_config["win"]
            elif self.state.surrendered:
                reward += self.reward_config["surrender"]
            else:
                reward += self.reward_config["lose"]
            terminated = True
        else:
            # Execute AI turn(s) until it's player's turn again
            while not self.state.is_player_turn and not self.state.is_finished:
                pre_damage_taken = self.state.total_damage_taken
                pre_units_lost = self.state.units_lost

                self._execute_ai_turn()

                damage_taken = self.state.total_damage_taken - pre_damage_taken
                units_lost = self.state.units_lost - pre_units_lost

                reward += damage_taken * self.reward_config["damage_taken"]
                reward += units_lost * self.reward_config["lose_unit"]

            if self.state.is_finished:
                if self.state.player_won:
                    reward += self.reward_config["win"]
                else:
                    reward += self.reward_config["lose"]
                terminated = True

        # Update action mapping for next step
        self._update_action_mapping()

        self.episode_reward += reward
        self.episode_length += 1

        obs = self._get_observation()
        info = self._get_info()

        return obs, reward, terminated, truncated, info

    def _execute_ai_turn(self):
        """Execute AI (enemy) turn."""
        if self.state is None or self.state.is_player_turn:
            return

        ai_actions = self.engine.get_valid_actions(self.state)
        if ai_actions:
            # Simple AI: random action
            action = self.engine.rng.choice(ai_actions)
            self.engine.execute_action(self.state, action)

        self.engine.end_turn(self.state)

    def _update_action_mapping(self):
        """Update mapping between discrete action indices and game actions."""
        self.valid_actions = []
        self.action_to_idx = {}
        self.idx_to_action = {}

        if self.state is None or self.state.is_finished or not self.state.is_player_turn:
            return

        self.valid_actions = self.engine.get_valid_actions(self.state)

        for idx, action in enumerate(self.valid_actions[:self.max_actions]):
            self.action_to_idx[action] = idx
            self.idx_to_action[idx] = action

    def _get_observation(self) -> np.ndarray:
        """Convert battle state to observation array."""
        if self.state is None:
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        return self.state.to_observation()

    def _get_info(self) -> dict:
        """Get additional info dictionary."""
        info = {
            "valid_actions": len(self.valid_actions),
            "episode_reward": self.episode_reward,
            "episode_length": self.episode_length,
        }

        if self.state:
            info.update({
                "turn": self.state.turn_number,
                "player_units_alive": len(self.state.get_living_units(Side.PLAYER)),
                "enemy_units_alive": len(self.state.get_living_units(Side.HOSTILE)),
                "damage_dealt": self.state.total_damage_dealt,
                "damage_taken": self.state.total_damage_taken,
                "is_finished": self.state.is_finished,
                "player_won": self.state.player_won,
            })

        return info

    def action_masks(self) -> np.ndarray:
        """Get mask of valid actions (for masked PPO/DQN)."""
        mask = np.zeros(self.max_actions, dtype=np.bool_)
        for i in range(min(len(self.valid_actions), self.max_actions)):
            mask[i] = True
        return mask

    def render(self) -> Optional[str]:
        """Render the current state."""
        if self.render_mode == "ansi" or self.render_mode == "human":
            return self._render_text()
        return None

    def _render_text(self) -> str:
        """Render state as text."""
        if self.state is None:
            return "No active battle"

        lines = []
        lines.append(f"=== Turn {self.state.turn_number} ===")
        lines.append(f"{'Player' if self.state.is_player_turn else 'Enemy'} turn")
        lines.append("")

        lines.append("Player Units:")
        for i, unit in enumerate(self.state.player_units):
            status = "DEAD" if not unit.is_alive else f"HP:{unit.current_hp}/{unit.stats.hp}"
            lines.append(f"  [{i}] {unit.template.name} @ pos {unit.position}: {status}")

        lines.append("")
        lines.append("Enemy Units:")
        for i, unit in enumerate(self.state.enemy_units):
            status = "DEAD" if not unit.is_alive else f"HP:{unit.current_hp}/{unit.stats.hp}"
            lines.append(f"  [{i}] {unit.template.name} @ pos {unit.position}: {status}")

        lines.append("")
        lines.append(f"Valid actions: {len(self.valid_actions)}")

        if self.state.is_finished:
            result = "VICTORY" if self.state.player_won else "DEFEAT"
            lines.append(f"\n*** {result} ***")

        output = "\n".join(lines)
        if self.render_mode == "human":
            print(output)
        return output

    def close(self):
        """Clean up resources."""
        pass


class BNMultiWaveEnv(BNBattleEnv):
    """
    Extended environment for multi-wave encounters.
    Handles 4-wave battles with surrender option.
    """

    def __init__(
        self,
        encounter_ids: list[int],  # One per wave
        player_units: list[tuple[int, int, int]],
        max_attempts: int = 10,
        surrender_threshold: float = 0.5,  # Surrender if HP below this %
        **kwargs
    ):
        super().__init__(player_units=player_units, **kwargs)
        self.encounter_ids = encounter_ids
        self.max_attempts = max_attempts
        self.surrender_threshold = surrender_threshold

        self.current_attempt = 0
        self.current_wave = 0
        self.wave_states: list[BattleState] = []

        # Extended reward config
        self.reward_config.update({
            "wave_complete": 5.0,
            "attempt_penalty": -2.0,  # Penalty per retry
        })

    def reset(self, *, seed=None, options=None):
        """Reset to first wave, first attempt."""
        self.current_attempt = 0
        self.current_wave = 0
        self.wave_states = []
        return super().reset(seed=seed, options=options)

    def _setup_current_wave(self):
        """Set up battle for current wave."""
        if self.current_wave < len(self.encounter_ids):
            enc_id = self.encounter_ids[self.current_wave]
            self.state = self.engine.setup_battle_from_encounter(
                enc_id,
                self.player_units_config
            )

            # Restore unit state from previous waves
            if self.wave_states:
                self._restore_unit_state()

    def _restore_unit_state(self):
        """Restore player unit HP/status from previous wave."""
        if not self.wave_states or self.state is None:
            return

        prev_state = self.wave_states[-1]
        for i, unit in enumerate(self.state.player_units):
            if i < len(prev_state.player_units):
                prev_unit = prev_state.player_units[i]
                unit.current_hp = prev_unit.current_hp
                unit.current_armor = prev_unit.current_armor
                unit.status_effects = prev_unit.status_effects.copy()

    def surrender_wave(self) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Surrender current wave and retry."""
        if self.state is None:
            return self._get_observation(), 0.0, True, False, self._get_info()

        # Only allow surrender if no units lost
        if self.state.units_lost > 0:
            # Can't surrender - must continue
            return self._get_observation(), 0.0, False, False, self._get_info()

        self.current_attempt += 1
        reward = self.reward_config["surrender"]
        reward += self.reward_config["attempt_penalty"] * self.current_attempt

        if self.current_attempt >= self.max_attempts:
            # Out of attempts
            return self._get_observation(), reward, True, False, self._get_info()

        # Restart current wave
        self._setup_current_wave()
        self._update_action_mapping()

        return self._get_observation(), reward, False, False, self._get_info()


def make_env(
    env_type: str = "battle",
    **kwargs
) -> gym.Env:
    """Factory function to create environments."""
    if env_type == "battle":
        return BNBattleEnv(**kwargs)
    elif env_type == "multiwave":
        return BNMultiWaveEnv(**kwargs)
    else:
        raise ValueError(f"Unknown environment type: {env_type}")


# Register environments
try:
    gym.register(
        id="BNBattle-v0",
        entry_point="src.gym_env:BNBattleEnv",
    )
    gym.register(
        id="BNMultiWave-v0",
        entry_point="src.gym_env:BNMultiWaveEnv",
    )
except gym.error.Error:
    pass  # Already registered
