import pytest

from vampires_ai.game.state import Cell, GameState, Species
from vampires_ai.game.state_builder import GameStateBuilder


def test_set_message_initializes_board_dimensions():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    assert builder.height == 5
    assert builder.width == 8


def test_hum_message_stores_human_house_positions():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hum", [[1, 2], [3, 4]]])

    assert builder.human_houses == ((1, 2), (3, 4))


def test_hme_message_stores_home_position():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    assert builder.home_position == (2, 3)


def test_map_message_builds_game_state():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hum", [[1, 2]]])
    builder.handle_message(["hme", [2, 3]])

    builder.handle_message([
        "map",
        [
            (1, 2, 4, 0, 0),
            (2, 3, 0, 6, 0),
            (6, 4, 0, 0, 5),
        ],
    ])

    state = builder.game_state

    assert isinstance(state, GameState)
    assert state.width == 8
    assert state.height == 5
    assert state.current_player == Species.VAMPIRE

    assert state.get_cell(1, 2) == Cell(Species.HUMAN, 4)
    assert state.get_cell(2, 3) == Cell(Species.VAMPIRE, 6)
    assert state.get_cell(6, 4) == Cell(Species.WEREWOLF, 5)
    assert state.get_cell(0, 0) is None


def test_map_rejects_multiple_species_in_one_cell():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(ValueError, match="multiple species"):
        builder.handle_message([
            "map",
            [
                (2, 3, 0, 6, 0),
                (4, 1, 0, 3, 2),
            ],
        ])


def test_upd_updates_cells_without_mutating_previous_state():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    builder.handle_message([
        "map",
        [
            (1, 2, 4, 0, 0),
            (2, 3, 0, 6, 0),
            (6, 4, 0, 0, 5),
        ],
    ])

    old_state = builder.game_state

    builder.handle_message([
        "upd",
        [
            (2, 3, 0, 4, 0),
            (1, 2, 0, 0, 0),
        ],
    ])

    new_state = builder.game_state

    assert new_state is not old_state

    # Updated Vampire count
    assert new_state.get_cell(2, 3) == Cell(Species.VAMPIRE, 4)

    # Empty cell should be removed
    assert new_state.get_cell(1, 2) is None

    # Unchanged Werewolf cell
    assert new_state.get_cell(6, 4) == Cell(Species.WEREWOLF, 5)

    # Previous state must remain unchanged
    assert old_state.get_cell(2, 3) == Cell(Species.VAMPIRE, 6)
    assert old_state.get_cell(1, 2) == Cell(Species.HUMAN, 4)

    # Player identity must remain unchanged
    assert new_state.current_player == Species.VAMPIRE


def test_upd_before_map_raises_value_error():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(ValueError, match="MAP must be received before UPD"):
        builder.handle_message([
            "upd",
            [(2, 3, 0, 4, 0)],
        ])


def test_map_rejects_duplicate_positions():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(ValueError, match="duplicate position"):
        builder.handle_message([
            "map",
            [
                (2, 3, 0, 6, 0),
                (1, 2, 4, 0, 0),
                (1, 2, 5, 0, 0),
            ],
        ])


def test_map_rejects_negative_unit_counts():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(ValueError, match="negative unit count"):
        builder.handle_message([
            "map",
            [
                (2, 3, 0, 6, 0),
                (1, 2, -3, 0, 0),
            ],
        ])


def test_upd_rejects_negative_unit_counts():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    builder.handle_message([
        "map",
        [
            (2, 3, 0, 6, 0),
            (6, 4, 0, 0, 5),
        ],
    ])

    old_state = builder.game_state

    with pytest.raises(ValueError, match="negative unit count"):
        builder.handle_message([
            "upd",
            [(2, 3, 0, -4, 0)],
        ])

    # Invalid updates must not modify the existing state
    assert builder.game_state is old_state


def test_upd_rejects_duplicate_positions():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    with pytest.raises(ValueError, match="duplicate position"):
        builder.handle_message([
            "upd",
            [
                (2, 3, 0, 5, 0),
                (2, 3, 0, 4, 0),
            ],
        ])

    assert builder.game_state is old_state


def test_upd_rejects_out_of_bounds_position():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    with pytest.raises(ValueError, match="outside the board"):
        builder.handle_message([
            "upd",
            [(8, 2, 0, 3, 0)],
        ])

    assert builder.game_state is old_state


def test_upd_rejects_out_of_bounds_empty_cell():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    with pytest.raises(ValueError, match="outside the board"):
        builder.handle_message([
            "upd",
            [(8, 2, 0, 0, 0)],
        ])

    assert builder.game_state is old_state


def test_map_rejects_non_integer_unit_counts():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(TypeError, match="unit counts must be integers"):
        builder.handle_message([
            "map",
            [
                (2, 3, 0, 6, 0),
                (1, 2, 3.5, 0, 0),
            ],
        ])


def test_map_rejects_non_integer_coordinates():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(TypeError, match="coordinates must be integers"):
        builder.handle_message([
            "map",
            [
                (2, 3, 0, 6, 0),
                (1.5, 2, 3, 0, 0),
            ],
        ])


def test_upd_rejects_non_integer_coordinates():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    with pytest.raises(TypeError, match="coordinates must be integers"):
        builder.handle_message([
            "upd",
            [(1.5, 2, 0, 3, 0)],
        ])

    assert builder.game_state is old_state


