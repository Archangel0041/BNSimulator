"""Tests for DOT (Damage Over Time) handler."""
import pytest

from src.simulator.battle import BattleUnit, ActiveStatusEffect
from src.simulator.battle_engine.dot_handler import DOTHandler
from src.simulator.models import (
    Position, UnitTemplate, UnitStats, StatusEffect
)
from src.simulator.enums import (
    Side, UnitClass, DamageType, BattleSide,
    StatusEffectType, StatusEffectFamily
)


@pytest.fixture
def basic_unit_template():
    """Create a basic unit template for testing."""
    stats = UnitStats(
        hp=100,
        armor_hp=50,
        defense=5,
        dodge=10,
        accuracy=10,
        critical=5.0,
        power=10,
        bravery=5
    )
    return UnitTemplate(
        id=1,
        name="Test Unit",
        class_type=UnitClass.SOLDIER,
        side=Side.PLAYER,
        stats=stats
    )


@pytest.fixture
def battle_unit(basic_unit_template):
    """Create a battle unit for testing."""
    return BattleUnit(
        template=basic_unit_template,
        position=Position(0, 0),
        battle_side=BattleSide.PLAYER_TEAM
    )


@pytest.fixture
def diminishing_dot_effect():
    """Create a diminishing DOT status effect."""
    return StatusEffect(
        id=1,
        effect_type=StatusEffectType.DOT,
        family=StatusEffectFamily.BURN,
        duration=3,
        dot_damage_type=DamageType.FIRE,
        dot_ability_damage_mult=1.0,
        dot_bonus_damage=0,
        dot_ap_percent=0.0,
        dot_diminishing=True  # Damage decreases over time
    )


@pytest.fixture
def constant_dot_effect():
    """Create a constant DOT status effect."""
    return StatusEffect(
        id=2,
        effect_type=StatusEffectType.DOT,
        family=StatusEffectFamily.POISON,
        duration=3,
        dot_damage_type=DamageType.FIRE,
        dot_ability_damage_mult=1.0,
        dot_bonus_damage=0,
        dot_ap_percent=0.0,
        dot_diminishing=False  # Constant damage each turn
    )


class TestDOTCalculation:
    """Tests for DOT damage calculation."""

    def test_diminishing_dot_full_duration(self, diminishing_dot_effect):
        """Test diminishing DOT over full duration."""
        # 100 base damage, 3-turn duration
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )

        # Turn 1: remaining_turns=3, should be 100% (3/3)
        assert DOTHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        # Turn 2: remaining_turns=2, should be 66.67% (2/3)
        damage_turn_2 = DOTHandler.calculate_dot_damage(status)
        assert abs(damage_turn_2 - 66.67) < 0.1
        status.remaining_turns -= 1

        # Turn 3: remaining_turns=1, should be 33.33% (1/3)
        damage_turn_3 = DOTHandler.calculate_dot_damage(status)
        assert abs(damage_turn_3 - 33.33) < 0.1

    def test_constant_dot_full_duration(self, constant_dot_effect):
        """Test constant DOT stays same over duration."""
        # 100 base damage, 3-turn duration
        status = ActiveStatusEffect(
            effect=constant_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )

        # All turns should be 100 damage
        assert DOTHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert DOTHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert DOTHandler.calculate_dot_damage(status) == 100.0

    def test_diminishing_dot_with_duration_4(self, diminishing_dot_effect):
        """Test diminishing DOT with duration=4."""
        diminishing_dot_effect.duration = 4
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=4,
            base_dot_damage=100.0
        )

        # Turn 1: 4/4 = 100%
        assert DOTHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        # Turn 2: 3/4 = 75%
        assert DOTHandler.calculate_dot_damage(status) == 75.0
        status.remaining_turns -= 1

        # Turn 3: 2/4 = 50%
        assert DOTHandler.calculate_dot_damage(status) == 50.0
        status.remaining_turns -= 1

        # Turn 4: 1/4 = 25%
        assert DOTHandler.calculate_dot_damage(status) == 25.0

    def test_diminishing_dot_with_duration_5(self, diminishing_dot_effect):
        """Test diminishing DOT with duration=5."""
        diminishing_dot_effect.duration = 5
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=5,
            base_dot_damage=100.0
        )

        # Turn 1: 5/5 = 100%
        assert DOTHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        # Turn 2: 4/5 = 80%
        assert DOTHandler.calculate_dot_damage(status) == 80.0
        status.remaining_turns -= 1

        # Turn 3: 3/5 = 60%
        assert DOTHandler.calculate_dot_damage(status) == 60.0
        status.remaining_turns -= 1

        # Turn 4: 2/5 = 40%
        assert DOTHandler.calculate_dot_damage(status) == 40.0
        status.remaining_turns -= 1

        # Turn 5: 1/5 = 20%
        assert DOTHandler.calculate_dot_damage(status) == 20.0

    def test_zero_duration_dot(self, diminishing_dot_effect):
        """Test DOT with duration=0 uses constant damage."""
        diminishing_dot_effect.duration = 0
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=1,
            base_dot_damage=100.0
        )

        # Should fall back to constant damage
        assert DOTHandler.calculate_dot_damage(status) == 100.0


