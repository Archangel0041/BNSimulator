"""Interactive battle visualizer for debugging and verification."""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING, List, Dict, Any
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from src.simulator.battle import BattleState, BattleUnit, Action
    from src.simulator.models import Position, Ability

from src.utils.localization import LocalizationManager

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


@dataclass
class BattleAction:
    """Represents a single action in battle."""
    action_type: str  # attack, dodge, crit, death, status_applied, status_tick, skip
    turn: int
    attacker_name: Optional[str] = None
    attacker_grid_id: Optional[int] = None
    target_name: Optional[str] = None
    target_grid_id: Optional[int] = None
    ability_name: Optional[str] = None
    hp_damage: int = 0
    armor_damage: int = 0
    status_effect_name: Optional[str] = None
    hit_count: int = 1
    message: str = ""
    is_player_turn: bool = True


@dataclass
class TurnSummary:
    """Summary statistics for a turn."""
    turn_number: int
    is_player_turn: bool
    total_hp_damage: int = 0
    total_armor_damage: int = 0
    crits: int = 0
    dodges: int = 0
    status_effects_applied: int = 0
    kills: int = 0


class BattleLog:
    """Tracks and displays battle history."""

    def __init__(self, max_actions: int = 100):
        self.actions: List[BattleAction] = []
        self.turn_summaries: Dict[int, TurnSummary] = {}
        self.max_actions = max_actions
        self.current_turn = 0

    def start_turn(self, turn_number: int, is_player_turn: bool):
        """Start tracking a new turn."""
        self.current_turn = turn_number
        if turn_number not in self.turn_summaries:
            self.turn_summaries[turn_number] = TurnSummary(
                turn_number=turn_number,
                is_player_turn=is_player_turn
            )

    def add_action(self, action: BattleAction):
        """Add an action to the log."""
        self.actions.append(action)

        # Update turn summary
        if action.turn in self.turn_summaries:
            summary = self.turn_summaries[action.turn]
            summary.total_hp_damage += action.hp_damage
            summary.total_armor_damage += action.armor_damage

            if action.action_type == "crit":
                summary.crits += 1
            elif action.action_type == "dodge":
                summary.dodges += 1
            elif action.action_type == "status_applied":
                summary.status_effects_applied += 1
            elif action.action_type == "death":
                summary.kills += 1

        # Limit log size
        if len(self.actions) > self.max_actions:
            self.actions = self.actions[-self.max_actions:]

    def get_action_icon(self, action_type: str) -> str:
        """Get icon for action type."""
        icons = {
            "attack": "⚔️",
            "dodge": "💨",
            "crit": "🎯",
            "death": "💀",
            "status_applied": "⚡",
            "status_tick": "🔥",
            "skip": "🛡️"
        }
        return icons.get(action_type, "•")

    def render_recent(self, n: int = 15) -> str:
        """Render the last N actions."""
        lines = [f"\n{Colors.BOLD}=== Battle Log (Last {n} actions) ==={Colors.RESET}"]

        if not self.actions:
            lines.append(f"{Colors.CYAN}No actions yet{Colors.RESET}")
            return "\n".join(lines)

        recent = self.actions[-n:]
        current_turn = None

        for action in recent:
            # Turn header
            if action.turn != current_turn:
                current_turn = action.turn
                turn_color = Colors.GREEN if action.is_player_turn else Colors.RED
                turn_label = "PLAYER" if action.is_player_turn else "ENEMY"
                lines.append(f"\n{turn_color}[Turn {action.turn} - {turn_label}]{Colors.RESET}")

                # Show turn summary if turn is complete
                if current_turn in self.turn_summaries and current_turn < self.current_turn:
                    summary = self.turn_summaries[current_turn]
                    if summary.total_hp_damage > 0 or summary.kills > 0:
                        stats = []
                        if summary.total_hp_damage > 0:
                            stats.append(f"{Colors.RED}{summary.total_hp_damage} HP dmg{Colors.RESET}")
                        if summary.total_armor_damage > 0:
                            stats.append(f"{Colors.CYAN}{summary.total_armor_damage} armor dmg{Colors.RESET}")
                        if summary.crits > 0:
                            stats.append(f"{Colors.YELLOW}{summary.crits} crit(s){Colors.RESET}")
                        if summary.dodges > 0:
                            stats.append(f"{Colors.BLUE}{summary.dodges} dodge(s){Colors.RESET}")
                        if summary.kills > 0:
                            stats.append(f"{Colors.RED}{summary.kills} kill(s){Colors.RESET}")
                        if stats:
                            lines.append(f"  📊 {', '.join(stats)}")

            # Action line
            icon = self.get_action_icon(action.action_type)
            line_parts = [f"  {icon}"]

            # Format based on action type
            if action.action_type == "attack":
                line_parts.append(f"{action.attacker_name}({action.attacker_grid_id})")
                if action.ability_name:
                    line_parts.append(f"→ {Colors.MAGENTA}{action.ability_name}{Colors.RESET}")
                line_parts.append(f"→ {action.target_name}({action.target_grid_id}):")

                dmg_parts = []
                if action.hp_damage > 0:
                    dmg_parts.append(f"{Colors.RED}{action.hp_damage} HP{Colors.RESET}")
                if action.armor_damage > 0:
                    dmg_parts.append(f"{Colors.CYAN}{action.armor_damage} armor{Colors.RESET}")

                if action.hit_count > 1:
                    line_parts.append(f"{Colors.MAGENTA}[{action.hit_count}x]{Colors.RESET}")

                if dmg_parts:
                    line_parts.append(", ".join(dmg_parts))

            elif action.action_type == "dodge":
                line_parts.append(f"{action.target_name}({action.target_grid_id})")
                line_parts.append(f"{Colors.BLUE}dodged!{Colors.RESET}")

            elif action.action_type == "crit":
                line_parts.append(f"{Colors.YELLOW}Critical hit!{Colors.RESET}")

            elif action.action_type == "death":
                line_parts.append(f"{action.target_name}({action.target_grid_id})")
                line_parts.append(f"{Colors.RED}defeated!{Colors.RESET}")
                if action.status_effect_name:
                    line_parts.append(f"(by {action.status_effect_name})")

            elif action.action_type == "status_applied":
                line_parts.append(f"{action.target_name}({action.target_grid_id})")
                line_parts.append(f"→ {Colors.MAGENTA}{action.status_effect_name}{Colors.RESET} applied")

            elif action.action_type == "status_tick":
                line_parts.append(f"{action.target_name}({action.target_grid_id})")
                line_parts.append(f"→ {Colors.MAGENTA}{action.status_effect_name}{Colors.RESET}:")
                dmg_parts = []
                if action.hp_damage > 0:
                    dmg_parts.append(f"{Colors.RED}{action.hp_damage} HP{Colors.RESET}")
                if action.armor_damage > 0:
                    dmg_parts.append(f"{Colors.CYAN}{action.armor_damage} armor{Colors.RESET}")
                if dmg_parts:
                    line_parts.append(", ".join(dmg_parts))

            elif action.action_type == "skip":
                line_parts.append(f"{action.attacker_name}({action.attacker_grid_id}) skipped turn")

            lines.append(" ".join(line_parts))

        return "\n".join(lines)


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
        self.battle_log = BattleLog()

        # Initialize localization
        self.loc = None
        try:
            loc_dir = Path("data") / "Assets" / "Localization"
            if loc_dir.exists():
                self.loc = LocalizationManager(loc_dir)
                self.loc.load("GameText", "en")
        except Exception as e:
            print(f"Warning: Failed to load localization: {e}")

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

        # Render rows - both sides now show back to front (flipped) so front rows are at bottom
        # This makes both sides face toward each other (enemy faces down, player faces up)
        row_order = range(self.GRID_HEIGHT - 1, -1, -1)
        row_labels = ["Front", "Mid  ", "Back "]

        for y in row_order:
            row_str = f"{row_labels[y]} │"

            for x in range(self.GRID_WIDTH):
                # Check if this cell should be blocked (back row corners)
                is_back_row = (y == self.GRID_HEIGHT - 1)
                is_corner = (x == 0 or x == self.GRID_WIDTH - 1)
                is_blocked = is_back_row and is_corner

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
                if is_blocked:
                    # Show blocked cell
                    cell = f"{Colors.BG_MAGENTA}    X    {Colors.RESET}"
                    cell = cell.ljust(self.CELL_WIDTH + 10)
                elif unit and unit.is_alive:
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

    def _get_localized(self, key: str) -> str:
        """Get localized text for a key, or return the key if localization unavailable."""
        if self.loc:
            return self.loc.get(key)
        return key

    def show_unit_info(self, unit: "BattleUnit") -> str:
        """Show detailed info about a unit."""
        t = unit.template
        s = t.stats

        # Get localized unit name
        unit_name = self._get_localized(t.name)

        # Check if unit has multiple ranks
        num_ranks = len(t.all_rank_stats)
        rank_info = f" (Rank {num_ranks} available)" if num_ranks > 1 else ""

        lines = [
            f"\n{Colors.BOLD}=== Unit Info ==={Colors.RESET}",
            f"Name: {unit_name}{rank_info}",
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

            # Get localized weapon name
            weapon_name = self._get_localized(weapon.name)

            lines.append(f"  [{wid}] {weapon_name}")
            lines.append(f"      Damage: {ws.base_damage_min}-{ws.base_damage_max}")
            lines.append(f"      {ammo_str} {cd_str}")

            # Show abilities
            for aid in weapon.abilities:
                ability = self.battle.data_loader.get_ability(aid)
                if ability:
                    # Get localized ability name
                    ability_name = self._get_localized(ability.name)
                    lines.append(f"      → {ability_name}")
                    lines.append(f"        Range: {ability.stats.min_range}-{ability.stats.max_range}")
                    lines.append(f"        Targets: {ability.stats.targets}")

        if unit.status_effects:
            lines.append(f"\nStatus Effects:")
            for status in unit.status_effects:
                # Get localized status effect name
                effect_name = self._get_localized(status.effect.name) if hasattr(status.effect, 'name') else status.effect.family.name
                lines.append(f"  - {effect_name}: {status.remaining_turns} turns")

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

    def show_damage_preview(self, unit_idx: int, weapon_id: int, target_x: int, target_y: int) -> str:
        """
        Show damage preview for an attack.

        This matches TypeScript functionality showing:
        - Min/Max HP damage
        - Min/Max Armor damage
        - Dodge chance
        - Critical chance
        - Status effects that will be applied
        - Blocking information
        """
        from src.simulator.combat import DamageCalculator

        lines = [f"\n{Colors.BOLD}=== Damage Preview ==={Colors.RESET}"]

        # Get attacker unit
        unit = self.battle.current_side_units[unit_idx]
        weapon = unit.template.weapons.get(weapon_id)

        if not weapon:
            lines.append(f"{Colors.RED}Invalid weapon{Colors.RESET}")
            return "\n".join(lines)

        # Get target unit
        target_units = self.battle.enemy_units if self.battle.is_player_turn else self.battle.player_units
        target_unit = None
        for u in target_units:
            if u.position.x == target_x and u.position.y == target_y and u.is_alive:
                target_unit = u
                break

        if not target_unit:
            lines.append(f"{Colors.YELLOW}No target at ({target_x}, {target_y}){Colors.RESET}")
            return "\n".join(lines)

        # Get weapon abilities
        if not weapon.abilities:
            lines.append(f"{Colors.RED}Weapon has no abilities{Colors.RESET}")
            return "\n".join(lines)

        ability_id = weapon.abilities[0]  # Use first ability
        ability = self.battle.data_loader.get_ability(ability_id)

        if not ability:
            lines.append(f"{Colors.RED}Invalid ability{Colors.RESET}")
            return "\n".join(lines)

        # Header
        attacker_name = self._get_localized(unit.template.name)
        target_name = self._get_localized(target_unit.template.name)
        ability_name = self._get_localized(ability.name)

        lines.append(f"{Colors.CYAN}{attacker_name}{Colors.RESET} → {Colors.MAGENTA}{ability_name}{Colors.RESET} → {Colors.YELLOW}{target_name}{Colors.RESET}")
        lines.append("")

        # Calculate damage using rank
        stats = ability.stats
        min_damage = stats.base_damage_min
        max_damage = stats.base_damage_max

        # Apply rank scaling
        calculator = DamageCalculator()
        power = unit.template.stats.power
        min_damage_scaled = calculator.calculate_damage_at_rank(min_damage, power)
        max_damage_scaled = calculator.calculate_damage_at_rank(max_damage, power)

        # Calculate dodge chance
        dodge_chance = calculator.calculate_dodge_chance(
            target_unit.template.stats.defense,
            stats.offense
        )

        # Get multi-hit info
        shots_per_attack = stats.shots_per_attack or 1
        attacks_per_use = 1  # From ability config
        total_shots = shots_per_attack * attacks_per_use

        # Display damage
        if total_shots > 1:
            total_min = min_damage_scaled * total_shots
            total_max = max_damage_scaled * total_shots
            lines.append(f"Damage: {Colors.RED}{min_damage_scaled}-{max_damage_scaled}{Colors.RESET} x {Colors.MAGENTA}{total_shots} hits{Colors.RESET} = {Colors.RED}{total_min}-{total_max} total{Colors.RESET}")
        else:
            lines.append(f"Damage: {Colors.RED}{min_damage_scaled}-{max_damage_scaled} HP{Colors.RESET}")

        # Display target HP/Armor
        target_hp = target_unit.current_hp
        target_armor = target_unit.current_armor

        lines.append(f"Target HP: {Colors.GREEN}{target_hp}/{target_unit.template.stats.hp}{Colors.RESET}")
        if target_armor > 0:
            lines.append(f"Target Armor: {Colors.CYAN}{target_armor}/{target_unit.template.stats.armor_hp}{Colors.RESET}")

        # Calculate remaining HP (rough estimate)
        min_hp_remaining = max(0, target_hp - (max_damage_scaled * total_shots))
        max_hp_remaining = max(0, target_hp - (min_damage_scaled * total_shots))

        if min_hp_remaining == max_hp_remaining:
            lines.append(f"Remaining HP: {Colors.GREEN}{min_hp_remaining}{Colors.RESET}")
        else:
            lines.append(f"Remaining HP: {Colors.GREEN}{min_hp_remaining}-{max_hp_remaining}{Colors.RESET}")

        lines.append("")

        # Display chances
        crit_chance = unit.template.stats.critical + (stats.critical_hit_percent or 0)
        lines.append(f"Dodge Chance: {Colors.YELLOW if dodge_chance > 0 else Colors.GREEN}{dodge_chance}%{Colors.RESET}")
        lines.append(f"Crit Chance: {Colors.YELLOW if crit_chance > 0 else Colors.GREEN}{crit_chance}%{Colors.RESET}")

        # Display status effects
        if stats.status_effects:
            lines.append("")
            lines.append(f"{Colors.BOLD}Status Effects:{Colors.RESET}")
            for effect_id, chance in stats.status_effects.items():
                effect = self.battle.data_loader.get_status_effect(effect_id)
                if effect:
                    effect_name = effect.family.name if hasattr(effect, 'family') else f"Effect {effect_id}"
                    duration = effect.duration if hasattr(effect, 'duration') else "?"
                    lines.append(f"  {Colors.MAGENTA}{effect_name}{Colors.RESET}: {chance}% chance, {duration} turns")

        # Check blocking
        # TODO: Implement blocking check when available in battle system

        return "\n".join(lines)

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
                    # Get localized weapon name
                    weapon_name = self._get_localized(weapon.name)
                    lines.append(f"  Weapon {weapon_id}: {weapon_name}")
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
        print("  p <unit> <weapon> <x> <y> - Preview damage")
        print("  a <unit> <weapon> <x> <y> - Execute action")
        print("  l - Show legal actions")
        print("  log [n] - Show battle log (last N actions, default 15)")
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
                elif command == 'p' and len(parts) >= 5:
                    unit_idx = int(parts[1])
                    weapon_id = int(parts[2])
                    x = int(parts[3])
                    y = int(parts[4])
                    print(self.viz.show_damage_preview(unit_idx, weapon_id, x, y))
                elif command == 'a' and len(parts) >= 5:
                    unit_idx = int(parts[1])
                    weapon_id = int(parts[2])
                    x = int(parts[3])
                    y = int(parts[4])
                    self._execute_action(unit_idx, weapon_id, x, y)
                elif command == 'l':
                    print(self.viz.show_legal_actions())
                elif command == 'log':
                    # Show battle log
                    n = 15
                    if len(parts) >= 2:
                        try:
                            n = int(parts[1])
                        except ValueError:
                            pass
                    print(self.viz.battle_log.render_recent(n))
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

        # Start tracking this turn
        self.viz.battle_log.start_turn(
            self.battle.turn_number,
            self.battle.is_player_turn
        )

        # Get unit and target info for logging
        unit = self.battle.current_side_units[unit_idx]
        attacker_name = unit.template.class_type.name
        attacker_grid_id = unit.position.x + unit.position.y * 5

        action = Action(
            unit_index=unit_idx,
            weapon_id=weapon_id,
            target_position=Position(x, y)
        )

        result = self.battle.execute_action(action)
        if result.success:
            # Log the action
            target_unit = None
            for u in self.battle.enemy_units if self.battle.is_player_turn else self.battle.player_units:
                if u.position.x == x and u.position.y == y and u.is_alive:
                    target_unit = u
                    break

            if target_unit:
                target_name = target_unit.template.class_type.name
                target_grid_id = x + y * 5

                # Get weapon/ability info
                weapon = unit.template.weapons.get(weapon_id)
                ability_name = weapon.name if weapon else f"Weapon {weapon_id}"

                # Log attack action
                battle_action = BattleAction(
                    action_type="attack",
                    turn=self.battle.turn_number,
                    attacker_name=attacker_name,
                    attacker_grid_id=attacker_grid_id,
                    target_name=target_name,
                    target_grid_id=target_grid_id,
                    ability_name=ability_name,
                    hp_damage=result.damage_dealt.get("hp", 0),
                    armor_damage=result.damage_dealt.get("armor", 0),
                    hit_count=result.damage_dealt.get("hits", 1),
                    is_player_turn=self.battle.is_player_turn
                )
                self.viz.battle_log.add_action(battle_action)

                # Log kills
                if result.kills:
                    for kill in result.kills:
                        death_action = BattleAction(
                            action_type="death",
                            turn=self.battle.turn_number,
                            target_name=target_name,
                            target_grid_id=target_grid_id,
                            is_player_turn=self.battle.is_player_turn
                        )
                        self.viz.battle_log.add_action(death_action)

                # Log status effects
                if result.status_applied:
                    for status_id in result.status_applied:
                        status_action = BattleAction(
                            action_type="status_applied",
                            turn=self.battle.turn_number,
                            target_name=target_name,
                            target_grid_id=target_grid_id,
                            status_effect_name=f"Effect {status_id}",
                            is_player_turn=self.battle.is_player_turn
                        )
                        self.viz.battle_log.add_action(status_action)

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
