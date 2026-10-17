from dataclasses import dataclass
from enum import Enum

class Species(Enum):
    HUMAN = 'human'
    VAMPIRE = 'vampire'
    WEREWOLF = 'werewolf'

@dataclass(frozen=True)
class Cell:
    species: Species
    count: int

    def __post_init__(self) -> None:
        if not isinstance(self.species, Species):
            raise TypeError("species must be a Species enum member")

        if type(self.count) is not int:
            raise TypeError("count must be an integer")

        if self.count <= 0:
            raise ValueError("count must be positive")