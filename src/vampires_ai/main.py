
from argparse import ArgumentParser

from vampires_ai.game.move import TurnAction
from vampires_ai.game.state_builder import GameStateBuilder
from vampires_ai.client import ClientSocket, EndException, ByeException


def process_message(
    builder: GameStateBuilder,
    message: list,
) -> bool:
    builder.handle_message(message)
    return message[0] == "upd"

def initialize_game(
    client,
    builder: GameStateBuilder,
) -> None:
    for _ in range(4):
        message = client.get_message()
        process_message(builder, message)

def play_turn(
    client,
    builder: GameStateBuilder,
    choose_move,
) -> None:
    message = client.get_message()

    should_move = process_message(builder, message)

    if should_move:
        result = choose_move(builder.game_state)

        if isinstance(result, TurnAction):
            nb_moves, moves = encode_turn_action(result)
        else:
            nb_moves, moves = result

        client.send_mov(nb_moves, moves)

def run_game_loop(
    client,
    builder: GameStateBuilder,
    choose_move,
) -> None:
    while True:
        try:
            play_turn(client, builder, choose_move)
        except (EndException, ByeException):
            break

def play_game(client, choose_move) -> None:
    builder = GameStateBuilder()

    initialize_game(client, builder)

    run_game_loop(client, builder, choose_move)

def parse_arguments(argv=None):
    parser = ArgumentParser()

    parser.add_argument(
        "ip",
        type=str,
        help="Server IP address",
    )

    parser.add_argument(
        "port",
        type=int,
        help="Server port",
    )

    return parser.parse_args(argv)

def main(argv=None, choose_move=None) -> None:
    args = parse_arguments(argv)

    if choose_move is None:
        raise ValueError("A move strategy is required")

    client = ClientSocket(args.ip, args.port)

    client.send_nme("VampiresAI")

    play_game(client, choose_move)


def encode_turn_action(action: TurnAction) -> tuple[int, list[tuple[int, int, int, int, int]]]:
    moves = []

    for move in action.moves:
        x, y = move.source
        x_new, y_new = move.destination

        moves.append(
            (x, y, move.count, x_new, y_new)
        )

    return len(moves), moves


if __name__ == "__main__":
    main()