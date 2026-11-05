import pytest

from unittest.mock import Mock, patch, call

from dataclasses import FrozenInstanceError

from vampires_ai.game.battle import BattleResult
from vampires_ai.game.battle import HumanBattleResult

from vampires_ai.game.battle import (
    battle_win_probability,
    simulate_battle,
    unit_survives,
    simulate_survivors,
    resolve_battle,
    expected_survivors,
    resolve_guaranteed_human_conversion,
    simulate_human_conversion,
    resolve_human_battle_victory,
    resolve_human_battle_defeat,
    resolve_human_battle,
    simulate_battle_with_probability,
    human_battle_win_probability,
)

def test_battle_win_probability_fewer_attackters():
    probability = battle_win_probability(4, 5)

    assert probability == pytest.approx(0.4)

def test_battle_win_probability_equal_population():
    probability = battle_win_probability(5, 5)

    assert probability == 0.5

def test_battle_win_probability_more_attackers():
    probability = battle_win_probability(6, 5)

    assert probability == 0.7

def test_battle_win_probability_guaranteed_win():
    probability = battle_win_probability(8, 5)

    assert probability == 1.0

def test_battle_win_probability_exact_threshold():
    probability = battle_win_probability(9, 6)

    assert probability == 1.0

def test_battle_win_probability_below_threshold():
    probability = battle_win_probability(8, 6)

    assert probability == pytest.approx(5 / 6)

def test_battle_win_probability_zero_defenders():
    with pytest.raises(ValueError):
        battle_win_probability(5, 0)

@pytest.mark.parametrize(
    "attackers, defenders",
    [
        (0, 5),
        (5, -2),
        (-3, 0),
    ],
)
def test_battle_win_probability_invalid_population(attackers, defenders):
    with pytest.raises(ValueError):
        battle_win_probability(attackers, defenders)

def test_battle_win_probability_float_population():
    with pytest.raises(TypeError):
        battle_win_probability(3.5, 5)

@pytest.mark.parametrize(
    "attackers, defenders",
    [
        ("3", 5),
        (3, "5"),
        (True, 5),
        (3, False),
    ],
)
def test_battle_win_probability_invalid_types(attackers, defenders):
    with pytest.raises(TypeError):
        battle_win_probability(attackers, defenders)

def test_simulate_battle_attacker_wins():
    result = simulate_battle(6, 5, random_number=0.2)

    assert result is True

def test_simulate_battle_defender_wins():
    result = simulate_battle(6, 5, random_number=0.9)

    assert result is False

def test_simulate_battle_random_equals_probability():
    result = simulate_battle(6, 5, random_number=0.7)

    assert result is False

def test_simulate_battle_invalid_random_number():
    with pytest.raises(ValueError):
        simulate_battle(6, 5, random_number=-0.5)

def test_simulate_battle_generates_random_number():
    with patch(
        "vampires_ai.game.battle.random.random",
        return_value=0.2,
    ) as mock_random:

        result = simulate_battle(
            attackers=5,
            defenders=6,
        )

        assert result is True

        mock_random.assert_called_once_with()

@pytest.mark.parametrize(
    "random_number",
    [
        1.0,
        1.5,
    ],
)
def test_simulate_battle_invalid_random_upper_bound(random_number):
    with pytest.raises(ValueError):
        simulate_battle(6, 5, random_number=random_number)

def test_simulate_battle_random_lower_boundary():
    result = simulate_battle(6, 5, random_number=0.0)

    assert result is True

def test_simulate_battle_nan_random_number():
    with pytest.raises(ValueError):
        simulate_battle(6, 5, random_number=float("nan"))

def test_simulate_battle_string_random_number():
    with pytest.raises(TypeError):
        simulate_battle(6, 5, random_number="0.2")

def test_simulate_battle_boolean_random_number():
    with pytest.raises(TypeError):
        simulate_battle(6, 5, random_number=True)

def test_battle_result_creation():
    result = BattleResult(
        attacker_wins=True,
        survivors=4,
    )

    assert result.attacker_wins is True
    assert result.survivors == 4

def test_battle_result_is_immutable():
    result = BattleResult(
        attacker_wins=True,
        survivors=4,
    )

    with pytest.raises(FrozenInstanceError):
        result.survivors = 10

