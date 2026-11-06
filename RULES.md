# Exact game rules (from the server binary, v3.2.1)

These rules come from disassembling `VVSW.Model.dll` (`Board.PerformMoves`, `Board.CheckMoves`, `Board.GetProba`, `Board.PerformRandomBattle`, `GameControl.GameRoutine`, `GameControl.InitiatePlayerComm`). **Where they differ from `Projectv10.pdf`, the server wins.** That's marked ⚠️.

## Players and turns
- Player 0 = **Vampires**, player 1 = **Werewolves**. Player index = `ply % 2`, so **Vampires move first**.
- `MaxPlays` (200 by default) counts **total plies** (both players), so 100 moves each.
- `MaxGameDuration` (5 min) is checked **only after Werewolves' moves** (`ply % 2 == 1`).
- After each move: if total vampires = 0, Werewolves win; if total werewolves = 0, Vampires win.
- When the plies or time run out: **the larger species total wins** (humans don't count). Equal totals mean no winner.

## Move validation (`CheckMoves`): any violation is an instant loss ⚠️
- An empty move list throws `NoMoveException` → "stayed static" → **loss**.
- A move set is bad if **any** single move:
  - has a target that is also a source of some move in this set (Rule 5),
  - has a source that is also a target of some move in this set (Rule 5),
  - starts from a cell whose species isn't the player's,
  - takes more creatures than the source cell holds,
  - moves more than 1 in x or in y (8-neighbourhood),
  - moves **0 creatures**.
- The counts leaving each source cell are **summed**, and the sum must be ≤ the cell's count.
- **No limit on the number of moves** per turn (the PDF's "n ≤ number of groups" isn't enforced). ⚠️
- **No bounds check on the target.** An off-board target crashes the server-side handler, which is caught as a generic exception → **loss**. We must never send one.
- Any other exception while handling the move (e.g. a byte overflow) → **loss**.

## Move resolution (`PerformMoves`)
1. Moves are **grouped by target**. The counts arriving at one target are **summed** (`Convert.ToByte`, which throws above 255 → loss ⚠️).
2. The creatures leave their source cells (sources keep the remainder).
3. Each target cell (with `A` = summed attackers):
   - **Empty:** becomes ours with count `A`.
   - **Ours:** merge, `count + A` (stored as a byte, **wraps above 255** ⚠️).
   - **Humans `H`:** if `A >= H`, the cell becomes ours with `A + H`. Otherwise **random battle**.
   - **Enemy `E`:** if `A >= 1.5·E` (inclusive), the cell becomes ours with `A` (the enemy dies). Otherwise **random battle**.
     ⚠️ There's **no** "defender at ≥ 1.5× kills all attackers automatically" rule. It's a random battle with a small P.

## Random battle (`GetProba` + `PerformRandomBattle`)
`P = GetProba(E1 = attackers, E2 = defenders, vsHumans)`, with `C = 1.0` vs humans and `1.5` vs monsters:
- `E1 == E2` → `P = 0.5`
- `E1 >= C·E2` → `P = 1` (never actually reached, because the deterministic cases above catch it first)
- `E1 < E2` → `P = E1 / (2·E2)`
- otherwise (monsters only, `E2 < E1 < 1.5·E2`) → `P = E1/E2 − 0.5`

The attacker **wins if `rand < P`**:
- **Win:** the cell becomes the attacker's. Each attacker survives with probability P, and **vs humans, each human is converted with probability P** too.
- **Loss:** all the attackers die. Each defender survives with probability `1 − P`, and the cell stays the defender's.

Expected attacker creatures after the battle: `P²·(E1 [+ H])`. Expected defenders: `(1−P)²·E2`. Random battles destroy a lot of material on average.

## Protocol (byte-exact)
- Client → `NME` + `t` (1 byte) + name (t ASCII bytes).
- Server → `SET rows cols` + `HUM n (x y)*n` + `HME x y` in **one packet**, then `MAP n (x y h v w)*n` (every non-empty cell).
- Each turn, server → `UPD n (x y h v w)*n`: the cells changed by **every player's last move** (so it includes our own last move). The first player's first `UPD` is empty.
- The server waits **≥ 4 bytes** (`MOV` + n) within `MaxMoveDuration`, then `5n` more bytes within the **same** deadline (measured from when it sent `UPD`). A timeout **skips the turn** (not a loss).
- **Before sending each `UPD`, the server discards any unread bytes** (up to 1300) from that player. A late `MOV` is discarded if it arrives before the next turn starts. If it arrives after the next `UPD`, it counts as the answer to the new turn (danger of an illegal move → loss).
- At the end: the server sleeps 4 s, then sends `END`, `BYE` and **closes the socket**. One game per connection.
- Coordinates: `x` = column, `y` = row, (0,0) at the top left. `SET` sends rows first, then columns.
