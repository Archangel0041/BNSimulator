"""Interactive battle visualizer for debugging and verification."""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import sys

if TYPE_CHECKING:
    from src.simulator.battle import BattleState, BattleUnit, Action
    from src.simulator.models import Position, Ability

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


class BattleVisualizer:
    """
    Terminal-based battle visualizer with interactive controls.

    Features:
    - View battle grid with unit positions
    - Highlight valid targets for selected unit/weapon
    - Show AOE damage patterns
    - Step-by-step battle execution
    """

    GRID_WIDTH = 5
    GRID_HEIGHT = 3
    CELL_WIDTH = 12

    def __init__(self, battle: "BattleState"):
        self.battle = battle
        self.selected_unit_idx: Optional[int] = None
        self.selected_weapon_idx: Optional[int] = None
        self.highlighted_targets: set[tuple[int, int]] = set()
        self.aoe_pattern: dict[tuple[int, int], float] = {}

    def render_grid(
        self,
        side: str = "both",
        show_targets: bool = True,
        show_aoe: bool = True
    ) -> str:
        """Render the battle grid as a string."""
        lines = []

        # Header
        lines.append(f"\n{Colors.BOLD}=== Turn {self.battle.turn_number} ==={Colors.RESET}")
        turn_indicator = f"{Colors.GREEN}PLAYER TURN{Colors.RESET}" if self.battle.is_player_turn else f"{Colors.RED}ENEMY TURN{Colors.RESET}"
        lines.append(turn_indicator)
        lines.append("")

        # Enemy grid (top)
        if side in ("both", "enemy"):
            lines.append(f"{Colors.RED}ENEMY SIDE{Colors.RESET}")
            lines.extend(self._render_side_grid(
                self.battle.enemy_units,
                is_enemy=True,
                show_targets=show_targets,
                show_aoe=show_aoe
            ))
            lines.append("")

        # Separator
        lines.append("─" * (self.CELL_WIDTH * self.GRID_WIDTH + self.GRID_WIDTH + 1))
        lines.append("")

        # Player grid (bottom)
        if side in ("both", "player"):
            lines.append(f"{Colors.GREEN}PLAYER SIDE{Colors.RESET}")
            lines.extend(self._render_side_grid(
                self.battle.player_units,
                is_enemy=False,
                show_targets=show_targets,
                show_aoe=show_aoe
            ))

        return "\n".join(lines)

    def _render_side_grid(
        self,
        units: list["BattleUnit"],
        is_enemy: bool,
        show_targets: bool,
        show_aoe: bool
    ) -> list[str]:
        """Render one side's grid."""
        lines = []

        # Column headers
        header = "     "
        for x in range(self.GRID_WIDTH):
            header += f"  Col {x}   "
        lines.append(header)

        # Create grid lookup
        unit_at = {}
        for unit in units:
            key = (unit.position.x, unit.position.y)
            unit_at[key] = unit

        # Render rows (front to back for enemy, back to front for player display)
        row_order = range(self.GRID_HEIGHT) if is_enemy else range(self.GRID_HEIGHT - 1, -1, -1)
        row_labels = ["Front", "Mid  ", "Back "]

        for y in row_order:
            row_str = f"{row_labels[y]} │"

            for x in range(self.GRID_WIDTH):
                pos = (x, y)
                unit = unit_at.get(pos)

                # Determine cell styling
                cell_bg = ""
                cell_fg = ""

                if show_aoe and pos in self.aoe_pattern:
                    dmg_pct = self.aoe_pattern[pos]
                    if dmg_pct >= 80:
                        cell_bg = Colors.BG_RED
                    elif dmg_pct >= 40:
                        cell_bg = Colors.BG_YELLOW
                    else:
                        cell_bg = Colors.BG_MAGENTA

                if show_targets and pos in self.highlighted_targets:
                    cell_bg = Colors.BG_CYAN

                # Build cell content
                if unit and unit.is_alive:
                    hp_pct = int(unit.current_hp / unit.template.stats.hp * 100)
                    class_short = unit.template.class_type.name[:3]

                    if hp_pct > 70:
                        hp_color = Colors.GREEN
                    elif hp_pct > 30:
                        hp_color = Colors.YELLOW
                    else:
                        hp_color = Colors.RED

                    # Check if this is the selected unit
                    if not is_enemy and self.selected_unit_idx is not None:
                        if units.index(unit) == self.selected_unit_idx:
                            cell_fg = Colors.BOLD + Colors.WHITE
                            cell_bg = Colors.BG_BLUE

                    cell = f"{cell_bg}{cell_fg}{class_short} {hp_color}{hp_pct:3d}%{Colors.RESET}"
                    cell = cell.ljust(self.CELL_WIDTH + 20)  # Account for ANSI codes
                else:
                    cell = f"{cell_bg}   ---   {Colors.RESET}"
                    cell = cell.ljust(self.CELL_WIDTH + 10)

                row_str += cell + "│"

            lines.append(row_str)

        return lines

    def show_unit_info(self, unit: "BattleUnit") -> str:
        """Show detailed info about a unit."""
        t = unit.template
        s = t.stats

        lines = [
            f"\n{Colors.BOLD}=== Unit Info ==={Colors.RESET}",
            f"Name: {t.name}",
            f"Class: {t.class_type.name}",
            f"Tags: {t.tags}",
            f"",
            f"HP: {unit.current_hp}/{s.hp} ({int(unit.current_hp/s.hp*100)}%)",
            f"Armor: {unit.current_armor}/{s.armor_hp}" if s.armor_hp > 0 else "",
            f"Position: ({unit.position.x}, {unit.position.y})",
            f"",
            f"Stats:",
            f"  Defense: {s.defense}",
            f"  Dodge: {s.dodge}%",
            f"  Accuracy: {s.accuracy}",
            f"  Critical: {s.critical}%",
            f"  Power: {s.power}",
            f"",
            f"Weapons ({len(t.weapons)}):"
        ]

        for wid, weapon in t.weapons.items():
            ws = weapon.stats
            cooldown = unit.weapon_cooldowns.get(wid, 0)
            ammo_str = f"Ammo: {unit.ammo.get(wid, 0)}/{ws.ammo}" if ws.ammo >= 0 else "Ammo: ∞"
            cd_str = f"[CD: {cooldown}]" if cooldown > 0 else "[Ready]"

            lines.append(f"  [{wid}] {weapon.name}")
            lines.append(f"      Damage: {ws.base_damage_min}-{ws.base_damage_max}")
            lines.append(f"      {ammo_str} {cd_str}")

            # Show abilities
            for aid in weapon.abilities:
                ability = self.battle.data_loader.get_ability(aid)
                if ability:
                    lines.append(f"      → {ability.name}")
                    lines.append(f"        Range: {ability.stats.min_range}-{ability.stats.max_range}")
                    lines.append(f"        Targets: {ability.stats.targets}")

        if unit.status_effects:
            lines.append(f"\nStatus Effects:")
            for status in unit.status_effects:
                lines.append(f"  - {status.effect.family.name}: {status.remaining_turns} turns")

        return "\n".join(filter(None, lines))

    def highlight_valid_targets(self, unit_idx: int, weapon_id: int) -> list[tuple[int, int]]:
        """Highlight valid targets for a unit/weapon combo."""
        self.selected_unit_idx = unit_idx
        self.selected_weapon_idx = weapon_id
        self.highlighted_targets.clear()
        self.aoe_pattern.clear()

        unit = self.battle.player_units[unit_idx]
        targets = self.battle.get_valid_targets(unit, weapon_id)

        for pos in targets:
            self.highlighted_targets.add((pos.x, pos.y))

        return list(self.highlighted_targets)

    def show_aoe_pattern(self, ability: "Ability", target_x: int, target_y: int):
        """Show AOE pattern for an ability at a target position."""
        self.aoe_pattern.clear()

        stats = ability.stats

        # Show damage_area pattern
        if stats.damage_area:
            for entry in stats.damage_area:
                px = target_x + entry.pos.x
                py = target_y + entry.pos.y
                self.aoe_pattern[(px, py)] = entry.damage_percent

        # Show target_area pattern if it's an AOE type
        if stats.target_area and stats.target_area.target_type != 2:  # Not single target
            for entry in stats.target_area.data:
                px = target_x + entry.pos.x
                py = target_y + entry.pos.y
                dmg = getattr(entry, 'damage_percent', 100)
                if (px, py) in self.aoe_pattern:
                    self.aoe_pattern[(px, py)] = max(self.aoe_pattern[(px, py)], dmg)
                else:
                    self.aoe_pattern[(px, py)] = dmg

    def clear_highlights(self):
        """Clear all highlights."""
        self.selected_unit_idx = None
        self.selected_weapon_idx = None
        self.highlighted_targets.clear()
        self.aoe_pattern.clear()

    def show_legal_actions(self) -> str:
        """Show all legal actions for current turn."""
        actions = self.battle.get_legal_actions()
        lines = [f"\n{Colors.BOLD}=== Legal Actions ({len(actions)}) ==={Colors.RESET}"]

        # Group by unit
        by_unit = {}
        for action in actions:
            if action.unit_index not in by_unit:
                by_unit[action.unit_index] = []
            by_unit[action.unit_index].append(action)

        for unit_idx, unit_actions in by_unit.items():
            unit = self.battle.current_side_units[unit_idx]
            lines.append(f"\nUnit {unit_idx}: {unit.template.class_type.name} at ({unit.position.x}, {unit.position.y})")

            # Group by weapon
            by_weapon = {}
            for action in unit_actions:
                if action.weapon_id not in by_weapon:
                    by_weapon[action.weapon_id] = []
                by_weapon[action.weapon_id].append(action)

            for weapon_id, weapon_actions in by_weapon.items():
                weapon = unit.template.weapons.get(weapon_id)
                if weapon:
                    lines.append(f"  Weapon {weapon_id}: {weapon.name}")
                    targets = [f"({a.target_position.x},{a.target_position.y})" for a in weapon_actions]
                    lines.append(f"    Targets: {', '.join(targets)}")

        return "\n".join(lines)


