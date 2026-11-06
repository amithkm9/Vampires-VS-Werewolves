# Vampires vs Werewolves: AI report

**Entry point:** `python main.py [options] <server_ip> <server_port>` (or `run.sh` / `run.bat`).
Pure Python 3 standard library, no third-party packages, and no AI, tree or graph libraries: every algorithm below is written by hand.

## 1. Knowing the exact rules (`RULES.md`)

The PDF leaves gaps (is the kill threshold ≥ or >? What is C? Are moves into one cell summed?). Those details decide games. We disassembled the server's `VVSW.Model.dll` (CIL bytecode, read with a small hand-written metadata parser) and recovered the referee's exact logic. Findings that **contradict or sharpen the PDF**:

| Rule | Server reality |
|---|---|
| Kill threshold | attacker **≥ 1.5 ×** defender (inclusive) → deterministic kill |
| Defender ≥ 1.5× attacker | **not** an automatic loss: random battle with P = E1/(2·E2) |
| Moves into the same cell | **summed** before resolving |
| Illegal / empty move, protocol error | **instant loss** (cheating) |
| Timeout | turn **skipped** (not a loss), but a late MOV can desync the next turn |
| Moves per turn | **no limit** (splits are free) |
| Counts | stored as **bytes**: above 255, the server wraps or crashes (we guard against it) |
| Turn order / end | Vampires move first; `MaxPlays` counts total plies; bigger total wins, equal = draw |

These are encoded once in `vvw/rules.py` (`win_probability`, `battle_outcomes`, `attack_ev`) and in the server-mirroring validator `vvw/state.py:validate`.

## 2. Architecture

Full documentation with diagrams and worked examples: [`README.md`](README.md) and the chapters in [`docs/`](docs/).

| File | Role |
|---|---|
| `main.py` | `parse_args` (IP/port = last two args), `play` (game loop, END/BYE, desync guard) |
| `vvw/client.py` | `ClientSocket`: byte-exact protocol, exact-length reads, single-write `MOV` |
| `vvw/ai.py` | `Agent`: state tracking from MAP/UPD, species detection, ply/time accounting, `decide` |
| `vvw/state.py` | `Board` (geometry, lazy distance rows, cached `steps_toward`), `State`, `validate`, `apply_moves` |
| `vvw/movegen.py` | `group_options`, `generate_moves`: strategic candidate turns |
| `vvw/evaluate.py` | `evaluate`, `terminal_value`, `_tours`, `win_value`, `utility_k`, `root_slope` |
| `vvw/search.py` | `Searcher.choose`, `_root`, `_ab`, `_value_of_move`, `_soft_min`: expectiminimax alpha-beta, per-root `RootContext` tables |
| `vvw/ponder.py` | `Ponderer` (thinking on the opponent's time), `OpponentTracker` (how predictable is the opponent?), `Session` (one game's thinking, shared by the client and the simulator) |
| `vvw/safety.py` | `fallback_move`, `ensure_legal`: a legal move no matter what |

## 3. Algorithms

