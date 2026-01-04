"""Tests for Status Effect Handler."""
import pytest

from src.simulator.battle import BattleUnit, ActiveStatusEffect, BattleState
from src.simulator.battle_engine.status_effect_handler import StatusEffectHandler
from src.simulator.battle_engine.player_turn_executor import PlayerTurnExecutor
from src.simulator.battle_engine.enemy_turn_executor import EnemyTurnExecutor
from src.simulator.models import (
    Position, UnitTemplate, UnitStats, StatusEffect
)
from src.simulator.enums import (
    Side, UnitClass, DamageType, BattleSide,
    StatusEffectType, StatusEffectFamily
)
from src.simulator.data_loader import GameDataLoader
from unittest.mock import Mock


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
def data_loader():
    """Create a real data loader with the test data."""
    loader = GameDataLoader("data")
    loader.load_all()
    return loader


@pytest.fixture
def diminishing_dot_effect(data_loader):
    """Get a diminishing DOT status effect from config (ID 9 - duration 3, family 5 FIRE)."""
    # ID 9: duration 3, diminishing, family 5 (FIRE), damage_type 5 (FIRE)
    return data_loader.status_effects[9]


@pytest.fixture
def constant_dot_effect(data_loader):
    """Get a constant DOT status effect from config (ID 11 - non-diminishing, duration 6)."""
    # ID 11: duration 6, non-diminishing, family 5 (FIRE), damage_type 5 (FIRE)
    return data_loader.status_effects[11]


@pytest.fixture
def stun_effect(data_loader):
    """Get a stun status effect from config (ID 39 - 1 turn stun with block_action)."""
    # ID 39: duration 1, stun_block_action=true, stun_block_movement=true, family 1 (BLEED/STUN)
    return data_loader.status_effects[39]


@pytest.fixture
def mock_data_loader():
    """Create a mock data loader."""
    loader = Mock(spec=GameDataLoader)
    return loader


