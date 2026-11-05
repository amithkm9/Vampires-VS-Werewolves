
import pytest
import subprocess
import sys

from unittest.mock import Mock, patch, call

from vampires_ai.game.move import Move, TurnAction
from vampires_ai.game.state import Cell, Species
from vampires_ai.game.state_builder import GameStateBuilder
from vampires_ai.client import EndException
from vampires_ai.main import (
    process_message, 
    initialize_game, 
    play_turn,
    run_game_loop,
    play_game,
    parse_arguments,
    main,
    encode_turn_action,
)


def test_process_message_builds_game_state():
    builder = GameStateBuilder()

    process_message(builder, ["set", [5, 8]])
    process_message(builder, ["hme", [2, 3]])
    process_message(builder, [
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    state = builder.game_state

    assert state is not None
    assert state.width == 8
    assert state.height == 5
    assert state.current_player == Species.VAMPIRE
    assert state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 6
    )

def test_process_message_triggers_move_only_on_upd():
    builder = GameStateBuilder()

    assert process_message(builder, ["set", [5, 8]]) is False
    assert process_message(builder, ["hum", []]) is False
    assert process_message(builder, ["hme", [2, 3]]) is False

    assert process_message(builder, [
        "map",
        [(2, 3, 0, 6, 0)],
    ]) is False

    assert process_message(builder, ["upd", []]) is True

def test_initialize_game_reads_initial_messages():
    client = Mock()

    client.get_message.side_effect = [
        ["set", [5, 8]],
        ["hum", [[1, 1]]],
        ["hme", [2, 3]],
        ["map", [
            (1, 1, 3, 0, 0),
            (2, 3, 0, 6, 0),
        ]],
    ]

    builder = GameStateBuilder()

    initialize_game(client, builder)

    assert client.get_message.call_count == 4
    assert builder.game_state is not None
    assert builder.game_state.width == 8
    assert builder.game_state.height == 5
    assert builder.game_state.current_player == Species.VAMPIRE
    assert builder.game_state.get_cell(1, 1) == Cell(
        Species.HUMAN, 3
    )
    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 6
    )

def test_play_turn_updates_state_and_sends_move():
    client = Mock()
    builder = GameStateBuilder()

    initialize_game_client = Mock()
    initialize_game_client.get_message.side_effect = [
        ["set", [5, 8]],
        ["hum", []],
        ["hme", [2, 3]],
        ["map", [(2, 3, 0, 6, 0)]],
    ]

    initialize_game(initialize_game_client, builder)

    client.get_message.return_value = [
        "upd",
        [(2, 3, 0, 4, 0)],
    ]

    choose_move = Mock(return_value=(
        1,
        [(2, 3, 4, 3, 3)],
    ))

    play_turn(client, builder, choose_move)

    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 4
    )

    choose_move.assert_called_once_with(builder.game_state)

    client.send_mov.assert_called_once_with(
        1,
        [(2, 3, 4, 3, 3)],
    )

def test_play_turn_sends_move_on_empty_upd():
    client = Mock()
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    old_state = builder.game_state

    client.get_message.return_value = ["upd", []]

    choose_move = Mock(return_value=(
        1,
        [(2, 3, 4, 3, 3)],
    ))

    play_turn(client, builder, choose_move)

    assert builder.game_state == old_state
    assert builder.game_state is not old_state

    choose_move.assert_called_once_with(builder.game_state)

    client.send_mov.assert_called_once_with(
        1,
        [(2, 3, 4, 3, 3)],
    )

def test_play_turn_does_not_send_move_when_strategy_fails():
    client = Mock()
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    client.get_message.return_value = ["upd", []]

    choose_move = Mock(side_effect=RuntimeError("Strategy failed"))

    with pytest.raises(RuntimeError, match="Strategy failed"):
        play_turn(client, builder, choose_move)

    choose_move.assert_called_once_with(builder.game_state)
    client.send_mov.assert_not_called()

def test_run_game_loop_handles_multiple_turns():
    client = Mock()
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message([
        "map",
        [(2, 3, 0, 6, 0)],
    ])

    client.get_message.side_effect = [
        ["upd", []],
        ["upd", [(2, 3, 0, 4, 0)]],
        EndException(),
    ]

    choose_move = Mock(return_value=(
        1,
        [(2, 3, 4, 3, 3)],
    ))

    run_game_loop(client, builder, choose_move)

    assert client.get_message.call_count == 3
    assert choose_move.call_count == 2
    assert client.send_mov.call_count == 2
    assert builder.game_state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 4
    )