class TestDOTApplication:
    """Tests for applying DOT to units."""

    def test_apply_single_dot_to_unit(self, battle_unit, diminishing_dot_effect):
        """Test applying a single DOT effect to a unit."""
        initial_hp = battle_unit.current_hp
        initial_armor = battle_unit.current_armor

        # Add a DOT effect (100 damage, 3 turns, diminishing)
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )
        battle_unit.status_effects.append(status)

        # Apply DOT (should do 100 damage on first turn)
        DOTHandler.apply_dot_to_unit(battle_unit)

        # With 50 armor: 50 damage to armor, 50 damage to HP
        assert battle_unit.current_armor == 0
        assert battle_unit.current_hp == initial_hp - 50

    def test_apply_multiple_dot_effects(self, battle_unit, diminishing_dot_effect, constant_dot_effect):
        """Test applying multiple DOT effects to a unit."""
        initial_hp = battle_unit.current_hp
        initial_armor = battle_unit.current_armor

        # Add two DOT effects
        status1 = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=50.0
        )
        status2 = ActiveStatusEffect(
            effect=constant_dot_effect,
            remaining_turns=3,
            base_dot_damage=30.0
        )
        battle_unit.status_effects.extend([status1, status2])

        # Apply DOT (should do 50 + 30 = 80 damage total)
        DOTHandler.apply_dot_to_unit(battle_unit)

        # With 50 armor: 50 damage to armor (depleted), 30 damage to HP
        assert battle_unit.current_armor == 0
        assert battle_unit.current_hp == initial_hp - 30

    def test_apply_dot_with_armor(self, battle_unit, diminishing_dot_effect):
        """Test that DOT respects armor and damage types."""
        initial_armor = battle_unit.current_armor
        initial_hp = battle_unit.current_hp

        # Add a DOT effect with 50 damage
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)

        # Apply DOT
        DOTHandler.apply_dot_to_unit(battle_unit)

        # Armor should be reduced (fire damage with 0 AP goes to armor first)
        assert battle_unit.current_armor < initial_armor or battle_unit.current_hp < initial_hp

    def test_apply_dot_with_armor_piercing(self, battle_unit):
        """Test DOT with armor piercing bypasses armor."""
        # Create DOT with 100% armor piercing
        dot_effect = StatusEffect(
            id=3,
            effect_type=StatusEffectType.DOT,
            family=StatusEffectFamily.BURN,
            duration=1,
            dot_damage_type=DamageType.FIRE,
            dot_ability_damage_mult=1.0,
            dot_bonus_damage=0,
            dot_ap_percent=1.0,  # 100% armor piercing
            dot_diminishing=False
        )

        initial_hp = battle_unit.current_hp
        initial_armor = battle_unit.current_armor

        status = ActiveStatusEffect(
            effect=dot_effect,
            remaining_turns=1,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)

        # Apply DOT with 100% AP
        DOTHandler.apply_dot_to_unit(battle_unit)

        # Armor should be unchanged, HP should be reduced
        assert battle_unit.current_armor == initial_armor
        assert battle_unit.current_hp < initial_hp