def test_battle_result_negative_survivors():
    with pytest.raises(ValueError):
        BattleResult(
            attacker_wins=True,
            survivors=-5,
        )

def test_battle_result_float_survivors():
    with pytest.raises(TypeError):
        BattleResult(
            attacker_wins=True,
            survivors=3.5
        )

def test_battle_result_invalid_attacker_wins():
    with pytest.raises(TypeError):
        BattleResult(
            attacker_wins="yes",
            survivors=4,
        )

def test_battle_result_zero_survivors():
    result = BattleResult(
        attacker_wins=True,
        survivors=0,
    )

    assert result.survivors == 0

def test_unit_survives():
    result = unit_survives(
        survival_probability=0.7,
        random_number=0.2,
    )

    assert result is True

def test_simulate_survivors():
    survivors = simulate_survivors(
        population=3,
        survival_probability=0.6,
        random_numbers=(0.2, 0.8, 0.4),
    )

    assert survivors == 2

def test_simulate_survivors_mismatched_random_numbers():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, 0.2, 0.3, 0.4, 0.5),
        )

def test_simulate_survivors_invalid_population_type():
    with pytest.raises(TypeError):
        simulate_survivors(
            population=3.5,
            survival_probability=0.6,
            random_numbers=(0.1, 0.2, 0.3),
        )

def test_simulate_survivors_negative_population():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=-3,
            survival_probability=0.6,
            random_numbers=(0.1, 0.2, 0.3),
        )

def test_simulate_survivors_probability_above_one():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=1.5,
            random_numbers=(0.1, 0.2, 0.3),
        )

def test_simulate_survivors_negative_probability():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=-0.2,
            random_numbers=(0.1, 0.2, 0.3),
        )

def test_simulate_survivors_zero_probability():
    survivors = simulate_survivors(
        population=3,
        survival_probability=0.0,
        random_numbers=(0.1, 0.5, 0.9),
    )

    assert survivors == 0

# avoid potential Regression
def test_simulate_survivors_full_probability():
    survivors = simulate_survivors(
        population=4,
        survival_probability=1.0,
        random_numbers=(0.0, 0.3, 0.7, 0.99),
    )

    assert survivors == 4

@pytest.mark.parametrize(
    "invalid_probability",
    [
        "0.5",
        None,
        True,
    ],
)
def test_simulate_survivors_invalid_probability_type(
    invalid_probability,
):
    with pytest.raises(
        TypeError,
        match="Survival probability must be numeric",
    ):
        simulate_survivors(
            population=5,
            survival_probability=invalid_probability,
        )

def test_simulate_survivors_nan_probability():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=float("nan"),
            random_numbers=(0.1, 0.2, 0.3),
        )

def test_simulate_survivors_random_number_above_range():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, 1.0, 0.3),
        )

def test_simulate_survivors_negative_random_number():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, -0.1, 0.3),
        )

def test_simulate_survivors_invalid_random_number_type():
    with pytest.raises(TypeError):
        simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, "0.2", 0.3),
        )

def test_simulate_survivors_nan_random_number():
    with pytest.raises(ValueError):
        simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, float("nan"), 0.3),
        )

def test_simulate_survivors_boolean_random_number():
    with pytest.raises(TypeError):
        simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, True, 0.3),
        )

def test_simulate_survivors_automatic_random_numbers():
    survivors = simulate_survivors(
        population=3,
        survival_probability=1.0,
    )

    assert survivors == 3

def test_simulate_survivors_mock_random():
    with patch(
        "vampires_ai.game.battle.random.random",
        side_effect=[0.2, 0.8, 0.4],
    ) as mock_random:

        survivors = simulate_survivors(
            population=3,
            survival_probability=0.6,
        )

        assert survivors == 2
        assert mock_random.call_count == 3

def test_simulate_survivors_zero_population_no_random_calls():
    with patch(
        "vampires_ai.game.battle.random.random"
    ) as mock_random:

        survivors = simulate_survivors(
            population=0,
            survival_probability=0.6,
        )

        assert survivors == 0
        mock_random.assert_not_called()

def test_simulate_survivors_one_random_call():
    with patch(
        "vampires_ai.game.battle.random.random",
        return_value=0.2,
    ) as mock_random:

        survivors = simulate_survivors(
            population=1,
            survival_probability=0.6,
        )

        assert survivors == 1
        mock_random.assert_called_once()

