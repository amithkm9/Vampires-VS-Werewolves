from dataclasses import dataclass

@dataclass(frozen=True)
class Move:
    source: tuple[int, int]
    destination: tuple[int, int]
    count: int

    def __post_init__(self) -> None:
        # Validate count
        if type(self.count) is not int:
            raise TypeError("count must be an integer")

        if self.count <= 0:
            raise ValueError("count must be positive")

        # Validate coordinates
        for position in (self.source, self.destination):

            if not isinstance(position, tuple) or len(position) != 2:
                raise TypeError("position must be a tuple (x, y)")

            x, y = position

            if type(x) is not int or type(y) is not int:
                raise TypeError("coordinates must be integers")


@dataclass(frozen=True)
class TurnAction:
    moves: tuple[Move, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.moves, tuple):
            raise TypeError("moves must be a tuple")

        if (len(self.moves)) == 0:
            raise ValueError("a turn action must contain at least one move")

        for move in self.moves:
            if not isinstance(move, Move):
                raise TypeError("all elements must be Move Ibjection")
