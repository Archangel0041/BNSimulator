"""
Training Pipeline for BN Simulator ML Agent.
Supports DQN, PPO, and baseline agents.
"""

import os
from pathlib import Path
from typing import Optional, Callable
import numpy as np

# RL imports
try:
    from stable_baselines3 import DQN, PPO, A2C
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.callbacks import (
        BaseCallback, CheckpointCallback, EvalCallback
    )
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.evaluation import evaluate_policy
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False
    print("Warning: stable-baselines3 not installed. Training disabled.")

from .gym_env import BNBattleEnv, make_env
from .battle_engine import BattleEngine
from .data_loader import get_game_data
from .models import Action, BattleState, Side


class RandomAgent:
    """Baseline random agent."""

    def __init__(self, env: BNBattleEnv):
        self.env = env
        self.rng = np.random.default_rng()

    def predict(self, obs, deterministic: bool = False):
        """Select a random valid action."""
        mask = self.env.action_masks()
        valid_indices = np.where(mask)[0]

        if len(valid_indices) == 0:
            return 0, None

        action = self.rng.choice(valid_indices)
        return action, None

    def learn(self, total_timesteps: int):
        """No learning for random agent."""
        pass


class HeuristicAgent:
    """
    Heuristic-based agent that uses simple rules:
    - Prioritize killing low-HP enemies
    - Use high-damage abilities
    - Target vulnerable unit types
    """

    def __init__(self, env: BNBattleEnv):
        self.env = env
        self.engine = env.engine
        self.game_data = env.game_data

    def predict(self, obs, deterministic: bool = False):
        """Select action based on heuristics."""
        if self.env.state is None or not self.env.valid_actions:
            return 0, None

        scored_actions = []
        for idx, action in enumerate(self.env.valid_actions):
            score = self._score_action(action)
            scored_actions.append((idx, score))

        # Sort by score descending
        scored_actions.sort(key=lambda x: x[1], reverse=True)

        if deterministic:
            return scored_actions[0][0], None
        else:
            # Softmax selection
            scores = np.array([s for _, s in scored_actions[:10]])
            scores = scores - scores.max()  # Numerical stability
            probs = np.exp(scores) / np.exp(scores).sum()
            idx = np.random.choice(len(probs), p=probs)
            return scored_actions[idx][0], None

    def _score_action(self, action: Action) -> float:
        """Score an action based on heuristics."""
        score = 0.0
        state = self.env.state

        if state is None:
            return score

        # Get attacker and target info
        attacker = state.player_units[action.unit_idx]
        ability = self.game_data.get_ability(action.ability_id)
        weapon = attacker.template.weapons.get(action.weapon_id)

        if not ability or not weapon:
            return score

        # Find target at position
        target = state.get_unit_at_position(action.target_pos, Side.ENEMY)
        if not target:
            return score

        # Score based on potential damage
        base_damage = (weapon.stats.base_damage_min + weapon.stats.base_damage_max) / 2
        score += base_damage * 0.1

        # Bonus for targeting low-HP enemies
        hp_percent = target.current_hp / max(target.stats.hp, 1)
        if hp_percent < 0.3:
            score += 50  # Big bonus for finishing off enemies
        elif hp_percent < 0.5:
            score += 20

        # Consider class advantage
        attacker_class = self.game_data.get_class_config(attacker.template.class_id)
        if attacker_class and target.template.class_id in attacker_class.damage_mods:
            mod = attacker_class.damage_mods[target.template.class_id]
            if mod > 1.1:
                score += 30 * (mod - 1.0)
            elif mod < 0.9:
                score -= 20 * (1.0 - mod)

        # Prefer abilities with status effects
        if ability.status_effects:
            score += 10

        # Penalize if ability is on cooldown next turn
        if ability.stats.ability_cooldown > 1:
            score -= 5

        return score

    def learn(self, total_timesteps: int):
        """No learning for heuristic agent."""
        pass


class MetricsCallback(BaseCallback):
    """Callback for logging training metrics."""

    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.win_rate = []

    def _on_step(self) -> bool:
        # Check for episode completion
        if self.locals.get("dones") is not None:
            for i, done in enumerate(self.locals["dones"]):
                if done:
                    info = self.locals["infos"][i]
                    self.episode_rewards.append(info.get("episode_reward", 0))
                    self.episode_lengths.append(info.get("episode_length", 0))
                    if "player_won" in info:
                        self.win_rate.append(1.0 if info["player_won"] else 0.0)

        return True

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return {
            "mean_reward": np.mean(self.episode_rewards[-100:]) if self.episode_rewards else 0,
            "mean_length": np.mean(self.episode_lengths[-100:]) if self.episode_lengths else 0,
            "win_rate": np.mean(self.win_rate[-100:]) if self.win_rate else 0,
            "total_episodes": len(self.episode_rewards),
        }


def create_training_env(
    n_envs: int = 1,
    encounter_id: Optional[int] = None,
    player_units: Optional[list] = None,
    enemy_units: Optional[list] = None,
    seed: int = 42,
    use_subproc: bool = False,
) -> DummyVecEnv:
    """Create vectorized training environment."""

    def make_env_fn(rank: int) -> Callable:
        def _init():
            env = BNBattleEnv(
                encounter_id=encounter_id,
                player_units=player_units,
                enemy_units=enemy_units,
                seed=seed + rank,
            )
            env = Monitor(env)
            return env
        return _init

    if n_envs == 1 or not use_subproc:
        env = DummyVecEnv([make_env_fn(i) for i in range(n_envs)])
    else:
        env = SubprocVecEnv([make_env_fn(i) for i in range(n_envs)])

    return env


