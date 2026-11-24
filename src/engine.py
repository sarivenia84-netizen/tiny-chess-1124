import json
import os
import urllib.request

PIECE_VALUE = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}

COL = [n % 8 for n in range(64)]
ROW = [n // 8 for n in range(64)]
JUMPERS = [[t for t in range(64) if abs(ROW[t] - ROW[n]) * abs(COL[t] - COL[n]) == 2] for n in range(64)]
ALWAYS_KING = [[t for t in range(64) if max(abs(ROW[t] - ROW[n]), abs(COL[t] - COL[n])) == 1] for n in range(64)]

DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1))
SLIDES = [[[n + dcol * k + drow * k * 8
            for k in range(1, 8)
            if 0 <= n // 8 + drow * k < 8 and 0 <= n % 8 + dcol * k < 8]
           for drow, dcol in DIAGONALS] for n in range(64)]

NODE_CAP = 8000
board_cache = {}
killer_cache = {}
history_cache = {}
visited = 0


def load_fen(text):
    parts = text.split()
    cells = []
    for glyph in parts[0].replace("/", ""):
        cells += ["."] * int(glyph) if glyph.isdigit() else [glyph]
    if parts[3] == "-":
        ep_square = None
    else:
        ep_square = (8 - int(parts[3][1])) * 8 + ord(parts[3][0]) - 97
    return cells, parts[1], parts[2], ep_square


def square_attacked(cells, target, attacker_white):
    own_pawn = "P" if attacker_white else "p"
    probes = (target + 9, target + 7) if attacker_white else (target - 9, target - 7)
    for probe in probes:
        if 0 <= probe < 64 and abs(COL[probe] - COL[target]) == 1 and cells[probe] == own_pawn:
            return True
    own_knight = "N" if attacker_white else "n"
    own_king = "K" if attacker_white else "k"
    if any(cells[s] == own_knight for s in JUMPERS[target]):
        return True
    if any(cells[s] == own_king for s in ALWAYS_KING[target]):
        return True
    own_bishop, own_rook, own_queen = ("B", "R", "Q") if attacker_white else ("b", "r", "q")
    for axis, line in enumerate(SLIDES[target]):
        for s in line:
            occupant = cells[s]
            if occupant == ".":
                continue
            slider = own_bishop if axis < 4 else own_rook
            if occupant == slider or occupant == own_queen:
                return True
            break
    return False


def expand_moves(state):
    cells, mover, rights, ep_square = state
    white = mover == "w"
    for src, glyph in enumerate(cells):
        if glyph == "." or glyph.isupper() != white:
            continue
        role = glyph.lower()
        if role == "p":
            forward = -8 if white else 8
            one = src + forward
            if cells[one] == ".":
                yield src, one
                home_row = 6 if white else 1
                if ROW[src] == home_row and cells[one + forward] == ".":
                    yield src, one + forward
            for side_step in (-1, 1):
                cap = src + forward + side_step
                if not (0 <= cap < 64):
                    continue
                if abs(COL[cap] - COL[src]) != 1:
                    continue
                occupied = cells[cap] != "."
                if (occupied and cells[cap].isupper() != white) or cap == ep_square:
                    yield src, cap
        elif role == "k":
            for dst in ALWAYS_KING[src]:
                if cells[dst] == "." or cells[dst].isupper() != white:
                    yield src, dst
            corner = 60 if white else 4
            flags = "KQ" if white else "kq"
            rook_base = 56 if white else 0
            if src == corner:
                for short, right in ((True, flags[0]), (False, flags[1])):
                    rook_sq = rook_base + (7 if short else 0)
                    if short:
                        between = (corner + 1, corner + 2)
                        path = (corner, corner + 1, corner + 2)
                    else:
                        between = (corner - 1, corner - 2, corner - 3)
                        path = (corner, corner - 1, corner - 2)
                    shadow = cells[:]
                    shadow[corner] = "."
                    rook_ok = cells[rook_sq] == ("R" if white else "r")
                    clear = all(cells[s] == "." for s in between)
                    safe = not any(square_attacked(shadow, s, not white) for s in path)
                    if right in rights and rook_ok and clear and safe:
                        yield src, corner + (2 if short else -2)
        elif role == "n":
            for dst in JUMPERS[src]:
                if cells[dst] == "." or cells[dst].isupper() != white:
                    yield src, dst
        else:
            axes = range(8) if role == "q" else range(4) if role == "b" else range(4, 8)
            for axis in axes:
                for dst in SLIDES[src][axis]:
                    if cells[dst] == "." or cells[dst].isupper() != white:
                        yield src, dst
                    if cells[dst] != ".":
                        break


def apply_move(state, pair):
    cells, mover, rights, ep_square = state
    src, dst = pair
    cells = list(cells)
    glyph = cells[src]
    cells[src] = "."
    next_ep = None
    role = glyph.lower()
    if role == "p" and (dst < 8 or dst >= 56):
        cells[dst] = "Q" if mover == "w" else "q"
    else:
        cells[dst] = glyph
    if role == "p":
        if dst == ep_square and COL[src] != COL[dst]:
            cells[dst + (8 if mover == "w" else -8)] = "."
        if abs(dst - src) == 16:
            next_ep = (src + dst) // 2
    elif role == "k" and abs(dst - src) == 2:
        short = dst > src
        rook_from = (src // 8) * 8 + (7 if short else 0)
        rook_to = dst - 1 if short else dst + 1
        cells[rook_to] = cells[rook_from]
        cells[rook_from] = "."
    lost = {0: "q", 7: "k", 4: "kq", 56: "Q", 63: "K", 60: "KQ"}
    for sq in (src, dst):
        rights = rights.replace(lost.get(sq, ""), "")
    return cells, ("b" if mover == "w" else "w"), rights, next_ep


def checked(state):
    cells, mover = state[0], state[1]
    king = "K" if mover == "w" else "k"
    return square_attacked(cells, cells.index(king), mover != "w")


def legal_moves(state):
    mover = state[1]
    king = "K" if mover == "w" else "k"
    enemy_king = "k" if mover == "w" else "K"
    for pair in expand_moves(state):
        if state[0][pair[1]] == enemy_king:
            continue
        after = apply_move(state, pair)
        if not square_attacked(after[0], after[0].index(king), mover != "w"):
            yield pair


def evaluate(state):
    cells, mover, rights, ep_square = state
    total = 0
    bishop_count = [0, 0]
    heavy = sum(1 for glyph in cells if glyph.lower() in "qrbn")
    for sq, glyph in enumerate(cells):
        if glyph == ".":
            continue
        white = glyph.isupper()
        sign = 1 if white else -1
        role = glyph.lower()
        rank = ROW[sq] if white else 7 - ROW[sq]
        file_off = 3.5 - abs(COL[sq] - 3.5)
        rank_off = 3.5 - abs(ROW[sq] - 3.5)
        bonus = 0
        if role == "p":
            bonus = rank * 7 + file_off * 2
        elif role == "n":
            bonus = file_off * 9 + rank_off * 5
            if rank == 0 and COL[sq] in (1, 6):
                bonus -= 12
        elif role == "b":
            bonus = file_off * 4 + rank_off * 3
            bishop_count[int(not white)] += 1
        elif role == "r":
            bonus = rank * 2
        elif role == "q":
            bonus = file_off * 2
        elif role == "k":
            bonus = (3.5 - file_off) * 7 if heavy > 6 else (file_off + rank_off) * 8
        total += sign * (PIECE_VALUE[role] + bonus)
    total += 30 * (int(bishop_count[0] >= 2) - int(bishop_count[1] >= 2))
    their_turn = (cells, "b" if mover == "w" else "w", rights, ep_square)
    activity = len(list(expand_moves(state))) - len(list(expand_moves(their_turn)))
    total += activity * 2 if mover == "w" else -activity * 2
    return total if mover == "w" else -total


def uci_text(pair, cells):
    src, dst = pair
    role = cells[src].lower()
    promoting = role == "p" and (dst < 8 or dst >= 56)
    text = chr(97 + COL[src]) + str(8 - ROW[src]) + chr(97 + COL[dst]) + str(8 - ROW[dst])
    return text + ("q" if promoting else "")


def order_key(pair, cells, best_move, killers, depth_left):
    src, dst = pair
    victim = cells[dst]
    if victim == "." and cells[src].lower() == "p" and COL[src] != COL[dst]:
        victim = "p"
    weight = 0
    if victim != ".":
        weight += 10000 + PIECE_VALUE[victim.lower()] * 10 - PIECE_VALUE[cells[src].lower()]
    if cells[src].lower() == "p" and (dst < 8 or dst >= 56):
        weight += 9000
    if best_move == pair:
        weight += 20000
    if killers and pair == killers[0]:
        weight += 5000
    elif killers and len(killers) > 1 and pair == killers[1]:
        weight += 4000
    return weight + history_cache.get((cells[src], src, dst), 0)


def negamax(state, depth, alpha, beta, ply=0, quiet_tail=False):
    global visited
    visited += 1
    if visited >= NODE_CAP:
        raise TimeoutError
    cells, mover, rights, ep_square = state
    signature = ("".join(cells), mover, rights, ep_square)
    hint = board_cache.get(signature)
    in_check = checked(state)
    if in_check and not quiet_tail:
        depth += 1
    if depth <= 0:
        quiet_tail = True
    if quiet_tail and not in_check:
        static = evaluate(state)
        if static >= beta:
            return static
        alpha = max(alpha, static)
        if depth <= -4:
            return static
    moves = list(legal_moves(state))
    if not moves:
        return (-9900 + ply) if in_check else 0
    killers = killer_cache.get(ply, ())
    moves.sort(key=lambda pair: order_key(pair, cells, hint, killers, ply), reverse=True)
    if quiet_tail and not in_check:
        tactical = []
        for pair in moves:
            src, dst = pair
            if cells[dst] != "." or dst == ep_square or (cells[src].lower() == "p" and (dst < 8 or dst >= 56)):
                tactical.append(pair)
        moves = tactical
        if not moves:
            return static
    chosen = None
    top = -10000
    for pair in moves:
        value = -negamax(apply_move(state, pair), depth - 1, -beta, -alpha, ply + 1, quiet_tail)
        if value > top:
            top, chosen = value, pair
        alpha = max(alpha, value)
        if alpha >= beta:
            if cells[pair[1]] == ".":
                prior = killer_cache.get(ply, ())
                killer_cache[ply] = (pair,) + tuple(x for x in prior if x != pair)[:1]
                slot = (cells[pair[0]], pair[0], pair[1])
                history_cache[slot] = min(20000, history_cache.get(slot, 0) + depth * depth)
            break
    board_cache[signature] = chosen
    return top


def choose_move(state, allowed_moves):
    global visited
    pool = list(legal_moves(state))
    pool = [pair for pair in pool if uci_text(pair, state[0]) in allowed_moves]
    if not pool:
        return allowed_moves[0]
    board_cache.clear()
    killer_cache.clear()
    history_cache.clear()
    visited = 0
    chosen = pool[0]
    for depth in range(1, 20):
        try:
            alpha = -10000
            round_best = chosen
            ordered = sorted(pool, key=lambda pair: pair == chosen, reverse=True)
            for pair in ordered:
                value = -negamax(apply_move(state, pair), depth - 1, -10000, -alpha)
                if value > alpha:
                    alpha, round_best = value, pair
            chosen = round_best
        except TimeoutError:
            break
    return uci_text(chosen, state[0])


def play():
    server = os.environ["MAKEFUN_ENV_URL"]

    def call(suffix, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(server + suffix, data, {"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=9).read())

    while True:
        game = call("/game", {})
        while game.get("status") == "your_move":
            reply = choose_move(load_fen(game["fen"]), game["legal_moves"])
            game = call("/move", {"game": game["game"], "move": reply})
        if game.get("status") != "over":
            return


if __name__ == "__main__" and "MAKEFUN_ENV_URL" in os.environ:
    try:
        play()
    except Exception:
        pass