@pytest.fixture
def mock_layout():
    """Create a mock grid layout."""
    from src.simulator.models import GridLayout
    layout = Mock(spec=GridLayout)
    layout.width = 5
    layout.height = 3
    return layout


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
        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        # Turn 2: remaining_turns=2, should be 66.67% (2/3)
        damage_turn_2 = StatusEffectHandler.calculate_dot_damage(status)
        assert abs(damage_turn_2 - 66.67) < 0.1
        status.remaining_turns -= 1

        # Turn 3: remaining_turns=1, should be 33.33% (1/3)
        damage_turn_3 = StatusEffectHandler.calculate_dot_damage(status)
        assert abs(damage_turn_3 - 33.33) < 0.1

    def test_constant_dot_full_duration(self, constant_dot_effect):
        """Test constant DOT stays same over duration."""
        # 100 base damage, 6-turn duration (ID 11 has duration 6)
        status = ActiveStatusEffect(
            effect=constant_dot_effect,
            remaining_turns=6,
            base_dot_damage=100.0
        )

        # All turns should be 100 damage (non-diminishing)
        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0

    def test_diminishing_dot_with_duration_4(self, data_loader):
        """Test diminishing DOT with duration=4."""
        # Use effect ID 7 from config: duration 4, diminishing, family 7 (ACID), damage_type 6 (TORPEDO)
        effect_4 = data_loader.status_effects[7]
        status = ActiveStatusEffect(
            effect=effect_4,
            remaining_turns=4,
            base_dot_damage=100.0
        )

        # Turn 1: 4/4 = 100%
        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        # Turn 2: 3/4 = 75%
        assert StatusEffectHandler.calculate_dot_damage(status) == 75.0
        status.remaining_turns -= 1

        # Turn 3: 2/4 = 50%
        assert StatusEffectHandler.calculate_dot_damage(status) == 50.0
        status.remaining_turns -= 1

        # Turn 4: 1/4 = 25%
        assert StatusEffectHandler.calculate_dot_damage(status) == 25.0

    def test_diminishing_dot_with_duration_5(self, data_loader):
        """Test diminishing DOT with duration=5."""
        # Use effect ID 10 which has duration 5
        effect_5 = data_loader.status_effects[10]
        status = ActiveStatusEffect(
            effect=effect_5,
            remaining_turns=5,
            base_dot_damage=100.0
        )

        # Turn 1: 5/5 = 100%
        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0
        status.remaining_turns -= 1

        # Turn 2: 4/5 = 80%
        assert StatusEffectHandler.calculate_dot_damage(status) == 80.0
        status.remaining_turns -= 1

        # Turn 3: 3/5 = 60%
        assert StatusEffectHandler.calculate_dot_damage(status) == 60.0
        status.remaining_turns -= 1

        # Turn 4: 2/5 = 40%
        assert StatusEffectHandler.calculate_dot_damage(status) == 40.0
        status.remaining_turns -= 1

        # Turn 5: 1/5 = 20%
        assert StatusEffectHandler.calculate_dot_damage(status) == 20.0

    def test_zero_duration_dot(self, diminishing_dot_effect):
        """Test DOT with duration=0 uses constant damage."""
        # Create a copy with duration 0
        from dataclasses import replace
        effect_0 = replace(diminishing_dot_effect, duration=0)
        status = ActiveStatusEffect(
            effect=effect_0,
            remaining_turns=1,
            base_dot_damage=100.0
        )

        # Should fall back to constant damage
        assert StatusEffectHandler.calculate_dot_damage(status) == 100.0


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
        StatusEffectHandler.apply_dot_to_unit(battle_unit)

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
        StatusEffectHandler.apply_dot_to_unit(battle_unit)

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
        StatusEffectHandler.apply_dot_to_unit(battle_unit)

        # Armor should be reduced (fire damage with 0 AP goes to armor first)
        assert battle_unit.current_armor < initial_armor or battle_unit.current_hp < initial_hp

    def test_apply_dot_with_armor_piercing(self, battle_unit, data_loader):
        """Test DOT with armor piercing bypasses armor."""
        # Use effect ID 1 which has 80% AP (0.8), but we'll create a copy with 100% AP
        # ID 1: duration 2, diminishing, 80% AP, family 9 (BURN), damage_type 5 (FIRE)
        from dataclasses import replace
        base_effect = data_loader.status_effects[1]
        dot_effect = replace(base_effect, dot_ap_percent=1.0)  # 100% armor piercing

        initial_hp = battle_unit.current_hp
        initial_armor = battle_unit.current_armor

        status = ActiveStatusEffect(
            effect=dot_effect,
            remaining_turns=1,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)

        # Apply DOT with 100% AP
        StatusEffectHandler.apply_dot_to_unit(battle_unit)

        # Armor should be unchanged, HP should be reduced
        assert battle_unit.current_armor == initial_armor
        assert battle_unit.current_hp < initial_hp


