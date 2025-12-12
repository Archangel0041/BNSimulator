"""Gymnasium environment wrapper for battle simulator."""
from __future__ import annotations
from typing import Optional, Any
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .battle import BattleSimulator, BattleState, BattleResult, Action, BattleUnit
from .models import Position
from .enums import Side


class BattleEnv(gym.Env):
    """
    Gymnasium environment for tactical combat.

    Observation Space:
        - Flattened representation of battle state
        - Unit stats (HP, position, class, cooldowns, etc.)
        - Global state (turn number, unit counts)

    Action Space:
        - Discrete action representing (unit_idx, weapon_idx, target_idx)
        - Action masking used to filter invalid actions

    Rewards:
        - +1.0 for winning the battle
        - -1.0 for losing the battle
        - Small negative reward per turn (encourages efficiency)
        - Small positive reward for dealing damage
        - Penalty for losing units
    """

    metadata = {"render_modes": ["ansi"], "render_fps": 1}

    # Constants for action encoding
    MAX_UNITS = 8
    MAX_WEAPONS = 4
    MAX_TARGETS = 15  # 5x3 grid

    def __init__(
        self,
        data_dir: str,
        encounter_id: Optional[int] = None,
        player_unit_ids: Optional[list[int]] = None,
        layout_id: int = 2,
        enemy_unit_ids: Optional[list[int]] = None,
        enemy_positions: Optional[list[int]] = None,
        render_mode: Optional[str] = None,
        max_turns: int = 100,
        reward_config: Optional[dict] = None
    ):
        super().__init__()

        self.data_dir = data_dir
        self.encounter_id = encounter_id
        self.player_unit_ids = player_unit_ids or []
        self.layout_id = layout_id
        self.enemy_unit_ids = enemy_unit_ids or []
        self.enemy_positions = enemy_positions or []
        self.render_mode = render_mode
        self.max_turns = max_turns

        # Reward configuration
        self.reward_config = reward_config or {
            "win": 1.0,
            "lose": -1.0,
            "turn_penalty": -0.01,
            "damage_dealt": 0.001,
            "damage_taken": -0.002,
            "unit_killed": 0.1,
            "unit_lost": -0.2,
            "surrender": -0.5
        }

        # Initialize simulator
        self.simulator = BattleSimulator(data_dir)
        self.battle: Optional[BattleState] = None

        # Calculate state size
        UNIT_FEATURES = 10
        GLOBAL_FEATURES = 10
        self.state_size = self.MAX_UNITS * UNIT_FEATURES * 2 + GLOBAL_FEATURES

        # Observation space: normalized floats
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(self.state_size,),
            dtype=np.float32
        )

        # Action space: flattened (unit, weapon, target) tuple
        # Total actions = MAX_UNITS * MAX_WEAPONS * MAX_TARGETS
        self.action_size = self.MAX_UNITS * self.MAX_WEAPONS * self.MAX_TARGETS
        self.action_space = spaces.Discrete(self.action_size)

        # Track previous state for reward calculation
        self._prev_player_hp = 0
        self._prev_enemy_hp = 0
        self._prev_player_count = 0
        self._prev_enemy_count = 0

    def _decode_action(self, action: int) -> tuple[int, int, int]:
        """Decode flat action index to (unit_idx, weapon_idx, target_idx)."""
        target_idx = action % self.MAX_TARGETS
        remainder = action // self.MAX_TARGETS
        weapon_idx = remainder % self.MAX_WEAPONS
        unit_idx = remainder // self.MAX_WEAPONS
        return unit_idx, weapon_idx, target_idx

    def _encode_action(self, unit_idx: int, weapon_idx: int, target_idx: int) -> int:
        """Encode (unit_idx, weapon_idx, target_idx) to flat action index."""
        return (unit_idx * self.MAX_WEAPONS + weapon_idx) * self.MAX_TARGETS + target_idx

    def _target_idx_to_position(self, target_idx: int) -> Position:
        """Convert target index to grid position."""
        return Position.from_grid_id(target_idx, width=5)

    def _position_to_target_idx(self, pos: Position) -> int:
        """Convert grid position to target index."""
        return pos.to_grid_id(width=5)

    def _get_action_mask(self) -> np.ndarray:
        """Get mask of valid actions."""
        mask = np.zeros(self.action_size, dtype=np.int8)

        if self.battle is None or self.battle.result != BattleResult.IN_PROGRESS:
            return mask

        legal_actions = self.battle.get_legal_actions()

        for action in legal_actions:
            # Map weapon_id to weapon_idx (0-based)
            unit = self.battle.player_units[action.unit_index]
            weapon_ids = list(unit.template.weapons.keys())
            if action.weapon_id in weapon_ids:
                weapon_idx = weapon_ids.index(action.weapon_id)
            else:
                continue

            target_idx = self._position_to_target_idx(action.target_position)

            flat_action = self._encode_action(
                action.unit_index,
                weapon_idx,
                target_idx
            )

            if 0 <= flat_action < self.action_size:
                mask[flat_action] = 1

        return mask

    def _action_to_battle_action(self, action: int) -> Optional[Action]:
        """Convert environment action to battle Action."""
        unit_idx, weapon_idx, target_idx = self._decode_action(action)

        if unit_idx >= len(self.battle.player_units):
            return None

        unit = self.battle.player_units[unit_idx]
        weapon_ids = list(unit.template.weapons.keys())

        if weapon_idx >= len(weapon_ids):
            return None

        weapon_id = weapon_ids[weapon_idx]
        target_pos = self._target_idx_to_position(target_idx)

        return Action(
            unit_index=unit_idx,
            weapon_id=weapon_id,
            target_position=target_pos
        )

    def _get_random_enemy_action(self) -> Optional[Action]:
        """Get a random valid action for the enemy."""
        if self.battle is None:
            return None

        legal_actions = self.battle.get_legal_actions()
        if not legal_actions:
            return None

        return self.battle.rng.choice(legal_actions)

    def _calculate_reward(self) -> float:
        """Calculate reward for the current step."""
        reward = 0.0

        if self.battle is None:
            return reward

        # Check terminal conditions
        if self.battle.result == BattleResult.PLAYER_WIN:
            return self.reward_config["win"]
        elif self.battle.result == BattleResult.ENEMY_WIN:
            return self.reward_config["lose"]
        elif self.battle.result == BattleResult.SURRENDER:
            return self.reward_config["surrender"]

        # Turn penalty
        reward += self.reward_config["turn_penalty"]

        # Damage dealt/taken rewards
        current_player_hp = sum(u.current_hp for u in self.battle.player_units)
        current_enemy_hp = sum(u.current_hp for u in self.battle.enemy_units)

        damage_dealt = max(0, self._prev_enemy_hp - current_enemy_hp)
        damage_taken = max(0, self._prev_player_hp - current_player_hp)

        reward += damage_dealt * self.reward_config["damage_dealt"]
        reward += damage_taken * self.reward_config["damage_taken"]

        # Unit count changes
        current_player_count = sum(1 for u in self.battle.player_units if u.is_alive)
        current_enemy_count = sum(1 for u in self.battle.enemy_units if u.is_alive)

        units_killed = self._prev_enemy_count - current_enemy_count
        units_lost = self._prev_player_count - current_player_count

        reward += units_killed * self.reward_config["unit_killed"]
        reward += units_lost * self.reward_config["unit_lost"]

        # Update previous state
        self._prev_player_hp = current_player_hp
        self._prev_enemy_hp = current_enemy_hp
        self._prev_player_count = current_player_count
        self._prev_enemy_count = current_enemy_count

        return reward

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict]:
        """Reset the environment for a new episode."""
        super().reset(seed=seed)

        # Create battle
        if self.encounter_id is not None:
            self.battle = self.simulator.create_battle_from_encounter(
                self.encounter_id,
                self.player_unit_ids
            )
        else:
            # Custom battle setup
            player_positions = list(range(len(self.player_unit_ids)))
            self.battle = self.simulator.create_custom_battle(
                self.layout_id,
                self.player_unit_ids,
                player_positions,
                self.enemy_unit_ids,
                self.enemy_positions
            )

        if self.battle is None:
            raise RuntimeError("Failed to create battle")

        if seed is not None:
            self.battle.seed(seed)

        # Initialize tracking variables
        self._prev_player_hp = sum(u.current_hp for u in self.battle.player_units)
        self._prev_enemy_hp = sum(u.current_hp for u in self.battle.enemy_units)
        self._prev_player_count = len([u for u in self.battle.player_units if u.is_alive])
        self._prev_enemy_count = len([u for u in self.battle.enemy_units if u.is_alive])

        obs = self.battle.get_state_vector()
        info = {
            "action_mask": self._get_action_mask(),
            "turn": self.battle.turn_number,
            "player_units_alive": self._prev_player_count,
            "enemy_units_alive": self._prev_enemy_count
        }

        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Execute one step in the environment."""
        if self.battle is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        terminated = False
        truncated = False

        # Check if battle already ended
        if self.battle.result != BattleResult.IN_PROGRESS:
            terminated = True
            obs = self.battle.get_state_vector()
            return obs, 0.0, terminated, truncated, {"action_mask": self._get_action_mask()}

        # Execute player action
        if self.battle.is_player_turn:
            battle_action = self._action_to_battle_action(action)
            if battle_action:
                # Validate action
                legal_actions = self.battle.get_legal_actions()
                is_legal = any(
                    a.unit_index == battle_action.unit_index and
                    a.weapon_id == battle_action.weapon_id and
                    a.target_position == battle_action.target_position
                    for a in legal_actions
                )
                if is_legal:
                    self.battle.execute_action(battle_action)

            self.battle.end_turn()

        # Execute enemy turn (simple random policy)
        while not self.battle.is_player_turn and self.battle.result == BattleResult.IN_PROGRESS:
            enemy_action = self._get_random_enemy_action()
            if enemy_action:
                self.battle.execute_action(enemy_action)
            self.battle.end_turn()

        # Calculate reward
        reward = self._calculate_reward()

        # Check termination
        if self.battle.result != BattleResult.IN_PROGRESS:
            terminated = True
        elif self.battle.turn_number >= self.max_turns:
            truncated = True

        obs = self.battle.get_state_vector()
        info = {
            "action_mask": self._get_action_mask(),
            "turn": self.battle.turn_number,
            "player_units_alive": sum(1 for u in self.battle.player_units if u.is_alive),
            "enemy_units_alive": sum(1 for u in self.battle.enemy_units if u.is_alive),
            "result": self.battle.result.name
        }

        return obs, reward, terminated, truncated, info

    def render(self) -> Optional[str]:
        """Render the current battle state."""
        if self.render_mode != "ansi" or self.battle is None:
            return None

        lines = []
        lines.append(f"=== Turn {self.battle.turn_number} ===")
        lines.append(f"{'Player Turn' if self.battle.is_player_turn else 'Enemy Turn'}")
        lines.append("")

        # Render enemy grid (top)
        lines.append("ENEMY:")
        for y in range(3):
            row_str = "  "
            for x in range(5):
                pos = Position(x, y)
                unit = None
                for u in self.battle.enemy_units:
                    if u.position == pos:
                        unit = u
                        break

                if unit and unit.is_alive:
                    hp_pct = int(unit.current_hp / unit.template.stats.hp * 100)
                    row_str += f"[{unit.template.class_type.name[:3]}{hp_pct:3d}%] "
                else:
                    row_str += "[     ] "
            lines.append(row_str)

        lines.append("")
        lines.append("-" * 50)
        lines.append("")

        # Render player grid (bottom)
        lines.append("PLAYER:")
        for y in range(3):
            row_str = "  "
            for x in range(5):
                pos = Position(x, y)
                unit = None
                for u in self.battle.player_units:
                    if u.position == pos:
                        unit = u
                        break

                if unit and unit.is_alive:
                    hp_pct = int(unit.current_hp / unit.template.stats.hp * 100)
                    row_str += f"[{unit.template.class_type.name[:3]}{hp_pct:3d}%] "
                else:
                    row_str += "[     ] "
            lines.append(row_str)

        lines.append("")
        lines.append(f"Result: {self.battle.result.name}")

        return "\n".join(lines)

    def close(self) -> None:
        """Clean up resources."""
        self.battle = None


class MultiWaveBattleEnv(BattleEnv):
    """
    Extended environment supporting multiple waves of enemies.

    This simulates the 4-wave encounter structure from the game.
    """

    def __init__(
        self,
        data_dir: str,
        wave_encounter_ids: list[int],
        player_unit_ids: list[int],
        render_mode: Optional[str] = None,
        max_turns_per_wave: int = 50,
        reward_config: Optional[dict] = None
    ):
        # Don't call super().__init__ yet
        self.wave_encounter_ids = wave_encounter_ids
        self.current_wave = 0
        self.max_turns_per_wave = max_turns_per_wave
        self.waves_completed = 0
        self.total_attempts = 0  # Track surrender/retry count

        # Extended reward config for waves
        default_rewards = {
            "win": 1.0,
            "lose": -1.0,
            "turn_penalty": -0.01,
            "damage_dealt": 0.001,
            "damage_taken": -0.002,
            "unit_killed": 0.1,
            "unit_lost": -0.2,
            "surrender": -0.5,
            "wave_complete": 0.5,
            "all_waves_complete": 2.0
        }
        if reward_config:
            default_rewards.update(reward_config)

        super().__init__(
            data_dir=data_dir,
            encounter_id=wave_encounter_ids[0] if wave_encounter_ids else None,
            player_unit_ids=player_unit_ids,
            render_mode=render_mode,
            max_turns=max_turns_per_wave,
            reward_config=default_rewards
        )

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict]:
        """Reset to first wave."""
        self.current_wave = 0
        self.waves_completed = 0

        # Set encounter to first wave
        if self.wave_encounter_ids:
            self.encounter_id = self.wave_encounter_ids[0]

        obs, info = super().reset(seed=seed, options=options)
        info["current_wave"] = self.current_wave
        info["total_waves"] = len(self.wave_encounter_ids)
        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Execute step with wave progression."""
        obs, reward, terminated, truncated, info = super().step(action)

        # Check if wave was won
        if terminated and self.battle and self.battle.result == BattleResult.PLAYER_WIN:
            self.waves_completed += 1
            reward += self.reward_config["wave_complete"]

            # Check if more waves
            if self.current_wave + 1 < len(self.wave_encounter_ids):
                # Progress to next wave
                self.current_wave += 1
                self.encounter_id = self.wave_encounter_ids[self.current_wave]

                # Carry over surviving player units' HP
                surviving_hp = {}
                if self.battle:
                    for i, unit in enumerate(self.battle.player_units):
                        if unit.is_alive:
                            surviving_hp[i] = (unit.current_hp, unit.current_armor)

                # Reset for next wave
                obs, _ = super().reset()

                # Restore HP state
                if self.battle:
                    for i, (hp, armor) in surviving_hp.items():
                        if i < len(self.battle.player_units):
                            self.battle.player_units[i].current_hp = hp
                            self.battle.player_units[i].current_armor = armor

                terminated = False
                truncated = False
            else:
                # All waves complete!
                reward += self.reward_config["all_waves_complete"]

        info["current_wave"] = self.current_wave
        info["waves_completed"] = self.waves_completed
        info["total_waves"] = len(self.wave_encounter_ids)

        return obs, reward, terminated, truncated, info

    def surrender_wave(self) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Surrender current wave and retry."""
        self.total_attempts += 1

        if self.battle:
            self.battle.surrender()

        # Calculate surrender penalty (exponential with attempts)
        surrender_penalty = self.reward_config["surrender"] * (1.1 ** self.total_attempts)

        # Reset current wave
        obs, info = super().reset()

        info["current_wave"] = self.current_wave
        info["total_attempts"] = self.total_attempts

        return obs, surrender_penalty, False, False, info


# Register environments with gymnasium
def register_envs():
    """Register custom environments with gymnasium."""
    gym.register(
        id="BattleSimulator-v0",
        entry_point="src.simulator.gym_env:BattleEnv",
    )

    gym.register(
        id="MultiWaveBattle-v0",
        entry_point="src.simulator.gym_env:MultiWaveBattleEnv",
    )
