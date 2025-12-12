#!/usr/bin/env python3
"""
Demo script for BN Simulator.
Shows how to use the simulator and test battles.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import get_game_data, GameData
from src.battle_engine import BattleEngine, BattleConfig
from src.gym_env import BNBattleEnv
from src.models import Side


def print_separator(title: str = ""):
    """Print a section separator."""
    print("\n" + "=" * 60)
    if title:
        print(f" {title}")
        print("=" * 60)
    print()


def demo_data_loading():
    """Demonstrate loading game data."""
    print_separator("Data Loading Demo")

    game_data = get_game_data()

    print(f"Loaded {len(game_data.units)} units")
    print(f"Loaded {len(game_data.abilities)} abilities")
    print(f"Loaded {len(game_data.encounters)} encounters")
    print(f"Loaded {len(game_data.status_effects)} status effects")
    print(f"Loaded {len(game_data.class_configs)} class configurations")
    print(f"Loaded {len(game_data.layouts)} grid layouts")

    # Show some sample units
    print("\nSample Player Units:")
    for unit in game_data.get_player_units()[:5]:
        if unit.stats_by_level:
            stats = unit.stats_by_level[0]
            print(f"  - {unit.name} (ID: {unit.id}): HP={stats.hp}, Power={stats.power}")

    print("\nSample Enemy Units:")
    for unit in game_data.get_enemy_units()[:5]:
        if unit.stats_by_level:
            stats = unit.stats_by_level[0]
            print(f"  - {unit.name} (ID: {unit.id}): HP={stats.hp}, Power={stats.power}")

    return game_data


def demo_battle_simulation(game_data: GameData):
    """Demonstrate battle simulation."""
    print_separator("Battle Simulation Demo")

    engine = BattleEngine(game_data, BattleConfig(seed=42, verbose=True))

    # Get some units for battle
    player_units = game_data.get_player_units()[:3]
    enemy_units = game_data.get_enemy_units()[:3]

    print("Setting up battle...")
    print(f"Player units: {[u.name for u in player_units]}")
    print(f"Enemy units: {[u.name for u in enemy_units]}")

    # Create battle
    state = engine.setup_custom_battle(
        [(u.id, 0, i) for i, u in enumerate(player_units)],
        [(u.id, 0, i + 5) for i, u in enumerate(enemy_units)]
    )

    print(f"\nBattle state initialized:")
    print(f"  Player units alive: {len(state.get_living_units(Side.PLAYER))}")
    print(f"  Enemy units alive: {len(state.get_living_units(Side.ENEMY))}")

    # Show valid actions
    actions = engine.get_valid_actions(state)
    print(f"\nValid actions available: {len(actions)}")

    if actions:
        action = actions[0]
        unit = state.player_units[action.unit_idx]
        ability = game_data.get_ability(action.ability_id)
        print(f"\nFirst action: {unit.template.name} uses {ability.name if ability else 'unknown'}")

        # Execute action
        result = engine.execute_action(state, action)
        print(f"Action executed:")
        for dmg_result in result.damage_results:
            target = state.enemy_units[dmg_result.target_idx]
            print(f"  - Hit {target.template.name} for {dmg_result.damage} damage")
            if dmg_result.is_crit:
                print("    (Critical hit!)")
            if dmg_result.killed:
                print("    (Killed!)")

    # Simulate rest of battle
    print("\nSimulating rest of battle...")
    state = engine.simulate_random_battle(state)

    print(f"\nBattle finished!")
    print(f"  Result: {'Victory' if state.player_won else 'Defeat'}")
    print(f"  Turns: {state.turn_number}")
    print(f"  Damage dealt: {state.total_damage_dealt}")
    print(f"  Damage taken: {state.total_damage_taken}")
    print(f"  Units lost: {state.units_lost}")
    print(f"  Enemies killed: {state.enemies_killed}")


def demo_gym_environment(game_data: GameData):
    """Demonstrate Gym environment."""
    print_separator("Gymnasium Environment Demo")

    # Create environment
    env = BNBattleEnv(seed=42, render_mode="ansi")
    obs, info = env.reset()

    print(f"Observation shape: {obs.shape}")
    print(f"Action space: {env.action_space}")
    print(f"Valid actions: {info['valid_actions']}")

    print("\nInitial state:")
    env.render()

    # Run a few steps
    print("\nRunning 5 random actions...")
    for i in range(5):
        mask = env.action_masks()
        valid_actions = [j for j in range(len(mask)) if mask[j]]

        if not valid_actions:
            print(f"  Step {i+1}: No valid actions, ending turn")
            break

        action = valid_actions[0]  # Take first valid action
        obs, reward, done, truncated, info = env.step(action)

        print(f"  Step {i+1}: action={action}, reward={reward:.2f}, done={done}")

        if done:
            print("\nBattle ended!")
            break

    env.close()


def demo_damage_lookup(game_data: GameData):
    """Demonstrate looking up damage information."""
    print_separator("Damage Information Lookup")

    # Find units by name pattern
    def find_unit_by_name(name_part: str) -> list:
        """Find units whose name contains the given string."""
        matches = []
        for unit in game_data.units.values():
            if name_part.lower() in unit.name.lower():
                matches.append(unit)
        return matches

    print("Searching for 'tank' units...")
    tank_units = find_unit_by_name("tank")[:5]
    for unit in tank_units:
        print(f"  - {unit.name} (ID: {unit.id}, Class: {unit.class_id})")
        if unit.stats_by_level:
            stats = unit.stats_by_level[0]
            print(f"      HP: {stats.hp}, Power: {stats.power}, Defense: {stats.defense}")
        if unit.weapons:
            print(f"      Weapons: {len(unit.weapons)}")
            for wid, weapon in unit.weapons.items():
                print(f"        - {weapon.name}: dmg {weapon.stats.base_damage_min}-{weapon.stats.base_damage_max}")

    print("\nSearching for 'raider' units...")
    raider_units = find_unit_by_name("raider")[:3]
    for unit in raider_units:
        print(f"  - {unit.name} (ID: {unit.id})")
        if unit.stats_by_level:
            stats = unit.stats_by_level[0]
            print(f"      HP: {stats.hp}, Defense: {stats.defense}")
            if stats.damage_mods:
                print(f"      Damage mods: {stats.damage_mods}")


def demo_encounter_info(game_data: GameData):
    """Demonstrate encounter information."""
    print_separator("Encounter Information")

    # Show some encounters
    encounters = list(game_data.encounters.values())[:5]

    for enc in encounters:
        print(f"Encounter {enc.id}: {enc.name}")
        print(f"  Level: {enc.level}")
        print(f"  Layout: {enc.layout_id}")
        print(f"  Attacker slots: {enc.attacker_slots}")
        print(f"  Waves: {len(enc.waves)}")

        if enc.waves:
            wave = enc.waves[0]
            print(f"  Wave 1 units: {len(wave.units)}")
            for grid_id, unit_id in wave.units[:3]:
                unit = game_data.get_unit(unit_id)
                if unit:
                    print(f"    - {unit.name} @ position {grid_id}")
        print()


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print(" BN SIMULATOR DEMO")
    print("=" * 60)

    game_data = demo_data_loading()
    demo_damage_lookup(game_data)
    demo_encounter_info(game_data)
    demo_battle_simulation(game_data)
    demo_gym_environment(game_data)

    print_separator("Demo Complete")
    print("You can now:")
    print("  - Run tests: pytest tests/ -v")
    print("  - Train an agent: python -m src.train --algorithm ppo --timesteps 10000")
    print("  - Use the Gym env: from src.gym_env import BNBattleEnv")


if __name__ == "__main__":
    main()