def test_simulate_survivors_random_called_once_with_no_arguments():
    with patch(
        "vampires_ai.game.battle.random.random",
        return_value=0.2,
    ) as mock_random:

        survivors = simulate_survivors(
            population=1,
            survival_probability=0.6,
        )

        assert survivors == 1
        mock_random.assert_called_once_with()

def test_mock_assert_any_call():

    mock_function = Mock()

    mock_function(1)
    mock_function(2)
    mock_function(3)

    mock_function.assert_any_call(2)

def test_mock_call_args_list():

    mock_function = Mock()

    mock_function("Vampire", 3)
    mock_function("Werewolf", 5)
    mock_function("Vampire", 7)

    assert mock_function.call_args_list == [
        call("Vampire", 3),
        call("Werewolf", 5),
        call("Vampire", 7),
    ]

def test_mock_assert_has_calls():

    mock_function = Mock()

    mock_function(10)
    mock_function(20)
    mock_function(30)
    mock_function(40)

    mock_function.assert_has_calls([
        call(20),
        call(30),
    ])

def test_mock_assert_has_calls_non_consecutive():

    mock_function = Mock()

    mock_function(10)
    mock_function(20)
    mock_function(30)
    mock_function(40)

    with pytest.raises(AssertionError):
        mock_function.assert_has_calls([
            call(20),
            call(40),
        ])

def test_mock_assert_has_calls_any_order():

    mock_function = Mock()

    mock_function(10)
    mock_function(20)
    mock_function(30)
    mock_function(40)

    mock_function.assert_has_calls(
        [
            call(40),
            call(20),
        ],
        any_order=True,
    )

def test_simulate_survivors_calls_unit_survives():
    with patch(
        "vampires_ai.game.battle.unit_survives",
        return_value=True,
    ) as mock_unit_survives:

        survivors = simulate_survivors(
            population=1,
            survival_probability=0.6,
            random_numbers=(0.2,),
        )

        assert survivors == 1

        mock_unit_survives.assert_called_once_with(
            0.6,
            0.2,
        )

def test_simulate_survivors_mock_mixed_results():
    with patch(
        "vampires_ai.game.battle.unit_survives",
        side_effect=[True, False, True],
    ) as mock_unit_survives:

        survivors = simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, 0.7, 0.3),
        )

        assert survivors == 2

        assert mock_unit_survives.call_count == 3

def test_simulate_survivors_unit_survives_calls():

    with patch(
        "vampires_ai.game.battle.unit_survives",
        side_effect=[True, False, True],
    ) as mock_unit_survives:

        survivors = simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, 0.7, 0.3),
        )

        assert survivors == 2

        mock_unit_survives.assert_has_calls(
            [
                call(0.6, 0.1),
                call(0.6, 0.7),
                call(0.6, 0.3),
            ]
        )

def test_simulate_survivors_exact_unit_survives_calls():

    with patch(
        "vampires_ai.game.battle.unit_survives",
        side_effect=[True, False, True],
    ) as mock_unit_survives:

        survivors = simulate_survivors(
            population=3,
            survival_probability=0.6,
            random_numbers=(0.1, 0.7, 0.3),
        )

        assert survivors == 2

        assert mock_unit_survives.call_args_list == [
            call(0.6, 0.1),
            call(0.6, 0.7),
            call(0.6, 0.3),
        ]

def test_resolve_battle_attacker_wins():
    result = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.2,
        survival_random_numbers=(
            0.1,
            0.2,
            0.4,
            0.8,
            0.9,
        ),
    )

    assert result == BattleResult(
        attacker_wins=True,
        survivors=3,
    )

def test_resolve_battle_defender_wins():
    result = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.8,
        survival_random_numbers=(
            0.1,
            0.2,
            0.4,
            0.6,
            0.8,
            0.9,
        ),
    )

    assert result == BattleResult(
        attacker_wins=False,
        survivors=3,
    )

def test_resolve_battle_deterministic_victory():
    result = resolve_battle(
        attackers=6,
        defenders=4,
        battle_random_number=0.9,
        survival_random_numbers=(0.1, 0.3, 0.5, 0.7, 0.9, 0.99,),
    )

    assert result == BattleResult(
        attacker_wins=True,
        survivors=6,
    )

