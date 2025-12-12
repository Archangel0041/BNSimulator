"""Training pipeline for battle ML agents."""
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

import numpy as np
import torch
from stable_baselines3 import PPO, DQN
from stable_baselines3.common.callbacks import (
    BaseCallback, EvalCallback, CheckpointCallback, CallbackList
)
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed

# Try to import MaskablePPO (optional dependency)
try:
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    HAS_MASKABLE_PPO = True
except ImportError:
    HAS_MASKABLE_PPO = False

from src.simulator.gym_env import BattleEnv, MultiWaveBattleEnv


class BattleMetricsCallback(BaseCallback):
    """Custom callback for logging battle-specific metrics."""

    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.win_count = 0
        self.loss_count = 0
        self.total_episodes = 0

    def _on_step(self) -> bool:
        # Check for episode end
        for info in self.locals.get("infos", []):
            if "episode" in info:
                self.episode_rewards.append(info["episode"]["r"])
                self.episode_lengths.append(info["episode"]["l"])
                self.total_episodes += 1

                # Track wins/losses
                result = info.get("result", "")
                if result == "PLAYER_WIN":
                    self.win_count += 1
                elif result == "ENEMY_WIN":
                    self.loss_count += 1

        # Log metrics periodically
        if self.n_calls % 1000 == 0 and self.total_episodes > 0:
            win_rate = self.win_count / self.total_episodes
            avg_reward = np.mean(self.episode_rewards[-100:]) if self.episode_rewards else 0
            avg_length = np.mean(self.episode_lengths[-100:]) if self.episode_lengths else 0

            self.logger.record("battle/win_rate", win_rate)
            self.logger.record("battle/avg_reward_100", avg_reward)
            self.logger.record("battle/avg_episode_length_100", avg_length)
            self.logger.record("battle/total_episodes", self.total_episodes)

        return True


def make_env(
    data_dir: str,
    encounter_id: Optional[int] = None,
    player_unit_ids: Optional[list[int]] = None,
    enemy_unit_ids: Optional[list[int]] = None,
    enemy_positions: Optional[list[int]] = None,
    rank: int = 0,
    seed: int = 0
) -> Callable:
    """Create environment factory function."""

    def _init() -> BattleEnv:
        env = BattleEnv(
            data_dir=data_dir,
            encounter_id=encounter_id,
            player_unit_ids=player_unit_ids,
            enemy_unit_ids=enemy_unit_ids,
            enemy_positions=enemy_positions
        )
        env = Monitor(env)
        env.reset(seed=seed + rank)
        return env

    set_random_seed(seed)
    return _init


def get_action_mask_fn(env: BattleEnv) -> np.ndarray:
    """Action mask function for MaskablePPO."""
    return env._get_action_mask()


class TrainingConfig:
    """Configuration for training runs."""

    def __init__(
        self,
        data_dir: str,
        output_dir: str = "models",
        algorithm: str = "ppo",  # "ppo", "maskable_ppo", "dqn"
        total_timesteps: int = 1_000_000,
        n_envs: int = 4,
        learning_rate: float = 3e-4,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        ent_coef: float = 0.01,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        policy_kwargs: Optional[dict] = None,
        seed: int = 42,
        eval_freq: int = 10000,
        save_freq: int = 50000,
        verbose: int = 1
    ):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.algorithm = algorithm
        self.total_timesteps = total_timesteps
        self.n_envs = n_envs
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_range = clip_range
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef
        self.max_grad_norm = max_grad_norm
        self.policy_kwargs = policy_kwargs or {
            "net_arch": [256, 256],
            "activation_fn": torch.nn.ReLU
        }
        self.seed = seed
        self.eval_freq = eval_freq
        self.save_freq = save_freq
        self.verbose = verbose

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "algorithm": self.algorithm,
            "total_timesteps": self.total_timesteps,
            "n_envs": self.n_envs,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "n_epochs": self.n_epochs,
            "gamma": self.gamma,
            "gae_lambda": self.gae_lambda,
            "clip_range": self.clip_range,
            "ent_coef": self.ent_coef,
            "vf_coef": self.vf_coef,
            "max_grad_norm": self.max_grad_norm,
            "seed": self.seed
        }