def test_upd_rejects_non_integer_unit_counts():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    with pytest.raises(TypeError, match="unit counts must be integers"):
        builder.handle_message([
            "upd",
            [(2, 3, 0, 3.5, 0)],
        ])

    assert builder.game_state is old_state


def test_set_rejects_zero_height():
    builder = GameStateBuilder()

    with pytest.raises(ValueError, match="board dimensions must be positive"):
        builder.handle_message(["set", [0, 8]])

    assert builder.width is None
    assert builder.height is None


def test_set_rejects_negative_width():
    builder = GameStateBuilder()

    with pytest.raises(
        ValueError,
        match="board dimensions must be positive",
    ):
        builder.handle_message(["set", [5, -8]])

    assert builder.width is None
    assert builder.height is None


def test_set_rejects_non_integer_dimensions():
    builder = GameStateBuilder()

    with pytest.raises(
        TypeError,
        match="board dimensions must be integers",
    ):
        builder.handle_message(["set", [5, 8.5]])

    assert builder.width is None
    assert builder.height is None


def test_hme_rejects_out_of_bounds_position():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    with pytest.raises(ValueError, match="outside the board"):
        builder.handle_message(["hme", [8, 3]])

    assert builder.home_position is None


def test_hum_rejects_out_of_bounds_position():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    with pytest.raises(ValueError, match="outside the board"):
        builder.handle_message([
            "hum",
            [[1, 2], [8, 3]],
        ])

    assert builder.human_houses is None


def test_hum_rejects_non_integer_coordinates():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    with pytest.raises(
        TypeError,
        match="coordinates must be integers",
    ):
        builder.handle_message([
            "hum",
            [[1, 2], [1.5, 3]],
        ])

    assert builder.human_houses is None


def test_hme_rejects_non_integer_coordinates():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    with pytest.raises(
        TypeError,
        match="coordinates must be integers",
    ):
        builder.handle_message(["hme", [2.5, 3]])

    assert builder.home_position is None



def test_map_rejects_missing_set():
    builder = GameStateBuilder()

    with pytest.raises(ValueError, match="SET"):
        builder.handle_message([
            "map",
            [(2, 3, 0, 6, 0)],
        ])

    assert builder.game_state is None


def test_map_rejects_missing_hme():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    with pytest.raises(ValueError, match="HME"):
        builder.handle_message([
            "map",
            [(2, 3, 0, 6, 0)],
        ])

    assert builder.game_state is None


def test_map_rejects_human_at_home_position():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(ValueError):
        builder.handle_message([
            "map",
            [(2, 3, 5, 0, 0)],
        ])

    assert builder.game_state is None


def test_map_rejects_empty_home_position():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    with pytest.raises(ValueError):
        builder.handle_message([
            "map",
            [
                (2, 3, 0, 0, 0),
                (4, 2, 0, 5, 0),
            ],
        ])

    assert builder.game_state is None


def test_map_identifies_werewolf_player():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    builder.handle_message([
        "map",
        [
            (2, 3, 0, 0, 6),
            (4, 2, 0, 5, 0),
            (1, 1, 3, 0, 0),
        ],
    ])

    assert builder.game_state is not None
    assert builder.game_state.current_player == Species.WEREWOLF
    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.WEREWOLF, 6
    )


def test_map_rejects_duplicate_initialization():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    with pytest.raises(ValueError, match="MAP already received"):
        builder.handle_message([
            "map",
            [(2, 3, 0, 10, 0)],
        ])

    assert builder.game_state is old_state
    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 6
    )


def test_set_rejects_duplicate_initialization():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])

    with pytest.raises(ValueError, match="SET already received"):
        builder.handle_message(["set", [10, 10]])

    assert builder.height == 5
    assert builder.width == 8


def test_hme_rejects_duplicate_initialization():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])

    old_home = builder.home_position

    with pytest.raises(ValueError, match="HME already received"):
        builder.handle_message(["hme", [4, 2]])

    assert builder.home_position == old_home
    assert builder.home_position == (2, 3)


def test_hum_rejects_duplicate_initialization():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message([
        "hum",
        [[1, 2], [4, 3]],
    ])

    old_houses = builder.human_houses

    with pytest.raises(ValueError, match="HUM already received"):
        builder.handle_message([
            "hum",
            [[2, 2]],
        ])

    assert builder.human_houses == old_houses
    assert builder.human_houses == ((1, 2), (4, 3))


def test_hum_rejects_duplicate_after_empty_list():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hum", []])

    assert builder.human_houses == ()

    with pytest.raises(ValueError, match="HUM already received"):
        builder.handle_message([
            "hum",
            [[1, 2]],
        ])

    assert builder.human_houses == ()


def test_upd_preserves_current_player():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    assert builder.game_state.current_player == Species.VAMPIRE

    builder.handle_message([
        "upd",
        [(2, 3, 0, 0, 4)],
    ])

    assert builder.game_state.current_player == Species.VAMPIRE
    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.WEREWOLF, 4
    )


def test_upd_creates_new_state_even_when_unchanged():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    builder.handle_message([
        "upd",
        [(2, 3, 0, 6, 0)],
    ])

    assert builder.game_state == old_state
    assert builder.game_state is not old_state