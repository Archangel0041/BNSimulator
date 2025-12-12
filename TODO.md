# Project TODO

## Phase 1: Data Setup ✓
- [x] Create repository structure
- [x] Add JSON files (units, abilities, enums, encounters)
- [x] Parse and validate JSON structure
- [x] Document data schema

## Phase 2: Simulator Development ✓
- [x] Core battle engine
  - [x] Grid system (variable sizes with dead corners)
  - [x] Unit placement system
  - [x] Turn execution (alternating single actions)
  - [x] Targeting system (range, patterns, line of sight)
  - [x] Damage calculation (ranges, crits, dodge)
  - [x] Status effects and modifiers
- [x] Action validation
  - [x] Legal move generation
  - [x] Target validation per ability
- [x] Win/loss/surrender conditions
- [x] Unit tests for simulator

## Phase 3: ML Environment ✓
- [x] Gymnasium environment wrapper
  - [x] State representation (grid + unit stats + game state)
  - [x] Action space (unit + ability + target)
  - [x] Reward function (win/loss, unit preservation, time penalty)
  - [x] Action masking for valid moves
- [x] Reset logic (wave progression, surrender handling)
- [x] Observation preprocessing

## Phase 4: Training Pipeline ✓
- [x] Baseline agent (random or heuristic)
- [x] DQN/PPO implementation
- [x] Reward shaping
  - [x] Surrender penalty (exponential with attempts)
  - [x] Unit preservation rewards
  - [x] Time efficiency incentives
- [ ] Curriculum learning (simple → complex encounters)
- [ ] Hyperparameter tuning

## Phase 5: Evaluation & Iteration
- [x] Performance metrics (win rate, avg attempts, avg turns)
- [ ] Visualizations (battle replays, learning curves)
- [ ] Strategy analysis
- [ ] Scale to full 4-wave encounters

## Refinements Needed
- [ ] Verify damage calculation formula against actual game
- [ ] Implement line_of_fire mechanics
- [ ] Implement blocking mechanics
- [ ] Refine AOE targeting patterns
- [ ] Add support for charge_time abilities
- [ ] Verify status effect interactions

## Nice-to-Have
- [ ] Web UI for watching battles
- [ ] Pre-battle positioning optimizer
- [ ] Multi-agent self-play
- [ ] Transfer learning across encounter types
