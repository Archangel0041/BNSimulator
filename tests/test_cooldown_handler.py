"""Tests for Cooldown Handler."""
import pytest

from src.simulator.battle import BattleUnit, ActiveStatusEffect, BattleState
from src.simulator.battle_engine.cooldown_handler import CooldownHandler
from src.simulator.models import (
    Position, UnitTemplate, UnitStats, StatusEffect
)
from src.simulator.enums import (
    Side, UnitClass, BattleSide,
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
def stun_effect(data_loader):
    """Get a stun status effect from config (ID 39 - 1 turn stun with block_action)."""
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


class TestIsUnitStunned:
    """Tests for checking if a unit is stunned."""

    def test_unit_not_stunned(self, battle_unit):
        """Test that a unit with no status effects is not stunned."""
        assert not CooldownHandler.is_unit_stunned(battle_unit)

    def test_unit_with_dot_not_stunned(self, battle_unit, data_loader):
        """Test that a unit with only DOT effects is not stunned."""
        dot_effect = data_loader.status_effects[9]  # DOT effect
        status = ActiveStatusEffect(
            effect=dot_effect,
            remaining_turns=3,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(status)
        
        assert not CooldownHandler.is_unit_stunned(battle_unit)

    def test_unit_with_stun_effect_is_stunned(self, battle_unit, stun_effect):
        """Test that a unit with a stun effect that blocks action is stunned."""
        status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=1,
            base_dot_damage=0.0
        )
        battle_unit.status_effects.append(status)
        
        assert CooldownHandler.is_unit_stunned(battle_unit)

    def test_unit_with_non_blocking_stun_not_stunned(self, battle_unit, data_loader):
        """Test that a unit with a stun effect that doesn't block action is not stunned."""
        # Use stun effect ID 22 which has stun_block_action=False
        stun_effect = data_loader.status_effects[22]
        status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=2,
            base_dot_damage=0.0
        )
        battle_unit.status_effects.append(status)
        
        assert not CooldownHandler.is_unit_stunned(battle_unit)

    def test_unit_with_multiple_effects_stunned(self, battle_unit, data_loader, stun_effect):
        """Test that a unit with multiple effects including a blocking stun is stunned."""
        # Add a DOT effect
        dot_effect = data_loader.status_effects[9]
        dot_status = ActiveStatusEffect(
            effect=dot_effect,
            remaining_turns=3,
            base_dot_damage=50.0
        )
        battle_unit.status_effects.append(dot_status)
        
        # Add a stun effect
        stun_status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=1,
            base_dot_damage=0.0
        )
        battle_unit.status_effects.append(stun_status)
        
        assert CooldownHandler.is_unit_stunned(battle_unit)


class TestReduceUnitCooldowns:
    """Tests for reducing cooldowns on a single unit."""

    def test_reduce_weapon_cooldowns(self, battle_unit):
        """Test that weapon cooldowns are reduced for non-stunned units."""
        # Set up cooldowns
        battle_unit.weapon_cooldowns[0] = 3
        battle_unit.weapon_cooldowns[1] = 2
        battle_unit.global_cooldown = 1
        
        CooldownHandler.reduce_unit_cooldowns(battle_unit)
        
        # Cooldowns should be reduced by 1
        assert battle_unit.weapon_cooldowns[0] == 2
        assert battle_unit.weapon_cooldowns[1] == 1
        assert battle_unit.global_cooldown == 0

    def test_cooldown_removed_when_reaches_zero(self, battle_unit):
        """Test that cooldowns are removed from dict when they reach 0."""
        # Set up cooldown at 1 (should be removed after reduction)
        battle_unit.weapon_cooldowns[0] = 1
        
        CooldownHandler.reduce_unit_cooldowns(battle_unit)
        
        # Cooldown should be removed from dict
        assert 0 not in battle_unit.weapon_cooldowns
        assert len(battle_unit.weapon_cooldowns) == 0

    def test_stunned_units_dont_reduce_cooldowns(self, battle_unit, stun_effect):
        """Test that stunned units do not have their cooldowns reduced."""
        # Set up cooldowns
        battle_unit.weapon_cooldowns[0] = 3
        battle_unit.global_cooldown = 2
        
        # Add stun effect
        stun_status = ActiveStatusEffect(
            effect=stun_effect,
            remaining_turns=2,
            base_dot_damage=0.0
        )
        battle_unit.status_effects.append(stun_status)
        
        CooldownHandler.reduce_unit_cooldowns(battle_unit)
        
        # Cooldowns should NOT be reduced (unit is stunned)
        assert battle_unit.weapon_cooldowns[0] == 3
        assert battle_unit.global_cooldown == 2

    def test_reduce_multiple_weapon_cooldowns(self, battle_unit):
        """Test reducing multiple weapon cooldowns."""
        battle_unit.weapon_cooldowns[0] = 5
        battle_unit.weapon_cooldowns[1] = 3
        battle_unit.weapon_cooldowns[2] = 1
        battle_unit.global_cooldown = 2
        
        CooldownHandler.reduce_unit_cooldowns(battle_unit)
        
        assert battle_unit.weapon_cooldowns[0] == 4
        assert battle_unit.weapon_cooldowns[1] == 2
        assert 2 not in battle_unit.weapon_cooldowns  # Removed when reached 0
        assert battle_unit.global_cooldown == 1

    def test_global_cooldown_at_zero_stays_zero(self, battle_unit):
        """Test that global cooldown at 0 stays at 0."""
        battle_unit.global_cooldown = 0
        battle_unit.weapon_cooldowns[0] = 2
        
        CooldownHandler.reduce_unit_cooldowns(battle_unit)
        
        assert battle_unit.global_cooldown == 0
        assert battle_unit.weapon_cooldowns[0] == 1

    def test_no_cooldowns_to_reduce(self, battle_unit):
        """Test reducing cooldowns when unit has none."""
        assert len(battle_unit.weapon_cooldowns) == 0
        assert battle_unit.global_cooldown == 0
        
        CooldownHandler.reduce_unit_cooldowns(battle_unit)
        
        # Should not error, cooldowns remain at 0
        assert len(battle_unit.weapon_cooldowns) == 0
        assert battle_unit.global_cooldown == 0


