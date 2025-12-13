# TypeScript to Python Porting Progress

This document tracks the incremental porting of features from bntoolkit (TypeScript) to BNSimulator (Python).

## Goal
Port the comprehensive battle simulator from TypeScript to Python with 100% formula and mechanic parity.

## Source Repository
- **TypeScript Reference**: https://github.com/Archangel0041/bntoolkit
- **Key Files**:
  - `src/lib/battleCalculations.ts` - Damage formulas
  - `src/lib/battleTargeting.ts` - Targeting and blocking
  - `src/types/battleSimulator.ts` - Type definitions

---

## ✅ Phase 1: Damage Calculation Formulas (COMPLETED)

### Changes Made

#### 1. Rank Scaling for Base Damage
**TypeScript Formula:**
```typescript
Damage = BaseDamage * (1 + 2 * 0.01 * Power)
```

**Implementation:** `src/simulator/combat.py:266-278`
- Added `DamageCalculator.calculate_damage_at_rank()` static method
- Power stat now properly scales base weapon damage
- Examples:
  - Power 0 → 1x damage (no scaling)
  - Power 50 → 2x damage
  - Power 25 → 1.5x damage

#### 2. Dodge Calculation Fix
**TypeScript Formula:**
```typescript
DodgeChance = max(0, Defense - Offense + 5)
```

**Old Python (WRONG):**
```python
dodge_chance = defender.dodge - attacker.accuracy
```

**New Python (CORRECT):** `src/simulator/combat.py:281-294`
- Added `DamageCalculator.calculate_dodge_chance()` static method
- Uses Defense vs Offense (not dodge vs accuracy)
- Includes +5 base dodge chance
- Properly capped at 0% minimum, 95% maximum

#### 3. Armor Mechanics Overhaul
**TypeScript Formula:**
```typescript
EffectiveArmorCapacity = ArmorHP / ArmorMod

// If armorMod is 0.6, armor can absorb MORE raw damage
// Example: 100 HP armor at 0.6 mod = 166 capacity
```

**Old Python (WRONG):**
- Applied armor_mod directly to damage
- Armor broke too quickly with low mods

**New Python (CORRECT):** `src/simulator/combat.py:371-450`
- Calculates effective armor capacity using division
- Properly handles armor piercing (bypasses armor directly to HP)
- Overflow damage correctly transitions to HP with HP mods
- Examples:
  - 100 armor @ 1.0 mod = 100 capacity
  - 100 armor @ 0.6 mod = 166 capacity (blocks more)
  - 100 armor @ 1.5 mod = 66 capacity (blocks less)

### Testing
All formulas validated with unit tests in `tests/test_damage_formulas.py`.

### Files Modified
- `src/simulator/combat.py` - DamageCalculator class
- `tests/test_damage_formulas.py` - New test file

---

## 🔄 Phase 2: Blocking & Line of Fire (PENDING)

### Features to Port

#### Blocking Levels
TypeScript has 4 blocking levels:
- **None (0)**: No blocking
- **Partial (1)**: Blocks Direct fire
- **Full (2)**: Blocks Direct + Precise fire
- **God (3)**: Blocks everything except Indirect

#### Line of Fire Types
- **Contact (0)**: Only hits closest row
- **Direct (1)**: Blocked by Partial+ blocking
- **Precise (2)**: Blocked by Full+ blocking
- **Indirect (3)**: Never blocked

#### Key Mechanics
- Blocking propagates to units behind
- Front row units block attacks to back row
- Column-based blocking (same X coordinate)

### Implementation Plan
1. Add blocking level enum to `enums.py`
2. Add blocking stat to `UnitStats` model
3. Implement `check_line_of_fire()` in targeting system
4. Update `get_valid_targets()` to respect blocking
5. Add blocking visualization to GUI

---

## 📋 Phase 3: AOE Targeting Patterns (PENDING)

### Features to Port

#### Target Area vs Damage Area
TypeScript distinguishes between:
- **target_area**: Where abilities can be AIMED (movable reticle)
- **damage_area**: Splash damage AROUND each impact point

#### Pattern Types
- **Single Target**: Direct hit, no pattern
- **Fixed Attacks**: Predetermined pattern, no aiming
- **AOE Patterns**: Movable reticle with splash
- **Random Weighted**: Randomly selects from weighted positions

#### Key Mechanics
- `targetType` determines pattern behavior
- `damagePercent` controls splash falloff
- `aoeOrderDelay` for staggered impacts
- `random` flag for weighted selection

---

## 🌍 Phase 4: Environmental Effects (PENDING)

### Features to Port

#### Environmental Damage Modifiers
- Terrain effects (e.g., Firemod increases fire damage)
- Applied to ALL damage before armor/HP mods
- Multiplicative with status effect mods

#### Status Effect Enhancements
- Status effects can modify incoming damage
- Freeze/Shatter mechanics
- Stun armor bypass for Active armor units
- Effect families for immunity grouping

---

## ⚡ Phase 5: Advanced Mechanics (PENDING)

### Features to Port

#### Multi-Hit Attacks
```typescript
totalShots = shotsPerAttack * attacksPerUse
```

#### Suppression/Aggro System
```typescript
suppressionValue = damage * suppressionMult + suppressionBonus
```

#### Ammo & Reload
- `ammoRequired` per use
- `weaponMaxAmmo` capacity
- `weaponReloadTime` turns

#### Charge Time
- Abilities with `chargeTime` delay before firing

---

## 📊 Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Damage Formulas | ✅ Complete | 100% |
| Phase 2: Blocking & LoF | ⏳ Pending | 0% |
| Phase 3: AOE Patterns | ⏳ Pending | 0% |
| Phase 4: Environmental | ⏳ Pending | 0% |
| Phase 5: Advanced | ⏳ Pending | 0% |
| **Overall** | **In Progress** | **~20%** |

---

## Testing Strategy

Each phase includes:
1. Unit tests for formula correctness
2. Integration tests with real game data
3. Comparison against TypeScript reference battles
4. GUI visualization for manual verification

---

## Notes

- All formulas sourced from bntoolkit TypeScript implementation
- Maintaining backward compatibility with existing Python code
- Each phase is independently testable
- Goal: 100% parity with TypeScript damage/mechanics
