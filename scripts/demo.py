#!/usr/bin/env python3
"""Demo script to test the battle simulator."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import (
    GameDataLoader, BattleSimulator, BattleResult,
    BattleEnv, Position
)
from src.ml.agents import RandomAgent, HeuristicAgent


def test_data_loading():
    """Test that data loads correctly."""
    print("=" * 50)
    print("Testing Data Loading...")
    print("=" * 50)

    loader = GameDataLoader("data")
    loader.load_all()

    print(f"Loaded {len(loader.units)} units")
    print(f"Loaded {len(loader.abilities)} abilities")
    print(f"Loaded {len(loader.encounters)} encounters")
    print(f"Loaded {len(loader.status_effects)} status effects")
    print(f"Loaded {len(loader.config.layouts)} layouts")

    # Show sample unit
    sample_id = next(iter(loader.units.keys()))
    sample_unit = loader.units[sample_id]
    print(f"\nSample Unit #{sample_id}:")
    print(f"  Name: {sample_unit.name}")
    print(f"  Class: {sample_unit.class_type.name}")
    print(f"  HP: {sample_unit.stats.hp}")
    print(f"  Weapons: {len(sample_unit.weapons)}")

    return loader


def test_battle_simulation(loader):
    """Test running a battle."""
    print("\n" + "=" * 50)
    print("Testing Battle Simulation...")
    print("=" * 50)

    simulator = BattleSimulator("data")

    # Get units that have weapons
    units_with_weapons = [
        uid for uid, unit in loader.units.items()
        if unit.weapons
    ][:8]

    if len(units_with_weapons) < 4:
        print("Not enough units with weapons for demo")
        return None

    print(f"Using units: {units_with_weapons[:4]}")

    # Create battle
    battle = simulator.create_custom_battle(
        layout_id=2,
        player_unit_ids=units_with_weapons[:2],
        player_positions=[0, 1],
        enemy_unit_ids=units_with_weapons[2:4],
        enemy_positions=[0, 1]
    )

    if battle is None:
        print("Failed to create battle")
        return None

    print(f"Battle created!")
    print(f"  Player units: {len(battle.player_units)}")
    print(f"  Enemy units: {len(battle.enemy_units)}")
    print(f"  Layout: {battle.layout.width}x{battle.layout.height}")

    # Run battle with heuristic agents
    player_agent = HeuristicAgent()
    enemy_agent = RandomAgent()

    def player_policy(state):
        return player_agent.select_action(state)

    def enemy_policy(state):
        return enemy_agent.select_action(state)

    result = simulator.run_battle(battle, player_policy, enemy_policy, max_turns=50)

    print(f"\nBattle Result: {result.name}")
    print(f"  Turns played: {battle.turn_number}")
    print(f"  Player units alive: {sum(1 for u in battle.player_units if u.is_alive)}")
    print(f"  Enemy units alive: {sum(1 for u in battle.enemy_units if u.is_alive)}")

    return battle


def test_gym_environment(loader):
    """Test the Gymnasium environment."""
    print("\n" + "=" * 50)
    print("Testing Gymnasium Environment...")
    print("=" * 50)

    units_with_weapons = [
        uid for uid, unit in loader.units.items()
        if unit.weapons
    ][:8]

    if len(units_with_weapons) < 4:
        print("Not enough units with weapons for demo")
        return

    env = BattleEnv(
        data_dir="data",
        player_unit_ids=units_with_weapons[:2],
        enemy_unit_ids=units_with_weapons[2:4],
        enemy_positions=[0, 1],
        render_mode="ansi"
    )

    print(f"Environment created!")
    print(f"  Observation space: {env.observation_space}")
    print(f"  Action space: {env.action_space}")

    # Run a few episodes
    total_reward = 0
    wins = 0
    episodes = 5

    for ep in range(episodes):
        obs, info = env.reset(seed=ep)
        done = False
        ep_reward = 0
        steps = 0

        while not done and steps < 100:
            # Use action mask to select valid action
            action_mask = info["action_mask"]
            valid_actions = [i for i in range(len(action_mask)) if action_mask[i] == 1]

            if valid_actions:
                import random
                action = random.choice(valid_actions)
            else:
                action = env.action_space.sample()

            obs, reward, terminated, truncated, info = env.step(action)
            ep_reward += reward
            done = terminated or truncated
            steps += 1

        total_reward += ep_reward
        if info.get("result") == "PLAYER_WIN":
            wins += 1

        print(f"  Episode {ep + 1}: Reward={ep_reward:.2f}, Steps={steps}, Result={info.get('result', 'N/A')}")

    print(f"\nSummary over {episodes} episodes:")
    print(f"  Win rate: {wins/episodes:.1%}")
    print(f"  Avg reward: {total_reward/episodes:.2f}")

    # Show render
    print("\nSample render:")
    env.reset()
    print(env.render())

    env.close()


def main():
    """Run all demo tests."""
    print("Battle Simulator ML Demo")
    print("========================\n")

    # Test data loading
    loader = test_data_loading()

    if loader:
        # Test battle simulation
        test_battle_simulation(loader)

        # Test gym environment
        test_gym_environment(loader)

    print("\n" + "=" * 50)
    print("Demo Complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