class TestStatusEffectDecay:
    """Tests for status effect duration decay."""

    def test_decay_single_effect(self, battle_unit, diminishing_dot_effect):
        """Test decaying a single status effect."""
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )
        battle_unit.status_effects.append(status)

        # Decay once
        DOTHandler.decay_status_effects(battle_unit)
        assert len(battle_unit.status_effects) == 1
        assert battle_unit.status_effects[0].remaining_turns == 2

        # Decay again
        DOTHandler.decay_status_effects(battle_unit)
        assert len(battle_unit.status_effects) == 1
        assert battle_unit.status_effects[0].remaining_turns == 1

        # Decay final time - should be removed
        DOTHandler.decay_status_effects(battle_unit)
        assert len(battle_unit.status_effects) == 0

    def test_decay_multiple_effects(self, battle_unit, diminishing_dot_effect, constant_dot_effect):
        """Test decaying multiple status effects with different durations."""
        status1 = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=2,
            base_dot_damage=100.0
        )
        status2 = ActiveStatusEffect(
            effect=constant_dot_effect,
            remaining_turns=3,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.extend([status1, status2])

        # First decay
        DOTHandler.decay_status_effects(battle_unit)
        assert len(battle_unit.status_effects) == 2
        assert battle_unit.status_effects[0].remaining_turns == 1
        assert battle_unit.status_effects[1].remaining_turns == 2

        # Second decay - first effect should be removed
        DOTHandler.decay_status_effects(battle_unit)
        assert len(battle_unit.status_effects) == 1
        assert battle_unit.status_effects[0].remaining_turns == 1

        # Third decay - all effects removed
        DOTHandler.decay_status_effects(battle_unit)
        assert len(battle_unit.status_effects) == 0


class TestDifferentDamageTypes:
    """Tests for DOT with different damage types."""

    def test_fire_damage_type(self, battle_unit):
        """Test DOT with fire damage type."""
        fire_dot = StatusEffect(
            id=4,
            effect_type=StatusEffectType.DOT,
            family=StatusEffectFamily.BURN,
            duration=1,
            dot_damage_type=DamageType.FIRE,
            dot_ability_damage_mult=1.0,
            dot_bonus_damage=0,
            dot_ap_percent=0.0,
            dot_diminishing=False
        )

        initial_hp = battle_unit.current_hp

        status = ActiveStatusEffect(
            effect=fire_dot,
            remaining_turns=1,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)

        DOTHandler.apply_dot_to_unit(battle_unit)

        # Damage should be applied
        assert battle_unit.current_hp < initial_hp or battle_unit.current_armor < battle_unit.template.stats.armor_hp

    def test_cold_damage_type(self, battle_unit):
        """Test DOT with cold damage type."""
        cold_dot = StatusEffect(
            id=5,
            effect_type=StatusEffectType.DOT,
            family=StatusEffectFamily.FREEZE,
            duration=1,
            dot_damage_type=DamageType.COLD,
            dot_ability_damage_mult=1.0,
            dot_bonus_damage=0,
            dot_ap_percent=0.0,
            dot_diminishing=False
        )

        initial_hp = battle_unit.current_hp

        status = ActiveStatusEffect(
            effect=cold_dot,
            remaining_turns=1,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)

        DOTHandler.apply_dot_to_unit(battle_unit)

        # Damage should be applied
        assert battle_unit.current_hp < initial_hp or battle_unit.current_armor < battle_unit.template.stats.armor_hp
