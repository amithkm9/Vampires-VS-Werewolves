from vampires_ai.game.state import GameState, Cell, Species
from vampires_ai.game.move import Move, TurnAction

from vampires_ai.game.rules import (
    are_adjacent, 
    is_within_bounds, 
    belongs_to_current_player,
    has_sufficient_population,
    has_no_source_destination_conflict,
    is_legal_action,
    generate_single_move_actions,
    generate_two_way_split_actions,
    generate_split_actions,
    generate_population_allocations,
    combine_actions,
    merge_selected_actions,
    generate_multi_source_actions,
    canonicalize_action,
)

def test_are_adjacent():
    assert are_adjacent((3, 3), (4, 4))
    assert are_adjacent((3, 3), (2, 3))
    assert are_adjacent((3, 3), (3, 4))


def test_not_adjacent():
    assert not are_adjacent((3, 3), (3, 3))
    assert not are_adjacent((3, 3), (5, 3))
    assert not are_adjacent((3, 3), (5, 5))

def test_position_within_bounds():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={},
        current_player=Species.VAMPIRE,
    )

    assert is_within_bounds(state, (0, 0))
    assert is_within_bounds(state, (2, 2))
    assert is_within_bounds(state, (4, 4))

def test_position_outside_bounds():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={},
        current_player=Species.VAMPIRE,
    )

    assert not is_within_bounds(state, (-1, 0))
    assert not is_within_bounds(state, (0, -1))
    assert not is_within_bounds(state, (5, 0))
    assert not is_within_bounds(state, (0, 5))

# Test current player
def test_position_belongs_to_current_player():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.WEREWOLF, 4),
        },
        current_player=Species.VAMPIRE,
    )

    assert belongs_to_current_player(state, (1, 1))

def test_position_belongs_to_opponent():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.WEREWOLF, 4),
        },
        current_player=Species.VAMPIRE,
    )

    assert not belongs_to_current_player(state, (3, 3))

# Empty Position doesn't belong to current player
def test_empty_position_does_not_belong_to_player():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.VAMPIRE,
    )

    assert not belongs_to_current_player(state, (4, 4))

def test_sufficient_population():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (2, 2): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((2, 2), (3, 3), 5),
            Move((2, 2), (1, 2), 3),
        )
    )

    assert has_sufficient_population(state, action)

def test_insufficient_population():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (2, 2): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((2, 2), (3, 3), 5),
            Move((2, 2), (1, 2), 6),
        )
    )

    assert not has_sufficient_population(state, action)

def test_population_missing_source():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={},
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((2, 2), (3, 3), 5),
        )
    )

    assert not has_sufficient_population(state, action)

def test_no_source_destination_conflict():
    action = TurnAction(
        moves=(
            Move((1, 1), (1, 2), 3),
            Move((3, 3), (3, 4), 2),
        )
    )

    assert has_no_source_destination_conflict(action)

def test_source_destinaton_conflict():
    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((2, 2), (3, 3), 2),
        )
    )

    assert not has_no_source_destination_conflict(action)

def test_multiple_moves_same_source_no_conflict():
    action = TurnAction(
        moves=(
            Move((2, 2), (3, 3), 3),
            Move((2, 2), (1, 1), 2),
        )
    )

    assert has_no_source_destination_conflict(action)

def test_legal_action():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (2, 2): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((2, 2), (3, 3), 5),
            Move((2, 2), (1, 2), 3),
        )
    )

    assert is_legal_action(state, action)

def test_illegal_action_non_adjacent():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (4, 4), 3),
        )
    )

    assert not is_legal_action(state, action)

def test_illegal_action_insufficient_population():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (2, 2): Cell(Species.VAMPIRE, 8),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((2, 2), (3, 3), 5),
            Move((2, 2), (1, 2), 6),
        )
    )

    assert not is_legal_action(state, action)

def test_generate_single_move_actions_center():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (2, 2): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_single_move_actions(state)

    assert len(actions) == 16

    assert all(
        is_legal_action(state, action)
        for action in actions
    )

def test_generate_single_move_actions_corner():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (0, 0): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_single_move_actions(state)

    assert len(actions) == 6

    assert all(
        is_legal_action(state, action)
        for action in actions
    )

# Test split actions
def test_generate_two_way_split_actions():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (1, 1): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_two_way_split_actions(state)

    assert len(actions) == 28

    assert all(
        len(action.moves) == 2
        for action in actions
    )

    assert all(
        is_legal_action(state, action)
        for action in actions
    )

def test_cannot_split_single_unit():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (1, 1): Cell(Species.VAMPIRE, 1),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_two_way_split_actions(state)

    assert actions == []

def test_generate_population_allocations_three_directions():

    allocations = generate_population_allocations(
        population=4,
        num_directions=3,
    )

    expected = {
        (1, 1, 1),
        (1, 1, 2),
        (1, 2, 1),
        (2, 1, 1),
    }

    assert set(allocations) == expected

