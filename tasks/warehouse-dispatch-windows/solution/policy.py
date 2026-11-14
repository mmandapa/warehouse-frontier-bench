"""Search feasible joint moves and replan from the next observed state."""

from collections import defaultdict
from functools import lru_cache
from itertools import product
from math import inf

from client import Dispatch


def plan(view, mode="robust"):
    carts, tick = view['carts'], view['tick']
    paths = defaultdict(list)
    for a, b, duration in view['lanes']:
        paths[a].append((b, duration))
        paths[b].append((a, duration))
    nodes = sorted(paths)
    distance = {(a, b): 0 if a == b else inf for a in nodes for b in nodes}
    for a in nodes:
        for b, duration in paths[a]:
            distance[a, b] = duration
    for mid in nodes:
        for a in nodes:
            for b in nodes:
                distance[a, b] = min(distance[a, b], distance[a, mid] + distance[mid, b])

    starting = tuple((c['at'], c['to'], c['remaining'], c['stage']) for c in carts)
    notice = view['notice']
    announcement = notice['announce_tick'] if notice else tick
    selected = view['selected']
    orders = notice['orders'] if notice else [[]]

    @lru_cache(maxsize=None)
    def unavailable(order, now):
        events = orders[order] if now >= announcement else []
        active = [e for e in events if e['start'] <= now < e['end']]
        return ({frozenset(e['lane']) for e in active if 'lane' in e},
                {e['bay'] for e in active if 'bay' in e})

    def estimate(state, now):
        remaining = []
        for (at, destination, left, stage), cart in zip(state, carts, strict=True):
            if stage == 2:
                remaining.append(0)
                continue
            at = destination if destination is not None else at
            pickup, delivery = cart['pickup'], cart['delivery']
            if stage == 0:
                left += distance[at, pickup] + distance[pickup, delivery]
            else:
                left += distance[at, delivery]
            if now + left > cart['deadline'] or now >= cart['deadline']:
                return None
            remaining.append(left)
        return max(remaining), sum(remaining)

    def successors(state, now, order):
        occupied = {at for at, dest, _, _ in state if dest is None}
        reserved = {dest for _, dest, _, _ in state if dest is not None}
        busy = {frozenset((at, dest)) for at, dest, _, _ in state if dest is not None}
        blocked, _ = unavailable(order, now)
        _, paused = unavailable(order, now + 1)
        options = []
        for at, dest, _, _ in state:
            allowed = [(None, 0)]
            if dest is None:
                for target, length in paths[at]:
                    if target not in occupied and target not in reserved and frozenset((at, target)) not in busy | blocked:
                        allowed.append((target, length))
            options.append(allowed)
        for choices in product(*options):
            targets = [target for target, _ in choices if target is not None]
            if len(targets) != len(set(targets)):
                continue
            updated = []
            for (at, dest, left, stage), (target, duration), cart in zip(state, choices, carts, strict=True):
                if target is not None:
                    dest, left = target, duration
                if dest is not None:
                    left -= 1
                    if not left:
                        at, dest = dest, None
                if dest is None and at not in paused:
                    if stage == 0 and at == cart['pickup']:
                        stage = 1
                    elif stage == 1 and at == cart['delivery']:
                        stage = 2
                updated.append((at, dest, left, stage))
            moves = {cart['id']: target for cart, (target, _) in zip(carts, choices, strict=True) if target is not None}
            yield tuple(updated), moves

    @lru_cache(maxsize=150_000)
    def find(now, state, order):
        if all(entry[-1] == 2 for entry in state):
            return {}
        if estimate(state, now) is None:
            return None
        candidates = []
        for after, moves in successors(state, now, order if order is not None else 0):
            estimate_after = estimate(after, now + 1)
            if estimate_after is not None:
                candidates.append((estimate_after, -len(moves), moves, after))
        candidates.sort(key=lambda item: item[:2])
        arrivals = {}
        reveal = order is None and now + 1 == announcement
        if reveal:
            # Service at the reveal boundary can differ between the orders.
            arrivals = {tuple(sorted(m.items())): other for other, m in successors(state, now, 1)}
        for _, _, moves, after in candidates:
            if reveal:
                other = arrivals[tuple(sorted(moves.items()))]
                feasible = find(now + 1, after, 0) is not None and find(now + 1, other, 1) is not None
            else:
                feasible = find(now + 1, after, order) is not None
            if feasible:
                return moves
        return None

    order = selected if selected is not None else None
    if order is None and mode in ('guess-a', 'guess-b'):
        order = int(mode == 'guess-b')
    if not notice:
        order = 0
    return find(tick, starting, order) or {}


if __name__ == '__main__':
    dispatch = Dispatch()
    while 'result' not in (view := dispatch.observe()):
        dispatch.step(plan(view))