def test_resolve_battle_invalid_battle_random_number():
    with pytest.raises(ValueError):
        resolve_battle(
            attackers=6,
            defenders=4,
            battle_random_number=1.0,
        )

def test_resolve_battle_invalid_survival_random_number():
    with pytest.raises(
        ValueError,
        match=r"Random number must be in \[0, 1\)",
    ):
        resolve_battle(
            attackers=5,
            defenders=6,
            battle_random_number=0.2,
            survival_random_numbers=(
                0.1,
                0.2,
                0.4,
                0.8,
                1.0,
            ),
        )

def test_resolve_battle_calls_simulate_survivors():
    with patch(
        "vampires_ai.game.battle.simulate_survivors",
        return_value=2,
    ) as mock_survivors:

        random_numbers = (
            0.1,
            0.2,
            0.4,
            0.8,
            0.9,
        )

        result = resolve_battle(
            attackers=5,
            defenders=6,
            battle_random_number=0.2,
            survival_random_numbers=random_numbers,
        )

        assert result == BattleResult(
            attacker_wins=True,
            survivors=2,
        )

        mock_survivors.assert_called_once_with(
            5,
            pytest.approx(5 / 12),
            random_numbers,
        )

def test_resolve_battle_calls_simulate_survivors_defender_wins():
    with patch(
        "vampires_ai.game.battle.simulate_survivors",
        return_value=4,
    ) as mock_survivors:

        random_numbers = (
            0.1,
            0.2,
            0.3,
            0.4,
            0.5,
            0.6,
        )

        result = resolve_battle(
            attackers=5,
            defenders=6,
            battle_random_number=0.8,
            survival_random_numbers=random_numbers,
        )

        assert result == BattleResult(
            attacker_wins=False,
            survivors=4,
        )

        mock_survivors.assert_called_once_with(
            6,
            pytest.approx(7 / 12),
            random_numbers,
        )

def test_resolve_battle_invalid_random_skips_survivors():
    with patch(
        "vampires_ai.game.battle.simulate_survivors",
        return_value=3,
    ) as mock_survivors:

        with pytest.raises(ValueError):
            resolve_battle(
                attackers=4,
                defenders=6,
                battle_random_number=1.0,
                survival_random_numbers=(0.1, 0.2, 0.3, 0.4),
            )

        mock_survivors.assert_not_called()

def test_resolve_battle_invalid_random_skips_survivors():
    with patch(
        "vampires_ai.game.battle.simulate_survivors",
        return_value=3,
    ) as mock_survivors:

        with pytest.raises(ValueError):
            resolve_battle(
                attackers=4,
                defenders=6,
                battle_random_number=1.0,
                survival_random_numbers=(0.1, 0.2, 0.3, 0.4),
            )

        mock_survivors.assert_not_called()

def test_caught_exception_allows_execution_to_continue():
    events = []

    try:
        events.append("A")
        raise ValueError("Error!")
        events.append("B")

    except ValueError:
        events.append("C")

    events.append("D")

    assert events == ["A", "C", "D"]

def test_finally_runs_without_exception():
    events = []

    try:
        events.append("A")
        events.append("B")

    finally:
        events.append("C")

    assert events == ["A", "B", "C"]

def test_finally_does_not_suppress_exception():
    events = []

    with pytest.raises(ValueError):
        try:
            events.append("A")
            raise ValueError("Error!")

        except TypeError:
            events.append("B")

        finally:
            events.append("C")

    assert events == ["A", "C"]

def test_resolve_battle_defender_survivors():
    result = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.8,
        survival_random_numbers=(
            0.1,
            0.2,
            0.3,
            0.6,
            0.7,
            0.9,
        ),
    )

    assert result == BattleResult(
        attacker_wins=False,
        survivors=3,
    )

def test_resolve_battle_attacker_wins_zero_survivors():
    result = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.2,
        survival_random_numbers=(
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
        ),
    )

    assert result == BattleResult(
        attacker_wins=True,
        survivors=0,
    )

def test_resolve_battle_defender_wins_zero_survivors():
    result = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.8,
        survival_random_numbers=(
            0.7,
            0.8,
            0.9,
            0.95,
            0.99,
            0.999,
        ),
    )

    assert result == BattleResult(
        attacker_wins=False,
        survivors=0,
    )

