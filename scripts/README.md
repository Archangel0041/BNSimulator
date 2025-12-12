# Battle Simulator Scripts

This directory contains various scripts for running and visualizing battles in the BN Simulator.

## Available Scripts

### `gui_battle_test.py` ⭐ NEW

A **GUI-based battle visualizer** with interactive targeting and AOE visualization.

**Features:**
- Visual grid display with color-coded units and HP bars
- Click units to select them
- Select weapons to see valid targeting patterns highlighted
- **Hover over targets to see AOE damage patterns**:
  - Red cells: Primary damage (100%)
  - Orange cells: Secondary damage (<100%)
- **Reticle-based targeting**: Click on highlighted targets to execute attacks
- Turn-by-turn battle progression with visual feedback
- Unit information panel showing stats, weapons, and status effects
- Rank information displayed (shows if unit has multiple ranks available)

**Requirements:**
- Python with tkinter (comes standard with most Python installations)
- If tkinter is not available, install with: `sudo apt-get install python3-tk` (Linux) or it comes pre-installed on Windows/Mac

**Usage:**

```bash
# Run the GUI visualizer
python scripts/gui_battle_test.py
```

**Choose from:**
1. **Encounter 133 vs Unit 530 Rank 6** - The test scenario from earlier
2. **Custom random battle** - Random units
3. **Simple 2v2** - Quick test battle

**Controls:**
- **Click on unit** → Select unit and show weapons
- **Click weapon button** → Show valid targets (blue highlight)
- **Hover over target** → See AOE pattern (red/orange overlay)
- **Click target** → Execute attack
- **End Turn** button → Pass to enemy
- **Clear Selection** button → Deselect current unit

**What You'll See:**
- Selected unit highlighted in yellow
- Valid targets highlighted in blue
- AOE damage patterns shown on hover:
  - Primary targets in red (100% damage)
  - Splash targets in orange (<100% damage)
- HP bars showing unit health
- Unit class abbreviations (SOL, CRI, VEH, etc.)

### `battle_step_by_step.py`

A step-by-step battle visualization tool that lets you see exactly what happens during each turn of a battle.

**Features:**
- See the initial battle state with all units and their stats
- Watch each turn unfold with detailed action descriptions
- See damage dealt, status effects applied, and unit HP changes
- Visual grid showing unit positions and health percentages
- Color-coded output for better readability

**Usage:**

```bash
# Run the script
python scripts/battle_step_by_step.py
```

**Modes:**

1. **Step-by-step mode (Interactive)**: Press Enter after each turn to advance
   - Best for: Understanding game mechanics, debugging, learning
   - Shows: Full details of each action and result
   - Control: Manual progression through each turn

2. **Auto-play mode**: Battle runs automatically with small delays
   - Best for: Watching complete battles, testing outcomes
   - Shows: Same details as step-by-step but with automatic progression
   - Control: Automated with 0.5s delays between turns

**What You'll See:**

1. **Battle Start**: Lists all units on both sides with their HP, weapons, and positions
2. **Battle Grid**: Visual representation of the battlefield showing unit positions
3. **Each Turn Shows**:
   - Which side is acting (Player or Enemy)
   - Attacker details (unit type, position, weapon)
   - Target details (unit being attacked)
   - Weapon damage range and abilities
   - **Results**:
     - Damage dealt to each target
     - Current HP after damage
     - Units defeated (if any)
     - Status effects applied (bleed, stun, etc.)
   - Updated battlefield grid with new HP percentages
4. **Battle End**: Final statistics and battle outcome

**Example Output:**

```
======================================================================
TURN 1: PLAYER PHASE
======================================================================

Action:
  Attacker: AIRCRAFT at (0, 0)
  Weapon: veh_ancient_robot_player_weapon_primary_name
  Target: AIRCRAFT at (0, 0)
  Base Damage: 36-54
  Ability: abil_robot_tailwhip_name
  Range: 1-5

Results:
  Damage Dealt:
    • AIRCRAFT: 44 damage (HP: 146/190)
  Status Effects Applied:
    • BLEED (3 turns)

Updated Battlefield:
[Visual grid showing unit positions and HP%]
```

**Color Coding:**
- Green: Player units and actions
- Red: Enemy units and actions, unit defeats
- Yellow: Warnings, damage numbers
- Cyan: Grid and informational text
- Magenta: Status effects

### `test_encounter_133_vs_530.py`

Test script demonstrating the rank system with a specific battle scenario.

**Features:**
- Shows encounter 133 (raptors) vs unit 530 (veteran troopers) at rank 6
- Displays rank stat progression (HP, Defense, Power)
- Demonstrates tag hierarchy targeting
- Can be run in step-by-step, auto-play, or summary mode

**Usage:**

```bash
python scripts/test_encounter_133_vs_530.py
```

### `demo.py`

The original demo script that tests the battle simulator functionality.

**Usage:**

```bash
python scripts/demo.py
```

**Features:**
- Tests data loading
- Runs complete battles with AI agents
- Tests the Gymnasium environment
- Shows summary statistics

## Requirements

### Minimum Requirements

```bash
pip install numpy pandas pydantic gymnasium
```

### For GUI Visualizer

The GUI visualizer requires tkinter, which comes standard with most Python installations:
- **Windows/Mac**: Pre-installed with Python
- **Linux**: Install with `sudo apt-get install python3-tk`

### Full Installation

For full functionality including ML features:

```bash
pip install -r requirements.txt
```

## Tips

### For Terminal Visualization
- Use **step-by-step mode** when you want to understand how battles work
- Use **auto-play mode** when you want to quickly see battle outcomes
- Press Ctrl+C at any time to stop a battle
- The battle uses AI agents (HeuristicAgent for player, RandomAgent for enemy) to make decisions
- Each battle is deterministic when using the same seed

### For GUI Visualization
- **Testing Targeting**: Select a unit and weapon to see which cells can be targeted
- **Testing AOE Patterns**: Hover over targets to see the exact damage pattern
- **Testing Abilities**: Different weapons have different ranges and patterns
- **Rank Information**: Units with multiple ranks will show "(Rank X available)" in the info panel
- **Manual Control**: You control player units, AI controls enemy units by default

## Rank System

The simulator now supports unit ranks (1-based):
- **Rank 1**: Lowest/starting rank
- **Rank 6** (or max): Highest available rank
- Most enemy units default to rank 1
- Units with multiple ranks will be logged during battle creation
- Example: Unit 530 at Rank 1 has 315 HP, at Rank 6 has 520 HP (+65%)

## Tag Hierarchy

Targeting uses tag hierarchy:
- Parent tags can target units with child tags
- Example: Tag 24 includes tag 38, so abilities targeting [24] can hit units with [38]
- This is loaded from `battle_config.json`
