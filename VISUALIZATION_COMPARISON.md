# Visualization Feature Comparison

**Comparing TypeScript (Web UI) vs Python (Terminal) Visualizers**

---

## 📊 Feature Overview

| Feature Category | TypeScript (Web) | Python (Terminal) | Parity |
|-----------------|------------------|-------------------|--------|
| **Grid Rendering** | ✅ Rich UI | ✅ ANSI Terminal | ✅ |
| **Unit Display** | ✅ Images | ✅ Text/Colors | ⚠️ |
| **HP/Armor Bars** | ✅ Visual bars | ✅ Percentage | ⚠️ |
| **Damage Preview** | ✅ Detailed | ❌ Missing | ❌ |
| **Battle Log** | ✅ Full history | ❌ Missing | ❌ |
| **AOE Patterns** | ✅ Visual | ✅ Highlighting | ✅ |
| **Targeting Info** | ✅ Can/Cannot | ⚠️ Basic | ⚠️ |
| **Status Effects** | ✅ Icons+Details | ⚠️ Text only | ⚠️ |
| **Ammo/Cooldowns** | ✅ Live tracking | ⚠️ Basic | ⚠️ |
| **Blocking Info** | ✅ Shows blocker | ❌ Missing | ❌ |
| **Multi-hit Display** | ✅ Shows count | ❌ Missing | ❌ |

---

## 🎨 TypeScript Features (Web UI)

### 1. **BattleGrid Component**

#### Grid Display:
- 5x3 grid with proper layout (front/mid/back rows)
- Unit images with HP/Armor bars
- Blocked cells (back row corners) marked
- Drag-and-drop for formation management

#### Damage Preview System:
```typescript
// Shows BEFORE attacking:
- Min/Max HP damage (green → orange → red bars)
- Min/Max Armor damage (blue → orange → red bars)
- Dodge chance (yellow badge)
- Critical chance
- Status effects that will be applied
- "Cannot target" reasons (out of range, blocked)
```

#### Targeting Patterns:
- Reticle movement (keyboard arrows or drag)
- AOE visualization (100%, 80%, 40% zones)
- Fixed attack patterns (cone, splash)
- Multi-hit indicators (e.g., "100% (3x)")
- Valid/invalid target highlighting

#### Blocking Information:
- Shows which unit is blocking
- Displays blocking level (Partial/Full/God)
- Visual "Blocked" overlay

### 2. **BattleLog Component**

#### Turn History:
```typescript
// Shows:
- Turn number
- Player/Enemy indicator
- Actions per turn:
  * Unit → Ability → Target
  * Damage dealt (HP + Armor)
  * Status effects applied
  * Dodges/Crits
  * Deaths
- Turn summaries (total damage, kills, etc.)
```

#### Action Types with Icons:
- ⚔️ Attack
- 💨 Dodge
- 🎯 Crit
- 💀 Death
- ⚡ Status Applied
- 🔥 Status Tick (DOT damage)
- 🛡️ Skip/Block

#### Features:
- Auto-scroll to latest
- Turn highlighting
- Localized text
- Multi-hit display

### 3. **UnitInfoPanel Component**

#### Core Stats Display:
```typescript
- HP: current/max (red if damaged)
- Armor: current/max (blue)
- Accuracy, Defense, Power
- Critical %, Bravery, PV
```

#### Properties:
- Class type
- Blocking level (color-coded)
- Preferred row (Front/Mid/Back)
- Size

#### Weapons & Abilities:
**Per Weapon:**
- Ammo: current/max (or ∞)
- Reload time
- Global cooldown

**Per Ability:**
- Icon + Localized name
- Damage type icon
- Damage range (min-max)
- Total shots (shots_per_attack × attacks_per_use)
- Offense, Range, Line of Fire
- Cooldown, Global CD
- Crit %
- Armor Piercing %

#### Advanced Features:
- **Targeting Categories:**
  - ✓ Can Target: Air, Sea, Soldier, Vehicle, etc. (color badges)
  - ✗ Cannot Target: (grayed out)

- **Crit Bonuses:**
  - Shows "+X% vs TagName" for each bonus

- **Status Effects:**
  - Shows effects ability inflicts
  - Icons + chance % + duration
  - DOT damage per turn

- **Immunities:**
  - Lists status effects unit is immune to
  - Shows icons

---

## 🖥️ Python Features (Terminal UI)

### Current Implementation:

#### Grid Display:
```python
# Shows:
- 5x3 grid (both sides)
- Unit class abbreviation (e.g., "SOL")
- HP percentage with color (Green/Yellow/Red)
- Blocked cells (back corners)
- Position labels (Front/Mid/Back)
```

