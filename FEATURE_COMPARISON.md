# Feature Comparison: TypeScript (bntoolkit) vs Python (BNSimulator)

**Last Updated:** Latest bntoolkit commit 80e3d25
**Comparison Date:** 2025-12-13

---

## ✅ FEATURES WITH 100% PARITY

### Phase 1: Damage Formulas
| Feature | TypeScript | Python | Status |
|---------|------------|--------|--------|
| Rank Scaling | `Damage = BaseDamage * (1 + 2 * 0.01 * Power)` | ✅ Identical | ✅ |
| Dodge Calculation | `max(0, Defense - Offense + 5)` | ✅ Identical | ✅ |
| Armor Capacity | `ArmorHP / ArmorMod` | ✅ Identical | ✅ |
| Critical Hits | 1.5x multiplier | ✅ Identical | ✅ |
| Class Modifiers | Attacker vs Defender class | ✅ Identical | ✅ |

### Phase 2: Blocking & Line of Fire
| Feature | TypeScript | Python | Status |
|---------|------------|--------|--------|
| Blocking Levels | None/Partial/Full/God | ✅ Identical | ✅ |
| Line of Fire Types | Contact/Direct/Precise/Indirect | ✅ Identical | ✅ |
| Blocking Propagation | Units behind blocker | ✅ Identical | ✅ |
| Column Blocking | Same X coordinate | ✅ Identical | ✅ |

### Phase 3: Attack Patterns
| Feature | TypeScript | Python | Status |
|---------|------------|--------|--------|
| Single Target | No AOE | ✅ Identical | ✅ |
| Fixed Patterns | Predetermined cells | ✅ Identical | ✅ |
| AOE Reticle | Movable pattern | ✅ Identical | ✅ |
| Splash Damage | damage_area falloff | ✅ Identical | ✅ |
| Random Weighted | Weighted selection | ✅ Identical | ✅ |
| Attack Direction | Forward/Backward/Any | ✅ Identical | ✅ |
| Multi-Hit | shots × attacks | ✅ Identical | ✅ |

### Phase 4: Environmental Effects
| Feature | TypeScript | Python | Status |
|---------|------------|--------|--------|
| Environmental Mods | Terrain effects | ✅ Identical | ✅ |
| Status Damage Mods | Freeze/Shatter | ✅ Identical | ✅ |
| Status Armor Mods | Armor vulnerability | ✅ Identical | ✅ |
| Stun Armor Bypass | Active armor bypass | ✅ Identical | ✅ |
| Modifier Stacking | Multiplicative | ✅ Identical | ✅ |

### Phase 5: Advanced Mechanics
| Feature | TypeScript | Python | Status |
|---------|------------|--------|--------|
| Ammo Management | consume, reload | ✅ Identical | ✅ |
| Charge Time | Delay before firing | ✅ Identical | ✅ |
| Suppression/Aggro | damage * mult + bonus | ✅ Identical | ✅ |
| Infinite Ammo | -1 special value | ✅ Identical | ✅ |

---

## ✅ DOT SYSTEM - UPDATED TO FULL PARITY

### DOT (Damage Over Time) Calculations

#### **STATUS: Python implementation NOW MATCHES TypeScript (commit 80e3d25)**

**Updated Python (CORRECT):**
```python
# When applying DOT (try_apply_effect):
dot_damage = actual_damage_dealt + effect.dot_bonus_damage

# Apply environmental mods (bake them in)
if environmental_damage_mods:
    env_mod = environmental_damage_mods.get(effect.dot_damage_type, 1.0)
    dot_damage = int(dot_damage * env_mod)

# Apply ability damage multiplier
dot_damage = int(dot_damage * effect.dot_ability_damage_mult)

# Store as original_dot_damage (with env mods baked in)
# Resistance is NOT applied here

# When ticking DOT (process_effects):
decay_multiplier = 1.0
if effect.dot_diminishing:
    d = status.original_duration
    t = status.current_turn
    if d > 0:
        decay_multiplier = (d - t + 1) / d

# Environmental mods already baked into original_dot_damage
raw_dot_damage = int(status.original_dot_damage * decay_multiplier)

# Apply damage with armor and resistance, but NO environmental mods
```

