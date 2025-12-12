#!/usr/bin/env python3
"""Launch GUI battle visualizer for testing targeting patterns and AOE.

This script creates a battle and launches the GUI visualizer to test:
- Targeting pattern visualization
- AOE/damage pattern overlays
- Reticle-based targeting
- Interactive battle progression
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import BattleSimulator
from src.utils.gui_visualizer import visualize_battle_gui


def main():
    """Launch GUI battle visualizer."""
    print("=" * 70)
    print("GUI Battle Visualizer")
    print("=" * 70)
    print()

    # Ask user for battle type
    print("Choose battle type:")
    print("  1. Encounter 133 vs Unit 530 Rank 6 (from previous test)")
    print("  2. Custom battle (random units)")
    print("  3. Simple 2v2 test battle")

    try:
        choice = input("\nEnter choice (1-3): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return

    simulator = BattleSimulator("data")

    if choice == "1":
        # Encounter 133 vs Unit 530 Rank 6
        encounter = simulator.data_loader.get_encounter(133)
        if not encounter:
            print("ERROR: Encounter 133 not found!")
            return

        layout = simulator.data_loader.get_layout(encounter.layout_id)
        num_player_units = min(5, layout.width)

        battle = simulator.create_battle_from_encounter(
            encounter_id=133,
            player_unit_ids=[530] * num_player_units,
            player_ranks=[6] * num_player_units
        )

    elif choice == "3":
        # Simple 2v2 test
        print("\nCreating simple 2v2 battle...")

        # Find units with weapons
        units_with_weapons = [
            uid for uid, unit in simulator.data_loader.units.items()
            if unit.weapons and len(unit.weapons) > 0
        ][:4]

        if len(units_with_weapons) < 4:
            print("ERROR: Not enough units with weapons!")
            return

        battle = simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=units_with_weapons[:2],
            player_positions=[0, 1],
            enemy_unit_ids=units_with_weapons[2:4],
            enemy_positions=[0, 1],
            player_ranks=[3, 3],  # Mid-level ranks
            enemy_ranks=[2, 2]
        )

    else:
        # Custom battle with random units
        print("\nCreating random battle...")

        units_with_weapons = [
            uid for uid, unit in simulator.data_loader.units.items()
            if unit.weapons
        ][:8]

        if len(units_with_weapons) < 4:
            print("ERROR: Not enough units with weapons!")
            return

        battle = simulator.create_custom_battle(
            layout_id=2,
            player_unit_ids=units_with_weapons[:3],
            player_positions=[0, 1, 5],
            enemy_unit_ids=units_with_weapons[3:6],
            enemy_positions=[0, 1, 5]
        )

    if not battle:
        print("ERROR: Failed to create battle!")
        return

    print("\n✓ Battle created successfully!")
    print(f"  Player units: {len(battle.player_units)}")
    print(f"  Enemy units: {len(battle.enemy_units)}")
    print(f"  Layout: {battle.layout.width}x{battle.layout.height}")
    print()

    print("=" * 70)
    print("GUI CONTROLS:")
    print("=" * 70)
    print("  • Click on your units to select them")
    print("  • Click on a weapon button to select weapon")
    print("  • Valid targets will be highlighted in blue")
    print("  • Hover over targets to see AOE damage patterns:")
    print("    - Red: Primary damage (100%)")
    print("    - Orange: Secondary damage (<100%)")
    print("  • Click on a target to execute the attack")
    print("  • Click 'End Turn' to pass to the enemy")
    print("  • Click 'Clear Selection' to deselect")
    print()
    print("Launching GUI...")
    print("=" * 70)
    print()

    # Set seed for reproducibility
    battle.seed(42)

    # Launch GUI
    visualize_battle_gui(battle)


if __name__ == "__main__":
    main()
