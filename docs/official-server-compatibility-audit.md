# Official Server Compatibility Audit

**Issue:** #16 — Audit Game Engine Compatibility with Official Server  
**Branch:** `feature/official-server-compatibility-audit`  
**Reference:** Official Vampires vs Werewolves Server v3.2.1

## 1. Purpose

This audit compares the Python game engine against the official Vampires vs Werewolves server implementation and the course game rules.

The project follows a **PDF First** policy:

- The course PDF is the primary reference for game rules.
- Decompiled server code is used to identify implementation differences.
- Differences are documented rather than automatically changing the Python engine.

## 2. Audit Methodology

The official .NET assemblies were inspected using ILSpy.

Key components reviewed:

- `VVSW.Model.Board.CheckMoves()`
- `VVSW.Model.Board.PerformMoves()`
- `VVSW.Model.Board.GetProba()`
- `VVSW.Model.Board.PerformRandomBattle()`
- `VVSW.Model.GameControl`

The Python implementation was reviewed in:

- `game/move.py`
- `game/rules.py`
- `game/battle.py`
- `game/transition.py`
- `game/state.py`

### 2.1 Reverse Engineering Tools and Usage

The official Vampires vs Werewolves Server v3.2.1 is distributed as compiled .NET assemblies rather than C# source code.

To inspect its implementation, this audit used **ILSpy**, an open-source .NET assembly browser and decompiler, through its command-line interface, `ilspycmd`.

#### Tools

- **ILSpy:** Decompiles .NET assemblies into readable C# source code.
- **ilspycmd:** The command-line version of ILSpy, used to inspect individual classes or decompile complete assemblies.
- **Visual Studio Code:** Used to read, search, and compare the decompiled C# implementation with the Python game engine.
- **Terminal utilities (`grep`, `sed`, `find`):** Used to locate relevant methods and inspect specific sections of decompiled code.

#### Decompiled Assemblies

The following official server components were inspected:

| Assembly | Purpose |
|---|---|
| `VVSW.Model.dll` | Core game model, movement rules, battle calculations, and game control |
| `VVSW.Controls.dll` | User-interface controls |
| `VampiresVsWerewolvesGameServer.exe` | Server application entry point and initialization |

#### Decompilation Procedure

**1. Decompile an entire assembly into C# source files:**

```bash
ilspycmd -p -o /tmp/VVSW-Model-Decompiled VVSW.Model.dll
```

The `-p` option generates a project-style output containing multiple source files, while `-o` specifies the output directory.

**2. Decompile an individual class:**

```bash
ilspycmd -t VVSW.Model.Board VVSW.Model.dll > /tmp/Board.cs
```

The `-t` option selects a specific .NET type. The `>` operator saves the generated source code to a file.

**3. Inspect the generated source code:**

```bash
code /tmp/Board.cs
```

**4. Locate important methods:**

```bash
grep -n "PerformMoves" /tmp/Board.cs
```

The `-n` option displays matching line numbers.

**5. Inspect a specific range of lines:**

```bash
sed -n '255,315p' /tmp/Board.cs
```

This displays lines 255 through 315 without modifying the file.

**6. Inspect .NET Intermediate Language (IL):**

```bash
ilspycmd -il VVSW.Model.dll
```

This provides a lower-level representation that can be useful when the decompiled C# is ambiguous.

#### Limitations

Decompiled C# is a reconstruction of the compiled assembly, not necessarily the original source code. Local variable names, formatting, and some control-flow structures may differ from the developer's original implementation.

Therefore, conclusions should be based on observable logic and, where necessary, corroborated through IL inspection or behavioral testing.

The decompiled code was used for analysis only. No modifications were made to the official server binaries.

## 3. Confirmed Compatibility

### 3.1 Move Validation

The Python engine implements the six movement rules specified in the course PDF:

1. At least one move per turn.
2. Only the current player's creatures may move.
3. The total number of creatures moved from a source cannot exceed its population.
4. Movement is limited to the eight adjacent cells.
5. Source and destination positions cannot overlap within the same turn.
6. Every move must contain at least one creature.

The Python implementation also validates board boundaries and coordinate types.

### 3.2 Human Battles

The Python engine implements:

- Guaranteed conversion when attackers are at least as numerous as humans.
- Random battle probability when attackers are fewer than humans.
- Independent survival calculations for attackers and converted humans after a random victory.
- Human survivor calculations after an attacker defeat.

These behaviors are consistent with the reviewed official server implementation.

### 3.3 Shared Destination Battles

Both implementations group moves by destination before resolving combat.

When multiple groups attack the same destination, their populations are combined and the destination is resolved once.

### 3.4 Turn Transitions

Both implementations:

- Validate the complete turn before applying moves.
- Deduct moved creatures from their sources.
- Merge friendly populations.
- Resolve battles at occupied destinations.

The Python `apply_turn()` function also switches the current player. The official server manages player switching in `GameControl`.

## 4. Known Compatibility Difference

### 4.1 Monster Battle: Guaranteed Defender Victory

The course PDF specifies that when defending monsters are at least 1.5 times as numerous as attackers, all attackers are defeated.

The Python implementation follows this rule:

```python
if defenders >= 1.5 * attackers:
    return 0.0
```

However, the official server's `GetProba()` does not implement this guaranteed-defeat condition.

For example:

| Attackers | Defenders | Python Probability | Official Server Probability |
|---|---|---|---|
| 3 | 6 | 0% | 25% |

**Decision:** Retain the Python behavior under the PDF First policy.

**Impact:** The Python engine intentionally differs from the official server for these battles. This may affect AI move evaluation and predicted battle outcomes.

## 5. Functionality Not Yet Identified in the Python Engine

### 5.1 Game Termination

The official server ends the game when either monster species is eliminated.

No dedicated terminal-state detection function was identified in the reviewed Python game modules.

### 5.2 Winner Determination

The official server determines the winner using:

- Elimination of one monster species.
- Invalid or missing moves resulting in forfeiture.
- Monster population totals when the match timer expires.
- A draw when the populations are equal at the end of the match.

Equivalent match-level winner determination was not identified in the reviewed Python modules.

### 5.3 Match Management

The official server also manages:

- Match timers.
- Move timeouts.
- Invalid-move forfeitures.
- End-of-game notifications.

These responsibilities may belong in a separate match controller rather than the game-state transition layer.

## 6. Additional Observations

- The official server uses byte-sized population values in parts of its implementation, while Python uses integers without a fixed upper bound.
- The official server and Python may consume random values in different orders, even when their battle probability distributions agree.
- The official server's `CheckMoves()` does not explicitly check board boundaries; the Python implementation does.
- The audit did not establish full equivalence for every protocol, boundary, or runtime behavior.

## 7. Recommended Follow-up Work

1. Design and test terminal-state detection.
2. Implement winner determination separately from `apply_turn()`, if required by the project scope.
3. Review population limits and protocol constraints.
4. Document the implications of the PDF First policy for AI battle evaluation.
5. Add focused regression tests for any compatibility differences that must remain intentional.

## 8. Conclusion

The reviewed Python engine implements the core movement, human battle, shared-destination battle, and turn-transition behaviors consistently with the course rules and the examined portions of the official server.

One confirmed behavioral difference concerns guaranteed defender victory in monster battles.

Under the PDF First policy, this difference is intentionally retained.

Game termination, winner determination, and match management remain candidates for future development.

This report documents the reviewed behavior; it does not claim complete compatibility with every aspect of the official server.