#### Highlighting:
- Valid targets (cyan background)
- AOE patterns (red/yellow/magenta by damage %)
- Selected unit (blue background)

#### Unit Info:
- Basic stats (HP, Armor, Position)
- Stats (Defense, Dodge%, Accuracy, Critical%, Power)
- Weapons list with cooldown status
- Abilities with range/targets

#### Interactive Controls:
- `g` - Show grid
- `u <idx>` - Show unit info
- `t <unit> <weapon>` - Highlight targets
- `a <unit> <weapon> <x> <y>` - Execute action
- `l` - Show legal actions
- `n` - Next turn
- `r` - Random action
- `c` - Clear highlights

---

## ❌ Missing Features in Python

### Critical Missing Features:

1. **Battle Log / Turn History**
   - No record of previous actions
   - Cannot see what happened in past turns
   - No damage tracking per turn

2. **Damage Preview**
   - Cannot see damage before attacking
   - No min/max damage display
   - No dodge chance preview
   - No status effect preview

3. **Advanced Unit Info:**
   - No targeting categories (what can be targeted)
   - No crit bonus display
   - No status effect details
   - No status effect immunities display
   - No ability icons/visual aids

4. **Blocking Information:**
   - Doesn't show WHO is blocking
   - Doesn't show blocking level
   - No "blocked by" messages

5. **Multi-hit Display:**
   - Doesn't show hit count
   - Doesn't show total shots calculation

6. **Ammo/Cooldown Tracking:**
   - No live ammo visualization
   - Limited cooldown info

7. **Status Effect Tracking:**
   - No current status effects on units
   - No DOT damage display
   - No turn countdown

---

## 🎯 Recommended Python Enhancements

### Priority 1: Battle Log (High Impact)

Add a simple text-based battle log:
```python
class BattleLog:
    """Track and display battle history."""

    def add_action(self, turn, attacker, target, ability, damage, effects):
        """Record an action."""

    def show_recent(self, n=10):
        """Show last N actions."""

    def show_turn_summary(self, turn):
        """Show summary of a specific turn."""
```

### Priority 2: Damage Preview (High Impact)

Enhance grid to show damage preview:
```python
# Before attack, show:
- [Target] SOL 80% → 45-60% (dodge: 15%)
- Damage: 120-150 HP, 30-40 Armor
- Effects: Burn (50%, 3t)
```

### Priority 3: Enhanced Unit Info (Medium Impact)

Add missing details to unit info display:
```python
- Show targeting restrictions
- Show crit bonuses
- Show status immunities
- Show active status effects on unit
```

### Priority 4: Blocking Info (Medium Impact)

Show blocking information in grid:
```python
# When hovering/selecting blocked target:
"Cannot attack: Blocked by SOL (15) [Full blocking]"
```

### Priority 5: Multi-hit Info (Low Impact)

Show multi-hit calculations:
```python
# In ability info:
"Damage: 50-60 x 3 hits = 150-180 total"
```

---

## 📝 Implementation Plan

### Phase 1: Battle Log System
1. Create BattleLog class
2. Track all actions (attacks, dodges, deaths, status)
3. Display last 10-20 actions
4. Add turn summaries

### Phase 2: Damage Preview
1. Calculate damage range before attack
2. Show min/max HP and Armor damage
3. Show dodge chance
4. Show potential status effects

### Phase 3: Enhanced Unit Display
1. Show active status effects
2. Show ammo/cooldown in grid
3. Show blocking info
4. Add "cannot target" reasons

### Phase 4: Advanced Info Panel
1. Add targeting categories
2. Add crit bonuses
3. Add status immunities
4. Show detailed ability info

---

## 🔧 Technical Considerations

### Terminal Limitations:
- No images (use ASCII art or emoji)
- No mouse (keyboard only)
- Limited colors (256-color palette)
- Fixed character width

### Advantages:
- Fast rendering
- Low resource usage
- Works over SSH
- Easy to test/debug

### Suggested Approach:
- Use **rich** library for better terminal UI
- Add tabbed interface (grid / log / info)
- Use color coding extensively
- Keep text concise

---

## 🎉 Goal: Feature Parity

**Target:** Match TypeScript functionality in terminal format

**Success Criteria:**
- ✅ Can see battle history
- ✅ Can preview damage before attacking
- ✅ Can see all blocking information
- ✅ Can see detailed ability/status info
- ✅ Can track ammo/cooldowns live
- ✅ Can see multi-hit calculations

**Estimated Effort:** 4-6 hours of development

**Files to Modify:**
- `src/utils/visualizer.py` (main changes)
- `src/simulator/battle.py` (add battle log tracking)
- `tests/test_visualizer.py` (new tests)
