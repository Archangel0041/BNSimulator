"""Machine learning agents and training pipeline."""
from .agents import (
    BaseAgent, RandomAgent, GreedyDamageAgent,
    FocusFireAgent, HeuristicAgent
)

__all__ = [
    # Agents
    "BaseAgent", "RandomAgent", "GreedyDamageAgent",
    "FocusFireAgent", "HeuristicAgent",
]

# Training components require torch and stable-baselines3
try:
    from .train import (
        TrainingConfig, Trainer, BattleMetricsCallback,
        train_simple_battle, curriculum_training
    )
    __all__.extend([
        "TrainingConfig", "Trainer", "BattleMetricsCallback",
        "train_simple_battle", "curriculum_training"
    ])
except ImportError:
    # torch or stable-baselines3 not installed
    pass
