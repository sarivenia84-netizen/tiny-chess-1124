"""Smoke test for the packed chess engine (stdlib only).

Starts from the initial position and asks the engine's top-level move picker
for three successive plies, asserting that each reply is legal and that a
second identical run produces the exact same moves.
"""
import runpy

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def load_engine():
    return runpy.run_path("main.py")


def advance(ns, state, uci):
    """Apply *uci* to *state*, returning the next state (all legal-move based)."""
    for pair in ns["legal_moves"](state):
        if ns["uci_text"](pair, state[0]) == uci:
            return ns["apply_move"](state, pair)
    raise AssertionError(f"engine returned an illegal move: {uci!r}")


def run_line():
    ns = load_engine()
    state = ns["load_fen"](START_FEN)
    played = []
    for _ in range(3):
        allowed = [ns["uci_text"](pair, state[0]) for pair in ns["legal_moves"](state)]
        assert allowed, "no legal moves in the starting line"
        reply = ns["choose_move"](state, allowed)
        assert reply in allowed, f"illegal move chosen: {reply!r}"
        played.append(reply)
        state = advance(ns, state, reply)
    return played


def main():
    first = run_line()
    second = run_line()
    assert first == second, f"nondeterministic output: {first} vs {second}"
    assert len(first) == 3, first
    print("ply1:", first[0])
    print("ply2:", first[1])
    print("ply3:", first[2])
    print("deterministic: OK")


if __name__ == "__main__":
    main()
