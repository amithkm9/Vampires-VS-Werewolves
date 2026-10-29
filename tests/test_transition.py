import pytest

from vampires_ai.game.state import GameState, Cell
from vampires_ai.game.move import Move
from vampires_ai.game.state import Species

from vampires_ai.game.transition import apply_move

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

# TODO: adjust this test after supporting combat
def test_apply_move_reject_enemy_destination():
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

    # Verify that apply_move raises ValueError
    with pytest.raises(ValueError) as error:
        apply_move(state, move)

    # with message "Combat is not supported yet"
    assert str(error.value) == "Combat is not supported yet"

# TODO: adjust this test after supporting attacking human
def test_apply_move_rejects_human_destination():
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

    # Verify that combat is rejected
    with pytest.raises(ValueError, match="Combat is not supported yet"):
        apply_move(state, move)

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