class Trainer:
    """Handles training of RL agents."""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.model = None
        self.train_env = None
        self.eval_env = None

        # Create output directory
        self.run_dir = Path(config.output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Save config
        with open(self.run_dir / "config.json", "w") as f:
            json.dump(config.to_dict(), f, indent=2)

    def setup_environments(
        self,
        encounter_id: Optional[int] = None,
        player_unit_ids: Optional[list[int]] = None,
        enemy_unit_ids: Optional[list[int]] = None,
        enemy_positions: Optional[list[int]] = None
    ) -> None:
        """Set up training and evaluation environments."""
        # Training environments (vectorized)
        env_fns = [
            make_env(
                self.config.data_dir,
                encounter_id=encounter_id,
                player_unit_ids=player_unit_ids,
                enemy_unit_ids=enemy_unit_ids,
                enemy_positions=enemy_positions,
                rank=i,
                seed=self.config.seed
            )
            for i in range(self.config.n_envs)
        ]

        if self.config.n_envs > 1:
            self.train_env = SubprocVecEnv(env_fns)
        else:
            self.train_env = DummyVecEnv(env_fns)

        # Evaluation environment
        eval_env = BattleEnv(
            data_dir=self.config.data_dir,
            encounter_id=encounter_id,
            player_unit_ids=player_unit_ids,
            enemy_unit_ids=enemy_unit_ids,
            enemy_positions=enemy_positions
        )
        self.eval_env = Monitor(eval_env)

    def create_model(self) -> None:
        """Create the RL model based on config."""
        common_kwargs = {
            "learning_rate": self.config.learning_rate,
            "gamma": self.config.gamma,
            "verbose": self.config.verbose,
            "seed": self.config.seed,
            "tensorboard_log": str(self.run_dir / "tensorboard")
        }

        if self.config.algorithm == "ppo":
            self.model = PPO(
                "MlpPolicy",
                self.train_env,
                batch_size=self.config.batch_size,
                n_epochs=self.config.n_epochs,
                gae_lambda=self.config.gae_lambda,
                clip_range=self.config.clip_range,
                ent_coef=self.config.ent_coef,
                vf_coef=self.config.vf_coef,
                max_grad_norm=self.config.max_grad_norm,
                policy_kwargs=self.config.policy_kwargs,
                **common_kwargs
            )

        elif self.config.algorithm == "maskable_ppo" and HAS_MASKABLE_PPO:
            # Wrap environment with action masker
            self.model = MaskablePPO(
                "MlpPolicy",
                self.train_env,
                batch_size=self.config.batch_size,
                n_epochs=self.config.n_epochs,
                gae_lambda=self.config.gae_lambda,
                clip_range=self.config.clip_range,
                ent_coef=self.config.ent_coef,
                vf_coef=self.config.vf_coef,
                max_grad_norm=self.config.max_grad_norm,
                policy_kwargs=self.config.policy_kwargs,
                **common_kwargs
            )

        elif self.config.algorithm == "dqn":
            self.model = DQN(
                "MlpPolicy",
                self.train_env,
                batch_size=self.config.batch_size,
                buffer_size=100000,
                exploration_fraction=0.1,
                exploration_final_eps=0.05,
                policy_kwargs=self.config.policy_kwargs,
                **common_kwargs
            )

        else:
            raise ValueError(f"Unknown algorithm: {self.config.algorithm}")

    def train(self) -> None:
        """Run the training loop."""
        if self.model is None:
            raise RuntimeError("Model not created. Call create_model() first.")

        # Set up callbacks
        callbacks = []

        # Evaluation callback
        eval_callback = EvalCallback(
            self.eval_env,
            best_model_save_path=str(self.run_dir / "best_model"),
            log_path=str(self.run_dir / "eval_logs"),
            eval_freq=self.config.eval_freq,
            deterministic=True,
            render=False
        )
        callbacks.append(eval_callback)

        # Checkpoint callback
        checkpoint_callback = CheckpointCallback(
            save_freq=self.config.save_freq,
            save_path=str(self.run_dir / "checkpoints"),
            name_prefix="model"
        )
        callbacks.append(checkpoint_callback)

        # Custom metrics callback
        metrics_callback = BattleMetricsCallback(verbose=self.config.verbose)
        callbacks.append(metrics_callback)

        # Train
        self.model.learn(
            total_timesteps=self.config.total_timesteps,
            callback=CallbackList(callbacks),
            progress_bar=True
        )

        # Save final model
        self.model.save(str(self.run_dir / "final_model"))

        print(f"\nTraining complete!")
        print(f"Models saved to: {self.run_dir}")

    def evaluate(self, n_episodes: int = 100) -> dict:
        """Evaluate the trained model."""
        if self.model is None:
            raise RuntimeError("No model to evaluate.")

        wins = 0
        losses = 0
        total_reward = 0
        total_turns = 0

        for _ in range(n_episodes):
            obs, info = self.eval_env.reset()
            done = False
            episode_reward = 0

            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = self.eval_env.step(action)
                episode_reward += reward
                done = terminated or truncated

            total_reward += episode_reward
            total_turns += info.get("turn", 0)

            if info.get("result") == "PLAYER_WIN":
                wins += 1
            elif info.get("result") == "ENEMY_WIN":
                losses += 1

        results = {
            "n_episodes": n_episodes,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / n_episodes,
            "avg_reward": total_reward / n_episodes,
            "avg_turns": total_turns / n_episodes
        }

        # Save results
        with open(self.run_dir / "evaluation_results.json", "w") as f:
            json.dump(results, f, indent=2)

        return results

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.train_env:
            self.train_env.close()
        if self.eval_env:
            self.eval_env.close()


def train_simple_battle(
    data_dir: str,
    player_unit_ids: list[int],
    enemy_unit_ids: list[int],
    enemy_positions: list[int],
    output_dir: str = "models",
    total_timesteps: int = 500_000,
    algorithm: str = "ppo"
) -> str:
    """
    Convenience function to train on a simple battle scenario.

    Returns path to trained model.
    """
    config = TrainingConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        algorithm=algorithm,
        total_timesteps=total_timesteps,
        n_envs=4
    )

    trainer = Trainer(config)
    trainer.setup_environments(
        player_unit_ids=player_unit_ids,
        enemy_unit_ids=enemy_unit_ids,
        enemy_positions=enemy_positions
    )
    trainer.create_model()
    trainer.train()

    results = trainer.evaluate()
    print(f"\nEvaluation Results:")
    print(f"  Win Rate: {results['win_rate']:.2%}")
    print(f"  Avg Reward: {results['avg_reward']:.2f}")
    print(f"  Avg Turns: {results['avg_turns']:.1f}")

    trainer.cleanup()

    return str(trainer.run_dir / "final_model")


