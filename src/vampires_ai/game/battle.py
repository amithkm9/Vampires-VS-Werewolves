from dataclasses import dataclass

import random

def battle_win_probability(attackers: int, defenders: int) -> float:
    if type(attackers) is not int or type(defenders) is not int:
        raise TypeError("Population must be integers")

    if attackers <= 0 or defenders <= 0:
        raise ValueError("Population must be positive")

    # Guaranteed attacker victory
    if attackers >= 1.5 * defenders:
        return 1.0

    # Guaranteed attacker defeat
    if defenders >= 1.5 * attackers:
        return 0.0

    # Random battle
    if attackers < defenders:
        return attackers / (2 * defenders)

    if attackers == defenders:
        return 0.5

    return attackers / defenders - 0.5

def human_battle_win_probability(
        attackers: int,
        humans: int,
) -> float:
    if type(attackers) is not int or type(humans) is not int:
        raise TypeError("Population must be integers")

    if attackers <= 0 or humans <= 0:
        raise ValueError("Population must be positive")

    if attackers >= humans:
        return 1.0

    return attackers / (2 * humans)

def simulate_battle(
        attackers: int,
        defenders: int,
        random_number: float | None = None,
) -> bool:
    probability = battle_win_probability(attackers, defenders)

    if random_number is None:
        random_number = random.random()

    if type(random_number) not in (int, float):
        raise TypeError("Random number must be numeric")

    if not 0 <= random_number < 1:
        raise ValueError("Random number must be in [0, 1)")

    return random_number < probability

# Create battle result for battle between vampires and werewolves
@dataclass(frozen=True)
class BattleResult:
    attacker_wins: bool
    survivors: int # Surviving Population of the Winner

    def __post_init__(self):
        if type(self.attacker_wins) is not bool:
            raise TypeError("attacker_wins must be a boolean")

        if type(self.survivors) is not int:
            raise TypeError("Survivors must be an integer")

        if self.survivors < 0:
            raise ValueError("Survivors cannot be negative")

def unit_survives(
        survival_probability: float,
        random_number: float,
) -> bool:
    return random_number < survival_probability

def simulate_survivors(
        population: int,
        survival_probability: float,
        random_numbers: tuple[float, ...] | None = None,
) -> int:
    if type(population) is not int:
        raise TypeError("Population must be an integer")

    if population < 0:
        raise ValueError("Population cannot be negative")

    # Validate the probability type before checking its range.
    if type(survival_probability) not in (int, float):
            raise TypeError("Survival probability must be numeric")

    # this can also check NaN (Not a Number, float type) and reject it correctly
    # nan_value = float("nan")
    # nan_value == nan_value # False
    # nan_value < 0 # False
    # nan_value > 1 # False
    if not 0 <= survival_probability <= 1:
        raise ValueError("Survival probability must be between 0 and 1")

    if random_numbers is None:
        random_numbers = tuple(
            random.random() for _ in range(population)
        )

    if len(random_numbers) != population:
        raise ValueError("Number of random values must match population")

    survivors = 0

    for random_number in random_numbers:
        # Validate Before Processing
        if type(random_number) not in (int, float):
            raise TypeError("Random number must be numeric")

        # this can also check NaN (Not a Number, float type) and reject it correctly
        if not 0 <= random_number < 1:
            raise ValueError("Random number must be in [0, 1)")

        if unit_survives(survival_probability, random_number):
            survivors += 1

    return survivors

def resolve_battle(
        attackers: int,
        defenders: int,
        battle_random_number: float | None = None,
        survival_random_numbers: tuple[float, ...] | None = None,
) -> BattleResult:

    probability = battle_win_probability(
        attackers,
        defenders,
    )

    attacker_wins = simulate_battle(
        attackers,
        defenders,
        battle_random_number,
    )

    if attacker_wins:
        population = attackers
        survival_probability = probability
    else:
        population = defenders
        survival_probability = 1 - probability

    survivors = simulate_survivors(
        population,
        survival_probability,
        survival_random_numbers,
    )

    return BattleResult(
        attacker_wins=attacker_wins,
        survivors=survivors,
    )

def expected_survivors(
        population: int,
        survival_probability: float,
) -> float:

    if type(population) is not int:
        raise TypeError("Population must be an integer")

    if population < 0:
        raise ValueError("Population cannot be negative")

    if type(survival_probability) not in (int, float):
        raise TypeError("Survival probability must be numeric")

    if not 0 <= survival_probability <= 1:
        raise ValueError(
            "Survival probability must be between 0 and 1"
        )

    return population * survival_probability

