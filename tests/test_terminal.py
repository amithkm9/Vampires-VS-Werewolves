import pytest

from vampires_ai.game.state import Cell, GameState, Species
from vampires_ai.game.terminal import is_terminal, get_winner


def test_game_is_not_terminal_when_both_species_exist():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (0, 0): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.WEREWOLF, 3),
        },
        current_player=Species.VAMPIRE,
    )

    assert is_terminal(state) is False

def test_game_is_terminal_when_vampires_are_eliminated():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (2, 2): Cell(Species.WEREWOLF, 3),
        },
        current_player=Species.VAMPIRE,
    )

    assert is_terminal(state) is True

def test_game_is_terminal_when_werewolves_are_eliminated():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (0, 0): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.WEREWOLF,
    )

    assert is_terminal(state) is True

def test_game_is_terminal_when_both_species_are_eliminated():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={},
        current_player=Species.VAMPIRE,
    )

    assert is_terminal(state) is True

def test_vampires_win_when_werewolves_are_eliminated():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (0, 0): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.VAMPIRE,
    )

    assert get_winner(state) == Species.VAMPIRE

def test_werewolves_win_when_vampires_are_eliminated():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (2, 2): Cell(Species.WEREWOLF, 3),
        },
        current_player=Species.VAMPIRE,
    )

    assert get_winner(state) == Species.WEREWOLF

def test_no_winner_when_both_species_are_eliminated():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={},
        current_player=Species.VAMPIRE,
    )

    assert get_winner(state) is None

def test_get_winner_raises_when_game_is_not_terminal():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (0, 0): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.WEREWOLF, 3),
        },
        current_player=Species.VAMPIRE,
    )

    with pytest.raises(ValueError, match="Game is not terminal"):
        get_winner(state)