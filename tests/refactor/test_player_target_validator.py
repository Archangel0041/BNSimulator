"""Tests for Player Target Validator."""
import pytest
from unittest.mock import Mock

from src.simulator.battle import BattleUnit, BattleState, Action
from src.simulator.battle_engine.player_target_validator import PlayerTargetValidator
from src.simulator.models import (
    Position, UnitTemplate, UnitStats, Ability, AbilityStats,
    TargetArea, DamageArea, Weapon, WeaponStats
)
from src.simulator.enums import (
    Side, UnitClass, BattleSide, TargetType, LineOfFire,
    AttackDirection, UnitBlocking, DamageType
)
from src.simulator.data_loader import GameDataLoader


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
        bravery=5,
        blocking=UnitBlocking.NONE
    )
    return UnitTemplate(
        id=1,
        name="Test Unit",
        class_type=UnitClass.SOLDIER,
        side=Side.PLAYER,
        stats=stats,
        weapons={}
    )


@pytest.fixture
def blocking_unit_template():
    """Create a unit template with Full blocking."""
    stats = UnitStats(
        hp=100,
        armor_hp=50,
        defense=5,
        dodge=10,
        accuracy=10,
        critical=5.0,
        power=10,
        bravery=5,
        blocking=UnitBlocking.FULL
    )
    return UnitTemplate(
        id=2,
        name="Blocking Unit",
        class_type=UnitClass.SOLDIER,
        side=Side.PLAYER,
        stats=stats,
        weapons={}
    )


@pytest.fixture
def mock_data_loader():
    """Create a mock data loader."""
    loader = Mock(spec=GameDataLoader)
    loader.config = Mock()
    loader.config.tag_hierarchy = {}
    return loader


@pytest.fixture
def mock_layout():
    """Create a mock grid layout."""
    from src.simulator.models import GridLayout
    layout = Mock(spec=GridLayout)
    layout.width = 5
    layout.height = 3
    return layout


@pytest.fixture
def basic_ability():
    """Create a basic ability for testing."""
    stats = AbilityStats(
        min_range=1,
        max_range=5,
        line_of_fire=LineOfFire.INDIRECT,
        attack_direction=AttackDirection.FORWARD
    )
    return Ability(
        id=1,
        name="Test Ability",
        stats=stats
    )


class TestRangeCalculation:
    """Tests for range distance calculation."""

    def test_same_row_range_one(self, mock_data_loader, mock_layout):
        """Test range calculation for same row (cross-grid distance is 1)."""
        attacker_pos = Position(0, 0)
        target_pos = Position(2, 0)
        
        # Create minimal battle state for range calculation
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[],
            player_is_attacker=True
        )
        
        distance = PlayerTargetValidator._calculate_range_distance(
            attacker_pos, target_pos, AttackDirection.FORWARD, battle
        )
        # Cross-grid attacks: even same row (y=0 to y=0) has distance 1 (crossing the gap)
        assert distance == 1

    def test_adjacent_row_range_two(self, mock_data_loader, mock_layout):
        """Test range calculation for adjacent rows (cross-grid)."""
        attacker_pos = Position(0, 0)
        target_pos = Position(0, 1)
        
        # Create minimal battle state for range calculation
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[],
            player_is_attacker=True
        )
        
        distance = PlayerTargetValidator._calculate_range_distance(
            attacker_pos, target_pos, AttackDirection.FORWARD, battle
        )
        # Cross-grid: attacker at row 0, target at row 1 = 0 + 1 + 1 = 2
        assert distance == 2

    def test_multiple_rows_range(self, mock_data_loader, mock_layout):
        """Test range calculation for multiple rows (cross-grid)."""
        attacker_pos = Position(0, 0)
        target_pos = Position(0, 3)
        
        # Create minimal battle state for range calculation
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[],
            player_is_attacker=True
        )
        
        distance = PlayerTargetValidator._calculate_range_distance(
            attacker_pos, target_pos, AttackDirection.FORWARD, battle
        )
        # Cross-grid: attacker at row 0, target at row 3 = 0 + 3 + 1 = 4
        assert distance == 4

    def test_range_symmetric(self, mock_data_loader, mock_layout):
        """Test that range is symmetric."""
        attacker_pos = Position(0, 0)
        target_pos = Position(0, 2)
        
        # Create minimal battle state for range calculation
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[],
            enemy_units=[],
            player_is_attacker=True
        )
        
        distance1 = PlayerTargetValidator._calculate_range_distance(
            attacker_pos, target_pos, AttackDirection.FORWARD, battle
        )
        distance2 = PlayerTargetValidator._calculate_range_distance(
            target_pos, attacker_pos, AttackDirection.FORWARD, battle
        )
        assert distance1 == distance2


