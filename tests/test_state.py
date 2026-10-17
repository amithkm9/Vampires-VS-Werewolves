from dataclasses import FrozenInstanceError

import pytest

from vampires_ai.game.state import Cell, Species

# Verify enum values
def test_species():
    assert Species.HUMAN.value == "human"
    assert Species.VAMPIRE.value == "vampire"
    assert Species.WEREWOLF.value == "werewolf"

# Verify valid object creation
def test_cell_creatoin():
    cell = Cell(Species.VAMPIRE, 8)

    assert cell.species == Species.VAMPIRE
    assert cell.count == 8

# Reject zero population
def test_cell_rejects_zero_population():
    with pytest.raises(ValueError):
        Cell(Species.VAMPIRE, 0)

# Reject negative population
def test_cell_rejects_negative_population():
    with pytest.raises(ValueError):
        Cell(Species.WEREWOLF, -5)

# Reject invalid species
def test_cell_rejects_invalid_species():
    with pytest.raises(TypeError):
        Cell("vampire", 8)

# Reject boolean counts
def test_cell_rejects_boolean_population():
    with pytest.raises(TypeError):
        Cell(Species.HUMAN, True)

# Prevent modifications
def test_cell_is_immutable():
    cell = Cell(Species.VAMPIRE, 8)

    with pytest.raises(FrozenInstanceError):
        cell.count = 10