class TestStatusEffectDecay:
    """Tests for status effect duration decay."""

    def test_decay_dot_effects_only(self, battle_unit, diminishing_dot_effect, stun_effect):
        """Test that decay_dot_effects only decays DOT effects, not stun effects."""
        dot_status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )
        stun_status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=2,
            base_dot_damage=0.0
        )
        battle_unit.status_effects.extend([dot_status, stun_status])

        # Decay DOT effects only
        StatusEffectHandler.decay_dot_effects(battle_unit)
        
        # DOT should be decayed, stun should remain unchanged
        assert len(battle_unit.status_effects) == 2
        dot_remaining = next(s for s in battle_unit.status_effects if s.effect.effect_type == StatusEffectType.DOT)
        stun_remaining = next(s for s in battle_unit.status_effects if s.effect.effect_type == StatusEffectType.STUN)
        assert dot_remaining.remaining_turns == 2
        assert stun_remaining.remaining_turns == 2  # Unchanged

    def test_decay_stun_effects_only(self, battle_unit, diminishing_dot_effect, stun_effect):
        """Test that decay_stun_effects only decays stun effects, not DOT effects."""
        dot_status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )
        stun_status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=2,
            base_dot_damage=0.0
        )
        battle_unit.status_effects.extend([dot_status, stun_status])

        # Decay stun effects only
        StatusEffectHandler.decay_stun_effects(battle_unit)
        
        # Stun should be decayed, DOT should remain unchanged
        assert len(battle_unit.status_effects) == 2
        dot_remaining = next(s for s in battle_unit.status_effects if s.effect.effect_type == StatusEffectType.DOT)
        stun_remaining = next(s for s in battle_unit.status_effects if s.effect.effect_type == StatusEffectType.STUN)
        assert dot_remaining.remaining_turns == 3  # Unchanged
        assert stun_remaining.remaining_turns == 1

    def test_decay_single_effect(self, battle_unit, diminishing_dot_effect):
        """Test decaying a single status effect."""
        status = ActiveStatusEffect(
            effect=diminishing_dot_effect,
            remaining_turns=3,
            base_dot_damage=100.0
        )
        battle_unit.status_effects.append(status)

        # Decay once
        StatusEffectHandler.decay_dot_effects(battle_unit)
        assert len(battle_unit.status_effects) == 1
        assert battle_unit.status_effects[0].remaining_turns == 2

        # Decay again
        StatusEffectHandler.decay_dot_effects(battle_unit)
        assert len(battle_unit.status_effects) == 1
        assert battle_unit.status_effects[0].remaining_turns == 1

        # Decay final time - should be removed
        StatusEffectHandler.decay_dot_effects(battle_unit)
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
        StatusEffectHandler.decay_dot_effects(battle_unit)
        assert len(battle_unit.status_effects) == 2
        assert battle_unit.status_effects[0].remaining_turns == 1
        assert battle_unit.status_effects[1].remaining_turns == 2

        # Second decay - first effect should be removed
        StatusEffectHandler.decay_dot_effects(battle_unit)
        assert len(battle_unit.status_effects) == 1
        assert battle_unit.status_effects[0].remaining_turns == 1

        # Third decay - all effects removed
        StatusEffectHandler.decay_dot_effects(battle_unit)
        assert len(battle_unit.status_effects) == 0


class TestDifferentDamageTypes:
    """Tests for DOT with different damage types."""

    def test_generic_damage_type(self, battle_unit, data_loader):
        """Test DOT with generic damage type."""
        # Use effect ID 2: duration 1, diminishing, family 9 (BURN), damage_type 5 (FIRE)
        dot_effect = data_loader.status_effects[2]

        initial_hp = battle_unit.current_hp

        status = ActiveStatusEffect(
            effect=dot_effect,
            remaining_turns=1,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)

        StatusEffectHandler.apply_dot_to_unit(battle_unit)

        # Damage should be applied
        assert battle_unit.current_hp < initial_hp or battle_unit.current_armor < battle_unit.template.stats.armor_hp


