from vampires_ai.game.battle import resolve_battle, resolve_human_battle
from vampires_ai.game.move import Move, TurnAction
from vampires_ai.game.rules import is_legal_action
from vampires_ai.game.state import Cell, GameState, Species


def apply_move(
        state: GameState,
        move: Move,
) -> GameState:
    """
    Apply a legal move and return a new game state.

    Handles movement, friendly merging, monster battles,
    and human battles without modifying the original state.

    The current player remains unchanged.
    """

    action = TurnAction(moves=(move,))

    if not is_legal_action(state, action):
        raise ValueError("Illegal move")

    new_board = dict(state.board)

    source_cell = new_board[move.source]
    target_cell = new_board.get(move.destination)

    remaining = source_cell.count - move.count

    # Update source cell
    if remaining == 0:
        del new_board[move.source]
    else:
        new_board[move.source] = Cell(
            species=source_cell.species,
            count=remaining,
        )

    # Update destination cell
    if target_cell is None:
        new_board[move.destination] = Cell(
            species=source_cell.species,
            count=move.count,
        )
    elif target_cell.species == source_cell.species:
        new_count = target_cell.count + move.count
        new_board[move.destination] = Cell(
            species=target_cell.species,
            count=new_count
        )
    elif target_cell.species == Species.HUMAN:
        result = resolve_human_battle(
            attackers=move.count,
            humans=target_cell.count,
        )

        if result.attacker_wins:
            new_count = (
                result.surviving_attackers
                + result.converted_humans
            )

            if new_count == 0:
                del new_board[move.destination]
            else:
                new_board[move.destination] = Cell(
                    species=source_cell.species,
                    count=new_count,
                )
        else:
            if result.surviving_humans == 0:
                del new_board[move.destination]
            else:
                new_board[move.destination] = Cell(
                    species=target_cell.species,
                    count=result.surviving_humans
                )
    else:
        result = resolve_battle(
            attackers=move.count,
            defenders=target_cell.count,
        )

        if result.survivors == 0:
            del new_board[move.destination]

        elif result.attacker_wins:
            new_board[move.destination] = Cell(
                species=source_cell.species,
                count=result.survivors,
            )
        else:
            new_board[move.destination] = Cell(
                species=target_cell.species,
                count=result.survivors,
            )

    # Return a new GameState
    return GameState.from_dict(
        width=state.width,
        height=state.height,
        board=new_board,
        current_player=state.current_player,
    )