import pytest

from vampires_ai.game.state import GameState, Cell, Species
from vampires_ai.game.move import Move, TurnAction
from vampires_ai.game.rules import is_legal_action
from vampires_ai.game.transition import apply_turn


def test_apply_turn_switches_vampire_to_werewolf():
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
            Move(
                source=(1, 1),
                destination=(2, 1),
                count=3,
            ),
        )
    )

    new_state = apply_turn(state, action)

    assert new_state.current_player == Species.WEREWOLF

def test_apply_turn_multiple_moves_from_same_source():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move(
                source=(1, 1),
                destination=(2, 1),
                count=4,
            ),
            Move(
                source=(1, 1),
                destination=(1, 2),
                count=6,
            ),
        )
    )

    new_state = apply_turn(state, action)

    # Source should be empty
    assert new_state.get_cell(1, 1) is None

    # First destination should contain 4 Vampires
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 4)

    # Second destination should contain 6 Vampires
    assert new_state.get_cell(1, 2) == Cell(Species.VAMPIRE, 6)

    # Current player should switch to WEREWOLF
    assert new_state.current_player == Species.WEREWOLF

    # Original state should remain unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.current_player == Species.VAMPIRE

def test_apply_turn_rejects_overcommitted_source():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move(
                source=(1, 1),
                destination=(2, 1),
                count=7,
            ),
            Move(
                source=(1, 1),
                destination=(1, 2),
                count=5,
            ),
        )
    )

    with pytest.raises(ValueError, match="Illegal turn action"):
        apply_turn(state, action)

    # Verify original source is unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)

    # Verify first destination is still empty
    assert state.get_cell(2, 1) is None

    # Verify second destination is still empty
    assert state.get_cell(1, 2) is None

    # Verify current player is unchanged
    assert state.current_player == Species.VAMPIRE

def test_apply_turn_rejects_source_destination_conflict():
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
            Move((1, 1), (2, 1), 5),
            Move((2, 1), (3, 1), 5),
        )
    )

    with pytest.raises(ValueError, match="Illegal turn action"):
        apply_turn(state, action)

    # Verify original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 1) is None
    assert state.get_cell(3, 1) is None
    assert state.current_player == Species.VAMPIRE

def test_apply_turn_move_order_independence():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (2, 1): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.VAMPIRE,
    )

    move_a = Move((1, 1), (1, 2), 5)
    move_b = Move((2, 1), (3, 1), 5)

    action_ab = TurnAction(moves=(move_a, move_b))
    action_ba = TurnAction(moves=(move_b, move_a))

    result_ab = apply_turn(state, action_ab)
    result_ba = apply_turn(state, action_ba)

    assert result_ab == result_ba

    assert result_ab.get_cell(1, 1) is None
    assert result_ab.get_cell(2, 1) is None

    assert result_ab.get_cell(1, 2) == Cell(Species.VAMPIRE, 5)
    assert result_ab.get_cell(3, 1) == Cell(Species.VAMPIRE, 5)

    assert result_ab.current_player == Species.WEREWOLF

def test_multiple_moves_can_share_destination():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.WEREWOLF, 6),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    assert is_legal_action(state, action)

def test_apply_turn_multiple_moves_to_same_empty_destination():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    # First source
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 2)

    # Second source
    assert new_state.get_cell(3, 3) == Cell(Species.VAMPIRE, 1)

    # Shared destination
    assert new_state.get_cell(2, 2) == Cell(Species.VAMPIRE, 7)

    # Next player
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(3, 3) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 2) is None

def test_apply_turn_multiple_moves_to_occupied_friendly_cell():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    # Verify both sources
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 2)
    assert new_state.get_cell(3, 3) == Cell(Species.VAMPIRE, 1)

    # Verify friendly destination
    assert new_state.get_cell(2, 2) == Cell(Species.VAMPIRE, 9)

    # Verify player switching
    assert new_state.current_player == Species.WEREWOLF

    # Verify original state
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(3, 3) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 2) == Cell(Species.VAMPIRE, 2)
    assert state.current_player == Species.VAMPIRE

def test_apply_turn_shared_destination_order_independence():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    move_a = Move((1, 1), (2, 2), 3)
    move_b = Move((3, 3), (2, 2), 4)

    action_ab = TurnAction(moves=(move_a, move_b))
    action_ba = TurnAction(moves=(move_b, move_a))

    result_ab = apply_turn(state, action_ab)
    result_ba = apply_turn(state, action_ba)

    # Both actions should produce identical states
    assert result_ab == result_ba

    # Destination should contain 9 Vampires
    assert result_ab.get_cell(2, 2) == Cell(Species.VAMPIRE, 9)

    # Original destination should remain unchanged
    assert state.get_cell(2, 2) == Cell(Species.VAMPIRE, 2)

    # Current player should switch to WEREWOLF
    assert result_ab.current_player == Species.WEREWOLF

def test_apply_turn_switches_werewolf_to_vampire():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.WEREWOLF, 8),
        },
        current_player=Species.WEREWOLF,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 1), 3),
        )
    )

    new_state = apply_turn(state, action)

    # Source after movement
    assert new_state.get_cell(1, 1) == Cell(Species.WEREWOLF, 5)

    # Destination after movement
    assert new_state.get_cell(2, 1) == Cell(Species.WEREWOLF, 3)

    # Next player
    assert new_state.current_player == Species.VAMPIRE

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.WEREWOLF, 8)
    assert state.current_player == Species.WEREWOLF

