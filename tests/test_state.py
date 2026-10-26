from dataclasses import FrozenInstanceError

import pytest

from vampires_ai.game.state import Cell, GameState, Species

# Verify enum values
def test_species():
    assert Species.HUMAN.value == "human"
    assert Species.VAMPIRE.value == "vampire"
    assert Species.WEREWOLF.value == "werewolf"

# Verify valid object creation
def test_cell_creatoin():
    cell = Cell(Species.VAMPIRE, 8)

    assert cell.species == Species.VAMPIRE
    assert cell.count == 8

# Reject zero population
def test_cell_rejects_zero_population():
    with pytest.raises(ValueError):
        Cell(Species.VAMPIRE, 0)

# Reject negative population
def test_cell_rejects_negative_population():
    with pytest.raises(ValueError):
        Cell(Species.WEREWOLF, -5)

# Reject invalid species
def test_cell_rejects_invalid_species():
    with pytest.raises(TypeError):
        Cell("vampire", 8)

# Reject boolean counts
def test_cell_rejects_boolean_population():
    with pytest.raises(TypeError):
        Cell(Species.HUMAN, True)

# Prevent modifications
def test_cell_is_immutable():
    cell = Cell(Species.VAMPIRE, 8)

    with pytest.raises(FrozenInstanceError):
        cell.count = 10


def test_game_state_creation():
    state = GameState(
        width=10,
        height=10,
        board=(
            ((1, 2), Cell(Species.HUMAN, 5)),
            ((3, 4), Cell(Species.VAMPIRE, 8)),
        ),
        current_player=Species.VAMPIRE
    )

    assert state.width == 10
    assert state.height == 10
    assert len(state.board) == 2
    assert state.current_player == Species.VAMPIRE

def test_game_state_rejects_negative_dimensions():
    with pytest.raises(ValueError):
        GameState(
            width=-10,
            height=10,
            board=(),
            current_player=Species.VAMPIRE,
        )

def test_game_state_rejects_out_of_bounds_position():
    with pytest.raises(ValueError):
        GameState(
            width=10,
            height=10,
            board=(
                ((12, 3), Cell(Species.HUMAN, 5)),
            ),
            current_player=Species.VAMPIRE,
        )

def test_game_state_rejects_human_player():
    with pytest.raises(ValueError):
        GameState(
            width=10,
            height=10,
            board=(),
            current_player=Species.HUMAN,
        )

def test_game_state_rejects_duplicate_positions():
    with pytest.raises(ValueError):
        GameState(
            width=10,
            height=10,
            board=(
                ((1, 2), Cell(Species.HUMAN, 5)),
                ((1, 2), Cell(Species.VAMPIRE, 8)),
            ),
            current_player=Species.VAMPIRE,
        )

def test_game_state_rejects_invalid_coordinate_types():
    with pytest.raises(TypeError):
        GameState(
            width=10,
            height=10,
            board=(
                ((True, 2), Cell(Species.HUMAN, 5)),
            ),
            current_player=Species.VAMPIRE,
        )

def test_game_state_rejects_mutable_board():
    with pytest.raises(TypeError):
        GameState(
            width=10,
            height=10,
            board={
                (1, 2): Cell(Species.HUMAN, 5),
            },
            current_player=Species.VAMPIRE,
        )

def test_game_state_canonical_board_ordering():
    state = GameState(
        width=10,
        height=10,
        board=(
            ((3, 4), Cell(Species.VAMPIRE, 8)),
            ((1, 2), Cell(Species.HUMAN, 5)),
        ),
        current_player=Species.VAMPIRE,
    )

    assert state.board == (
        ((1, 2), Cell(Species.HUMAN, 5)),
        ((3, 4), Cell(Species.VAMPIRE, 8)),
    )

def test_game_state_equality():
    state_a = GameState(
        width=10,
        height=10,
        board=(
            ((1, 2), Cell(Species.HUMAN, 5)),
            ((3, 4), Cell(Species.VAMPIRE, 8)),
        ),
        current_player=Species.VAMPIRE,
    )

    state_b = GameState(
        width=10,
        height=10,
        board=(
            ((3, 4), Cell(Species.VAMPIRE, 8)),
            ((1, 2), Cell(Species.HUMAN, 5)),
        ),
        current_player=Species.VAMPIRE,
    )

    assert state_a == state_b
    assert hash(state_a) == hash(state_b)

def test_game_state_from_dict():
    board = {
        (3, 4): Cell(Species.VAMPIRE, 8),
        (1, 2): Cell(Species.HUMAN, 5),
    }

    state = GameState.from_dict(
        width=10,
        height=10,
        board=board,
        current_player=Species.VAMPIRE,
    )

    assert state.board == (
        ((1, 2), Cell(Species.HUMAN, 5)),
        ((3, 4), Cell(Species.VAMPIRE, 8)),
    )

def test_game_state_from_dict_is_independent():
    board = {
        (1, 2): Cell(Species.HUMAN, 5),
    }

    state = GameState.from_dict(
        width=10,
        height=10,
        board=board,
        current_player=Species.VAMPIRE,
    )

    # Modify the orginial dictionary
    board[(1, 2)] = Cell(Species.HUMAN, 10)

    # The GameState should remain unchanged
    assert state.board == (
        ((1, 2), Cell(Species.HUMAN, 5)),
    )

def test_game_state_get_call():
    state = GameState.from_dict(
        width=10,
        height=10,
        board={
            (1, 2): Cell(Species.HUMAN, 5),
            (3, 4): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    assert state.get_cell(1, 2) == Cell(Species.HUMAN, 5)
    assert state.get_cell(3, 4) == Cell(Species.VAMPIRE, 8)

def test_game_state_get_empty_cell():
    state = GameState.from_dict(
        width=10,
        height=10,
        board={
            (1, 2): Cell(Species.HUMAN, 5),
        },
        current_player=Species.VAMPIRE,
    )

    assert state.get_cell(0, 0) is None
    assert state.get_cell(5, 5) is None