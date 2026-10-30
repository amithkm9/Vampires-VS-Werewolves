import pytest

from unittest.mock import patch

from vampires_ai.game.state import GameState, Cell
from vampires_ai.game.move import Move
from vampires_ai.game.state import Species
from vampires_ai.game.battle import BattleResult, HumanBattleResult

from vampires_ai.game.transition import apply_move
from vampires_ai.game.battle import resolve_battle, resolve_human_battle

def test_apply_move_to_empty_cell():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    new_state = apply_move(state, move)

    # Check source population
    assert new_state.get_cell(1, 1).count == 3

    # Check destination population
    assert new_state.get_cell(2, 1).count == 5

    # Check original state
    assert state.get_cell(1, 1).count == 8

def test_apply_move_full_population():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=8,
    )

    new_state = apply_move(state, move)

    # Source should be empty
    assert new_state.get_cell(1, 1) is None

    # Destination should contain 8 Vampires
    assert new_state.get_cell(2, 1).count == 8

    # Original state should remain unchanged
    assert state.get_cell(1, 1).count == 8
    assert state.get_cell(2, 1) is None

def test_apply_move_friendly_merge():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
            (2, 1): Cell(Species.VAMPIRE, 3),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    new_state = apply_move(state, move)

    # Check new source population
    assert new_state.get_cell(1, 1).count == 3

    # Check merged destination population
    assert new_state.get_cell(2, 1).count == 8

    # Check original source population
    assert state.get_cell(1, 1).count == 8

    # Check original destination population
    assert state.get_cell(2, 1).count == 3

def test_apply_move_insufficient_population():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=10,
    )

    with pytest.raises(ValueError, match="Illegal move") as error:
        apply_move(state, move)

def test_apply_move_calls_resolve_battle():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
            (2, 1): Cell(Species.WEREWOLF, 5),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = BattleResult(
        attacker_wins=True,
        survivors=3,
    )

    # Interaction Testing
    with patch(
        "vampires_ai.game.transition.resolve_battle",
        return_value=fake_result,
    ) as mock_battle:
        new_state = apply_move(state, move)

    mock_battle.assert_called_once_with(
        attackers=5,
        defenders=5,
    )

    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 3)

def test_apply_move_calls_resolve_human_battle():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
            (2, 1): Cell(Species.HUMAN, 4),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=5,
        converted_humans=4,
        surviving_humans=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_human_battle",
        return_value=fake_result,
    ) as mock_battle:
        new_state = apply_move(state, move)

    mock_battle.assert_called_once_with(
        attackers=5,
        humans=4,
    )

    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 3)
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 9)

def test_apply_move_preserves_unaffected_cells():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
            (4, 4): Cell(Species.WEREWOLF, 6),
            (0, 0): Cell(Species.HUMAN, 3),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    new_state = apply_move(state, move)

    # Check unaffected Werewolf cell
    old_werewolf_cell = state.get_cell(4, 4)
    new_werewolf_cell = new_state.get_cell(4, 4)

    assert new_werewolf_cell is not None
    assert old_werewolf_cell.species == new_werewolf_cell.species
    assert old_werewolf_cell.count == new_werewolf_cell.count

    # Check unaffected Human cell
    old_human_cell = state.get_cell(0, 0)
    new_human_cell = new_state.get_cell(0, 0)

    assert new_human_cell is not None
    assert old_human_cell.species == new_human_cell.species
    assert old_human_cell.count == new_human_cell.count

    # # Also, we can samplify these checks above
    # assert new_state.get_cell(4, 4) == state.get_cell(4, 4)
    # assert new_state.get_cell(0, 0) == state.get_cell(0, 0)

def test_apply_move_preserves_current_player():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    new_state = apply_move(state, move)

    # Check current player in new state
    assert new_state.current_player == Species.VAMPIRE

    # Check current player in original state
    assert state.current_player == Species.VAMPIRE

def test_apply_move_returns_new_state():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    new_state = apply_move(state, move)

    # Verify that new_state is a different object - Object Identity
    assert new_state is not state

    # Verify that width remains unchanged - Dimension Preservation
    assert new_state.width == state.width

    # Verify that height remains unchanged - Immutability
    assert new_state.height == state.height

def test_apply_move_monster_battle_attacker_wins():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.WEREWOLF, 6),
        },
        current_player=Species.VAMPIRE
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = BattleResult(
        attacker_wins=True,
        survivors=3,
    )

    with patch(
        "vampires_ai.game.transition.resolve_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Source loses the 5 attacking Vampires
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Attackers win and occupy the destination
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 3)

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.WEREWOLF, 6)

def test_apply_move_monster_battle_defender_wins():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.WEREWOLF, 6),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = BattleResult(
        attacker_wins=False,
        survivors=2,
    )

    with patch(
        "vampires_ai.game.transition.resolve_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Check source after battle
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    # Check destination after defender victory
    assert new_state.get_cell(2, 1) == Cell(Species.WEREWOLF, 2)

    # Check original state
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.WEREWOLF, 6)

def test_apply_move_monster_battle_zero_survivors():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.WEREWOLF, 6),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = BattleResult(
        attacker_wins=True,
        survivors=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Source loses 5 vampires
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Destination becomes empty
    assert new_state.get_cell(2, 1) is None

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.WEREWOLF, 6)

def test_apply_move_monster_battle_defender_zero_survivors():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.WEREWOLF, 6),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = BattleResult(
        attacker_wins=False,
        survivors=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Verify source
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Verify destination is empty
    assert new_state.get_cell(2, 1) is None

    # Verify original state is unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.WEREWOLF, 6)

def test_apply_move_human_battle_guaranteed_conversion():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.HUMAN, 4),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=5,
        converted_humans=4,
        surviving_humans=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_human_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Source after battle
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Destination after conversion
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 9)

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.HUMAN, 4)

def test_apply_move_human_battle_defender_wins():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.HUMAN, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = HumanBattleResult(
        attacker_wins=False,
        surviving_attackers=0,
        converted_humans=0,
        surviving_humans=3,
    )

    with patch(
        "vampires_ai.game.transition.resolve_human_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Source after battle
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Destination after Humans win
    assert new_state.get_cell(2, 1) == Cell(Species.HUMAN, 3)

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.HUMAN, 8)

def test_apply_move_human_battle_defender_zero_survivors():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.HUMAN, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = HumanBattleResult(
        attacker_wins=False,
        surviving_attackers=0,
        converted_humans=0,
        surviving_humans=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_human_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Verify source
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Verify destination is empty
    assert new_state.get_cell(2, 1) is None

    # Verify original state is unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.HUMAN, 8)

def test_apply_move_human_battle_attacker_zero_survivors():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.HUMAN, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=0,
        converted_humans=0,
        surviving_humans=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_human_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Source after battle
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Destination becomes empty
    assert new_state.get_cell(2, 1) is None

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.HUMAN, 8)

def test_apply_move_human_battle_only_converted_humans_survive():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.HUMAN, 8),
        },
        current_player=Species.VAMPIRE,
    )

    move = Move(
        source=(1, 1),
        destination=(2, 1),
        count=5,
    )

    fake_result = HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=0,
        converted_humans=3,
        surviving_humans=0,
    )

    with patch(
        "vampires_ai.game.transition.resolve_human_battle",
        return_value=fake_result,
    ):
        new_state = apply_move(state, move)

    # Verify source after battle
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Verify destination contains converted Vampires
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 3)

    # Verify original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.HUMAN, 8)