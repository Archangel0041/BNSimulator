# Battle Simulator ML

A reinforcement learning project to train an AI agent for optimal turn-based tactical combat.

## Project Structure

```
battle-simulator-ml/
├── data/                  # Game data files
│   ├── units.json        # Unit definitions (700+ units)
│   ├── abilities.json    # Ability/attack definitions
│   ├── enums.json        # Game behavior enums
│   └── encounters.json   # Enemy encounter layouts
├── src/                   # Source code
│   ├── simulator/        # Battle simulator engine
│   ├── ml/               # ML training code
│   └── utils/            # Helper functions
├── tests/                 # Unit tests
├── notebooks/             # Jupyter notebooks for analysis
└── docs/                  # Documentation

```

## Game Mechanics

### Grid Layout
- Variable grid sizes: 3x3, 4x3, or 5x3
- Both player and enemy have mirrored grids
- Row 1 (front): 3-5 positions (facing opponent)
- Row 2 (mid): 3-5 positions
- Row 3 (back): 3 positions (center-aligned, corners are dead zones)

### Combat System
- **Turn-based**: Player unit acts → Enemy unit acts → repeat
- **Single unit action per turn**: Choose (unit, ability, target)
- **Static positioning**: No movement during combat
- **RNG elements**: Damage ranges, crit chance, dodge chance
- **Targeting patterns**: Unit/ability-specific (melee, ranged, column, AOE, etc.)

### Victory Conditions
- Eliminate all enemy units across 4 waves
- Can surrender with no penalty if no units lost yet
- Goal: Minimize attempts (resets) while achieving acceptable outcomes

## ML Approach

### Training Objectives
1. **Strategic Layer**: Learn optimal unit placement pre-battle
2. **Tactical Layer**: Learn optimal ability usage during combat
3. **Meta-Strategy**: Balance "perfect" outcomes vs time/attempts

### Key Challenges
- Avoid "perfectionism trap" (endless resets for perfect RNG)
- Handle variable grid sizes and unit compositions
- Learn targeting priorities and sequencing
- Manage 4-wave progression strategy

## Getting Started

1. Drop JSON files in `data/` directory
2. Run simulator validation
3. Train ML agent
4. Evaluate performance

## Status
🚧 **Phase 1**: Setting up repository and data structure
