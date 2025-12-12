#!/usr/bin/env python3
"""Test visualization: Encounter 133 vs Unit 530 (Rank 6).

This script creates a specific battle scenario:
- Enemy side: Encounter 133 (with its configured units and ranks)
- Friendly side: Unit 530 at rank 6 on each position in the first row
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import BattleSimulator
from src.ml.agents import RandomAgent, HeuristicAgent
from scripts.battle_step_by_step import StepByStepBattle


def main():
    """Run the test battle."""
    print("=" * 70)
    print("Test Battle: Encounter 133 vs Unit 530 (Rank 6)")
    print("=" * 70)
    print()

    # Load data
    print("Loading game data...")
    simulator = BattleSimulator("data")

    # Check if encounter 133 exists
    encounter = simulator.data_loader.get_encounter(133)
    if not encounter:
        print("ERROR: Encounter 133 not found!")
        return

    # Check if unit 530 exists
    unit_530 = simulator.data_loader.get_unit(530)
    if not unit_530:
        print("ERROR: Unit 530 not found!")
        return

    print(f"✓ Encounter 133 loaded: {encounter.name}")
    print(f"  Layout ID: {encounter.layout_id}")
    print(f"  Enemy units: {len(encounter.enemy_units)}")
    for i, enemy in enumerate(encounter.enemy_units[:10]):
        unit = simulator.data_loader.get_unit(enemy.unit_id)
        if unit:
            print(f"    [{i}] Unit {enemy.unit_id} ({unit.name}) at grid {enemy.grid_id}, rank {enemy.rank}")

    print(f"\n✓ Unit 530 loaded: {unit_530.name}")
    print(f"  Class: {unit_530.class_type.name}")
    print(f"  Available ranks: 1-{len(unit_530.all_rank_stats)}")

    # Ranks are 1-based: rank 1 is index 0, rank 6 is index 5
    if len(unit_530.all_rank_stats) >= 6:
        rank_6_stats = unit_530.all_rank_stats[5]  # Rank 6 = index 5
        rank_1_stats = unit_530.all_rank_stats[0]  # Rank 1 = index 0
        print(f"  Rank 1 HP: {rank_1_stats.hp} | Rank 6 HP: {rank_6_stats.hp}")
        print(f"  Rank 1 Defense: {rank_1_stats.defense} | Rank 6 Defense: {rank_6_stats.defense}")
        print(f"  Rank 1 Power: {rank_1_stats.power} | Rank 6 Power: {rank_6_stats.power}")
    else:
        max_rank = len(unit_530.all_rank_stats)
        print(f"  WARNING: Rank 6 not available (max rank: {max_rank})")
        print(f"  Will use rank {max_rank} instead")

    # Get layout to determine first row positions
    layout = simulator.data_loader.get_layout(encounter.layout_id)
    if not layout:
        print(f"ERROR: Layout {encounter.layout_id} not found!")
        return

    # First row positions (y=0) - typically positions 0-4 for a 5-wide grid
    first_row_positions = list(range(min(5, layout.width)))
    num_player_units = len(first_row_positions)

    print(f"\n✓ Layout {layout.id} loaded: {layout.width}x{layout.height}")
    print(f"  Player positions (first row): {first_row_positions}")

    # Create player unit list (all unit 530)
    player_unit_ids = [530] * num_player_units
    player_ranks = [6] * num_player_units  # All at rank 6

    print(f"\n✓ Creating battle:")
    print(f"  Player: {num_player_units}x Unit 530 at rank 6")
    print(f"  Enemy: Encounter 133 ({len(encounter.enemy_units)} units)")

    print(f"\n  NOTE: Unit 530 weapons target tag [24], but raptors have tags [38, 32].")
    print(f"  This may result in no valid actions if weapons cannot target these enemies.")

    # Create battle from encounter
    battle = simulator.create_battle_from_encounter(
        encounter_id=133,
        player_unit_ids=player_unit_ids,
        player_ranks=player_ranks
    )

    if not battle:
        print("ERROR: Failed to create battle!")
        return

    print("\n✓ Battle created successfully!")

    # Set RNG seed for reproducibility
    battle.seed(42)

    # Ask for visualization mode
    print("\nChoose visualization mode:")
    print("  1. Step-by-step (press Enter after each turn)")
    print("  2. Auto-play (automatic with small delays)")
    print("  3. Skip visualization (just show final results)")

    try:
        mode = input("\nEnter choice (1, 2, or 3): ").strip()
    except (KeyboardInterrupt, EOFError):
        mode = "3"

    if mode in ["1", "2"]:
        auto_mode = (mode == "2")
        step_battle = StepByStepBattle(
            battle,
            player_agent=HeuristicAgent(),
            enemy_agent=RandomAgent(),
            auto_mode=auto_mode
        )
        step_battle.run_battle(max_turns=50)
    else:
        # Just run battle without visualization
        from src.simulator import BattleResult

        print("\nRunning battle...")
        player_agent = HeuristicAgent()
        enemy_agent = RandomAgent()

        def player_policy(state):
            return player_agent.select_action(state)

        def enemy_policy(state):
            return enemy_agent.select_action(state)

        result = simulator.run_battle(battle, player_policy, enemy_policy, max_turns=50)

        print(f"\n{'=' * 70}")
        print("BATTLE COMPLETE")
        print(f"{'=' * 70}")
        print(f"Result: {result.name}")
        print(f"Turns: {battle.turn_number}")
        print(f"Player units alive: {sum(1 for u in battle.player_units if u.is_alive)}/{len(battle.player_units)}")
        print(f"Enemy units alive: {sum(1 for u in battle.enemy_units if u.is_alive)}/{len(battle.enemy_units)}")


if __name__ == "__main__":
    main()
