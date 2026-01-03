# Battle Engine Refactoring Plan

## Goal
Refactor the battle engine to have a very structured, step-by-step turn execution with explicit method calls for each step.

## Key Requirements
1. **One big master function** for player turn and enemy turn
2. **Each step is a separate method**
3. **Completely separate code** for player and enemy turns (NO code sharing - you'll merge later)
4. **Explicit flow** - reading the master function shows exactly what happens each turn

---

## Architecture

### File Structure
```
src/simulator/battle_engine/
├── __init__.py
├── battle_types.py              # Enums, dataclasses for results
├── player_turn_executor.py      # All player turn logic
├── enemy_turn_executor.py       # All enemy turn logic
└── battle_state.py              # Main battle state (refactored to use executors)
```

### Key Classes

**PlayerTurnExecutor** - Handles all player turn steps
- Has one master method: `execute_player_turn(action)`
- Each step is a separate private method: `_step_xxx()`

**EnemyTurnExecutor** - Handles all enemy turn steps
- Has one master method: `execute_enemy_turn()`
- Each step is a separate private method: `_step_xxx()`

**BattleState** - Manages overall battle
- Creates PlayerTurnExecutor and EnemyTurnExecutor instances
- Delegates turn execution to appropriate executor

---

## Player Turn Flow

```python
class PlayerTurnExecutor:
    def __init__(self, battle_state: BattleState):
        self.battle = battle_state
        self.rng = battle_state.rng

    def execute_player_turn(self, action: Action) -> TurnResult:
        """Execute complete player turn."""

        # 1. Apply DOT to player units
        self._step_apply_dot_to_player()

        # 2. Check if all player units dead -> end battle with loss
        if self._step_check_all_player_units_dead():
            self.battle.result = BattleResult.ENEMY_WIN
            return TurnResult.BATTLE_ENDED

        # 3. Collapse 1 row if no units on front row
        self._step_collapse_player_front_row()

        # 4. Reduce cooldowns (unit must not be stunned)
        self._step_reduce_player_cooldowns()

        # 5. Player selects action (passed in as parameter)
        # (This is handled externally)

        # 6. Check if unit is stunned/frozen/disabled
        if self._step_is_unit_disabled(action):
            return TurnResult.UNIT_CANNOT_ACT

        # 7. Check if targeting location is valid
        if not self._step_is_target_valid(action):
            return TurnResult.INVALID_TARGET

        # 8. Calculate base damage
        base_damage = self._step_calculate_base_damage(action)

        # 9. Check for dodges/misses/etc
        hit_result = self._step_check_hit(action)
        if not hit_result.hit:
            self._step_update_cooldown_and_ammo(action)
            return TurnResult.ATTACK_MISSED

        # Apply critical hit if rolled
        if hit_result.is_critical:
            base_damage *= 1.5

        # 10. Apply multipliers and armor
        final_damage = self._step_apply_multipliers_and_armor(action, base_damage)

        # 11. Apply damage
        self._step_apply_damage(action, final_damage)

        # 12. Check for dead units
        self._step_check_for_dead_units()

        # Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED

        # 13. Apply DOT status effects based on final damage
        self._step_apply_status_effects(action, final_damage)

        # 14. Update cooldown and ammo
        self._step_update_cooldown_and_ammo(action)

        return TurnResult.SUCCESS
```

---

## Enemy Turn Flow

```python
class EnemyTurnExecutor:
    def __init__(self, battle_state: BattleState):
        self.battle = battle_state
        self.rng = battle_state.rng
        self.ai_policy = None  # Set externally

    def execute_enemy_turn(self) -> TurnResult:
        """Execute complete enemy turn."""

        # 1. Apply DOT to enemy units
        self._step_apply_dot_to_enemy()

        # 2. Check if all enemy units dead -> end battle with victory
        if self._step_check_all_enemy_units_dead():
            self.battle.result = BattleResult.PLAYER_WIN
            return TurnResult.BATTLE_ENDED

        # 3. Collapse 1 row if no units on front row
        self._step_collapse_enemy_front_row()

        # 4. Reduce cooldowns (unit must not be stunned)
        self._step_reduce_enemy_cooldowns()

        # 5. Make list of all alive units and abilities
        all_possible_actions = self._step_list_all_alive_units_and_abilities()

        # 6. Filter all units which are stunned/frozen
        filtered_actions = self._step_filter_stunned_units(all_possible_actions)

        # 7. Filter abilities on cooldown
        filtered_actions = self._step_filter_cooldown_abilities(filtered_actions)

        # 8. Calculate valid targets for each ability
        # (empty locations & targets that will not take damage are not valid)
        actions_with_targets = self._step_calculate_valid_targets(filtered_actions)

        # 9. Filter abilities with no valid target
        valid_actions = self._step_filter_no_valid_targets(actions_with_targets)

        # No valid actions - skip turn
        if not valid_actions:
            return TurnResult.NO_VALID_ACTIONS

        # Select action using AI policy
        action = self._step_select_action(valid_actions)

        # 10. Calculate base damage
        base_damage = self._step_calculate_base_damage(action)

        # 11. Check for dodges/misses/etc
        hit_result = self._step_check_hit(action)
        if not hit_result.hit:
            self._step_update_cooldown_and_ammo(action)
            return TurnResult.ATTACK_MISSED

        # Apply critical hit if rolled
        if hit_result.is_critical:
            base_damage *= 1.5

        # 12. Apply modifiers & armor
        final_damage = self._step_apply_modifiers_and_armor(action, base_damage)

        # 13. Deal damage
        self._step_deal_damage(action, final_damage)

        # 14. Check for dead units
        self._step_check_for_dead_units()

        # Check if all player units dead -> end battle with loss
        if self._step_check_all_player_units_dead():
            self.battle.result = BattleResult.ENEMY_WIN
            return TurnResult.BATTLE_ENDED

        # 15. Apply DOT status effects
        self._step_apply_status_effects(action, final_damage)

        # 16. Update cooldown and ammo
        self._step_update_cooldown_and_ammo(action)

        return TurnResult.SUCCESS
```

---

## Supporting Types

```python
# battle_types.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class TurnResult(Enum):
    SUCCESS = "success"
    BATTLE_ENDED = "battle_ended"
    UNIT_CANNOT_ACT = "unit_cannot_act"
    INVALID_TARGET = "invalid_target"
    ATTACK_MISSED = "attack_missed"
    NO_VALID_ACTIONS = "no_valid_actions"

class BattleResult(Enum):
    IN_PROGRESS = "in_progress"
    PLAYER_WIN = "player_win"
    ENEMY_WIN = "enemy_win"
    SURRENDER = "surrender"

@dataclass
class HitResult:
    hit: bool
    is_critical: bool
    hit_chance: float

@dataclass
class Action:
    unit: BattleUnit
    ability: Ability
    target_position: Position
    # ... other fields
```

---

## Implementation Steps

### Step 1: Create new file structure
- Create `src/simulator/battle_engine/` directory
- Create `battle_types.py` with enums and dataclasses
- Create empty `player_turn_executor.py`
- Create empty `enemy_turn_executor.py`

### Step 2: Implement PlayerTurnExecutor
- Write the master `execute_player_turn()` function
- Implement each `_step_xxx()` method one by one
- Extract logic from current `battle.py`

### Step 3: Implement EnemyTurnExecutor
- Write the master `execute_enemy_turn()` function
- Implement each `_step_xxx()` method one by one
- Extract logic from current `battle.py`

### Step 4: Update BattleState
- Create instances of both executors
- Delegate to appropriate executor based on turn
- Keep existing interface for backward compatibility

### Step 5: Test
- Run existing tests
- Verify behavior matches old implementation
- Add new tests for individual steps

### Step 6: Update other systems
- Update CLI to use new battle engine
- Update Gymnasium environment
- Update any other integration points

---

## Key Implementation Notes

### DOT Application
- Iterate through all units on the current side
- For each status effect, calculate DOT damage:
  ```python
  dot_damage = source_damage * effect.dot_ability_damage_mult + effect.dot_bonus_damage
  ```
- Apply as fire damage (or effect's specified type)
- Decrement effect duration

### Row Collapse
- Check if row 0 (front row) has any alive units
- If not, move all units forward by 1 row
- Only collapse ONE row per turn (even if multiple rows are empty)

### Cooldown Reduction
- For each alive unit:
  - Check if unit can act (not stunned with stun_block_action)
  - If yes, decrement all weapon cooldowns
  - Decrement status effect durations

### Damage Calculation
1. Roll base weapon damage between min and max
2. Calculate attack contribution:
   ```
   attack = attacker.stats.attack + weapon.base_atk + attacker.stats.power
   ```
3. Calculate defense: `defender.stats.defense`
4. Base damage = weapon_damage + (attack - defense)
5. Apply class modifier (lookup table)
6. Roll critical hit (multiply by 1.5 if crit)
7. Apply type modifiers
8. Apply AOE falloff if applicable
9. Minimum damage = 1

### Hit/Miss Check
1. Base hit chance = 80%
2. Modify by: `attacker.accuracy - defender.dodge`
3. Clamp to 5-95% range
4. Roll against hit chance

### Armor Application
- If armor > 0 and ability AP < 1.0:
  - Damage to armor = damage * (1 - AP)
  - Damage to HP = damage * AP
  - If armor breaks, overflow goes to HP
- Type modifiers apply to both armor and HP

### Status Effect Application
- Check if target is immune to effect
- Roll for application chance
- If successful, add to target's status_effects list
- Store source_damage for DOT calculation

### Valid Target Rules (Enemy AI)
- Target position must be in range
- Target position must have a unit (if ability deals damage)
- Unit must be alive
- Empty positions are NOT valid targets
- Positions where ability deals 0 damage are NOT valid targets

---

## Migration from Old Code

Current code is in `src/simulator/battle.py`:
- `BattleUnit` class (lines 38-190) - Keep mostly as-is
- `BattleState` class (lines 211-675) - Refactor to use executors
- `BattleSimulator` class (lines 677-846) - Minimal changes

Current damage calculation is in `BattleState._calculate_damage()` (lines 520-557)
- Extract to `_step_calculate_base_damage()` in both executors

Current hit check is in `BattleState._execute_attack()` (lines 559-566)
- Extract to `_step_check_hit()` in both executors

Current status effects in `BattleUnit.tick_status_effects()` (lines 169-190)
- Use in `_step_apply_dot_to_player/enemy()` methods

---

## Testing Strategy

1. **Unit tests for individual steps**
   - Test each `_step_xxx()` method in isolation
   - Mock dependencies

2. **Integration tests for turn execution**
   - Test complete player turn
   - Test complete enemy turn
   - Test battle end conditions

3. **Regression tests**
   - Run existing battle simulations
   - Compare outputs with old implementation
   - Verify damage calculations match

4. **Edge cases**
   - All units stunned
   - No valid targets
   - Row collapse with multiple empty rows
   - DOT killing all units

---

## Benefits

1. **Readability**: The master function is like a table of contents for the turn
2. **Debuggability**: Can add breakpoints at any step
3. **Testability**: Each step can be tested individually
4. **Maintainability**: Easy to modify individual steps
5. **Documentation**: Code structure matches game design doc exactly
6. **Clarity**: No hidden logic - everything is explicit

---

## Next Steps

1. Create the directory structure
2. Implement `battle_types.py` with all necessary types
3. Implement `PlayerTurnExecutor` with all step methods
4. Implement `EnemyTurnExecutor` with all step methods
5. Refactor `BattleState` to use the executors
6. Update tests
7. Verify everything works