def test_unit_survives_equal_probability():
    result = unit_survives(
        survival_probability=0.5,
        random_number=0.5,
    )

    assert result is False

def test_simulate_battle_equal_probability_boundary():
    result = simulate_battle(
        attackers=4,
        defenders=4,
        random_number=0.5,
    )

    assert result is False

@pytest.mark.parametrize(
    "random_number, expected",
    [
        (0.49, True),
        (0.50, False),
        (0.51, False),
    ]
)
def test_simulate_battle_probability_boundary(
    random_number,
    expected,
):
    result = simulate_battle(
        attackers=4,
        defenders=4,
        random_number=random_number,
    )

    assert result is expected

@pytest.mark.parametrize(
    "attackers, defenders, expected",
    [
        (4, 4, 0.5),
        (6, 4, 1.0),
        (4, 5, 0.4),
        (2, 4, 0.0),
        (4, 2, 1.0),
    ],
)
def test_battle_probability_parametrized(
    attackers,
    defenders,
    expected,
):
    result = battle_win_probability(
        attackers,
        defenders,
    )

    assert result == pytest.approx(expected)

@pytest.mark.parametrize(
    "population, probability, expected",
    [
        (0, 0.5, 0),
        (3, 0.0, 0),
        (3, 1.0, 3),
        (5, 1.0, 5),
        (10, 0.0, 0),
    ],
)
def test_simulate_survivors_extreme_probabilities(
    population,
    probability,
    expected,
):
    result = simulate_survivors(
        population=population,
        survival_probability=probability,
    )

    assert result == expected

def test_simulate_survivors_is_deterministic_with_fixed_random_numbers():
    random_numbers = (0.1, 0.2, 0.7, 0.8)

    first_result = simulate_survivors(
        population=4,
        survival_probability=0.5,
        random_numbers=random_numbers,
    )

    second_result = simulate_survivors(
        population=4,
        survival_probability=0.5,
        random_numbers=random_numbers,
    )

    assert first_result == 2
    assert second_result == 2
    assert first_result == second_result

def test_simulate_survivors_fixed_random_numbers_skip_random_generation():
    with patch(
        "vampires_ai.game.battle.random.random"
    ) as mock_random:

        result = simulate_survivors(
            population=4,
            survival_probability=0.5,
            random_numbers=(0.1, 0.4, 0.6, 0.9),
        )

        assert result == 2

        mock_random.assert_not_called()

def test_simulate_survivors_generates_one_random_number_per_unit():
    with patch(
        "vampires_ai.game.battle.random.random",
        return_value=0.2,
    ) as mock_random:

        result = simulate_survivors(
            population=4,
            survival_probability=0.5,
        )

        assert result == 4
        assert mock_random.call_count == 4

def test_simulate_survivors_with_mock_side_effect():
    with patch(
        "vampires_ai.game.battle.random.random",
        side_effect=[0.1, 0.7, 0.3, 0.9],
    ) as mock_random:

        result = simulate_survivors(
            population=4,
            survival_probability=0.5,
        )

        assert result == 2
        assert mock_random.call_count == 4

def test_simulate_survivors_propagates_random_generator_error():
    with patch(
        "vampires_ai.game.battle.random.random",
        side_effect=RuntimeError("Random generator failed"),
    ) as mock_random:

        with pytest.raises(
            RuntimeError,
            match="Random generator failed",
        ):
            simulate_survivors(
                population=4,
                survival_probability=0.5,
            )

        mock_random.assert_called_once()

def test_simulate_survivors_random_generator_fails_on_second_call():
    with patch(
        "vampires_ai.game.battle.random.random",
        side_effect=[
            0.1,
            RuntimeError("Generator failed"),
            0.3,
            0.4,
        ],
    ) as mock_random:

        with pytest.raises(
            RuntimeError,
            match="Generator failed",
        ):
            simulate_survivors(
                population=4,
                survival_probability=0.5,
            )

        assert mock_random.call_count == 2

def test_simulate_survivors_mock_side_effect_exhausted():
    with patch(
        "vampires_ai.game.battle.random.random",
        side_effect=[0.1, 0.2],
    ) as mock_random:

        # https://peps.python.org/pep-0479/?utm_source=chatgpt.com
        # “When StopIteration is raised inside a generator, it is replaced with RuntimeError.”
        with pytest.raises(
            RuntimeError,
            match="generator raised StopIteration",
        ):
            simulate_survivors(
                population=4,
                survival_probability=0.5,
            )

        assert mock_random.call_count == 3

