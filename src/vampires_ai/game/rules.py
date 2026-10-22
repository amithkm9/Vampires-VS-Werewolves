from vampires_ai.game.state import GameState
from vampires_ai.game.move import Move, TurnAction

from itertools import combinations
from itertools import product

def are_adjacent(
        source: tuple[int, int],
        destination: tuple[int, int],
) -> bool:

    x1, y1 = source
    x2, y2 = destination

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)

    return max(dx, dy) == 1

def is_within_bounds(
        state: GameState,
        position: tuple[int, int],
) -> bool:
    x, y = position

    return (
        0 <= x < state.width
        and 0 <= y < state.height
    )

def belongs_to_current_player(
        state: GameState,
        position: tuple[int, int],
) -> bool:

    cell = state.get_cell(*position)

    if cell is None:
        return False

    return cell.species == state.current_player

def has_sufficient_population(
        state: GameState,
        action: TurnAction,
) -> bool:

    outgoing = {}

    for move in action.moves:
        source = move.source

        outgoing[source] = outgoing.get(source, 0) + move.count

    for source, total_count in outgoing.items():
        cell = state.get_cell(*source)

        if cell is None:
             return False

        if total_count > cell.count:
            return False

    return True

def has_no_source_destination_conflict(
        action: TurnAction,
) -> bool:

    source = set()
    destination = set()

    for move in action.moves:
        source.add(move.source)
        destination.add(move.destination)

    return source.isdisjoint(destination)

def is_legal_action(
        state: GameState,
        action: TurnAction,
) -> bool:

    # Rule 1: Check every individual move
    for move in action.moves:

        # Both positions must be inside the board
        if not is_within_bounds(state, move.source):
            return False

        if not is_within_bounds(state, move.destination):
            return False

        # Movement must be to one of the 8 neighboring cells
        if not are_adjacent(move.source, move.destination):
            return False

        # The source must belong to the current player
        if not belongs_to_current_player(state, move.source):
            return False

    # Rule 2: Check the complete turn action
    if not has_sufficient_population(state, action):
        return False

    if not has_no_source_destination_conflict(action):
        return False

    return True

def generate_single_move_actions(
        state: GameState,
) -> list[TurnAction]:

    actions = []

    for position, cell in state.board:

        if cell.species != state.current_player:
            continue

        x, y = position

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):

                if dx == 0 and dy == 0:
                    continue

                destination = (x + dx, y + dy)

                if not is_within_bounds(state, destination):
                    continue

                for count in range(1, cell.count + 1):

                    move = Move(
                        source=position,
                        destination=destination,
                        count=count
                    )

                    action = TurnAction(moves=(move,))

                    if is_legal_action(state, action):
                        actions.append(action)

    return actions

def generate_two_way_split_actions(
    state: GameState,
) -> list[TurnAction]:

    actions = []

    for position, cell in state.board:

        if cell.species != state.current_player:
            continue

        if cell.count < 2:
            continue

        x, y = position

        destinations = []

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):

                if dx == 0 and dy == 0:
                    continue

                destination = (x + dx, y + dy)

                if is_within_bounds(state, destination):
                    destinations.append(destination)

        for i in range(len(destinations)):
            for j in range(i + 1, len(destinations)):

                destination_1 = destinations[i]
                destination_2 = destinations[j]

                for count_1 in range(1, cell.count):
                    for count_2 in range(
                        1,
                        cell.count - count_1 + 1,
                    ):

                        action = TurnAction(
                            moves=(
                                Move(position, destination_1, count_1),
                                Move(position, destination_2, count_2),
                            )
                        )

                        if is_legal_action(state, action):
                            actions.append(action)

    return actions

def generate_population_allocations(
    population: int,
    num_directions: int,
) -> list[tuple[int, ...]]:

    allocations = []

    def backtrack(
        remaining: int,
        current: tuple[int, ...],
    ) -> None:

        if len(current) == num_directions:
            allocations.append(current)
            return

        directions_left = num_directions - len(current)

        max_count = remaining - (directions_left - 1)

        for count in range(1, max_count + 1):
            backtrack(
                remaining - count,
                current + (count,),
            )

    if num_directions <= 0:
        return []

    if population < num_directions:
        return []

    backtrack(population, ())

    return allocations

def generate_split_actions(
        state: GameState,
) -> list[TurnAction]:

    actions = []

    for position, cell in state.board:

        if cell.species != state.current_player:
            continue

        if cell.count < 2:
            continue

        x, y = position

        destinations = []

        # Find neighboring destinations
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):

                if dx == 0 and dy == 0:
                    continue

                destination = (x + dx, y + dy)

                if is_within_bounds(state, destination):
                    destinations.append(destination)

        max_directions = min(
            len(destinations),
            cell.count
        )

        # Select 2 or more destinations
        for num_directions in range(2, max_directions + 1):

            for selected in combinations(
                destinations,
                num_directions,
            ):

                allocations = generate_population_allocations(
                    cell.count,
                    num_directions,
                )

                for allocation in allocations:

                    moves = tuple(
                        Move(position, destination, count)
                        for destination, count in zip(
                            selected,
                            allocation
                        )
                    )

                    action = TurnAction(moves=moves)

                    if is_legal_action(state, action):
                        actions.append(action)

    return actions

def combine_actions(
        state: GameState,
        action_1: TurnAction,
        action_2: TurnAction,
) -> TurnAction | None:

    combined = TurnAction(
        moves=action_1.moves + action_2.moves
    )

    if is_legal_action(state, combined):
        return combined

    return None

def merge_selected_actions(
        state: GameState,
        selected: tuple[TurnAction, ...],
) -> TurnAction | None:

    combined_moves = ()

    for action in selected:
        combined_moves += action.moves

    if not combined_moves:
        return None

    combined = TurnAction(moves=combined_moves)

    if is_legal_action(state, combined):
        return combined

    return None

def group_actions_by_source(
    actions: list[TurnAction],
) -> dict[tuple[int, int], list[TurnAction]]:

    grouped = {}

    for action in actions:
        source = action.moves[0].source

        if source not in grouped:
            grouped[source] = []

        grouped[source].append(action)

    return grouped

def generate_multi_source_actions(
        state: GameState,
) -> list[TurnAction]:

    single_actions = generate_single_move_actions(state)
    split_actions = generate_split_actions(state)

    all_actions = single_actions + split_actions

    grouped = group_actions_by_source(all_actions)

    action_groups = []

    for actions in grouped.values():
        choices = actions + [None]
        action_groups.append(choices)

    results = set()

    for combination in product(*action_groups):

        selected = tuple(
            action
            for action in combination
            if action is not None
        )

        if not selected:
            continue

        merged = merge_selected_actions(state, selected)

        if merged is not None:
            results.add(merged)

    return list(results)