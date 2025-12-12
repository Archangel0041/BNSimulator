"""Baseline and trained agents for battle simulation."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import random
import numpy as np

from src.simulator.battle import BattleState, Action, BattleResult


class BaseAgent(ABC):
    """Base class for battle agents."""

    @abstractmethod
    def select_action(self, battle: BattleState) -> Optional[Action]:
        """Select an action given the current battle state."""
        pass

    def reset(self) -> None:
        """Reset agent state for new episode."""
        pass


class RandomAgent(BaseAgent):
    """Agent that selects random legal actions."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def select_action(self, battle: BattleState) -> Optional[Action]:
        legal_actions = battle.get_legal_actions()
        if not legal_actions:
            return None
        return self.rng.choice(legal_actions)


class GreedyDamageAgent(BaseAgent):
    """Agent that prioritizes dealing maximum damage."""

    def select_action(self, battle: BattleState) -> Optional[Action]:
        legal_actions = battle.get_legal_actions()
        if not legal_actions:
            return None

        best_action = None
        best_score = -float('inf')

        for action in legal_actions:
            score = self._evaluate_action(battle, action)
            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def _evaluate_action(self, battle: BattleState, action: Action) -> float:
        """Evaluate an action based on potential damage."""
        units = battle.current_side_units
        if action.unit_index >= len(units):
            return -float('inf')

        unit = units[action.unit_index]
        weapon = unit.template.weapons.get(action.weapon_id)
        if not weapon:
            return -float('inf')

        # Base score from weapon damage
        score = (weapon.stats.base_damage_min + weapon.stats.base_damage_max) / 2

        # Bonus for targeting low HP enemies
        target = battle.get_unit_at_position(action.target_position)
        if target:
            hp_ratio = target.current_hp / target.template.stats.hp
            # Prefer low HP targets (finishing blows)
            score += (1 - hp_ratio) * 50

            # Bonus for class advantage
            class_mod = battle.data_loader.get_class_damage_mod(
                unit.template.class_type.value,
                target.template.class_type.value
            )
            score *= class_mod

        return score


class FocusFireAgent(BaseAgent):
    """Agent that focuses fire on single targets until dead."""

    def __init__(self):
        self.current_target: Optional[int] = None

    def select_action(self, battle: BattleState) -> Optional[Action]:
        legal_actions = battle.get_legal_actions()
        if not legal_actions:
            return None

        # Group actions by target
        targets = {}
        for action in legal_actions:
            target = battle.get_unit_at_position(action.target_position)
            if target and target.is_alive:
                target_idx = battle.opposing_side_units.index(target)
                if target_idx not in targets:
                    targets[target_idx] = []
                targets[target_idx].append(action)

        if not targets:
            return random.choice(legal_actions)

        # Check if current target is still valid
        if self.current_target is not None and self.current_target in targets:
            target_idx = self.current_target
        else:
            # Select new target (prefer lowest HP)
            target_idx = min(
                targets.keys(),
                key=lambda i: battle.opposing_side_units[i].current_hp
            )
            self.current_target = target_idx

        # Select best action against target
        target_actions = targets[target_idx]
        return max(target_actions, key=lambda a: self._action_damage_estimate(battle, a))

    def _action_damage_estimate(self, battle: BattleState, action: Action) -> float:
        """Estimate damage from an action."""
        units = battle.current_side_units
        unit = units[action.unit_index]
        weapon = unit.template.weapons.get(action.weapon_id)
        if not weapon:
            return 0
        return (weapon.stats.base_damage_min + weapon.stats.base_damage_max) / 2

    def reset(self) -> None:
        self.current_target = None


class HeuristicAgent(BaseAgent):
    """
    Agent using hand-crafted heuristics.

    Priorities:
    1. Kill low HP enemies (finishing blows)
    2. Focus fire on single targets
    3. Use class advantages
    4. Prefer high-damage abilities
    5. Protect low HP friendly units (attack threats)
    """

    def __init__(self):
        self.current_target: Optional[int] = None
        self.priority_targets: list[int] = []

    def select_action(self, battle: BattleState) -> Optional[Action]:
        legal_actions = battle.get_legal_actions()
        if not legal_actions:
            return None

        # Score all actions
        scored_actions = []
        for action in legal_actions:
            score = self._score_action(battle, action)
            scored_actions.append((score, action))

        scored_actions.sort(reverse=True, key=lambda x: x[0])

        # Add some randomness among top actions
        top_actions = [a for s, a in scored_actions[:3] if s > scored_actions[0][0] - 10]
        return random.choice(top_actions) if top_actions else scored_actions[0][1]

    def _score_action(self, battle: BattleState, action: Action) -> float:
        """Score an action based on heuristics."""
        units = battle.current_side_units
        unit = units[action.unit_index]
        weapon = unit.template.weapons.get(action.weapon_id)
        if not weapon:
            return -1000

        target = battle.get_unit_at_position(action.target_position)
        if not target:
            return -1000

        score = 0.0

        # Base damage estimate
        avg_damage = (weapon.stats.base_damage_min + weapon.stats.base_damage_max) / 2
        score += avg_damage

        # Huge bonus for potential kills
        if target.current_hp <= avg_damage * 1.5:
            score += 200

        # Class advantage bonus
        class_mod = battle.data_loader.get_class_damage_mod(
            unit.template.class_type.value,
            target.template.class_type.value
        )
        if class_mod > 1.0:
            score += (class_mod - 1.0) * 50
        elif class_mod < 1.0:
            score -= (1.0 - class_mod) * 30

        # Focus fire bonus (same target as before)
        if self.current_target is not None:
            try:
                if battle.opposing_side_units.index(target) == self.current_target:
                    score += 20
            except (ValueError, IndexError):
                pass

        # HP-based targeting (prefer low HP)
        hp_ratio = target.current_hp / target.template.stats.hp
        score += (1 - hp_ratio) * 30

        # Threat assessment (prioritize high damage enemies)
        enemy_power = target.template.stats.power
        score += enemy_power * 0.5

        # Penalize overkill
        if avg_damage > target.current_hp * 2:
            score -= 20

        # Cooldown efficiency (prefer abilities we can use again soon)
        ability_id = weapon.abilities[0] if weapon.abilities else None
        if ability_id:
            ability = battle.data_loader.get_ability(ability_id)
            if ability and ability.stats.ability_cooldown > 2:
                score -= ability.stats.ability_cooldown * 5

        return score

    def reset(self) -> None:
        self.current_target = None
        self.priority_targets = []


class MaskablePPOAgent(BaseAgent):
    """Wrapper for trained Stable-Baselines3 MaskablePPO model."""

    def __init__(self, model_path: str, env):
        from sb3_contrib import MaskablePPO
        self.model = MaskablePPO.load(model_path)
        self.env = env

    def select_action(self, battle: BattleState) -> Optional[Action]:
        # Get observation
        obs = battle.get_state_vector()

        # Get action mask
        action_mask = self.env._get_action_mask()

        # Predict action
        action, _ = self.model.predict(obs, action_masks=action_mask, deterministic=True)

        # Convert to battle action
        return self.env._action_to_battle_action(int(action))