def test_simulate_survivors_generator_error_cause():
    with patch(
        "vampires_ai.game.battle.random.random",
        side_effect=[0.1, 0.2],
    ) as mock_random:

        with pytest.raises(RuntimeError) as exc_info:
            simulate_survivors(
                population=4,
                survival_probability=0.5,
            )

        assert isinstance(
            exc_info.value.__cause__,
            StopIteration,
        )

        assert mock_random.call_count == 3

def test_explicit_exception_chaining():
    with pytest.raises(RuntimeError) as exc_info:
        try:
            raise ValueError("Original error")

        except ValueError as error:
            raise RuntimeError("New error") from error

    assert isinstance(
        exc_info.value.__cause__,
        ValueError,
    )

def test_implicit_exception_chaining():
    with pytest.raises(ValueError) as exc_info:
        try:
            raise TypeError("First error")

        except TypeError:
            raise ValueError("Second error")

    assert exc_info.value.__cause__ is None

    assert isinstance(
        exc_info.value.__context__,
        TypeError,
    )

def test_resolve_battle_is_deterministic_with_fixed_random_numbers():
    random_numbers = (0.1, 0.2, 0.4, 0.8, 0.9)

    result1 = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.2,
        survival_random_numbers=random_numbers,
    )

    result2 = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.2,
        survival_random_numbers=random_numbers,
    )

    assert result1 == result2

    assert result1 == BattleResult(
        attacker_wins=True,
        survivors=3,
    )

def test_resolve_battle_survivors_change_with_random_numbers():
    result1 = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.2,
        survival_random_numbers=(
            0.1,
            0.2,
            0.4,
            0.8,
            0.9,
        ),
    )

    result2 = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.2,
        survival_random_numbers=(
            0.1,
            0.5,
            0.6,
            0.8,
            0.9,
        ),
    )

    assert result1.attacker_wins is True
    assert result2.attacker_wins is True

    assert result1.survivors == 3
    assert result2.survivors == 1

    assert result1 != result2

def test_resolve_battle_defender_win_requires_defender_random_numbers():
    with pytest.raises(
        ValueError,
        match="Number of random values must match population",
    ):
        resolve_battle(
            attackers=4,
            defenders=6,
            battle_random_number=0.5,
            survival_random_numbers=(0.1, 0.2, 0.3, 0.8),
        )

def test_resolve_battle_defender_win_with_correct_random_count():
    result = resolve_battle(
        attackers=5,
        defenders=6,
        battle_random_number=0.8,
        survival_random_numbers=(
            0.1,
            0.2,
            0.3,
            0.5,
            0.7,
            0.9,
        ),
    )

    assert result == BattleResult(
        attacker_wins=False,
        survivors=4,
    )

def test_simulate_survivors_can_return_zero():
    result = simulate_survivors(
        population=10,
        survival_probability=0.6,
        random_numbers=(0.9,) * 10, # duplicate a tuple with single element 10 times
    )

    assert result == 0

def test_expected_survivors():
    result = expected_survivors(
        population=10,
        survival_probability=0.6
    )

    assert result == pytest.approx(6.0)

def test_expected_survivors_rejects_negative_population():
    with pytest.raises(ValueError):
        expected_survivors(
            population=-5,
            survival_probability=0.6,
        )

def test_expected_survivors_rejects_invalid_probability():
    with pytest.raises(ValueError):
        expected_survivors(
            population=10,
            survival_probability=1.5,
        )

def test_expected_survivors_rejects_float_population():
    with pytest.raises(TypeError):
        expected_survivors(
            population=5.5,
            survival_probability=0.6,
        )

def test_expected_survivors_rejects_boolean_probability():
    with pytest.raises(TypeError):
        expected_survivors(
            population=10,
            survival_probability=True,
        )

def test_guaranteed_human_conversion():
    result = resolve_guaranteed_human_conversion(
        attackers=5,
        humans=3,
    )

    assert result == 8

def test_guaranteed_human_conversion_equal_population():
    result = resolve_guaranteed_human_conversion(
        attackers=5,
        humans=5,
    )

    assert result == 10