class TestCooldownReduction:
    """Tests for cooldown reduction functionality."""

    def test_reduce_ability_cooldowns(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test that ability cooldowns are reduced for non-stunned units."""
        unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Set up cooldowns (using ability IDs)
        unit.ability_cooldowns[1] = 3
        unit.ability_cooldowns[2] = 2
        unit.global_cooldowns[0] = 1  # weapon_id 0
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_reduce_player_cooldowns()
        
        # Get the unit from battle state (deep copy)
        battle_unit = next(iter(battle.player_units.values()))
        
        # Cooldowns should be reduced by 1
        assert battle_unit.ability_cooldowns[1] == 2
        assert battle_unit.ability_cooldowns[2] == 1
        assert battle_unit.global_cooldowns.get(0, 0) == 0

    def test_cooldown_removed_when_reaches_zero(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test that cooldowns are removed from dict when they reach 0."""
        unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Set up cooldown at 1 (should be removed after reduction)
        unit.ability_cooldowns[1] = 1
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_reduce_player_cooldowns()
        
        # Get the unit from battle state (deep copy)
        battle_unit = next(iter(battle.player_units.values()))
        
        # Cooldown should be removed from dict
        assert 1 not in battle_unit.ability_cooldowns
        assert len(battle_unit.ability_cooldowns) == 0

    def test_stunned_units_dont_reduce_cooldowns(self, basic_unit_template, mock_data_loader, mock_layout, stun_effect):
        """Test that stunned units do not have their cooldowns reduced."""
        unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Set up cooldowns
        unit.ability_cooldowns[1] = 3
        unit.global_cooldowns[0] = 2
        
        # Add stun effect
        stun_status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=2,
            base_dot_damage=0.0
        )
        unit.status_effects.append(stun_status)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_reduce_player_cooldowns()
        
        # Get the unit from battle state (deep copy)
        battle_unit = next(iter(battle.player_units.values()))
        
        # Cooldowns should NOT be reduced (unit is stunned)
        assert battle_unit.ability_cooldowns[1] == 3
        assert battle_unit.global_cooldowns.get(0, 0) == 2

    def test_reduce_enemy_cooldowns(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test reducing cooldowns for enemy units."""
        unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        # Set up cooldowns
        unit.ability_cooldowns[1] = 2
        unit.global_cooldowns[0] = 1
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[unit],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_reduce_enemy_cooldowns()
        
        # Get the unit from battle state (deep copy)
        battle_unit = next(iter(battle.enemy_units.values()))
        
        # Cooldowns should be reduced
        assert battle_unit.ability_cooldowns[1] == 1
        assert battle_unit.global_cooldowns.get(0, 0) == 0

    def test_reduce_multiple_units_cooldowns(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test reducing cooldowns for multiple units."""
        unit1 = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        unit2 = BattleUnit(
            template=basic_unit_template,
            position=Position(1, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        unit1.ability_cooldowns[1] = 2
        unit1.global_cooldowns[0] = 1  # weapon_id 0
        unit2.ability_cooldowns[1] = 3
        unit2.global_cooldowns[0] = 2  # weapon_id 0
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit1, unit2],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_reduce_player_cooldowns()
        
        # Get units from battle state (deep copies)
        battle_units = list(battle.player_units.values())
        battle_unit1 = battle_units[0]
        battle_unit2 = battle_units[1]
        
        # Both units should have cooldowns reduced
        assert battle_unit1.ability_cooldowns[1] == 1
        assert battle_unit1.global_cooldowns.get(0, 0) == 0
        assert battle_unit2.ability_cooldowns[1] == 2
        assert battle_unit2.global_cooldowns.get(0, 0) == 1

    def test_mixed_stunned_and_non_stunned_units(self, basic_unit_template, mock_data_loader, mock_layout, stun_effect):
        """Test cooldown reduction with mix of stunned and non-stunned units."""
        unit1 = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        unit2 = BattleUnit(
            template=basic_unit_template,
            position=Position(1, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        unit1.ability_cooldowns[1] = 2
        unit1.global_cooldowns[0] = 1  # weapon_id 0
        
        unit2.ability_cooldowns[1] = 2
        unit2.global_cooldowns[0] = 1  # weapon_id 0
        
        # Stun unit2
        stun_status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=1,
            base_dot_damage=0.0
        )
        unit2.status_effects.append(stun_status)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit1, unit2],
            enemy_units=[],
            player_is_attacker=True
        )
        
        executor = PlayerTurnExecutor(battle)
        executor._step_reduce_player_cooldowns()
        
        # Get units from battle state (deep copies)
        # Find unit1 and unit2 by position
        battle_unit1 = battle.player_units.get(Position(0, 0))
        battle_unit2 = battle.player_units.get(Position(1, 0))
        
        # Unit1 (not stunned) should have cooldowns reduced
        assert battle_unit1.ability_cooldowns[1] == 1
        assert battle_unit1.global_cooldowns.get(0, 0) == 0
        
        # Unit2 (stunned) should NOT have cooldowns reduced
        assert battle_unit2.ability_cooldowns[1] == 2
        assert battle_unit2.global_cooldowns.get(0, 0) == 1

