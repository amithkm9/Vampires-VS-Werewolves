import pytest

from vampires_ai.game.move import Move, TurnAction

def test_move_creation():
    move = Move(
        source=(3, 3),
        destination=(4, 4),
        count=5,
    )

    assert move.source == (3, 3)
    assert move.destination == (4, 4)
    assert move.count == 5

def test_move_rejects_zero_count():
    with pytest.raises(ValueError):
        Move((3, 3), (4, 4), 0)

def test_move_rejects_negative_count():
    with pytest.raises(ValueError):
        Move((3, 3), (4, 4), -5)

def test_move_rejects_boolean_count():
    with pytest.raises(TypeError):
        Move((3, 3), (4, 4), True)

def test_move_rejects_list_corrdinates():
    with pytest.raises(TypeError):
        Move(
            source=[3, 3],
            destination=(4, 4),
            count=5,
        )

def test_move_rejects_wrong_coordinate_length():
    with pytest.raises(TypeError):
        Move(
            source=(3, 3, 3),
            destination=(4, 4),
            count=5,
        )

def test_move_rejects_boolean_corrdinates():
    with pytest.raises(TypeError):
        Move(
            source=(True, 3),
            destination=(4, 4),
            count=5,
        )

# Test TurnAction
def test_turn_action_creation():
    move_1 = Move((3, 3), (4, 4), 5)
    move_2 = Move((3, 3), (2, 3), 3)

    action = TurnAction(
        moves=(move_1, move_2)
    )

    assert len(action.moves) == 2
    assert action.moves[0] == move_1
    assert action.moves[1] == move_2

def test_turn_action_rejects_empty_moves():
    with pytest.raises(ValueError):
        TurnAction(moves=())

def test_turn_action_rejects_invalid_move():
    with pytest.raises(TypeError):
        TurnAction(
            moves=(
                Move((3, 3), (4, 4), 5),
                "hello",
            )
        )