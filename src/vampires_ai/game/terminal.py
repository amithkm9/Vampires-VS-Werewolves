from vampires_ai.game.state import GameState, Species

def _get_monster_species(state: GameState) -> set[Species]:
    return {
        cell.species
        for _, cell in state.board
        if cell.species in (Species.VAMPIRE, Species.WEREWOLF)
    }

def is_terminal(state: GameState) -> bool:
    species_present = _get_monster_species(state)

    return (
        Species.VAMPIRE not in species_present
        or Species.WEREWOLF not in species_present
    )

def get_winner(state: GameState) -> Species | None:
    species_present = _get_monster_species(state)

    vampires_present = Species.VAMPIRE in species_present
    werewolves_present = Species.WEREWOLF in species_present

    # Both species eliminated: draw
    if not vampires_present and not werewolves_present:
        return None

    # Vampires eliminated: werewolves win
    if not vampires_present:
        return Species.WEREWOLF

    # Werewolves eliminated: vampires win
    if not werewolves_present:
        return Species.VAMPIRE

    # Both species still exist
    raise ValueError("Game is not terminal")