class InteractiveBattleSession:
    """Interactive session for debugging battles."""

    def __init__(self, battle: "BattleState"):
        self.battle = battle
        self.viz = BattleVisualizer(battle)
        self.history = []

    def run(self):
        """Run interactive session."""
        print(f"\n{Colors.BOLD}=== Interactive Battle Session ==={Colors.RESET}")
        print("Commands:")
        print("  g - Show grid")
        print("  u <idx> - Show unit info (e.g., 'u 0' for player unit 0)")
        print("  t <unit> <weapon> - Highlight targets (e.g., 't 0 1')")
        print("  a <unit> <weapon> <x> <y> - Execute action")
        print("  l - Show legal actions")
        print("  n - Next turn (skip)")
        print("  r - Random action")
        print("  c - Clear highlights")
        print("  q - Quit")
        print("")

        while self.battle.result.name == "IN_PROGRESS":
            try:
                cmd = input(f"\n[Turn {self.battle.turn_number}] > ").strip().lower()

                if not cmd:
                    continue

                parts = cmd.split()
                command = parts[0]

                if command == 'q':
                    break
                elif command == 'g':
                    print(self.viz.render_grid())
                elif command == 'u' and len(parts) >= 2:
                    idx = int(parts[1])
                    units = self.battle.player_units if self.battle.is_player_turn else self.battle.enemy_units
                    if 0 <= idx < len(units):
                        print(self.viz.show_unit_info(units[idx]))
                elif command == 't' and len(parts) >= 3:
                    unit_idx = int(parts[1])
                    weapon_id = int(parts[2])
                    targets = self.viz.highlight_valid_targets(unit_idx, weapon_id)
                    print(f"Valid targets: {targets}")
                    print(self.viz.render_grid())
                elif command == 'a' and len(parts) >= 5:
                    unit_idx = int(parts[1])
                    weapon_id = int(parts[2])
                    x = int(parts[3])
                    y = int(parts[4])
                    self._execute_action(unit_idx, weapon_id, x, y)
                elif command == 'l':
                    print(self.viz.show_legal_actions())
                elif command == 'n':
                    self.battle.end_turn()
                    print("Turn ended.")
                    print(self.viz.render_grid())
                elif command == 'r':
                    self._random_action()
                elif command == 'c':
                    self.viz.clear_highlights()
                    print("Highlights cleared.")
                else:
                    print("Unknown command. Type 'q' to quit.")

            except (ValueError, IndexError) as e:
                print(f"Error: {e}")
            except KeyboardInterrupt:
                break

        print(f"\nBattle ended: {self.battle.result.name}")

    def _execute_action(self, unit_idx: int, weapon_id: int, x: int, y: int):
        """Execute an action."""
        from src.simulator.battle import Action
        from src.simulator.models import Position

        action = Action(
            unit_index=unit_idx,
            weapon_id=weapon_id,
            target_position=Position(x, y)
        )

        result = self.battle.execute_action(action)
        if result.success:
            print(f"Action executed!")
            print(f"  Damage dealt: {result.damage_dealt}")
            if result.kills:
                print(f"  Kills: {result.kills}")
            if result.status_applied:
                print(f"  Status effects: {result.status_applied}")
            self.battle.end_turn()
        else:
            print(f"Action failed: {result.message}")

        print(self.viz.render_grid())

    def _random_action(self):
        """Take a random legal action."""
        import random

        actions = self.battle.get_legal_actions()
        if not actions:
            print("No legal actions available!")
            self.battle.end_turn()
            return

        action = random.choice(actions)
        print(f"Random action: Unit {action.unit_index}, Weapon {action.weapon_id}, Target ({action.target_position.x}, {action.target_position.y})")
        self._execute_action(action.unit_index, action.weapon_id, action.target_position.x, action.target_position.y)


def start_interactive_session(data_dir: str = "data", unit_ids: list[int] = None):
    """Start an interactive battle session."""
    from src.simulator import BattleSimulator

    sim = BattleSimulator(data_dir)

    # Use default units if none specified
    if unit_ids is None:
        # Find units with weapons
        units_with_weapons = [
            uid for uid, unit in sim.data_loader.units.items()
            if unit.weapons
        ][:8]
        unit_ids = units_with_weapons

    print(f"Using units: {unit_ids[:4]} vs {unit_ids[4:8] if len(unit_ids) > 4 else unit_ids[:4]}")

    battle = sim.create_custom_battle(
        layout_id=2,
        player_unit_ids=unit_ids[:4] if len(unit_ids) >= 4 else unit_ids,
        player_positions=list(range(min(4, len(unit_ids)))),
        enemy_unit_ids=unit_ids[4:8] if len(unit_ids) > 4 else unit_ids[:4],
        enemy_positions=list(range(min(4, len(unit_ids))))
    )

    if battle:
        session = InteractiveBattleSession(battle)
        session.run()
    else:
        print("Failed to create battle!")


if __name__ == "__main__":
    start_interactive_session()