def test_apply_turn_illegal_action_does_not_switch_player():
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
            Move((1, 1), (2, 1), 6),
        )
    )

    original_state = state

    with pytest.raises(ValueError, match="Illegal turn action"):
        apply_turn(state, action)

    # Original player remains VAMPIRE
    assert state.current_player == Species.VAMPIRE

    # Original source remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)

    # Original destination remains empty
    assert state.get_cell(2, 1) is None

    # Original state remains unchanged
    assert state == original_state

def test_apply_turn_resolves_guaranteed_monster_battle():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.WEREWOLF, 3),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 1), 10),
        )
    )

    new_state = apply_turn(state, action)

    # Source becomes empty
    assert new_state.get_cell(1, 1) is None

    # Vampires win the battle
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 10)

    # Player switches
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.WEREWOLF, 3)

def test_apply_turn_resolves_guaranteed_human_battle():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
            (2, 1): Cell(Species.HUMAN, 3),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 1), 10),
        )
    )

    new_state = apply_turn(state, action)

    # Source becomes empty
    assert new_state.get_cell(1, 1) is None

    # Humans are converted into Vampires
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 13)

    # Player switches
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) == Cell(Species.HUMAN, 3)
    assert state.current_player == Species.VAMPIRE

def test_apply_turn_combines_attackers_before_monster_battle():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.WEREWOLF, 4),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 2)
    assert new_state.get_cell(3, 3) == Cell(Species.VAMPIRE, 1)
    assert new_state.get_cell(2, 2) == Cell(Species.VAMPIRE, 7)
    assert new_state.current_player == Species.WEREWOLF

    # Original state must remain unchanged.
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(3, 3) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 2) == Cell(Species.WEREWOLF, 4)

def test_apply_turn_combines_moves_to_empty_destination():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    # Both groups arrive at the same empty destination.
    assert new_state.get_cell(2, 2) == Cell(Species.VAMPIRE, 7)

    # Sources lose only the units they sent.
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 2)
    assert new_state.get_cell(3, 3) == Cell(Species.VAMPIRE, 1)

    # Player switches after the complete turn.
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged.
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(3, 3) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 2) is None

def test_apply_turn_combines_moves_with_friendly_destination():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.VAMPIRE, 2),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    # Both incoming groups merge with existing friendly units.
    assert new_state.get_cell(2, 2) == Cell(Species.VAMPIRE, 9)

    # Source counts are updated correctly.
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 2)
    assert new_state.get_cell(3, 3) == Cell(Species.VAMPIRE, 1)

    # Player switches after the complete turn.
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged.
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(3, 3) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 2) == Cell(Species.VAMPIRE, 2)

def test_apply_turn_combines_attackers_before_human_battle():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.HUMAN, 6),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 2), 3),
            Move((3, 3), (2, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    # Combined attackers convert all humans.
    assert new_state.get_cell(2, 2) == Cell(Species.VAMPIRE, 13)

    # Sources retain their remaining units.
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 2)
    assert new_state.get_cell(3, 3) == Cell(Species.VAMPIRE, 1)

    # Player switches after the complete turn.
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged.
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(3, 3) == Cell(Species.VAMPIRE, 5)
    assert state.get_cell(2, 2) == Cell(Species.HUMAN, 6)

def test_apply_turn_splits_one_source_across_destinations():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 10),
        },
        current_player=Species.VAMPIRE,
    )

    action = TurnAction(
        moves=(
            Move((1, 1), (2, 1), 3),
            Move((1, 1), (1, 2), 4),
        )
    )

    new_state = apply_turn(state, action)

    # Source loses the total number of moved units.
    assert new_state.get_cell(1, 1) == Cell(Species.VAMPIRE, 3)

    # Both destinations receive the correct number of units.
    assert new_state.get_cell(2, 1) == Cell(Species.VAMPIRE, 3)
    assert new_state.get_cell(1, 2) == Cell(Species.VAMPIRE, 4)

    # Player switches after the complete turn.
    assert new_state.current_player == Species.WEREWOLF

    # Original state remains unchanged.
    assert state.get_cell(1, 1) == Cell(Species.VAMPIRE, 10)
    assert state.get_cell(2, 1) is None
    assert state.get_cell(1, 2) is None

def test_apply_turn_shared_destination_is_order_independent():
    state = GameState.from_dict(
        width=5,
        height=5,
        board={
            (1, 1): Cell(Species.VAMPIRE, 5),
            (3, 3): Cell(Species.VAMPIRE, 5),
            (2, 2): Cell(Species.WEREWOLF, 4),
        },
        current_player=Species.VAMPIRE,
    )

    move_a = Move((1, 1), (2, 2), 3)
    move_b = Move((3, 3), (2, 2), 4)

    action_a = TurnAction(moves=(move_a, move_b))
    action_b = TurnAction(moves=(move_b, move_a))

    result_a = apply_turn(state, action_a)
    result_b = apply_turn(state, action_b)

    # Reordering moves to the same destination
    # must not change the deterministic result.
    assert result_a == result_b

    assert result_a.get_cell(2, 2) == Cell(
        Species.VAMPIRE, 7
    )

    assert result_a.get_cell(1, 1) == Cell(
        Species.VAMPIRE, 2
    )

    assert result_a.get_cell(3, 3) == Cell(
        Species.VAMPIRE, 1
    )