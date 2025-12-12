# Project TODO

## Phase 1: Data Setup ✓
- [x] Create repository structure
- [ ] Add JSON files (units, abilities, enums, encounters)
- [ ] Parse and validate JSON structure
- [ ] Document data schema

## Phase 2: Simulator Development
- [ ] Core battle engine
  - [ ] Grid system (variable sizes with dead corners)
  - [ ] Unit placement system
  - [ ] Turn execution (alternating single actions)
  - [ ] Targeting system (range, patterns, line of sight)
  - [ ] Damage calculation (ranges, crits, dodge)
  - [ ] Status effects and modifiers
- [ ] Action validation
  - [ ] Legal move generation
  - [ ] Target validation per ability
- [ ] Win/loss/surrender conditions
- [ ] Unit tests for simulator

## Phase 3: ML Environment
- [ ] Gymnasium environment wrapper
  - [ ] State representation (grid + unit stats + game state)
  - [ ] Action space (unit + ability + target)
  - [ ] Reward function (win/loss, unit preservation, time penalty)
  - [ ] Action masking for valid moves
- [ ] Reset logic (wave progression, surrender handling)
- [ ] Observation preprocessing

## Phase 4: Training Pipeline
- [ ] Baseline agent (random or heuristic)
- [ ] DQN/PPO implementation
- [ ] Reward shaping
  - [ ] Surrender penalty (exponential with attempts)
  - [ ] Unit preservation rewards
  - [ ] Time efficiency incentives
- [ ] Curriculum learning (simple → complex encounters)
- [ ] Hyperparameter tuning

## Phase 5: Evaluation & Iteration
- [ ] Performance metrics (win rate, avg attempts, avg turns)
- [ ] Visualizations (battle replays, learning curves)
- [ ] Strategy analysis
- [ ] Scale to full 4-wave encounters

## Nice-to-Have
- [ ] Web UI for watching battles
- [ ] Pre-battle positioning optimizer
- [ ] Multi-agent self-play
- [ ] Transfer learning across encounter types