def test_resolve_guaranteed_human_conversion_rejects_fewer_attackers():
    with pytest.raises(
        ValueError,
        match="Attackters must be at least as numerous as humans",
    ):
        resolve_guaranteed_human_conversion(
            attackers=3,
            humans=5,
        )

def test_simulate_human_conversion():
    converted = simulate_human_conversion(
        humans=5,
        conversion_probability=0.4,
        random_numbers=(0.1, 0.3, 0.5, 0.7, 0.9),
    )

    assert converted == 2

@pytest.mark.parametrize(
    "attackers, humans",
    [
        (3.5, 5),
        (3, 5.5),
        ("3", 5),
        (3, "5"),
        (True, 5),
        (3, False),
        (None, 5),
        (3, None),
    ],
)
def test_resolve_human_battle_invalid_population_types(
    attackers,
    humans,
):
    with pytest.raises(
        TypeError,
        match="Population must be integers",
    ):
        resolve_human_battle(
            attackers=attackers,
            humans=humans,
        )

def test_resolve_human_battle_victory():
    result = resolve_human_battle_victory(
        attackers=3,
        humans=5,
        survival_probability=0.4,
        attacker_random_numbers=(0.1, 0.3, 0.8),
        human_random_numbers=(0.1, 0.2, 0.5, 0.7, 0.9),
    )

    assert result == 4

def test_resolve_human_battle_defeat():
    survivors = resolve_human_battle_defeat(
        humans=5,
        attacker_win_probability=0.4,
        human_random_numbers=(0.1, 0.3, 0.5, 0.7, 0.9),
    )

    assert survivors == 3

def test_resolve_human_battle_defeat_zero_win_probability():
    survivors = resolve_human_battle_defeat(
        humans=4,
        attacker_win_probability=0.0,
        human_random_numbers=(0.1, 0.3, 0.6, 0.9),
    )

    assert survivors == 4

def test_human_battle_result():
    result = HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=2,
        converted_humans=2,
        surviving_humans=0,
    )

    assert result.attacker_wins is True
    assert result.surviving_attackers == 2
    assert result.converted_humans == 2
    assert result.surviving_humans == 0

def test_human_battle_result_is_immutable():
    result = HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=3,
        converted_humans=4,
        surviving_humans=0,
    )

    with pytest.raises(FrozenInstanceError):
        result.converted_humans = 10

def test_resolve_human_battle_guaranteed_conversion():
    result = resolve_human_battle(
        attackers=5,
        humans=3,
    )

    assert result == HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=5,
        converted_humans=3,
        surviving_humans=0,
    )

def test_resolve_human_battle_random_victory():
    result = resolve_human_battle(
        attackers=3,
        humans=5,
        battle_random_number=0.2,
        attacker_random_numbers=(0.1, 0.3, 0.8),
        human_random_numbers=(0.1, 0.2, 0.5, 0.7, 0.9),
    )

    assert result == HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=1,
        converted_humans=2,
        surviving_humans=0,
    )

def test_resolve_human_battle_random_defeat():
    result = resolve_human_battle(
        attackers=3,
        humans=5,
        battle_random_number=0.5,
        human_random_numbers=(0.1, 0.3, 0.5, 0.7, 0.9),
    )

    assert result == HumanBattleResult(
        attacker_wins=False,
        surviving_attackers=0,
        converted_humans=0,
        surviving_humans=3,
    )

def test_resolve_human_battle_equal_population():
    result = resolve_human_battle(
        attackers=4,
        humans=4,
    )

    assert result == HumanBattleResult(
        attacker_wins=True,
        surviving_attackers=4,
        converted_humans=4,
        surviving_humans=0,
    )

def test_resolve_human_battle_rejects_negative_attackers():
    with pytest.raises(
        ValueError,
        match="Population must be positive",
    ):
        resolve_human_battle(
            attackers=-3,
            humans=5,
        )

def test_resolve_human_battle_rejects_negative_populations():
    with pytest.raises(
        ValueError,
        match="Population must be positive",
    ):
        resolve_human_battle(
            attackers=-3,
            humans=-5,
        )

def test_human_battle_result_rejects_negative_survivors():
    with pytest.raises(
        ValueError,
        match="Population cannot be negative",
    ):
        HumanBattleResult(
            attacker_wins=True,
            surviving_attackers=-3,
            converted_humans=5,
            surviving_humans=0,
        )

