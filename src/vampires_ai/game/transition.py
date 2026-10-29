from vampires_ai.game.state import GameState, Cell
from vampires_ai.game.move import Move, TurnAction

from vampires_ai.game.rules import is_legal_action

def apply_move(
        state: GameState,
        move: Move,
) -> GameState:
    """Apply one non-combat move and return a new immutable game state."""

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
    else:
        raise ValueError("Combat is not supported yet")

    # Return a new GameState
    return GameState.from_dict(
        width=state.width,
        height=state.height,
        board=new_board,
        current_player=state.current_player,
    )