class TestTargetTypeValidation:
    """Tests for different target type validations."""

    def test_target_type_none_requires_alive_unit(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that target type NONE requires an alive unit at target position."""
        # Create attacker
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Create target
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        # Create ability with target_type NONE
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        # Add weapon to attacker
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        # Should be valid with alive unit
        assert PlayerTargetValidator.is_action_valid(action, battle) is True
        
        # Should be invalid with dead unit - modify the unit in battle state
        battle_unit = battle.enemy_units.get(Position(0, 1))
        if battle_unit:
            battle_unit.current_hp = 0
        assert PlayerTargetValidator.is_action_valid(action, battle) is False
        
        # Should be invalid with no unit
        battle.enemy_units.clear()
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_target_type_weapon_validates_all_positions(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that target type WEAPON validates all positions in pattern."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        # Create ability with target_type WEAPON and pattern
        target_area = TargetArea(
            target_type=TargetType.WEAPON,
            data=[
                DamageArea(pos=Position(0, 0), damage_percent=100.0),
                DamageArea(pos=Position(1, 0), damage_percent=50.0)
            ]
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                target_area=target_area
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        # Should validate all positions in pattern
        assert PlayerTargetValidator.is_action_valid(action, battle) is True

    def test_target_type_target_reticle_based(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that target type TARGET works for reticle-based attacks."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        target_area = TargetArea(
            target_type=TargetType.TARGET,
            data=[DamageArea(pos=Position(0, 0), damage_percent=100.0)]
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                target_area=target_area
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is True


class TestLineOfFire:
    """Tests for line of fire validation."""

    def test_indirect_ignores_blocking(
        self, basic_unit_template, blocking_unit_template, mock_data_loader, mock_layout
    ):
        """Test that Indirect line of fire ignores blocking."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        blocker = BattleUnit(
            template=blocking_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker, blocker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 2)
        )
        
        # Indirect should ignore blocking
        assert PlayerTargetValidator.is_action_valid(action, battle) is True

    def test_contact_only_first_target(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that Contact line of fire only hits first target."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        first_target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        second_target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.CONTACT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[first_target, second_target],
            player_is_attacker=True
        )
        
        # First target should be valid
        action1 = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        assert PlayerTargetValidator.is_action_valid(action1, battle) is True
        
        # Second target should be blocked
        action2 = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 2)
        )
        assert PlayerTargetValidator.is_action_valid(action2, battle) is False

    def test_direct_past_none_blocking(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that Direct can hit past units with None blocking."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Unit with None blocking
        blocker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.DIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker, blocker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 2)
        )
        
        # Direct should allow hitting past None blocking
        assert PlayerTargetValidator.is_action_valid(action, battle) is True

    def test_precise_blocked_by_full(
        self, basic_unit_template, blocking_unit_template, mock_data_loader, mock_layout
    ):
        """Test that Precise is blocked by Full blocking."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Blocker should be on enemy side, in front of target (y=1 < y=2)
        blocker = BattleUnit(
            template=blocking_unit_template,
            position=Position(0, 1),  # Enemy side, in front of target
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.PRECISE
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[blocker, target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 2)
        )
        
        # Precise should be blocked by Full blocking
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_attacker_side_blocker_does_not_block(
        self, basic_unit_template, blocking_unit_template, mock_data_loader, mock_layout
    ):
        """Test that a blocker on the attacker's side does not block the ability."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Blocker on player side (same side as attacker) with FULL blocking
        blocker = BattleUnit(
            template=blocking_unit_template,
            position=Position(0, 1),  # Player side, behind attacker
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.PRECISE
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker, blocker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 2)
        )
        
        # Blocker on attacker's side should NOT block the ability
        # Only enemy-side blockers can block
        assert PlayerTargetValidator.is_action_valid(action, battle) is True


class TestRangeValidation:
    """Tests for range validation."""

    def test_range_too_short(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that targets out of range are invalid."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),  # Same row (range 1 for cross-grid)
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=2,  # Requires at least range 2 (same row is range 1)
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 0)
        )
        
        # Range is 1 (0+0+1), but min_range is 2, so should be invalid
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_range_too_long(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that targets beyond max range are invalid."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 6),  # Range 6
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,  # Max range 5
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 6)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_range_valid(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that targets within range are valid."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),  # Range 2
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 2)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is True