def test_play_game_initializes_and_runs_one_turn():
    client = Mock()

    client.get_message.side_effect = [
        ["set", [5, 8]],
        ["hum", []],
        ["hme", [2, 3]],
        ["map", [(2, 3, 0, 6, 0)]],
        ["upd", [(2, 3, 0, 4, 0)]],
        EndException(),
    ]

    choose_move = Mock(return_value=(
        1,
        [(2, 3, 4, 3, 3)],
    ))

    play_game(client, choose_move)

    assert client.get_message.call_count == 6
    assert choose_move.call_count == 1
    assert client.send_mov.call_count == 1

    state = choose_move.call_args.args[0]

    assert state.width == 8
    assert state.height == 5
    assert state.current_player == Species.VAMPIRE
    assert state.get_cell(2, 3) == Cell(
        Species.VAMPIRE, 4
    )

    client.send_mov.assert_called_once_with(
        1,
        [(2, 3, 4, 3, 3)],
    )

def test_parse_args_reads_server_address():
    args = parse_arguments(["127.0.0.1", "5555"])

    assert args.ip == "127.0.0.1"
    assert args.port == 5555

def test_main_creates_client_and_starts_game():
    choose_move = Mock()

    with patch("vampires_ai.main.ClientSocket") as mock_client:
        with patch("vampires_ai.main.play_game") as mock_play_game:
            main(
                argv=["127.0.0.1", "5555"],
                choose_move=choose_move,
            )

    mock_client.assert_called_once_with(
        "127.0.0.1",
        5555,
    )

    mock_play_game.assert_called_once_with(
        mock_client.return_value,
        choose_move,
    )

def test_main_creates_client_and_starts_game():
    choose_move = Mock()

    with patch("vampires_ai.main.ClientSocket") as mock_client:
        with patch("vampires_ai.main.play_game") as mock_play_game:
            main(
                argv=["127.0.0.1", "5555"],
                choose_move=choose_move,
            )

    mock_client.assert_called_once_with(
        "127.0.0.1",
        5555,
    )

    client = mock_client.return_value

    client.send_nme.assert_called_once_with("VampiresAI")

    mock_play_game.assert_called_once_with(
        client,
        choose_move,
    )

def test_main_sends_name_before_starting_game():
    choose_move = Mock()
    calls = []

    with patch("vampires_ai.main.ClientSocket") as mock_client:
        with patch("vampires_ai.main.play_game") as mock_play_game:
            client = mock_client.return_value

            client.send_nme.side_effect = lambda name: calls.append("nme")
            mock_play_game.side_effect = lambda c, s: calls.append("play")

            main(
                argv=["127.0.0.1", "5555"],
                choose_move=choose_move,
            )

    assert calls == ["nme", "play"]

def test_main_module_executes_entry_point():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vampires_ai.main",
            "127.0.0.1",
            "5555",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode != 0
    assert "A move strategy is required" in result.stderr

def test_encode_turn_action_for_server():
    action = TurnAction(
        moves=(
            Move((2, 3), (3, 3), 4),
            Move((5, 5), (4, 5), 2),
        )
    )

    nb_moves, moves = encode_turn_action(action)

    assert nb_moves == 2
    assert moves == [
        (2, 3, 4, 3, 3),
        (5, 5, 2, 4, 5),
    ]

def test_play_turn_encodes_turn_action_before_sending():
    builder = GameStateBuilder()

    builder.handle_message(["set", [5, 8]])
    builder.handle_message(["hme", [2, 3]])
    builder.handle_message(["map", [(2, 3, 0, 6, 0)]])

    client = Mock()
    client.get_message.return_value = [
        "upd",
        [(2, 3, 0, 4, 0)],
    ]

    action = TurnAction(
        moves=(
            Move((2, 3), (3, 3), 4),
        )
    )

    choose_move = Mock(return_value=action)

    play_turn(client, builder, choose_move)

    choose_move.assert_called_once_with(builder.game_state)
    client.send_mov.assert_called_once_with(
        1,
        [(2, 3, 4, 3, 3)],
    )
