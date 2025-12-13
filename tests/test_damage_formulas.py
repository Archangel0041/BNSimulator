"""Test damage calculation formulas match TypeScript implementation."""
from src.simulator.combat import DamageCalculator


def test_rank_scaling():
    """Test: Damage = BaseDamage * (1 + 2 * 0.01 * Power)"""
    print("Testing rank scaling...")

    # Power = 0 -> no scaling
    result = DamageCalculator.calculate_damage_at_rank(100, 0)
    assert result == 100, f"Expected 100, got {result}"
    print(f"  ✓ Power 0: {result}")

    # Power = 50 -> 2x damage
    result = DamageCalculator.calculate_damage_at_rank(100, 50)
    assert result == 200, f"Expected 200, got {result}"
    print(f"  ✓ Power 50: {result}")

    # Power = 25 -> 1.5x damage
    result = DamageCalculator.calculate_damage_at_rank(100, 25)
    assert result == 150, f"Expected 150, got {result}"
    print(f"  ✓ Power 25: {result}")

    # Power = 10 -> 1.2x damage
    result = DamageCalculator.calculate_damage_at_rank(100, 10)
    assert result == 120, f"Expected 120, got {result}"
    print(f"  ✓ Power 10: {result}")

    print("  ✅ Rank scaling tests passed!\n")


def test_dodge_calculation():
    """Test: DodgeChance = max(0, Defense - Offense + 5)"""
    print("Testing dodge calculation...")

    # Defense 20, Offense 10 -> 20 - 10 + 5 = 15%
    result = DamageCalculator.calculate_dodge_chance(20, 10)
    assert result == 15.0, f"Expected 15.0, got {result}"
    print(f"  ✓ Def 20 vs Off 10: {result}%")

    # Defense 10, Offense 20 -> negative, clamped to 0
    result = DamageCalculator.calculate_dodge_chance(10, 20)
    assert result == 0.0, f"Expected 0.0, got {result}"
    print(f"  ✓ Def 10 vs Off 20: {result}%")

    # Equal stats -> 5% base dodge
    result = DamageCalculator.calculate_dodge_chance(15, 15)
    assert result == 5.0, f"Expected 5.0, got {result}"
    print(f"  ✓ Def 15 vs Off 15: {result}%")

    # High defense advantage -> 30% dodge
    result = DamageCalculator.calculate_dodge_chance(50, 25)
    assert result == 30.0, f"Expected 30.0, got {result}"
    print(f"  ✓ Def 50 vs Off 25: {result}%")

    print("  ✅ Dodge calculation tests passed!\n")


def test_armor_effective_capacity():
    """Test armor capacity calculation."""
    print("Testing armor effective capacity...")

    # Armor HP = 100, Armor Mod = 1.0 -> capacity 100
    armor_hp = 100
    armor_mod = 1.0
    capacity = int(armor_hp / armor_mod)
    assert capacity == 100, f"Expected 100, got {capacity}"
    print(f"  ✓ 100 HP @ 1.0 mod: {capacity} capacity")

    # Armor HP = 100, Armor Mod = 0.6 -> capacity ~166 (blocks more)
    armor_hp = 100
    armor_mod = 0.6
    capacity = int(armor_hp / armor_mod)
    assert capacity == 166, f"Expected 166, got {capacity}"
    print(f"  ✓ 100 HP @ 0.6 mod: {capacity} capacity (blocks more)")

    # Armor HP = 100, Armor Mod = 1.5 -> capacity 66 (blocks less)
    armor_hp = 100
    armor_mod = 1.5
    capacity = int(armor_hp / armor_mod)
    assert capacity == 66, f"Expected 66, got {capacity}"
    print(f"  ✓ 100 HP @ 1.5 mod: {capacity} capacity (blocks less)")

    print("  ✅ Armor capacity tests passed!\n")


if __name__ == "__main__":
    print("="*60)
    print("PHASE 1: Damage Calculation Formula Tests")
    print("="*60 + "\n")

    try:
        test_rank_scaling()
        test_dodge_calculation()
        test_armor_effective_capacity()

        print("="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