def test_generate_population_allocations_insufficient():

    allocations = generate_population_allocations(
        population=2,
        num_directions=3,
    )

    assert allocations == []

def test_generate_three_way_split_actions():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (1, 1): Cell(Species.VAMPIRE, 3),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_split_actions(state)

    three_way_actions = [
        action
        for action in actions
        if len(action.moves) == 3
    ]

    assert len(three_way_actions) == 56

def test_general_split_matches_two_way_split():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (1, 1): Cell(Species.VAMPIRE, 3),
        },
        current_player=Species.VAMPIRE,
    )

    general_actions = generate_split_actions(state)

    two_way_actions = generate_two_way_split_actions(state)

    general_two_way = {
        action
        for action in general_actions
        if len(action.moves) == 2
    }

    assert general_two_way == set(two_way_actions)

def test_general_split_single_unit():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (1, 1): Cell(Species.VAMPIRE, 1),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_split_actions(state)

    assert actions == []

def test_combine_actions_valid():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 3),
            (3, 3): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    # # Step 1: 创建 Move 对象
    # move_1 = Move((2, 2), (3, 2), 2)

    # # Step 2: 创建只包含一个 Move 的 tuple
    # moves_1 = (move_1,)

    # # Step 3: 创建 TurnAction 对象
    # action_1 = TurnAction(moves=moves_1)

    action_1 = TurnAction(
        moves=(Move((1, 1), (1, 2), 3),)
    )

    action_2 = TurnAction(
        moves=(Move((3, 3), (4, 3), 2),)
    )

    combined = combine_actions(state, action_1, action_2)

    assert combined is not None
    assert len(combined.moves) == 2
    assert is_legal_action(state, combined)

def test_combine_actions_insufficient_population():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (2, 2): Cell(Species.VAMPIRE, 3)
        },
        current_player=Species.VAMPIRE,
    )

    action_1 = TurnAction(
        moves=(Move((2, 2), (3, 2), 2),)
    )

    action_2 = TurnAction(
        moves=(Move((2, 2), (2, 3), 2),)
    )

    combined = combine_actions(state, action_1, action_2)

    assert combined is None

def test_merged_selected_actions_valid():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 3),
            (3, 3): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    action_1 = TurnAction(
        moves=(Move((1, 1), (1, 2), 3),)
    )

    action_2 = TurnAction(
        moves=(Move((3, 3), (4, 3), 2),)
    )

    merged = merge_selected_actions(
        state,
        (action_1, action_2)
    )

    assert merged is not None
    assert len(merged.moves) == 2
    assert is_legal_action(state, merged)

def test_merge_selected_actions_empty():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 3),
            (3, 3): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    merged = merge_selected_actions(state, ())

    assert merged is None

def test_generate_multi_source_actions():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 1),
            (3, 3): Cell(Species.VAMPIRE, 1),
        },
        current_player=Species.VAMPIRE
    )

    actions = generate_multi_source_actions(state)

    assert len(actions) > 0

    assert all(
        is_legal_action(state, action)
        for action in actions
    )

    # found = False

    # for action in actions:
    #     sources = set()

    #     for move in action.moves:
    #         sources.add(move.source)

    #     if len(sources) == 2:
    #         found = True
    #         break

    # assert found

    assert any(
        len({move.source for move in action.moves}) == 2
        for action in actions
    )

def test_generate_multi_source_actions_no_own_units():
    state = GameState.from_dict(
        width=3,
        height=3,
        board={
            (1, 1): Cell(Species.WEREWOLF, 3),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_multi_source_actions(state)

    assert actions == []

def test_generate_multi_source_actions_no_source_destination_conflict():
    state = GameState.from_dict(
        width=4,
        height=3,
        board={
            (1, 1): Cell(Species.VAMPIRE, 1),
            (2, 1): Cell(Species.VAMPIRE, 1),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_multi_source_actions(state)

    for action in actions:
        sources = {move.source for move in action.moves}
        destinations = {move.destination for move in action.moves}

        assert sources.isdisjoint(destinations)

def test_generate_multi_source_actions_no_duplicates():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 1),
            (3, 3): Cell(Species.VAMPIRE, 1),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_multi_source_actions(state)

    assert len(actions) == len(set(actions))

def test_canonicalize_action_order_independent():
    action_a = TurnAction(
        moves=(
            Move((1, 1), (1, 2), 1),
            Move((3, 3), (3, 4), 1),
        )
    )

    action_b = TurnAction(
        moves=(
            Move((3, 3), (3, 4), 1),
            Move((1, 1), (1, 2), 1),
        )
    )

    assert action_a != action_b

    assert canonicalize_action(action_a) == canonicalize_action(action_b)

def test_generate_multi_source_actions_are_canonical():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 1),
            (3, 3): Cell(Species.VAMPIRE, 1),
        },
        current_player=Species.VAMPIRE,
    )

    actions = generate_multi_source_actions(state)

    assert actions

    for action in actions:
        assert action == canonicalize_action(action)