**TypeScript (commit 80e3d25):**
```typescript
// When applying DOT:
const actualDamageDealt = totalHpDamage + totalArmorDamage;
const dotBonusDamage = effect.dot_bonus_damage ?? 0;
const dotAbilityDamageMult = effect.dot_ability_damage_mult ?? 1;

let dotDamage = actualDamageDealt + dotBonusDamage;

// Apply environmental mods (bake them in)
if (environmentalDamageMods && effect.dot_damage_type !== undefined) {
  const envMod = environmentalDamageMods[effect.dot_damage_type.toString()];
  if (envMod !== undefined) {
    dotDamage = Math.floor(dotDamage * envMod);
  }
}

// Apply ability damage multiplier
dotDamage = Math.floor(dotDamage * dotAbilityDamageMult);

// When ticking DOT:
let decayMultiplier = 1;
if (effect.dotDiminishing) {
  const d = effect.originalDuration;
  const t = effect.currentTurn;
  decayMultiplier = (d - t + 1) / d;
}

const rawDotDamage = Math.floor(effect.originalDotDamage * decayMultiplier);
```

#### **All Features Now Match:**

1. **Order of Operations:**
   - ✅ Python: `(source + bonus) * envMod * mult`
   - ✅ TypeScript: `(source + bonus) * envMod * mult`

2. **Environmental Mods:**
   - ✅ Python: Applied when DOT is applied, baked into original_dot_damage
   - ✅ TypeScript: Applied when DOT is applied, baked into originalDotDamage

3. **Resistance:**
   - ✅ Python: Applied when DOT ticks (each turn)
   - ✅ TypeScript: Applied when DOT ticks (each turn)

4. **Decay/Diminishing:**
   - ✅ Python: `decayMultiplier = (duration - turn + 1) / duration` if `dot_diminishing == true`
   - ✅ TypeScript: `decayMultiplier = (duration - turn + 1) / duration` if `dot_diminishing == true`

5. **Environmental Mods on Tick:**
   - ✅ Python: NOT applied on tick (already baked in)
   - ✅ TypeScript: NOT applied on tick (already baked in)

6. **Storage:**
   - ✅ Python: Stores `original_dot_damage`, `original_duration`, `current_turn`
   - ✅ TypeScript: Stores `originalDotDamage`, `originalDuration`, `currentTurn`

---

## 📊 Overall Feature Parity

| Category | Total Features | Matching | Outdated | Parity % |
|----------|----------------|----------|----------|----------|
| Phase 1: Damage Formulas | 5 | 5 | 0 | 100% ✅ |
| Phase 2: Blocking & LoF | 4 | 4 | 0 | 100% ✅ |
| Phase 3: Attack Patterns | 7 | 7 | 0 | 100% ✅ |
| Phase 4: Environmental | 5 | 5 | 0 | 100% ✅ |
| Phase 5: Advanced | 4 | 4 | 0 | 100% ✅ |
| **DOT System** | **6** | **6** | **0** | **100%** ✅ |
| **Overall** | **31** | **31** | **0** | **100%** 🎯 |

---

## ✅ Updates Completed

### 1. Updated ActiveStatusEffect Model ✅
```python
@dataclass
class ActiveStatusEffect:
    effect: StatusEffect
    remaining_turns: int
    original_dot_damage: float = 0.0  # ✅ Stores original DOT with env mods
    original_duration: int = 0         # ✅ For decay calculation
    current_turn: int = 1              # ✅ Track which turn we're on
    source_damage: float = 0.0         # DEPRECATED: kept for backward compatibility
```

### 2. Updated try_apply_effect() ✅
- ✅ Calculate DOT as: `(actualDamage + bonus) * envMod * mult`
- ✅ Store `original_dot_damage` (with env mods baked in)
- ✅ Store `original_duration` and `current_turn`
- ✅ Do NOT apply resistance when applying

### 3. Updated process_effects() ✅
- ✅ Calculate decay: `decayMult = (d - t + 1) / d` if `dot_diminishing`
- ✅ Calculate raw DOT: `originalDotDamage * decayMult`
- ✅ Apply damage with NO environmental mods (already baked in)
- ✅ Apply resistance when ticking
- ✅ Increment `current_turn`

---

## 📝 Summary

**Current State:**
- ✅ **31 of 31 features** have full parity (100%)
- ✅ **All DOT features** updated
- 🎯 **GOAL ACHIEVED:** 100% parity with TypeScript! 🎉

**Completed Updates:**
1. ✅ Updated DOT calculation to match new TypeScript formula
2. ✅ Added decay/diminishing logic
3. ✅ Baked environmental mods into DOT when applied
4. ✅ Track original DOT damage, duration, and current turn
5. ✅ Apply resistance on tick, not on application

**Files Updated:**
- `src/simulator/battle.py` - Updated ActiveStatusEffect dataclass
- `src/simulator/combat.py` - Updated try_apply_effect() and process_effects()
- `tests/test_dot_system.py` - New comprehensive DOT tests (all passing)
