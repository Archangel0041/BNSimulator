#!/usr/bin/env python3
"""Test script to verify battle simulator fixes."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.simulator import BattleSimulator
from src.simulator.battle import BattleResult

def test_battle():
    """Test battle mechanics."""
    print("=" * 70)
    print("Testing Battle Simulator Fixes")
    print("=" * 70)
    print()

    simulator = BattleSimulator("data")

    # Create a simple battle
    print("Creating battle...")
    battle = simulator.create_battle_from_encounter(
        encounter_id=133,
        player_unit_ids=[530, 530],
        player_ranks=[6, 6]
    )

    if not battle:
        print("ERROR: Failed to create battle!")
        return False

    print(f"✓ Battle created")
    print(f"  Player units: {len(battle.player_units)}")
    print(f"  Enemy units: {len(battle.enemy_units)}")
    print()

    # Test 1: Check unit icons are set
    print("Test 1: Checking unit icons...")
    for i, unit in enumerate(battle.player_units):
        icon = unit.template.icon
        if icon:
            print(f"  ✓ Player unit {i}: icon='{icon}'")
        else:
            print(f"  ✗ Player unit {i}: No icon set!")
            return False

    for i, unit in enumerate(battle.enemy_units):
        icon = unit.template.icon
        if icon:
            print(f"  ✓ Enemy unit {i}: icon='{icon}'")
        else:
            print(f"  ✗ Enemy unit {i}: No icon set!")
            return False
    print()

    # Test 2: Execute a player action
    print("Test 2: Testing player attack...")
    battle.seed(42)  # For reproducibility

    legal_actions = battle.get_legal_actions()
    if not legal_actions:
        print("  ✗ No legal actions available!")
        return False

    print(f"  Found {len(legal_actions)} legal actions")
    action = legal_actions[0]
    unit = battle.player_units[action.unit_index]
    weapon = unit.template.weapons[action.weapon_id]

    print(f"  Executing: Unit {action.unit_index} uses weapon {action.weapon_id} ({weapon.name})")
    print(f"  Target: {action.target_position}")

    initial_hp = {}
    for i, enemy in enumerate(battle.enemy_units):
        initial_hp[i] = enemy.current_hp
        print(f"  Enemy {i} initial HP: {enemy.current_hp}")

    result = battle.execute_action(action)

    print(f"  After action:")
    for i, enemy in enumerate(battle.enemy_units):
        print(f"  Enemy {i} current HP: {enemy.current_hp}")

    if not result.success:
        print(f"  ✗ Action failed: {result.message}")
        return False

    print(f"  ✓ Action executed successfully")
    if result.damage_dealt:
        for unit_idx, damage in result.damage_dealt.items():
            print(f"    - Result says: Dealt {damage} damage to unit index {unit_idx}")

        # Check all enemy units to see actual HP changes
        print(f"  Checking actual HP changes...")
        any_damage = False
        for i, enemy in enumerate(battle.enemy_units):
            actual_damage = initial_hp[i] - enemy.current_hp
            if actual_damage != 0:
                print(f"    Enemy {i}: {initial_hp[i]} -> {enemy.current_hp} (took {actual_damage} damage)")
                any_damage = True

        if not any_damage:
            print(f"  ✗ No damage was actually applied to any enemy!")
            print(f"  Debugging info:")
            print(f"    - Target position: {action.target_position}")
            print(f"    - Result kills: {result.kills}")
            print(f"    - Result message: {result.message}")
            return False
        print(f"  ✓ Damage applied correctly")
    print()

    # Test 3: Check cooldowns
    print("Test 3: Testing cooldowns...")
    cooldown = unit.weapon_cooldowns.get(action.weapon_id, 0)
    if cooldown > 0:
        print(f"  ✓ Cooldown set: {cooldown} turns")
    else:
        print(f"  ℹ No cooldown (weapon ready immediately)")
    print()

    # Test 4: Test enemy turn
    print("Test 4: Testing enemy turns...")
    battle.end_turn()

    if battle.is_player_turn:
        print("  ✗ Still player turn after ending turn!")
        return False

    print("  ✓ Switched to enemy turn")

    # Get enemy actions
    enemy_actions = battle.get_legal_actions()
    if not enemy_actions:
        print("  ℹ No enemy actions available (enemies may be immobilized or out of range)")
    else:
        print(f"  Found {len(enemy_actions)} legal enemy actions")
        # Execute one enemy action
        enemy_action = battle.rng.choice(enemy_actions)
        enemy_unit = battle.enemy_units[enemy_action.unit_index]
        enemy_weapon = enemy_unit.template.weapons[enemy_action.weapon_id]
        print(f"  Executing: Enemy unit {enemy_action.unit_index} uses weapon {enemy_action.weapon_id}")

        player_initial_hp = {}
        for i, player in enumerate(battle.player_units):
            player_initial_hp[i] = player.current_hp

        enemy_result = battle.execute_action(enemy_action)

        if not enemy_result.success:
            print(f"  ✗ Enemy action failed: {enemy_result.message}")
            return False

        print(f"  ✓ Enemy action executed")
        if enemy_result.damage_dealt:
            for unit_idx, damage in enemy_result.damage_dealt.items():
                print(f"    - Dealt {damage} damage to player {unit_idx}")
                # Verify damage was applied
                actual_damage = player_initial_hp[unit_idx] - battle.player_units[unit_idx].current_hp
                if actual_damage != damage:
                    print(f"    ✗ Damage not applied correctly! Expected {damage}, got {actual_damage}")
                    return False
            print(f"  ✓ Enemy damage applied correctly")

    print()

    # Test 5: Verify cooldown ticking
    print("Test 5: Testing cooldown ticking...")
    battle.end_turn()  # End enemy turn

    if not battle.is_player_turn:
        print("  ✗ Not player turn after ending enemy turn!")
        return False

    print("  ✓ Back to player turn")

    # Check if cooldown ticked
    new_cooldown = unit.weapon_cooldowns.get(action.weapon_id, 0)
    if cooldown > 0:
        if new_cooldown == cooldown - 1:
            print(f"  ✓ Cooldown ticked: {cooldown} -> {new_cooldown}")
        else:
            print(f"  ✗ Cooldown not ticking correctly: {cooldown} -> {new_cooldown}")
            return False
    print()

    print("=" * 70)
    print("All tests passed! ✓")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = test_battle()
    sys.exit(0 if success else 1)