def resolve_guaranteed_human_conversion(
        attackers: int,
        humans: int,
) -> int:

    if attackers < humans:
        raise ValueError(
            "Attackters must be at least as numerous as humans"
        )

    return attackers + humans

def simulate_human_conversion(
        humans: int,
        conversion_probability: float,
        random_numbers: tuple[float, ...] | None = None,
) -> int:
    return simulate_survivors(
        population=humans,
        survival_probability=conversion_probability,
        random_numbers=random_numbers
    )

def resolve_human_battle_victory(
        attackers: int,
        humans: int,
        survival_probability: float,
        attacker_random_numbers: tuple[float, ...] | None = None,
        human_random_numbers: tuple[float, ...] | None = None,
) -> int:

    surviving_attackers = simulate_survivors(
        population=attackers,
        survival_probability=survival_probability,
        random_numbers=attacker_random_numbers,
    )

    converted_humans = simulate_human_conversion(
        humans=humans,
        conversion_probability=survival_probability,
        random_numbers=human_random_numbers,
    )

    return surviving_attackers + converted_humans

def resolve_human_battle_defeat(
        humans: int,
        attacker_win_probability: float,
        human_random_numbers: tuple[float, ...] | None = None,
) -> int:

    human_survival_probability = (
        1 - attacker_win_probability
    )

    return simulate_survivors(
        population=humans,
        survival_probability=human_survival_probability,
        random_numbers=human_random_numbers,
    )

# Create battle result for battle between human and monster

# Dataclasses compare instances by field values, not object identity.
# frozen=True prevents modifying fields after initialization.
@dataclass(frozen=True)
class HumanBattleResult:
    attacker_wins: bool
    surviving_attackers: int
    converted_humans: int
    surviving_humans: int

    def __post_init__(self):
        if type(self.attacker_wins) is not bool:
            raise TypeError("attacker_wins must be a boolean")

        populations = (
            self.surviving_attackers,
            self.converted_humans,
            self.surviving_humans,
        )

        for population in populations:
            if type(population) is not int:
                raise TypeError("Population must be integers")

            if population < 0:
                raise ValueError("Population cannot be negative")

def resolve_human_battle(
        attackers: int,
        humans: int,
        battle_random_number: float | None = None,
        attacker_random_numbers: tuple[float, ...] | None = None,
        human_random_numbers: tuple[float, ...] | None = None,
) -> HumanBattleResult:

    # Validate population types
    if type(attackers) is not int or type(humans) is not int:
        raise TypeError("Population must be integers")

    # Validate population values
    if attackers <= 0 or humans <= 0:
        raise ValueError("Population must be positive")

    # Case 1: Guaranteed human conversion
    if attackers >= humans:
        resolve_guaranteed_human_conversion(
            attackers=attackers,
            humans=humans,
        )

        return HumanBattleResult(
            attacker_wins=True,
            surviving_attackers=attackers,
            converted_humans=humans,
            surviving_humans=0,
        )

    # Case 2: Random human battle
    probability = human_battle_win_probability(
        attackers,
        humans,
    )

    attacker_wins = simulate_battle_with_probability(
        probability=probability,
        random_number=battle_random_number,
    )

    # Case 2A: Attackers win
    if attacker_wins:

        surviving_attackers = simulate_survivors(
            population=attackers,
            survival_probability=probability,
            random_numbers=attacker_random_numbers,
        )

        converted_humans = simulate_human_conversion(
            humans=humans,
            conversion_probability=probability,
            random_numbers=human_random_numbers,
        )

        return HumanBattleResult(
            attacker_wins=True,
            surviving_attackers=surviving_attackers,
            converted_humans=converted_humans,
            surviving_humans=0,
        )

    # Case 2B: Attackers lose
    surviving_humans = resolve_human_battle_defeat(
        humans=humans,
        attacker_win_probability=probability,
        human_random_numbers=human_random_numbers,
    )

    return HumanBattleResult(
        attacker_wins=False,
        surviving_attackers=0,
        converted_humans=0,
        surviving_humans=surviving_humans,
    )

def simulate_battle_with_probability(
        probability: float,
        random_number: float | None = None,
) -> bool:
    # Validate probability
    if type(probability) not in (int, float):
        raise TypeError("Probability must be numeric")

    if not 0 <= probability <= 1:
        raise ValueError("Probability must be between 0 and 1")

    # Generate random number if needed
    if random_number is None:
        random_number = random.random()

    # Validate random number
    if type(random_number) not in (int, float):
        raise TypeError("Random number must be numeric")

    if not 0 <= random_number < 1:
        raise ValueError("Random number must be in [0, 1)")

    return random_number < probability
