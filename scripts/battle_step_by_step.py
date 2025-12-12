#!/usr/bin/env python3
"""Step-by-step battle visualization script.

This script runs a battle and visualizes each turn, showing:
- Initial battle state
- What happens when the battle begins
- Each side's attacks turn by turn
- Results of each action
- Final battle outcome
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import (
    GameDataLoader, BattleSimulator, BattleResult, Action
)
from src.simulator.models import Position
from src.utils.visualizer import BattleVisualizer, Colors
from src.ml.agents import RandomAgent, HeuristicAgent


class StepByStepBattle:
    """Run and visualize a battle step-by-step."""

    def __init__(self, battle, player_agent=None, enemy_agent=None, auto_mode=False):
        self.battle = battle
        self.viz = BattleVisualizer(battle)
        self.player_agent = player_agent or HeuristicAgent()
        self.enemy_agent = enemy_agent or RandomAgent()
        self.turn_count = 0
        self.auto_mode = auto_mode

    def show_initial_state(self):
        """Show the initial battle state."""
        print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}")
        print(f"{Colors.BOLD}BATTLE BEGINS!{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

        print(f"{Colors.GREEN}Player Forces:{Colors.RESET}")
        for i, unit in enumerate(self.battle.player_units):
            print(f"  [{i}] {unit.template.class_type.name} - HP: {unit.current_hp}/{unit.template.stats.hp} - "
                  f"Position: ({unit.position.x}, {unit.position.y})")
            for wid, weapon in unit.template.weapons.items():
                print(f"      • {weapon.name} (DMG: {weapon.stats.base_damage_min}-{weapon.stats.base_damage_max})")

        print(f"\n{Colors.RED}Enemy Forces:{Colors.RESET}")
        for i, unit in enumerate(self.battle.enemy_units):
            print(f"  [{i}] {unit.template.class_type.name} - HP: {unit.current_hp}/{unit.template.stats.hp} - "
                  f"Position: ({unit.position.x}, {unit.position.y})")
            for wid, weapon in unit.template.weapons.items():
                print(f"      • {weapon.name} (DMG: {weapon.stats.base_damage_min}-{weapon.stats.base_damage_max})")

        print(f"\n{Colors.CYAN}Battle Grid:{Colors.RESET}")
        print(self.viz.render_grid())

        if not self.auto_mode:
            input(f"\n{Colors.YELLOW}Press Enter to start the battle...{Colors.RESET}")

    def execute_turn(self):
        """Execute one complete turn (one side's action)."""
        self.turn_count += 1

        # Determine whose turn it is
        current_side = "PLAYER" if self.battle.is_player_turn else "ENEMY"
        side_color = Colors.GREEN if self.battle.is_player_turn else Colors.RED

        print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}")
        print(f"{side_color}{Colors.BOLD}TURN {self.turn_count}: {current_side} PHASE{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

        # Get legal actions
        legal_actions = self.battle.get_legal_actions()

        if not legal_actions:
            print(f"{Colors.YELLOW}No valid actions available. Turn skipped.{Colors.RESET}")
            self.battle.end_turn()
            return

        # Choose action based on agent
        if self.battle.is_player_turn:
            action = self.player_agent.select_action(self.battle)
        else:
            action = self.enemy_agent.select_action(self.battle)

        # Validate action
        if action not in legal_actions:
            # Try to find a matching action
            action = self._find_matching_action(action, legal_actions)
            if action is None:
                print(f"{Colors.YELLOW}Agent selected invalid action. Using random action.{Colors.RESET}")
                import random
                action = random.choice(legal_actions)

        # Show action details
        self._show_action_details(action)

        # Execute action
        result = self.battle.execute_action(action)

        # Show results
        self._show_action_results(action, result)

        # End turn
        self.battle.end_turn()

        # Show updated grid
        print(f"\n{Colors.CYAN}Updated Battlefield:{Colors.RESET}")
        print(self.viz.render_grid())

        # Check if battle ended
        if self.battle.result != BattleResult.IN_PROGRESS:
            return False

        # Pause for user to see the results
        if not self.auto_mode:
            input(f"\n{Colors.YELLOW}Press Enter to continue to next turn...{Colors.RESET}")
        return True

    def _find_matching_action(self, action, legal_actions):
        """Find a legal action that matches the given action."""
        for legal in legal_actions:
            if (action.unit_index == legal.unit_index and
                action.weapon_id == legal.weapon_id and
                action.target_position == legal.target_position):
                return legal
        return None

    def _show_action_details(self, action):
        """Show details about the action being taken."""
        units = self.battle.current_side_units
        unit = units[action.unit_index]
        weapon = unit.template.weapons.get(action.weapon_id)

        target_unit = self.battle.get_unit_at_position(action.target_position)
        target_name = target_unit.template.class_type.name if target_unit else "Empty Space"

        print(f"{Colors.BOLD}Action:{Colors.RESET}")
        print(f"  Attacker: {unit.template.class_type.name} at ({unit.position.x}, {unit.position.y})")
        print(f"  Weapon: {weapon.name if weapon else 'Unknown'}")
        print(f"  Target: {target_name} at ({action.target_position.x}, {action.target_position.y})")

        if weapon:
            print(f"  Base Damage: {weapon.stats.base_damage_min}-{weapon.stats.base_damage_max}")

            # Show ability info
            if weapon.abilities:
                ability = self.battle.data_loader.get_ability(weapon.abilities[0])
                if ability:
                    print(f"  Ability: {ability.name}")
                    print(f"  Range: {ability.stats.min_range}-{ability.stats.max_range}")

    def _show_action_results(self, action, result):
        """Show the results of an action."""
        print(f"\n{Colors.BOLD}Results:{Colors.RESET}")

        if not result.success:
            print(f"  {Colors.RED}✗ Action failed: {result.message}{Colors.RESET}")
            return

        if result.damage_dealt:
            print(f"  {Colors.YELLOW}Damage Dealt:{Colors.RESET}")
            opposing_units = self.battle.opposing_side_units
            for unit_idx, damage in result.damage_dealt.items():
                if unit_idx < len(opposing_units):
                    target = opposing_units[unit_idx]
                    status = f"HP: {target.current_hp}/{target.template.stats.hp}"
                    if not target.is_alive:
                        status = f"{Colors.RED}DEFEATED!{Colors.RESET}"
                    print(f"    • {target.template.class_type.name}: {damage} damage ({status})")

        if result.kills:
            print(f"  {Colors.RED}Units Defeated: {len(result.kills)}{Colors.RESET}")

        if result.status_applied:
            print(f"  {Colors.MAGENTA}Status Effects Applied:{Colors.RESET}")
            for unit_idx, effect_id in result.status_applied:
                effect = self.battle.data_loader.status_effects.get(effect_id)
                if effect:
                    print(f"    • {effect.family.name} ({effect.duration} turns)")

        if not result.damage_dealt and not result.kills and not result.status_applied:
            print(f"  {Colors.YELLOW}Attack missed or had no effect{Colors.RESET}")

    def run_battle(self, max_turns=50):
        """Run the complete battle step-by-step."""
        # Show initial state
        self.show_initial_state()

        # Run turns until battle ends or max turns reached
        while self.battle.result == BattleResult.IN_PROGRESS and self.battle.turn_number < max_turns:
            continue_battle = self.execute_turn()

            if not continue_battle:
                break

            # In auto mode, add small delay for readability
            if self.auto_mode:
                import time
                time.sleep(0.5)

        # Show final results
        self._show_final_results()

    def _show_final_results(self):
        """Show the final battle results."""
        print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}")
        print(f"{Colors.BOLD}BATTLE ENDED!{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

        if self.battle.result == BattleResult.PLAYER_WIN:
            print(f"{Colors.GREEN}{Colors.BOLD}VICTORY!{Colors.RESET}")
            print(f"{Colors.GREEN}Player forces have defeated the enemy!{Colors.RESET}")
        elif self.battle.result == BattleResult.ENEMY_WIN:
            print(f"{Colors.RED}{Colors.BOLD}DEFEAT!{Colors.RESET}")
            print(f"{Colors.RED}Enemy forces have defeated the player!{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Battle ended in a draw or surrender.{Colors.RESET}")

        print(f"\n{Colors.CYAN}Final Statistics:{Colors.RESET}")
        print(f"  Total Turns: {self.battle.turn_number}")
        print(f"  Total Actions: {len(self.battle.action_history)}")

        player_alive = sum(1 for u in self.battle.player_units if u.is_alive)
        enemy_alive = sum(1 for u in self.battle.enemy_units if u.is_alive)
        print(f"  Player Units Remaining: {player_alive}/{len(self.battle.player_units)}")
        print(f"  Enemy Units Remaining: {enemy_alive}/{len(self.battle.enemy_units)}")

        print(f"\n{Colors.CYAN}Final Battlefield:{Colors.RESET}")
        print(self.viz.render_grid())


def main():
    """Run a step-by-step battle visualization."""
    print(f"{Colors.BOLD}Battle Simulator - Step-by-Step Visualization{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

    # Load data and create battle
    print("Loading game data...")
    simulator = BattleSimulator("data")

    # Get units with weapons
    units_with_weapons = [
        uid for uid, unit in simulator.data_loader.units.items()
        if unit.weapons
    ][:8]

    if len(units_with_weapons) < 4:
        print("Not enough units with weapons for demo")
        return

    print(f"Creating battle with units: {units_with_weapons[:4]} vs {units_with_weapons[4:8]}\n")

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
        return

    # Set RNG seed for reproducibility
    battle.seed(42)

    # Ask for mode
    print(f"{Colors.YELLOW}Choose mode:{Colors.RESET}")
    print("  1. Step-by-step (press Enter after each turn)")
    print("  2. Auto-play (automatic with small delays)")

    try:
        mode = input("\nEnter choice (1 or 2): ").strip()
        auto_mode = mode == "2"
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    # Run battle
    step_battle = StepByStepBattle(
        battle,
        player_agent=HeuristicAgent(),
        enemy_agent=RandomAgent(),
        auto_mode=auto_mode
    )

    try:
        step_battle.run_battle(max_turns=50)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Battle interrupted by user.{Colors.RESET}")


if __name__ == "__main__":
    main()
