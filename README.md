# Tiny Chess 1124

A packed Python chess engine (alpha-beta search with quiescence, transposition and killer/history move ordering) that plays via the make.fun game loop.

## Design

The engine is a single-file negamax searcher. It runs iterative deepening from depth 1 upward, keeping a transposition table of best moves and ordering candidates by captures (MVV-LVA), promotions, the previous best move, then killer and history heuristics. At the leaves it extends into a quiescence search so that capture sequences are resolved before scoring, and a fixed node budget stops the deepening loop early when time runs short. Evaluation is a material sum with piece-square tables, a small bishop-pair bonus, and a mobility term derived from counting pseudo-legal moves for each side. Positions in check are searched a ply deeper so tactical escapes are not cut off.

## Run

```bash
python3 build.py        # pack src/engine.py into the self-extracting main.py
python3 test_smoke.py   # run the 3-ply smoke test
```
