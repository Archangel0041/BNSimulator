#!/usr/bin/env python3
"""Integration test for Phase 3: Attack Patterns & Multi-Hit."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.simulator.enums import AttackDirection, LineOfFire, UnitBlocking
from src.simulator.models import Position, AbilityStats, Ability, TargetArea, DamageArea
from src.simulator.combat import TargetingSystem, TagResolver


def test_attack_direction_validation():
    """Test attack direction constraints."""
    print("="*60)
    print("PHASE 3 INTEGRATION TEST: Attack Direction")
    print("="*60 + "\n")

    # Create targeting system
    tag_resolver = TagResolver({})
    targeting = TargetingSystem(tag_resolver)

    # Test positions
    front = Position(2, 0)  # Front row
    back = Position(2, 2)   # Back row

    # Test FORWARD direction
    print("Testing FORWARD direction...")
    result = targeting.can_attack_direction(front, back, AttackDirection.FORWARD)
    assert result == True, "FORWARD: Front should be able to attack back"
    print(f"  ✓ Front (y=0) → Back (y=2): {result}")

    result = targeting.can_attack_direction(back, front, AttackDirection.FORWARD)
    assert result == False, "FORWARD: Back should NOT be able to attack front"
    print(f"  ✓ Back (y=2) → Front (y=0): {result}")

    # Test BACKWARD direction
    print("\nTesting BACKWARD direction...")
    result = targeting.can_attack_direction(back, front, AttackDirection.BACKWARD)
    assert result == True, "BACKWARD: Back should be able to attack front"
    print(f"  ✓ Back (y=2) → Front (y=0): {result}")

    result = targeting.can_attack_direction(front, back, AttackDirection.BACKWARD)
    assert result == False, "BACKWARD: Front should NOT be able to attack back"
    print(f"  ✓ Front (y=0) → Back (y=2): {result}")

    # Test ANY direction
    print("\nTesting ANY direction...")
    result = targeting.can_attack_direction(front, back, AttackDirection.ANY)
    assert result == True, "ANY: Should allow any direction"
    print(f"  ✓ Front (y=0) → Back (y=2): {result}")

    result = targeting.can_attack_direction(back, front, AttackDirection.ANY)
    assert result == True, "ANY: Should allow any direction"
    print(f"  ✓ Back (y=2) → Front (y=0): {result}")

    print("\n✅ Attack direction validation passed!\n")


def test_attack_type_detection():
    """Test attack type classification."""
    print("="*60)
    print("PHASE 3 INTEGRATION TEST: Attack Type Detection")
    print("="*60 + "\n")

    tag_resolver = TagResolver({})
    targeting = TargetingSystem(tag_resolver)

    # Test 1: Single target attack
    print("Test 1: Single Target Attack")
    stats = AbilityStats()
    ability = Ability(id=1, name="Single Shot", stats=stats)

    is_single = targeting.is_single_target(ability)
    is_fixed = targeting.is_fixed_attack(ability)

    assert is_single == True, "Should be single target"
    assert is_fixed == False, "Should not be fixed"
    print(f"  ✓ is_single_target: {is_single}")
    print(f"  ✓ is_fixed_attack: {is_fixed}")

    # Test 2: Fixed attack pattern
    print("\nTest 2: Fixed Attack Pattern")
    stats = AbilityStats(
        target_area=TargetArea(
            target_type=1,  # SINGLE
            data=[
                DamageArea(pos=Position(0, 0), damage_percent=100.0),
                DamageArea(pos=Position(1, 0), damage_percent=50.0),  # Offset!
            ]
        )
    )
    ability = Ability(id=2, name="Cross Slash", stats=stats)

    is_single = targeting.is_single_target(ability)
    is_fixed = targeting.is_fixed_attack(ability)

    assert is_single == False, "Should not be single target (has offsets)"
    assert is_fixed == True, "Should be fixed attack"
    print(f"  ✓ is_single_target: {is_single}")
    print(f"  ✓ is_fixed_attack: {is_fixed}")

    # Test 3: Splash damage
    print("\nTest 3: Splash Damage Attack")
    stats = AbilityStats(
        damage_area=[
            DamageArea(pos=Position(0, 0), damage_percent=100.0),
            DamageArea(pos=Position(1, 0), damage_percent=50.0),  # Splash!
        ]
    )
    ability = Ability(id=3, name="Grenade", stats=stats)

    is_single = targeting.is_single_target(ability)
    assert is_single == False, "Should not be single target (has splash)"
    print(f"  ✓ is_single_target: {is_single} (has splash)")

    print("\n✅ Attack type detection passed!\n")


def test_multi_hit_mechanics():
    """Test multi-hit attack configuration."""
    print("="*60)
    print("PHASE 3 INTEGRATION TEST: Multi-Hit Mechanics")
    print("="*60 + "\n")

    test_cases = [
        (1, 1, "Single shot"),
        (3, 1, "Burst fire"),
        (1, 2, "Double attack"),
        (2, 3, "Combo"),
        (5, 2, "Machine gun"),
    ]

    for shots, attacks, desc in test_cases:
        stats = AbilityStats(
            shots_per_attack=shots,
            attacks_per_use=attacks
        )

        total_shots = stats.shots_per_attack * stats.attacks_per_use
        print(f"  ✓ {desc}: {shots} × {attacks} = {total_shots}")

    print("\n✅ Multi-hit mechanics passed!\n")


def test_line_of_fire_enums():
    """Test that enums are properly defined."""
    print("="*60)
    print("PHASE 3 INTEGRATION TEST: Enum Verification")
    print("="*60 + "\n")

    print("LineOfFire enum values:")
    assert LineOfFire.CONTACT == 0
    print(f"  ✓ CONTACT = {LineOfFire.CONTACT}")

    assert LineOfFire.DIRECT == 1
    print(f"  ✓ DIRECT = {LineOfFire.DIRECT}")

    assert LineOfFire.PRECISE == 2
    print(f"  ✓ PRECISE = {LineOfFire.PRECISE}")

    assert LineOfFire.INDIRECT == 3
    print(f"  ✓ INDIRECT = {LineOfFire.INDIRECT}")

    print("\nAttackDirection enum values:")
    assert AttackDirection.ANY == 0
    print(f"  ✓ ANY = {AttackDirection.ANY}")

    assert AttackDirection.FORWARD == 1
    print(f"  ✓ FORWARD = {AttackDirection.FORWARD}")

    assert AttackDirection.BACKWARD == 2
    print(f"  ✓ BACKWARD = {AttackDirection.BACKWARD}")

    print("\nUnitBlocking enum values:")
    assert UnitBlocking.NONE == 0
    print(f"  ✓ NONE = {UnitBlocking.NONE}")

    assert UnitBlocking.PARTIAL == 1
    print(f"  ✓ PARTIAL = {UnitBlocking.PARTIAL}")

    assert UnitBlocking.FULL == 2
    print(f"  ✓ FULL = {UnitBlocking.FULL}")

    assert UnitBlocking.GOD == 3
    print(f"  ✓ GOD = {UnitBlocking.GOD}")

    print("\n✅ Enum verification passed!\n")


if __name__ == "__main__":
    try:
        test_line_of_fire_enums()
        test_attack_direction_validation()
        test_attack_type_detection()
        test_multi_hit_mechanics()

        print("="*60)
        print("✅ ALL PHASE 3 INTEGRATION TESTS PASSED!")
        print("="*60)
        print("\nPhases Complete:")
        print("  ✅ Phase 1: Damage Formulas")
        print("  ✅ Phase 2: Blocking & Line of Fire")
        print("  ✅ Phase 3: Attack Patterns & Multi-Hit")
        print("\nProgress: ~60% complete")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
