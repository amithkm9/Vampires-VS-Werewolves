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

@dataclass(frozen=True)
class GameState:
    width: int
    height: int
    board: tuple[tuple[tuple[int, int], Cell], ...]
    current_player: Species

    def __post_init__(self) -> None:
        # Validate current player
        if not isinstance(self.current_player, Species):
            raise TypeError("current_player must be a Species")

        if self.current_player == Species.HUMAN:
            raise ValueError("humans cannot be the current player")

        # Validate board structure
        if not isinstance(self.board, tuple):
            raise TypeError("board must be a tuple")

        # Validate board dimensions
        if type(self.width) is not int:
            raise TypeError("width must be an integer")

        if type(self.height) is not int:
            raise TypeError("height must be an integer")

        if self.width <= 0 or self.height <= 0:
            raise ValueError("board dimensions must be positive")

        seen_positions = set()

        for entry in self.board:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("each board entry must be (position, cell)")

            position, cell = entry

            if not isinstance(position, tuple) or len(position) != 2:
                raise TypeError("position must be a tuple (x, y)")

            x, y = position

            if type(x) is not int or type(y) is not int:
                raise TypeError("coordinates must be integers")

            if not (0 <= x < self.width and 0 <= y < self.height):
                raise ValueError("position is outside the board")

            if not isinstance(cell, Cell):
                raise TypeError("board values must be Cell objects")

            if position in seen_positions:
                raise ValueError("duplicate board position")

            seen_positions.add(position)

        # Normalize board representation
        canonical_board = tuple(
            sorted(self.board, key=lambda entry: entry[0])
        )

        object.__setattr__(self, "board", canonical_board)

    @classmethod
    def from_dict(
        cls,
        width: int,
        height: int,
        board: dict[tuple[int, int], Cell],
        current_player: Species,
    ) -> "GameState":
        if not isinstance(board, dict):
            raise TypeError("board must be a dictionary")

        return cls(
            width=width,
            height=height,
            board=tuple(board.items()),
            current_player=current_player,
        )

    def get_cell(self, x: int, y: int) -> Cell | None:
        for position, cell in self.board:
            if position == (x, y):
                return cell

        return None