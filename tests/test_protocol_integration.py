
from unittest.mock import patch

from vampires_ai.game.state import Cell, Species
from vampires_ai.game.state_builder import GameStateBuilder


def test_parsed_server_messages_build_game_state():
    from vampires_ai.client import ClientSocket

    builder = GameStateBuilder()

    messages = [
        ("SET", [5, 8]),
        ("HME", [2, 3]),
        ("MAP", [1, 2, 3, 0, 6, 0]),
    ]

    for command, values in messages:
        with patch.object(
            ClientSocket,
            "_get_command",
            return_value=command,
        ):
            with patch.object(
                ClientSocket,
                "_get_message",
                side_effect=values,
            ):
                client = ClientSocket.__new__(ClientSocket)
                message = client._parse_message()
                builder.handle_message(message)

    state = builder.game_state

    assert state is not None
    assert state.width == 8
    assert state.height == 5
    assert state.current_player == Species.VAMPIRE
    assert state.get_cell(2, 3) == Cell(Species.VAMPIRE, 6)


def test_client_parses_upd_and_updates_game_state():
    from vampires_ai.client import ClientSocket

    builder = GameStateBuilder()
    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    # Simulate a server UPD message:
    # One updated cell at (2, 3), with 4 vampires.
    client = ClientSocket.__new__(ClientSocket)

    with patch.object(client, "_get_command", return_value="UPD"):
        with patch.object(
            client,
            "_get_message",
            side_effect=[1, 2, 3, 0, 4, 0],
        ):
            message = client._parse_message()

    assert message == ["upd", [(2, 3, 0, 4, 0)]]

    builder.handle_message(message)

    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 4
    )
    assert builder.game_state is not old_state
    assert old_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 6
    )


def test_client_parses_empty_upd():
    from vampires_ai.client import ClientSocket

    builder = GameStateBuilder()
    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    client = ClientSocket.__new__(ClientSocket)

    with patch.object(client, "_get_command", return_value="UPD"):
        with patch.object(
            client,
            "_get_message",
            side_effect=[0],
        ):
            message = client._parse_message()

    assert message == ["upd", []]

    builder.handle_message(message)

    assert builder.game_state == old_state
    assert builder.game_state is not old_state
    assert builder.game_state.current_player == Species.VAMPIRE
    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 6
    )