class TestAttackDirection:
    """Tests for attack direction handling."""

    def test_backward_attack_direction(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that Backward attack direction uses back-most row."""
        # Attacker on front row
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        # Another unit on back row
        back_unit = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 2),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                attack_direction=AttackDirection.BACKWARD
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker, back_unit],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        # Backward attack should use back-most row (y=2) for range calculation
        # From y=2 to y=1 is range 1, which is valid
        assert PlayerTargetValidator.is_action_valid(action, battle) is True


class TestCooldownAndAmmo:
    """Tests for cooldown and ammo validation."""

    def test_weapon_cooldown_blocks_action(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that weapon cooldown blocks action."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Set ability on cooldown (ability_id 1) - modify the unit in battle state
        battle_unit = battle.player_units.get(Position(0, 0))
        if battle_unit:
            battle_unit.ability_cooldowns[1] = 2
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_global_cooldown_blocks_action(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that global cooldown blocks action."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Set weapon-specific global cooldown - modify the unit in battle state
        battle_unit = battle.player_units.get(Position(0, 0))
        if battle_unit:
            battle_unit.global_cooldowns[1] = 1
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_insufficient_ammo_blocks_action(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that insufficient ammo blocks action."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                ammo_required=1  # Requires 1 ammo per use
            )
        )
        
        weapon = Weapon(
            id=1,
            name="Test Weapon",
            abilities=[1],
            stats=WeaponStats(ammo=5)  # Limited ammo
        )
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Set ammo to 0 - modify the unit in battle state
        # With ammo_required=1, having 0 ammo should block the action
        battle_unit = battle.player_units.get(Position(0, 0))
        if battle_unit:
            battle_unit.ammo[1] = 0
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is False

    def test_unlimited_ammo_allows_action(
        self, basic_unit_template, mock_data_loader, mock_layout, basic_ability
    ):
        """Test that unlimited ammo (-1) allows action even with 0 ammo."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT
            )
        )
        
        weapon = Weapon(
            id=1,
            name="Test Weapon",
            abilities=[1],
            stats=WeaponStats(ammo=-1)  # Unlimited ammo
        )
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Ammo is 0 but weapon has unlimited ammo
        attacker.ammo[1] = 0
        
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is True


class TestChargeTime:
    """Tests for charge time (prep time) validation."""

    def test_charge_time_blocks_first_turn(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that charge_time blocks action on first turn."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM,
            turn_entered_field=0
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                charge_time=1  # Needs 1 turn prep time
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Turn 0, entered at turn 0, charge_time 1 -> can't use
        battle.turn_number = 0
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is False
        
        # Turn 1, entered at turn 0, charge_time 1 -> can use
        battle.turn_number = 1
        assert PlayerTargetValidator.is_action_valid(action, battle) is True

    def test_charge_time_multiple_turns(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that charge_time requires multiple turns."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM,
            turn_entered_field=0
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                charge_time=3  # Needs 3 turns prep time
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Turn 0, 1, 2 -> can't use
        for turn in [0, 1, 2]:
            battle.turn_number = turn
            action = Action(
                unit_position=Position(0, 0),
                weapon_id=1,
                target_position=Position(0, 1)
            )
            assert PlayerTargetValidator.is_action_valid(action, battle) is False
        
        # Turn 3 -> can use
        battle.turn_number = 3
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        assert PlayerTargetValidator.is_action_valid(action, battle) is True

    def test_no_charge_time_allows_immediate_use(
        self, basic_unit_template, mock_data_loader, mock_layout
    ):
        """Test that no charge_time allows immediate use."""
        attacker = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 0),
            battle_side=BattleSide.PLAYER_TEAM,
            turn_entered_field=0
        )
        
        target = BattleUnit(
            template=basic_unit_template,
            position=Position(0, 1),
            battle_side=BattleSide.ENEMY_TEAM
        )
        
        ability = Ability(
            id=1,
            name="Test",
            stats=AbilityStats(
                min_range=1,
                max_range=5,
                line_of_fire=LineOfFire.INDIRECT,
                charge_time=0  # No charge time
            )
        )
        
        weapon = Weapon(id=1, name="Test Weapon", abilities=[1])
        attacker.template.weapons[1] = weapon
        mock_data_loader.get_ability = Mock(return_value=ability)
        
        battle = BattleState(
            data_loader=mock_data_loader,
            layout=mock_layout,
            player_units=[attacker],
            enemy_units=[target],
            player_is_attacker=True
        )
        
        # Turn 0 -> can use immediately
        battle.turn_number = 0
        action = Action(
            unit_position=Position(0, 0),
            weapon_id=1,
            target_position=Position(0, 1)
        )
        
        assert PlayerTargetValidator.is_action_valid(action, battle) is True

