"""GUI-based battle visualizer with interactive targeting.

This module provides a graphical interface for visualizing battles with:
- Visual grid display with units
- Targeting pattern visualization
- AOE/damage pattern overlays
- Reticle-based targeting
- Turn-by-turn battle progression
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

if TYPE_CHECKING:
    from src.simulator.battle import BattleState, BattleUnit, Action, ActionResult
    from src.simulator.models import Ability

from src.simulator.models import Position
from src.utils.localization import LocalizationManager
from src.utils.icon_manager import IconManager

# Color scheme
COLORS = {
    'player_cell': '#4CAF50',
    'enemy_cell': '#F44336',
    'player_unit': '#2E7D32',
    'enemy_unit': '#C62828',
    'selected_unit': '#FFC107',
    'valid_target': '#64B5F6',
    'aoe_primary': '#FF5722',
    'aoe_secondary': '#FF9800',
    'empty_cell': '#E0E0E0',
    'blocked_cell': '#757575',
    'grid_line': '#9E9E9E',
    'hp_bar_bg': '#BDBDBD',
    'hp_bar_high': '#4CAF50',
    'hp_bar_med': '#FFC107',
    'hp_bar_low': '#F44336',
}


@dataclass
class CellInfo:
    """Information about a grid cell."""
    x: int
    y: int
    is_player_side: bool
    unit: Optional[BattleUnit] = None
    is_valid_target: bool = False
    aoe_damage_percent: float = 0.0  # 0-100


class BattleGUIVisualizer:
    """GUI visualizer for battles with interactive targeting."""

    def __init__(self, battle: "BattleState", cell_size: int = 80):
        self.battle = battle
        self.cell_size = cell_size
        self.padding = 10
        self.hp_bar_height = 8

        # Selection state
        self.selected_unit_idx: Optional[int] = None
        self.selected_weapon_id: Optional[int] = None
        self.selected_is_player: bool = True
        self.valid_targets: list[Position] = []
        self.aoe_pattern: dict[tuple[int, int], float] = {}
        self.hovered_cell: Optional[tuple[int, int]] = None

        # Callback for action execution
        self.on_action_callback: Optional[Callable[[Action], ActionResult]] = None

        # Initialize localization
        self.loc = None
        try:
            loc_dir = Path("data") / "Assets" / "Localization"
            if loc_dir.exists():
                self.loc = LocalizationManager(loc_dir)
                self.loc.load("GameText", "en")
        except Exception as e:
            print(f"Warning: Failed to load localization: {e}")

        # Initialize icon manager
        self.icons = None
        try:
            icons_dir = Path("data") / "Assets" / "Art" / "icons"
            if icons_dir.exists():
                self.icons = IconManager(icons_dir)
        except Exception as e:
            print(f"Warning: Failed to load icon manager: {e}")

        # Create window
        self.root = tk.Tk()
        self.root.title("Battle Visualizer")
        self.root.configure(bg='#263238')

        # Create main layout
        self._create_ui()
        self._update_display()

    def _create_ui(self):
        """Create the UI layout."""
        # Main container
        main_frame = tk.Frame(self.root, bg='#263238')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Battle grid
        grid_frame = tk.Frame(main_frame, bg='#263238')
        grid_frame.pack(side=tk.LEFT, padx=10)

        # Grid title
        tk.Label(
            grid_frame,
            text=f"Turn {self.battle.turn_number}",
            font=('Arial', 16, 'bold'),
            bg='#263238',
            fg='white'
        ).pack(pady=(0, 10))

        # Canvas for battle grid
        grid_width = self.battle.layout.width * self.cell_size + self.padding * 2
        grid_height = (self.battle.layout.height * 2 + 1) * self.cell_size + self.padding * 2

        self.canvas = tk.Canvas(
            grid_frame,
            width=grid_width,
            height=grid_height,
            bg='#37474F',
            highlightthickness=0
        )
        self.canvas.pack()

        # Bind mouse events
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        self.canvas.bind('<Motion>', self._on_canvas_hover)

        # Right panel - Controls and info
        control_frame = tk.Frame(main_frame, bg='#263238', width=300)
        control_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # Turn indicator
        turn_text = "PLAYER TURN" if self.battle.is_player_turn else "ENEMY TURN"
        turn_color = '#4CAF50' if self.battle.is_player_turn else '#F44336'
        self.turn_label = tk.Label(
            control_frame,
            text=turn_text,
            font=('Arial', 14, 'bold'),
            bg=turn_color,
            fg='white',
            pady=10
        )
        self.turn_label.pack(fill=tk.X, pady=(0, 10))

        # Unit info panel
        info_panel = tk.Frame(control_frame, bg='#37474F', relief=tk.RIDGE, bd=2)
        info_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(
            info_panel,
            text="UNIT INFO",
            font=('Arial', 12, 'bold'),
            bg='#37474F',
            fg='white'
        ).pack(pady=5)

        # Scrollable unit info
        info_scroll = tk.Scrollbar(info_panel)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.info_text = tk.Text(
            info_panel,
            height=15,
            wrap=tk.WORD,
            bg='#263238',
            fg='white',
            font=('Courier', 9),
            yscrollcommand=info_scroll.set,
            relief=tk.FLAT
        )
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        info_scroll.config(command=self.info_text.yview)

        # Weapon selection panel
        weapon_panel = tk.Frame(control_frame, bg='#37474F', relief=tk.RIDGE, bd=2)
        weapon_panel.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            weapon_panel,
            text="WEAPONS",
            font=('Arial', 12, 'bold'),
            bg='#37474F',
            fg='white'
        ).pack(pady=5)

        self.weapon_frame = tk.Frame(weapon_panel, bg='#37474F')
        self.weapon_frame.pack(fill=tk.X, padx=5, pady=5)

        # Action buttons
        button_frame = tk.Frame(control_frame, bg='#263238')
        button_frame.pack(fill=tk.X)

        tk.Button(
            button_frame,
            text="End Turn",
            command=self._end_turn,
            bg='#546E7A',
            fg='white',
            font=('Arial', 11, 'bold'),
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=5
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame,
            text="Clear Selection",
            command=self._clear_selection,
            bg='#546E7A',
            fg='white',
            font=('Arial', 11, 'bold'),
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=5
        ).pack(side=tk.LEFT, padx=5)

        # Legend
        legend_frame = tk.Frame(control_frame, bg='#37474F', relief=tk.RIDGE, bd=2)
        legend_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(
            legend_frame,
            text="LEGEND",
            font=('Arial', 10, 'bold'),
            bg='#37474F',
            fg='white'
        ).pack(pady=5)

        legend_items = [
            ("Selected Unit", COLORS['selected_unit']),
            ("Valid Target", COLORS['valid_target']),
            ("AOE Primary", COLORS['aoe_primary']),
            ("AOE Secondary", COLORS['aoe_secondary']),
        ]

        for label, color in legend_items:
            item_frame = tk.Frame(legend_frame, bg='#37474F')
            item_frame.pack(fill=tk.X, padx=10, pady=2)

            tk.Label(
                item_frame,
                bg=color,
                width=3,
                relief=tk.RAISED,
                bd=1
            ).pack(side=tk.LEFT, padx=5)

            tk.Label(
                item_frame,
                text=label,
                bg='#37474F',
                fg='white',
                font=('Arial', 9)
            ).pack(side=tk.LEFT)

    def _draw_grid(self):
        """Draw the battle grid."""
        self.canvas.delete('all')
        # Clear icon references to allow garbage collection
        self._icon_refs = []

        # Draw enemy grid (top)
        y_offset = self.padding
        self._draw_side_grid(0, y_offset, is_player=False)

        # Draw separator
        y_offset += self.battle.layout.height * self.cell_size + 20
        self.canvas.create_line(
            self.padding,
            y_offset,
            self.padding + self.battle.layout.width * self.cell_size,
            y_offset,
            fill='white',
            width=2
        )

        # Draw player grid (bottom)
        y_offset += 20
        self._draw_side_grid(0, y_offset, is_player=True)

    def _draw_side_grid(self, x_offset: int, y_offset: int, is_player: bool):
        """Draw one side's grid (player or enemy)."""
        units = self.battle.player_units if is_player else self.battle.enemy_units

        # Create unit lookup
        unit_at = {}
        for unit in units:
            unit_at[(unit.position.x, unit.position.y)] = unit

        # Draw cells
        # Enemy grid should be flipped vertically so units face downward toward player
        for row in range(self.battle.layout.height):
            # Flip enemy rows: row 0 (front) becomes row 2 (back) in display
            display_row = (self.battle.layout.height - 1 - row) if not is_player else row

            for col in range(self.battle.layout.width):
                cell_x = self.padding + x_offset + col * self.cell_size
                cell_y = y_offset + display_row * self.cell_size

                pos = (col, row)
                unit = unit_at.get(pos)

                # Determine cell color
                cell_color = COLORS['empty_cell']

                # Check if this cell is part of selection/targeting
                if self.selected_unit_idx is not None and self.selected_is_player == is_player:
                    selected_unit = units[self.selected_unit_idx]
                    if selected_unit.position.x == col and selected_unit.position.y == row:
                        cell_color = COLORS['selected_unit']

                # Check if valid target
                if any(t.x == col and t.y == row for t in self.valid_targets):
                    if not is_player if self.selected_is_player else is_player:
                        cell_color = COLORS['valid_target']

                # Check AOE pattern
                if pos in self.aoe_pattern:
                    damage_pct = self.aoe_pattern[pos]
                    if damage_pct >= 80:
                        cell_color = COLORS['aoe_primary']
                    else:
                        cell_color = COLORS['aoe_secondary']

                # Draw cell background
                self.canvas.create_rectangle(
                    cell_x, cell_y,
                    cell_x + self.cell_size, cell_y + self.cell_size,
                    fill=cell_color,
                    outline=COLORS['grid_line'],
                    width=2,
                    tags=f'cell_{col}_{display_row}_{"player" if is_player else "enemy"}'
                )

                # Draw unit if present
                if unit and unit.is_alive:
                    self._draw_unit(cell_x, cell_y, unit, is_player)

    def _draw_unit(self, x: int, y: int, unit: "BattleUnit", is_player: bool):
        """Draw a unit in a cell."""
        margin = 10

        # Try to load and display unit icon
        icon_displayed = False
        if self.icons:
            # Use back_icon for player units, icon for enemy units
            icon_name = unit.template.back_icon if is_player else unit.template.icon
            # Determine facing based on side (enemy=front, player=back)
            facing = "back" if is_player else "front"
            icon_size = (self.cell_size - margin * 2 - 20, self.cell_size - margin * 2 - 20)

            if icon_name:  # Only try to load if icon name exists
                icon = self.icons.get_unit_tk_icon(icon_name, facing, icon_size)
                if icon:
                    icon_x = x + self.cell_size // 2
                    icon_y = y + margin + (self.cell_size - margin * 2 - 20) // 2
                    self.canvas.create_image(icon_x, icon_y, image=icon)
                    # Keep reference to avoid garbage collection
                    if not hasattr(self, '_icon_refs'):
                        self._icon_refs = []
                    self._icon_refs.append(icon)
                    icon_displayed = True

        # Fallback to text if no icon
        if not icon_displayed:
            class_text = unit.template.class_type.name[:3]
            self.canvas.create_text(
                x + self.cell_size // 2,
                y + self.cell_size // 2 - 10,
                text=class_text,
                fill='white',
                font=('Arial', 12, 'bold')
            )

        # HP bar
        hp_percent = unit.current_hp / max(1, unit.template.stats.hp)
        self._draw_hp_bar(x, y + self.cell_size - margin - self.hp_bar_height - 5, hp_percent)

        # HP text
        self.canvas.create_text(
            x + self.cell_size // 2,
            y + self.cell_size // 2 + 10,
            text=f"{int(hp_percent * 100)}%",
            fill='white',
            font=('Arial', 9)
        )

    def _draw_hp_bar(self, x: int, y: int, hp_percent: float):
        """Draw HP bar."""
        bar_width = self.cell_size - 20
        bar_x = x + 10

        # Background
        self.canvas.create_rectangle(
            bar_x, y,
            bar_x + bar_width, y + self.hp_bar_height,
            fill=COLORS['hp_bar_bg'],
            outline='',
        )

        # HP fill
        fill_width = int(bar_width * hp_percent)
        if hp_percent > 0.7:
            color = COLORS['hp_bar_high']
        elif hp_percent > 0.3:
            color = COLORS['hp_bar_med']
        else:
            color = COLORS['hp_bar_low']

        if fill_width > 0:
            self.canvas.create_rectangle(
                bar_x, y,
                bar_x + fill_width, y + self.hp_bar_height,
                fill=color,
                outline='',
            )

    def _on_canvas_click(self, event):
        """Handle canvas click events."""
        # Convert click to grid coordinates
        cell_info = self._get_cell_from_coords(event.x, event.y)
        if not cell_info:
            return

        # Check if clicking on a unit to select it
        if cell_info.unit and cell_info.unit.is_alive:
            # Only select units on the current turn's side
            is_unit_player = cell_info.unit.battle_side.name == 'PLAYER_TEAM'
            if is_unit_player == self.battle.is_player_turn:
                self._select_unit(cell_info)
                return

        # Check if clicking on a valid target
        target_pos = Position(cell_info.x, cell_info.y)
        if target_pos in self.valid_targets and self.selected_weapon_id is not None:
            self._execute_action(target_pos)

    def _on_canvas_hover(self, event):
        """Handle mouse hover to show AOE patterns."""
        cell_info = self._get_cell_from_coords(event.x, event.y)
        if not cell_info:
            self.hovered_cell = None
            self.aoe_pattern.clear()
            self._draw_grid()
            return

        pos = (cell_info.x, cell_info.y)
        if pos == self.hovered_cell:
            return

        self.hovered_cell = pos

        # Show AOE pattern if hovering over a valid target
        target_pos = Position(cell_info.x, cell_info.y)
        if target_pos in self.valid_targets and self.selected_weapon_id is not None:
            self._show_aoe_pattern(target_pos)
        else:
            self.aoe_pattern.clear()

        self._draw_grid()

    def _get_cell_from_coords(self, x: int, y: int) -> Optional[CellInfo]:
        """Convert canvas coordinates to cell info."""
        # Determine which grid (player or enemy)
        enemy_grid_height = self.battle.layout.height * self.cell_size
        separator_y = self.padding + enemy_grid_height + 20

        if y < separator_y:
            # Enemy grid
            is_player = False
            grid_y_offset = self.padding
            units = self.battle.enemy_units
        else:
            # Player grid
            is_player = True
            grid_y_offset = separator_y + 20
            units = self.battle.player_units

        # Calculate cell coordinates
        rel_x = x - self.padding
        rel_y = y - grid_y_offset

        if rel_x < 0 or rel_y < 0:
            return None

        cell_x = rel_x // self.cell_size
        cell_y = rel_y // self.cell_size

        if cell_x >= self.battle.layout.width or cell_y >= self.battle.layout.height:
            return None

        # For enemy grid, reverse the flip to get logical coordinates
        # Enemy display is flipped: display_row = height - 1 - logical_row
        # So to get logical_row from display_row: logical_row = height - 1 - display_row
        if not is_player:
            cell_y = self.battle.layout.height - 1 - cell_y

        # Find unit at this position
        unit = None
        for u in units:
            if u.position.x == cell_x and u.position.y == cell_y and u.is_alive:
                unit = u
                break

        return CellInfo(x=cell_x, y=cell_y, is_player_side=is_player, unit=unit)

    def _select_unit(self, cell_info: CellInfo):
        """Select a unit and show its weapons."""
        units = self.battle.player_units if cell_info.is_player_side else self.battle.enemy_units

        # Find unit index
        for idx, unit in enumerate(units):
            if unit == cell_info.unit:
                self.selected_unit_idx = idx
                self.selected_is_player = cell_info.is_player_side
                self.selected_weapon_id = None
                self.valid_targets.clear()
                self.aoe_pattern.clear()

                self._update_unit_info(cell_info.unit)
                self._update_weapon_panel(cell_info.unit)
                self._draw_grid()
                return

    def _get_localized(self, key: str) -> str:
        """Get localized text for a key, or return the key if localization unavailable."""
        if self.loc:
            return self.loc.get(key)
        return key

    def _update_unit_info(self, unit: "BattleUnit"):
        """Update the unit info panel."""
        self.info_text.delete('1.0', tk.END)

        # Check if unit has multiple ranks available
        num_ranks = len(unit.template.all_rank_stats)
        rank_info = f" (Rank {num_ranks} available)" if num_ranks > 1 else ""

        # Get localized unit name
        unit_name = self._get_localized(unit.template.name)

        info = f"""
UNIT: {unit_name}{rank_info}
CLASS: {unit.template.class_type.name}
POSITION: ({unit.position.x}, {unit.position.y})

HP: {unit.current_hp}/{unit.template.stats.hp}
ARMOR: {unit.current_armor}/{unit.template.stats.armor_hp}

STATS:
  Defense: {unit.template.stats.defense}
  Accuracy: {unit.template.stats.accuracy}
  Dodge: {unit.template.stats.dodge}%
  Critical: {unit.template.stats.critical}%
  Power: {unit.template.stats.power}

WEAPONS: {len(unit.template.weapons)}
"""

        for wid, weapon in unit.template.weapons.items():
            cd = unit.weapon_cooldowns.get(wid, 0)
            cd_str = f"[CD: {cd}]" if cd > 0 else "[Ready]"
            ammo_str = ""
            if weapon.stats.ammo >= 0:
                ammo_str = f" ({unit.ammo.get(wid, 0)}/{weapon.stats.ammo})"

            # Get localized weapon name
            weapon_name = self._get_localized(weapon.name)

            info += f"\n  [{wid}] {weapon_name}{ammo_str} {cd_str}"
            info += f"\n      DMG: {weapon.stats.base_damage_min}-{weapon.stats.base_damage_max}"

        if unit.status_effects:
            info += f"\n\nSTATUS EFFECTS: {len(unit.status_effects)}"
            for effect in unit.status_effects:
                # Get localized status effect name
                effect_name = self._get_localized(effect.effect.name) if hasattr(effect.effect, 'name') else effect.effect.family.name
                info += f"\n  {effect_name}: {effect.remaining_turns} turns"

        self.info_text.insert('1.0', info)

    def _update_weapon_panel(self, unit: "BattleUnit"):
        """Update weapon selection buttons."""
        # Clear existing buttons
        for widget in self.weapon_frame.winfo_children():
            widget.destroy()

        available_weapons = unit.get_available_weapons()

        if not available_weapons:
            tk.Label(
                self.weapon_frame,
                text="No weapons available",
                bg='#37474F',
                fg='#BDBDBD',
                font=('Arial', 10)
            ).pack(pady=10)
            return

        for weapon_id in available_weapons:
            weapon = unit.template.weapons[weapon_id]

            # Get localized weapon name
            weapon_name = self._get_localized(weapon.name)

            # Try to get icon for first ability of this weapon
            icon = None
            if self.icons and weapon.abilities:
                ability_id = weapon.abilities[0]
                ability = self.battle.data_loader.get_ability(ability_id)
                if ability:
                    # Remove _name suffix from ability name
                    ability_name = ability.name.replace("_name", "")
                    icon = self.icons.get_ability_tk_icon(ability_name, (24, 24))

            if icon:
                btn = tk.Button(
                    self.weapon_frame,
                    text=f" {weapon_name}\n{weapon.stats.base_damage_min}-{weapon.stats.base_damage_max} DMG",
                    image=icon,
                    compound=tk.LEFT,
                    command=lambda wid=weapon_id: self._select_weapon(wid),
                    bg='#455A64',
                    fg='white',
                    font=('Arial', 9),
                    relief=tk.RAISED,
                    bd=2,
                    pady=5
                )
                # Keep reference to avoid garbage collection
                btn.image = icon
            else:
                btn = tk.Button(
                    self.weapon_frame,
                    text=f"{weapon_name}\n{weapon.stats.base_damage_min}-{weapon.stats.base_damage_max} DMG",
                    command=lambda wid=weapon_id: self._select_weapon(wid),
                    bg='#455A64',
                    fg='white',
                    font=('Arial', 9),
                    relief=tk.RAISED,
                    bd=2,
                    pady=5
                )
            btn.pack(fill=tk.X, pady=2)

    def _select_weapon(self, weapon_id: int):
        """Select a weapon and show valid targets."""
        self.selected_weapon_id = weapon_id

        # Get valid targets
        units = self.battle.player_units if self.selected_is_player else self.battle.enemy_units
        unit = units[self.selected_unit_idx]

        self.valid_targets = self.battle.get_valid_targets(unit, weapon_id)
        self.aoe_pattern.clear()

        self._draw_grid()

    def _show_aoe_pattern(self, target_pos: Position):
        """Show AOE damage pattern for the selected target."""
        if self.selected_weapon_id is None or self.selected_unit_idx is None:
            return

        units = self.battle.player_units if self.selected_is_player else self.battle.enemy_units
        unit = units[self.selected_unit_idx]
        weapon = unit.template.weapons.get(self.selected_weapon_id)

        if not weapon or not weapon.abilities:
            return

        ability_id = weapon.abilities[0]
        ability = self.battle.data_loader.get_ability(ability_id)
        if not ability:
            return

        # Clear existing AOE pattern
        self.aoe_pattern.clear()

        # Show damage_area pattern
        for area in ability.stats.damage_area:
            aoe_x = target_pos.x + area.pos.x
            aoe_y = target_pos.y + area.pos.y

            if 0 <= aoe_x < self.battle.layout.width and 0 <= aoe_y < self.battle.layout.height:
                self.aoe_pattern[(aoe_x, aoe_y)] = area.damage_percent

    def _execute_action(self, target_pos: Position):
        """Execute an attack action."""
        if self.selected_unit_idx is None or self.selected_weapon_id is None:
            return

        from src.simulator.battle import Action

        action = Action(
            unit_index=self.selected_unit_idx,
            weapon_id=self.selected_weapon_id,
            target_position=target_pos
        )

        # Execute through callback if set
        if self.on_action_callback:
            result = self.on_action_callback(action)
            self._show_action_result(action, result)
        else:
            # Execute directly
            result = self.battle.execute_action(action)
            self._show_action_result(action, result)
            self.battle.end_turn()

        # Clear selection
        self._clear_selection()
        self._update_display()

    def _show_action_result(self, action: Action, result: ActionResult):
        """Show action result in a message box."""
        if not result.success:
            messagebox.showerror("Action Failed", result.message)
            return

        msg = "Action executed!\n\n"

        if result.damage_dealt:
            msg += "Damage dealt:\n"
            opposing_units = self.battle.opposing_side_units
            for unit_idx, damage in result.damage_dealt.items():
                if unit_idx < len(opposing_units):
                    target = opposing_units[unit_idx]
                    status = "DEFEATED" if not target.is_alive else f"{target.current_hp}/{target.template.stats.hp} HP"
                    msg += f"  {target.template.class_type.name}: {damage} damage ({status})\n"

        if result.kills:
            msg += f"\nUnits defeated: {len(result.kills)}"

        if result.status_applied:
            msg += f"\nStatus effects applied: {len(result.status_applied)}"

        messagebox.showinfo("Action Result", msg)

    def _end_turn(self):
        """End the current turn."""
        self.battle.end_turn()
        self._clear_selection()
        self._update_display()

    def _clear_selection(self):
        """Clear current selection."""
        self.selected_unit_idx = None
        self.selected_weapon_id = None
        self.valid_targets.clear()
        self.aoe_pattern.clear()
        self.hovered_cell = None

        self.info_text.delete('1.0', tk.END)
        self.info_text.insert('1.0', "\n\n  Select a unit to view details")

        for widget in self.weapon_frame.winfo_children():
            widget.destroy()

    def _update_display(self):
        """Update the entire display."""
        # Update turn label
        turn_text = "PLAYER TURN" if self.battle.is_player_turn else "ENEMY TURN"
        turn_color = '#4CAF50' if self.battle.is_player_turn else '#F44336'
        self.turn_label.config(text=f"Turn {self.battle.turn_number}: {turn_text}", bg=turn_color)

        # Update title
        self.root.title(f"Battle Visualizer - Turn {self.battle.turn_number}")

        # Redraw grid
        self._draw_grid()

        # Check if battle ended
        from src.simulator.battle import BattleResult
        if self.battle.result != BattleResult.IN_PROGRESS:
            self._show_battle_end()

    def _show_battle_end(self):
        """Show battle end message."""
        result_text = {
            'PLAYER_WIN': "PLAYER WINS!",
            'ENEMY_WIN': "ENEMY WINS!",
            'SURRENDER': "BATTLE SURRENDERED",
        }.get(self.battle.result.name, "BATTLE ENDED")

        messagebox.showinfo("Battle Complete", f"{result_text}\n\nTurns: {self.battle.turn_number}")

    def run(self):
        """Run the GUI main loop."""
        self.root.mainloop()

    def set_action_callback(self, callback: Callable[[Action], ActionResult]):
        """Set callback for action execution."""
        self.on_action_callback = callback


def visualize_battle_gui(battle: "BattleState"):
    """
    Launch GUI visualizer for a battle.

    Args:
        battle: The battle state to visualize
    """
    visualizer = BattleGUIVisualizer(battle)
    visualizer.run()
