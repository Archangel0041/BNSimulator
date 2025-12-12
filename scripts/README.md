# Battle Simulator Scripts

This directory contains various scripts for running and visualizing battles in the BN Simulator.

## Available Scripts

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

Make sure you have installed the required dependencies:

```bash
pip install numpy pandas pydantic gymnasium
```

For full functionality including ML features, install all requirements:

```bash
pip install -r requirements.txt
```

## Tips

- Use **step-by-step mode** when you want to understand how battles work
- Use **auto-play mode** when you want to quickly see battle outcomes
- Press Ctrl+C at any time to stop a battle
- The battle uses AI agents (HeuristicAgent for player, RandomAgent for enemy) to make decisions
- Each battle is deterministic when using the same seed