def train_dqn(
    env,
    total_timesteps: int = 100000,
    learning_rate: float = 1e-4,
    buffer_size: int = 50000,
    batch_size: int = 64,
    gamma: float = 0.99,
    exploration_fraction: float = 0.2,
    exploration_final_eps: float = 0.05,
    save_path: Optional[str] = None,
    verbose: int = 1,
) -> DQN:
    """Train a DQN agent."""
    if not HAS_SB3:
        raise ImportError("stable-baselines3 required for DQN training")

    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=learning_rate,
        buffer_size=buffer_size,
        batch_size=batch_size,
        gamma=gamma,
        exploration_fraction=exploration_fraction,
        exploration_final_eps=exploration_final_eps,
        verbose=verbose,
        tensorboard_log="./logs/dqn/",
    )

    callbacks = [MetricsCallback()]

    if save_path:
        callbacks.append(CheckpointCallback(
            save_freq=10000,
            save_path=save_path,
            name_prefix="dqn_bn"
        ))

    model.learn(total_timesteps=total_timesteps, callback=callbacks)

    if save_path:
        model.save(os.path.join(save_path, "dqn_final"))

    return model


def train_ppo(
    env,
    total_timesteps: int = 100000,
    learning_rate: float = 3e-4,
    n_steps: int = 2048,
    batch_size: int = 64,
    n_epochs: int = 10,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_range: float = 0.2,
    save_path: Optional[str] = None,
    verbose: int = 1,
) -> PPO:
    """Train a PPO agent."""
    if not HAS_SB3:
        raise ImportError("stable-baselines3 required for PPO training")

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        verbose=verbose,
        tensorboard_log="./logs/ppo/",
    )

    callbacks = [MetricsCallback()]

    if save_path:
        callbacks.append(CheckpointCallback(
            save_freq=10000,
            save_path=save_path,
            name_prefix="ppo_bn"
        ))

    model.learn(total_timesteps=total_timesteps, callback=callbacks)

    if save_path:
        model.save(os.path.join(save_path, "ppo_final"))

    return model


def evaluate_agent(
    model,
    env,
    n_episodes: int = 100,
    deterministic: bool = True,
) -> dict:
    """Evaluate an agent's performance."""
    episode_rewards = []
    episode_lengths = []
    wins = 0
    total_damage_dealt = 0
    total_damage_taken = 0

    for _ in range(n_episodes):
        obs, info = env.reset()
        done = False
        episode_reward = 0

        while not done:
            action, _ = model.predict(obs, deterministic=deterministic)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            episode_reward += reward

        episode_rewards.append(episode_reward)
        episode_lengths.append(info.get("episode_length", 0))
        if info.get("player_won", False):
            wins += 1
        total_damage_dealt += info.get("damage_dealt", 0)
        total_damage_taken += info.get("damage_taken", 0)

    return {
        "mean_reward": np.mean(episode_rewards),
        "std_reward": np.std(episode_rewards),
        "mean_length": np.mean(episode_lengths),
        "win_rate": wins / n_episodes,
        "avg_damage_dealt": total_damage_dealt / n_episodes,
        "avg_damage_taken": total_damage_taken / n_episodes,
    }


def compare_agents(
    env,
    agents: dict,
    n_episodes: int = 100,
) -> dict:
    """Compare multiple agents on same environment."""
    results = {}

    for name, agent in agents.items():
        print(f"Evaluating {name}...")
        results[name] = evaluate_agent(agent, env, n_episodes)

    # Print comparison
    print("\n=== Agent Comparison ===")
    print(f"{'Agent':<20} {'Win Rate':<12} {'Mean Reward':<15} {'Avg Turns':<12}")
    print("-" * 60)

    for name, metrics in results.items():
        print(f"{name:<20} {metrics['win_rate']:.2%} {'':<5} {metrics['mean_reward']:<15.2f} {metrics['mean_length']:<12.1f}")

    return results


def run_training_pipeline(
    algorithm: str = "ppo",
    total_timesteps: int = 100000,
    n_envs: int = 4,
    encounter_id: Optional[int] = None,
    save_path: str = "./models",
):
    """Run the full training pipeline."""
    print("Setting up environment...")
    env = create_training_env(
        n_envs=n_envs,
        encounter_id=encounter_id,
    )

    print(f"Training {algorithm.upper()} agent...")
    if algorithm.lower() == "dqn":
        model = train_dqn(env, total_timesteps=total_timesteps, save_path=save_path)
    elif algorithm.lower() == "ppo":
        model = train_ppo(env, total_timesteps=total_timesteps, save_path=save_path)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    print("Evaluating trained agent...")
    eval_env = BNBattleEnv(encounter_id=encounter_id)
    results = evaluate_agent(model, eval_env, n_episodes=100)

    print("\n=== Training Results ===")
    for key, value in results.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    env.close()
    return model, results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train BN Battle Agent")
    parser.add_argument("--algorithm", type=str, default="ppo", choices=["dqn", "ppo"])
    parser.add_argument("--timesteps", type=int, default=100000)
    parser.add_argument("--n_envs", type=int, default=4)
    parser.add_argument("--encounter", type=int, default=None)
    parser.add_argument("--save_path", type=str, default="./models")

    args = parser.parse_args()

    run_training_pipeline(
        algorithm=args.algorithm,
        total_timesteps=args.timesteps,
        n_envs=args.n_envs,
        encounter_id=args.encounter,
        save_path=args.save_path,
    )
