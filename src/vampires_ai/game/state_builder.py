
from vampires_ai.game.state import Cell, GameState, Species

class GameStateBuilder:
    def __init__(self) -> None:
        self.width: int | None = None
        self.height: int | None = None
        self.human_houses: tuple[tuple[int, int], ...] | None = None
        self.home_position: tuple[int, int] | None = None
        self.game_state: GameState | None = None

    def handle_message(self, message: list) -> None:
        command, data = message
        
        if command == "set":
            if self.width is not None or self.height is not None:
                raise ValueError("SET already received")
    
            height, width = data

            if type(height) is not int or type(width) is not int:
                raise TypeError("board dimensions must be integers")

            if height <= 0 or width <= 0:
                raise ValueError("board dimensions must be positive")

            self.height = height
            self.width = width

        elif command == "hum":
            if self.human_houses is not None:
                raise ValueError("HUM already received")
            
            houses = []

            for x, y in data:
                self._validate_position(x, y)
                houses.append((x, y))

            self.human_houses = tuple(houses)

        elif command == "hme":
            x, y = data

            if self.home_position is not None:
                raise ValueError("HME already received")
            
            self._validate_position(x, y)

            self.home_position = (x, y)
        
        elif command == "map":
            if self.game_state is not None:
                raise ValueError("MAP already received")
    
            if (
                self.width is None
                or self.height is None
                or self.home_position is None
            ):
                raise ValueError("SET and HME must be received before MAP")

            board = {}
            seen_positions = set()

            for x, y, humans, vampires, werewolves in data:
                self._validate_position(x, y)

                position = (x, y)

                if position in seen_positions:
                    raise ValueError("duplicate position in MAP")

                seen_positions.add(position)

                self._validate_unit_counts(humans, vampires, werewolves)

                species_count = sum(
                    count > 0
                    for count in (humans, vampires, werewolves)
                )
                if species_count > 1:
                    raise ValueError("Cell contains multiple species")

                if humans > 0:
                    board[(x, y)] = Cell(Species.HUMAN, humans)
                elif vampires > 0:
                    board[(x, y)] = Cell(Species.VAMPIRE, vampires)
                elif werewolves > 0:
                    board[(x, y)] = Cell(Species.WEREWOLF, werewolves)

            home_cell = board.get(self.home_position)

            if home_cell is None:
                raise ValueError("Home position is missing from MAP")

            if home_cell.species == Species.HUMAN:
                raise ValueError("Home position cannot contain humans")

            self.game_state = GameState.from_dict(
                width=self.width,
                height=self.height,
                board=board,
                current_player=home_cell.species,
            )

        
        elif command == "upd":
            if self.game_state is None:
                raise ValueError("MAP must be received before UPD")

            # Copy the existing board
            board = dict(self.game_state.board)

            seen_positions = set()

            for x, y, humans, vampires, werewolves in data:
                self._validate_position(x, y)

                position = (x, y)

                if position in seen_positions:
                    raise ValueError("duplicate position in UPD")

                seen_positions.add(position)

                self._validate_unit_counts(humans, vampires, werewolves)

                position = (x, y)

                if humans > 0:
                    board[position] = Cell(Species.HUMAN, humans)
                elif vampires > 0:
                    board[position] = Cell(Species.VAMPIRE, vampires)
                elif werewolves > 0:
                    board[position] = Cell(Species.WEREWOLF, werewolves)
                else:
                    board.pop(position, None)

            # Create a new immutable GameState
            self.game_state = GameState.from_dict(
                width=self.game_state.width,
                height=self.game_state.height,
                board=board,
                current_player=self.game_state.current_player,
            )
    
    @staticmethod
    def _validate_unit_counts(
        humans: int,
        vampires: int,
        werewolves: int,
    ) -> None:
        counts = (humans, vampires, werewolves)

        # Reject non-integer counts
        if any(type(count) is not int for count in counts):
            raise TypeError("unit counts must be integers")

        # Reject negative counts
        if any(count < 0 for count in counts):
            raise ValueError("negative unit count")

        # Reject multiple species in one cell
        if sum(count > 0 for count in counts) > 1:
            raise ValueError("Cell contains multiple species")
    
    
    def _validate_position(self, x: int, y: int) -> None:
        if self.width is None or self.height is None:
            raise ValueError("SET must be received before coordinates")

        if type(x) is not int or type(y) is not int:
            raise TypeError("coordinates must be integers")

        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("position is outside the board")