@pytest.mark.parametrize(
    "attackers, humans",
    [
        (5, 5),
        (6, 5),
        (10, 3),
    ],
)
def test_human_battle_win_probability_guaranteed_victory(
    attackers,
    humans,
):
    probability = human_battle_win_probability(
        attackers,
        humans,
    )

    assert probability == 1.0

@pytest.mark.parametrize(
    "attackers, humans",
    [
        (3.5, 5),
        (3, 5.5),
        ("3", 5),
        (3, "5"),
        (True, 5),
        (3, False),
        (None, 5),
        (3, None),
    ],
)
def test_human_battle_win_probability_invalid_types(
    attackers,
    humans,
):
    with pytest.raises(
        TypeError,
        match="Population must be integers",
    ):
        human_battle_win_probability(
            attackers,
            humans,
        )

@pytest.mark.parametrize(
    "attackers, humans",
    [
        (0, 5),
        (3, 0),
        (-1, 5),
        (3, -1),
        (0, 0),
        (-3, -5),
    ],
)
def test_human_battle_win_probability_invalid_values(
    attackers,
    humans,
):
    with pytest.raises(
        ValueError,
        match="Population must be positive",
    ):
        human_battle_win_probability(
            attackers,
            humans,
        )

@pytest.mark.parametrize(
    "invalid_attacker_wins",
    [
        1,
        0,
        "True",
        None,
    ],
)
def test_human_battle_result_invalid_attacker_wins_type(
    invalid_attacker_wins,
):
    with pytest.raises(
        TypeError,
        match="attacker_wins must be a boolean",
    ):
        HumanBattleResult(
            attacker_wins=invalid_attacker_wins,
            surviving_attackers=3,
            converted_humans=2,
            surviving_humans=0,
        )

@pytest.mark.parametrize(
    "field_name, invalid_value",
    [
        ("surviving_attackers", 3.5),
        ("converted_humans", "2"),
        ("surviving_humans", True),
    ],
)
def test_human_battle_result_invalid_population_types(
    field_name,
    invalid_value,
):
    populations = {
        "surviving_attackers": 3,
        "converted_humans": 2,
        "surviving_humans": 0,
    }

    populations[field_name] = invalid_value

    with pytest.raises(
        TypeError,
        match="Population must be integers",
    ):
        HumanBattleResult(
            attacker_wins=True,
            **populations,
        )

def test_simulate_battle_with_probability_rejects_negative_random_number():
    with pytest.raises(
        ValueError,
        match="Random number must be in",
    ):
        simulate_battle_with_probability(
            probability=0.3,
            random_number=-0.5,
        )

@pytest.mark.parametrize(
    "invalid_probability",
    [
        "0.5",
        None,
        True,
        False,
    ],
)
def test_simulate_battle_with_probability_invalid_probability_type(
    invalid_probability,
):
    with pytest.raises(
        TypeError,
        match="Probability must be numeric",
    ):
        simulate_battle_with_probability(
            probability=invalid_probability,
            random_number=0.2,
        )

@pytest.mark.parametrize(
    "invalid_probability",
    [
        -0.1,
        -1.0,
        1.1,
        2.0,
        float("nan"),
    ],
)
def test_simulate_battle_with_probability_invalid_probability_range(
    invalid_probability,
):
    with pytest.raises(
        ValueError,
        match="Probability must be between 0 and 1",
    ):
        simulate_battle_with_probability(
            probability=invalid_probability,
            random_number=0.2,
        )

def test_simulate_battle_with_probability_generates_random_number():
    with patch(
        "vampires_ai.game.battle.random.random",
        return_value=0.2,
    ) as mock_random:

        result = simulate_battle_with_probability(
            probability=0.4,
        )

        assert result is True

        mock_random.assert_called_once_with()

@pytest.mark.parametrize(
    "invalid_random_number",
    [
        "0.2",
        True,
        False,
        [],
    ],
)
def test_simulate_battle_with_probability_invalid_random_number_type(
    invalid_random_number,
):
    with pytest.raises(
        TypeError,
        match="Random number must be numeric",
    ):
        simulate_battle_with_probability(
            probability=0.4,
            random_number=invalid_random_number,
        )

def test_battle_win_probability_guaranteed_defeat():
    probability = battle_win_probability(
        attackers=4,
        defenders=6,
    )

    assert probability == 0.0