### 3.1 Adversarial search: alpha-beta expectiminimax (`vvw/search.py`)
- **`Searcher._ab`**: depth-limited **minimax with alpha-beta pruning**. One ply = one player's whole turn. Our turns maximize and the opponent's minimize, using *the same move generator*: we assume a rational opponent (not a reflex agent).
- **Chance nodes** (`Searcher._value_of_move`): a random battle splits the position into a win branch and a loss branch with the server's exact probability P and the expected survivors (`rules.battle_outcomes`, `state.apply_moves`). The node's value is the probability-weighted mean.
- **Iterative deepening** under a hard deadline (`Searcher.choose`): depth 1, 2, 3, … until time runs out. The previous best move is searched first, so a partially finished iteration is still usable.
- **Transposition table** keyed by the position (frozensets of cells) + side to move + plies left, storing depth, bound type (exact/lower/upper) and best move. The stored move is tried first.
- **Move ordering**: transposition-table move, then the generator's heuristic order. At the root, all moves are pre-sorted by a one-ply static look (`Searcher._order_root`).
- **Tempo bonus**: material won k plies into the future gets an extra `tempo · λ^k`, scaled by the slope of the utility at the root (`evaluate.root_slope`). Without it, the search sees that a capture can be made "later" for the same final value and postpones it forever (observed, then fixed).
- **Pondering: thinking on the opponent's time** (`vvw/ponder.py:Ponderer`). After sending our move we predict the opponent's 3 most likely replies: the reply our own search expected (`Searcher.expected_reply`) plus the next best by a 1-ply look from its side (`Searcher.ranked_moves`). We pre-search our answer to each, round-robin. Search tables live in a per-root `RootContext`, so when the real position arrives and was pondered, `Searcher.choose` resumes at the depth reached, with its transposition table. A test checks that this gives exactly the same move and value as a fresh search. `stop()` (is the server's message waiting?) is polled every 128 nodes, so pondering ends within ~1–7 ms, and the move clock starts from when the message was noticed. Measured: the pondered position is the real one on **77%** of turns against engines. It is useless against instant-reply bots (2%), which leave no time to use. `--no-ponder` turns it off.
- **Opponent model** (`Searcher._soft_min`, `ponder.OpponentTracker`). Minimax assumes the opponent always finds its best reply. At the opponent's first reply we can instead score `(1−ε)·min + ε·mean(3 lowest)`, which favours moves that leave it only one good answer (traps). The bound is kept exact under pruning: replies are searched with β = the current 3rd-lowest value, and the node fails low once its upper bound reaches α. ε is **adaptive**. We track how often the opponent plays exactly the reply we predicted (engines 56–58%, greedy bots 24–26%, random 4%), and ε goes from 0 (≥ 50% match) to 0.1 (≤ 25%). A fixed ε = 0.1 cost games against an equal engine (0.475), which is why it adapts.
- **Risk aversion on our own gambles**: our chance nodes subtract `risk × mean-absolute-deviation`. A fair coin flip then scores below a quiet move, and we only gamble when the expected gain is real (for example when clearly behind). Measured effect: games lost to a 50/50 battle we started went from 11/16 losses to 0.

### 3.2 Evaluation: one scale for heuristics and game outcomes (`vvw/evaluate.py:evaluate`)
`value = raw + G · tanh(raw / k)`
- `raw`: expected final material margin, made up of:
  - **Material** (ours − theirs).
  - **Human race** (`_tours`): every group runs a greedy capture tour, repeatedly converting the most valuable human cell it is big enough for, *growing as it goes*. Each human cell is credited to the side that arrives first (ties go to the side to move), discounted by γ^time. This captures chains ("take the 4, then you're big enough for the 8") and rewards splitting to cover several cells.
  - **Combat threats**: every group is threatened by the best *bigger* enemy group in range, weighted by the attack's **expected material swing** `rules.attack_ev`. This is positive for *any* size advantage, not just ≥ 1.5× (a 1.3× attacker wins 80% of the time). The weight depends on distance and on who moves next.
  - Fragmentation and an endgame contact nudge: the leader avoids contact, the trailer seeks it.
- `G` (`win_value`): what winning is worth, in creatures, fixed for a whole search. Terminal positions (`terminal_value`) are worth ±1.5·G + margin.
- `k` (`utility_k`): uncertainty of the final result. Large while many humans remain, small in the endgame and near the ply limit.

So `(value − raw)/G ≈ 2·P(win) − 1`. Because heuristic scores and terminal outcomes share one scale, expectimax is **risk-aware for free**: ahead in the endgame, a 52% coin flip throws away a ~95% win; clearly behind, the same gamble is the best hope.

### 3.3 Strategic move generation (`vvw/movegen.py:generate_moves`)
Enumerating every split of every group explodes combinatorially. Each group instead gets a handful of **purposeful options** (`group_options`):
- step toward a human cell it can convert, or an enemy group it can kill (≥ 1.5×) or beat in expectation (> 1×)
- flee from bigger enemies; merge with an ally
- adjacent random-battle attacks (**always kept**, so the search never overlooks the opponent's desperate gamble)
- **splits** (`_split_options`), always kept on top of the best single-cell options:
  - two parts for two human cells (exact force to the smaller one)
  - three parts for three cells
  - a **detachment**: exactly the force one human cell needs breaks off while the main body stays or takes its own best option. This lets the AI collect far humans without abandoning the front.
- wider at the root (7 options per group instead of 5), since every root move gets searched anyway
- stay put; plus at least two "quiet" moves, so a gamble is never the only candidate

Joint turns combine the best option per group with single and pairwise deviations, filtered for Rule 5 and the server's byte limits (`_joint_ok`).

### 3.4 Never forfeit (`vvw/safety.py`, `main.py`)
- Every outgoing move set is checked by `state.validate`, a line-by-line mirror of the server's `CheckMoves` plus the crash cases (off-board, byte overflow). `ensure_legal` swaps in `fallback_move` (one whole group to its safest neighbour) if anything is wrong. Search exceptions are caught too.
- Time: a hard deadline (1.3 s of the 2 s) is checked at every node. The cyclic garbage collector is disabled because it was measured pausing ~400 ms on our tables. Worst case on 50×50 maps: 1300 ms.
- Desync guard (`main.play`): if a newer server message is already waiting, the stale move is not sent.
- Pondering is fenced off: any exception in it is caught and only drops the pondered tables, and memory stays bounded (≈ 240 MB per client measured on 50×50 maps). With the cyclic GC disabled, reference cycles would never be freed, so a recursive closure in the move generator was replaced; a GC check now finds 0 cycles per search.

## 4. How we tested it
- **Byte-exact fake server** (`sim/fake_server.py`), reproduced from the disassembled `GameRoutine`. Real client *processes* (`main.py`, pondering on and off) play complete games over TCP (`tests/test_protocol.py`, `sim/fuzz.py`).
- **In-process referee** with real dice (`sim/referee.py`) and baseline bots (`sim/bots.py`: random, greedy, aggressive), plus **frozen snapshots** of earlier versions for regression matches (`sim/snapshots/`). After each move, the referee lets the other bot ponder for exactly as long as the mover thought, as it would on the real server with the two AIs on separate cores.
- **Tournaments** on point-symmetric random maps, both species per map (`sim/tournament.py`).
- **Weight tuning** by coordinate descent on deterministic fixed-depth self-play (`sim/tune.py`), validated on a held-out map set.
- 46 unit tests (`tests/`), passing on Python 3.9, 3.11 and 3.14. They include a property test that the move generator never proposes a move the server would reject, regression tests for each strategic bug found, and an **edge-case suite** (`tests/test_edge_cases.py`): 1-cell-wide corridors, 2×2 boards, no humans, armies near the 255 byte limit, adjacent starts, 60×60 boards, boxed-in groups, a second game on the same connection, and a turn limit longer than assumed.

## 5. Results

Final engine (v6), measured with the decisive-game counts that matter. Against an equally careful engine most games are draws, so we compare wins against losses. Each map is played as both species; maps are point-symmetric random maps.

| Match | Win / Draw / Loss | Score |
|---|---|---|
| v6 vs v5, 0.5 s/move, 204 games on maps never used in development | 40 / 133 / 31 | 0.522 |
| new move generation vs v5, 0.1 s/move, 404 games | 88 / 260 / 56 | 0.540 (p ≈ 0.01) |
| pondering vs the same engine without it, 0.1 s/move, 404 games | 77 / 265 / 62 | 0.519 |
| *for scale:* double thinking time vs the same engine, 404 games | 88 / 260 / 56 | 0.540 |
| v6 vs greedy, 0.1 s/move, 404 games | 313 / 0 / 91 | 0.775 (v5: 0.780) |
| v6 vs aggressive, 0.1 s/move, 404 games | 321 / 0 / 83 | 0.795 (v5: 0.797) |

The two 88 / 260 / 56 rows are two different matches that happened to end with identical counts.

On the earlier 62-map set, v5 scored 0.903 against both greedy bots. The 404-game set has more maps whose symmetric human race ends exactly tied with one group each. The greedy bot then walks into us, and that battle is a pure 50/50: almost all of those losses are such coin flips. No version changes that, so the baseline scores stayed flat.

Timing at the real 1.3 s budget, pondering on: worst move 1300 ms on 30×30 to 50×50 maps, and **1310 ms with the machine fully loaded** (26 simultaneous games, 520 moves, none above 1.4 s). No forfeits and no timeouts in any test.

What changed the results most (each change was measured, not guessed):

| Change | Effect |
|---|---|
| Tempo bonus | stopped endless postponing of free captures (seen in traces) |
| One scale for heuristics and outcomes (`G · tanh`) | stopped 51% coin flips while winning |
| Threat = expected value of *any* bigger attacker | aggressive bot: 69% → 75% |
| Never offer only a gamble; always keep adjacent attacks | removed suicidal forced gambles; fixed "safe" adjacency to a desperate opponent |
| Risk aversion (ours, then also the opponent's gambles) | greedy: 75% → 84%; losses vs aggressive 17 → 7 |
| GC disabled during search | worst-case move time 1567 ms → 1300 ms |
| Leaf-evaluation cache, γ-power table, killer moves | 3.6× more nodes per second (one search depth deeper in busy positions); killers alone 11% faster with identical results |
| Competition-aware human race + endgame cornering | vs aggressive 0.859 → 0.875 on fresh maps |
| Risk aversion fades over the last 20 plies; tied endgames seek contact | draws vs baselines 7 → 0, all converted to wins (aggressive 0.875 → 0.903) |
| Splits: 2 or 3 parts, detachments, wider root | vs v5: 0.540 (88 W / 56 L in decisive games, p ≈ 0.01) |
| Pondering (77% hit rate vs engines) | +0.019 vs the same engine without it, in line with what doubling the time is worth here (+0.040) |
| Adaptive opponent model | within noise everywhere (vs greedy 0.770 → 0.775, vs aggressive 0.792 → 0.795); a fixed ε = 0.1 hurt vs engines (0.475), so it adapts |
| Turn limit / game time learned when the game outlives the assumption | no false "last turn" panic if the tournament uses more than 200 plies |

### Known limitations
- More time helps less than one would hope: doubling it gains only 0.04 against an equal engine, so the engine is limited by its evaluation and move choices more than by speed.
- Pondering needs a free CPU core (it runs while the opponent thinks). If both AIs share one core, use `--no-ponder`.
- Python limits search to roughly depth 4–7 in busy positions. Long plans (for example "split a guard toward the far human cluster while chasing") are beyond the horizon. Example seen: a 120 v 64 lead spent chasing a group that could never be caught while it collected 50 humans.
- On a finite grid a determined pursuer can always force contact (push the evader to a wall, then a corner). So an endgame lead below 1.5× is not safe over many plies; the AI then takes the battle on its own terms (attacking gives the better odds).
- Against an equally careful opponent on a symmetric map, the outcome is often decided by a final-turn 50/50 battle. We choose that over a draw because a draw wins nothing.

## 6. Pitch (5 minutes)
1. **"We read the referee's code."** We disassembled the server DLL. The PDF is wrong on one key rule: a defender with 1.5× is *not* safe, it's a dice roll. We know the exact thresholds, the byte limits and the cheat checks; other AIs are guessing.
2. **"We never forfeit."** Every move is checked against a mirror of the server's validator before sending. There's a guaranteed-legal fallback and a hard deadline checked every node. Thousands of simulated games, 0 illegal moves, 0 timeouts.
3. **"We think in win probability, not creatures."** One scale for heuristics and outcomes. When we lead we refuse coin flips; when we trail we take the best one, at the best moment.
4. **"We look ahead at you, and on your time."** Expectiminimax with alpha-beta and real battle probabilities. While you think, we already search our answer to your 3 most likely moves, and we guess right 77% of the time against engines. We also measure how predictable you are: against a bot that doesn't find its best replies, we start setting traps.
5. Live numbers: the win rates in section 5.