class TestReduceCooldownsForSide:
    """Tests for reducing cooldowns for all units on a side."""

    def test_reduce_player_cooldowns(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test reducing cooldowns for player units."""
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
        
        unit1.weapon_cooldowns[0] = 2
        unit1.global_cooldown = 1
        unit2.weapon_cooldowns[0] = 3
        unit2.global_cooldown = 2
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit1, unit2],
            enemy_units=[],
            player_is_attacker=True
        )
        
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.PLAYER_TEAM)
        
        # Get units from battle state (deep copies)
        battle_units = list(battle.player_units.values())
        battle_unit1 = battle_units[0]
        battle_unit2 = battle_units[1]
        
        # Both units should have cooldowns reduced
        assert battle_unit1.weapon_cooldowns[0] == 1
        assert battle_unit1.global_cooldown == 0
        assert battle_unit2.weapon_cooldowns[0] == 2
        assert battle_unit2.global_cooldown == 1

    def test_reduce_enemy_cooldowns(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test reducing cooldowns for enemy units."""
        unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        unit.weapon_cooldowns[0] = 2
        unit.global_cooldown = 1
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[unit],
            player_is_attacker=True
        )
        
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.ENEMY_TEAM)
        
        # Get the unit from battle state (deep copy)
        battle_unit = next(iter(battle.enemy_units.values()))
        
        # Cooldowns should be reduced
        assert battle_unit.weapon_cooldowns[0] == 1
        assert battle_unit.global_cooldown == 0

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
        
        unit1.weapon_cooldowns[0] = 2
        unit1.global_cooldown = 1
        
        unit2.weapon_cooldowns[0] = 2
        unit2.global_cooldown = 1
        
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
        
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.PLAYER_TEAM)
        
        # Get units from battle state (deep copies)
        # Find unit1 and unit2 by position
        battle_unit1 = battle.player_units.get(Position(0, 0))
        battle_unit2 = battle.player_units.get(Position(1, 0))
        
        # Unit1 (not stunned) should have cooldowns reduced
        assert battle_unit1.weapon_cooldowns[0] == 1
        assert battle_unit1.global_cooldown == 0
        
        # Unit2 (stunned) should NOT have cooldowns reduced
        assert battle_unit2.weapon_cooldowns[0] == 2
        assert battle_unit2.global_cooldown == 1

    def test_empty_side_no_error(self, mock_data_loader, mock_layout):
        """Test that reducing cooldowns for an empty side doesn't error."""
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[],
            player_is_attacker=True
        )
        
        # Should not raise an error
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.PLAYER_TEAM)
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.ENEMY_TEAM)
        
        assert len(battle.player_units) == 0
        assert len(battle.enemy_units) == 0

    def test_multiple_reductions(self, basic_unit_template, mock_data_loader, mock_layout):
        """Test that multiple reductions work correctly."""
        unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        unit.weapon_cooldowns[0] = 5
        unit.global_cooldown = 3
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[unit],
            enemy_units=[],
            player_is_attacker=True
        )
        
        # Reduce 3 times
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.PLAYER_TEAM)
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.PLAYER_TEAM)
        CooldownHandler.reduce_cooldowns_for_side(battle, BattleSide.PLAYER_TEAM)
        
        battle_unit = next(iter(battle.player_units.values()))
        
        assert battle_unit.weapon_cooldowns[0] == 2
        assert battle_unit.global_cooldown == 0