def curriculum_training(
    data_dir: str,
    player_unit_ids: list[int],
    encounter_ids: list[int],  # Ordered from easy to hard
    output_dir: str = "models/curriculum",
    timesteps_per_stage: int = 200_000
) -> str:
    """
    Train using curriculum learning - start with easy encounters,
    progress to harder ones.
    """
    model_path = None

    for stage, encounter_id in enumerate(encounter_ids):
        print(f"\n{'='*50}")
        print(f"Curriculum Stage {stage + 1}/{len(encounter_ids)}")
        print(f"Encounter ID: {encounter_id}")
        print(f"{'='*50}\n")

        config = TrainingConfig(
            data_dir=data_dir,
            output_dir=f"{output_dir}/stage_{stage}",
            algorithm="ppo",
            total_timesteps=timesteps_per_stage,
            n_envs=4
        )

        trainer = Trainer(config)
        trainer.setup_environments(
            encounter_id=encounter_id,
            player_unit_ids=player_unit_ids
        )
        trainer.create_model()

        # Load previous model weights if available
        if model_path and os.path.exists(model_path + ".zip"):
            print(f"Loading weights from: {model_path}")
            trainer.model.set_parameters(model_path)

        trainer.train()
        results = trainer.evaluate()

        print(f"Stage {stage + 1} Results: Win Rate = {results['win_rate']:.2%}")

        model_path = str(trainer.run_dir / "final_model")
        trainer.cleanup()

    return model_path


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="Train battle ML agent")
    parser.add_argument("--data-dir", default="data", help="Path to game data directory")
    parser.add_argument("--output-dir", default="models", help="Output directory for models")
    parser.add_argument("--timesteps", type=int, default=500_000, help="Total training timesteps")
    parser.add_argument("--algorithm", default="ppo", choices=["ppo", "maskable_ppo", "dqn"])
    parser.add_argument("--encounter-id", type=int, help="Encounter ID to train on")

    args = parser.parse_args()

    # Default training scenario if no encounter specified
    if args.encounter_id:
        config = TrainingConfig(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            algorithm=args.algorithm,
            total_timesteps=args.timesteps
        )
        trainer = Trainer(config)
        trainer.setup_environments(encounter_id=args.encounter_id)
        trainer.create_model()
        trainer.train()
        trainer.evaluate()
        trainer.cleanup()
    else:
        print("Please specify --encounter-id or provide unit IDs for custom battle")
