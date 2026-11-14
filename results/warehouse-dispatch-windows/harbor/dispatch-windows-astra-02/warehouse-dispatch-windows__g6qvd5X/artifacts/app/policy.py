"""Contingent, deadline-constrained joint dispatch planning.

The search shares all decisions before the notice and requires a complete
continuation for each order. Single-cart time-expanded shortest paths are
admissible bounds; the joint search enforces the stronger reservation rules.
"""
from client import Dispatch
import sys
import time

INF = 10 ** 9


class OutOfTime(Exception):
    pass


class Planner:
    def __init__(self, view, seconds=25.0):
        self.stop = time.monotonic() + seconds
        self.ids = [c['id'] for c in view['carts']]
        names = {v for a, b, _ in view['lanes'] for v in (a, b)}
        names.update(c[k] for c in view['carts'] for k in ('at', 'pickup', 'delivery'))
        self.names = sorted(names)
        self.nodes = {v: i for i, v in enumerate(self.names)}
        n = len(self.names)
        self.adj = [[] for _ in range(n)]
        self.edges = {}
        for a, b, d in view['lanes']:
            a, b = self.nodes[a], self.nodes[b]
            edge = tuple(sorted((a, b)))
            self.edges[edge] = d
        for (a, b), d in self.edges.items():
            self.adj[a].append((b, d, (a, b)))
            self.adj[b].append((a, d, (a, b)))
        self.jobs = [(self.nodes[c['pickup']], self.nodes[c['delivery']], c['deadline'])
                     for c in view['carts']]
        self.horizon = max(c['deadline'] for c in view['carts'])
        notice = view.get('notice')
        self.announce = notice['announce_tick'] if notice else 0
        orders = notice['orders'] if notice else [[], []]
        self.closed, self.paused, self.bounds = [], [], []
        for order in orders:
            closed = [set() for _ in range(self.horizon + 1)]
            paused = [set() for _ in range(self.horizon + 1)]
            for event in order:
                for t in range(max(0, event['start']), min(self.horizon + 1, event['end'])):
                    if 'lane' in event:
                        closed[t].add(tuple(sorted(self.nodes[v] for v in event['lane'])))
                    else:
                        paused[t].add(self.nodes[event['bay']])
            # The observation is authoritative about the current tick.
            closed[view['tick']] = {tuple(sorted(self.nodes[v] for v in e)) for e in view['closed']}
            paused[view['tick']] = {self.nodes[v] for v in view['paused']}
            self.closed.append(closed)
            self.paused.append(paused)
            tables = []
            for pickup, delivery, deadline in self.jobs:
                table = [[[INF] * n for _ in range(2)] for _ in range(deadline + 1)]
                for t in range(deadline, -1, -1):
                    for stage in (1, 0):
                        for at in range(n):
                            if at not in paused[t]:
                                if stage == 1 and at == delivery:
                                    table[t][stage][at] = 0
                                    continue
                                if stage == 0 and at == pickup:
                                    table[t][stage][at] = table[t][1][at]
                                    continue
                            best = 1 + table[t + 1][stage][at] if t < deadline else INF
                            for dest, duration, edge in self.adj[at]:
                                if t + duration <= deadline and edge not in closed[t]:
                                    best = min(best, duration + table[t + duration][stage][dest])
                            table[t][stage][at] = min(INF, best)
                tables.append(table)
            self.bounds.append(tables)
        self.failed = [set(), set(), set()]
        self.solutions = [{}, {}]
        self.visits = 0
        self.initial = tuple((self.nodes[c['at']], self.nodes[c['to']] if c['to'] is not None else -1,
                              c['remaining'], c['stage']) for c in view['carts'])
        self.start = view['tick']
        self.selected = view['selected'] if notice else 0

    def check_time(self):
        self.visits += 1
        if self.visits % 128 == 0 and time.monotonic() >= self.stop:
            raise OutOfTime

    def service(self, state, tick, mode):
        paused = self.paused[mode][tick]
        result = []
        for (at, dest, left, stage), (pickup, delivery, _) in zip(state, self.jobs):
            if dest == -1 and at not in paused:
                if stage == 0 and at == pickup:
                    stage = 1
                elif stage == 1 and at == delivery:
                    stage = 2
            result.append((at, dest, left, stage))
        return tuple(result)

    def distance(self, cart, state, tick, mode):
        at, dest, left, stage = state
        if stage == 2:
            return 0
        if dest != -1:
            tick += left
            at = dest
        else:
            left = 0
        if tick > self.jobs[cart][2]:
            return INF
        return left + self.bounds[mode][cart][tick][stage][at]

    def feasible(self, state, tick, modes):
        return all(self.distance(i, s, tick, m) < INF
                   for m in modes for i, s in enumerate(state))

    def children(self, state, tick, modes):
        """Generate valid simultaneous batches, keeping start-of-tick occupancy."""
        occupied = {at for at, dest, _, _ in state if dest == -1}
        reserved = {dest for _, dest, _, _ in state if dest != -1}
        busy = {tuple(sorted((at, dest))) for at, dest, _, _ in state if dest != -1}
        closed = self.closed[modes[0]][tick]
        options = []
        for i, (at, dest, left, stage) in enumerate(state):
            choices = []
            if dest != -1:
                nxt = (dest, -1, 0, stage) if left == 1 else (at, dest, left - 1, stage)
                choices.append((-1, nxt, None))
            else:
                choices.append((-1, (at, -1, 0, stage), None))
                for target, duration, edge in self.adj[at]:
                    if target in occupied or target in reserved or edge in busy or edge in closed:
                        continue
                    nxt = ((target, -1, 0, stage) if duration == 1
                           else (at, target, duration - 1, stage))
                    choices.append((target, nxt, edge))
            choices = [(target, nxt, edge, tuple(self.distance(i, nxt, tick + 1, m) for m in modes))
                       for target, nxt, edge in choices]
            choices = [c for c in choices if max(c[3]) < INF]
            if not choices:
                return []
            options.append(choices)
        candidates = []
        next_state, moves = [], []

        def combine(i, claimed, lanes, costs, movement):
            if i == len(state):
                # Lower remaining work first. A small movement cost prevents
                # gratuitous motion while preserving moves by delivered carts.
                score = max(costs) + movement * 0.04
                candidates.append((score, tuple(next_state), tuple(moves)))
                return
            for target, nxt, edge, bounds in options[i]:
                if target != -1 and (target in claimed or edge in lanes):
                    continue
                next_state.append(nxt)
                moves.append(target)
                if target != -1:
                    claimed.add(target)
                    lanes.add(edge)
                combine(i + 1, claimed, lanes, [a + b for a, b in zip(costs, bounds)],
                        movement + (target != -1))
                if target != -1:
                    claimed.remove(target)
                    lanes.remove(edge)
                moves.pop()
                next_state.pop()

        combine(0, set(), set(), [0] * len(modes), 0)
        candidates.sort(key=lambda c: c[0])
        return candidates

    def known(self, state, tick, mode):
        self.check_time()
        state = self.service(state, tick, mode)
        if all(s[3] == 2 for s in state):
            return ()
        key = (tick, state)
        if key in self.failed[mode]:
            return None
        if key in self.solutions[mode]:
            return self.solutions[mode][key]
        if tick >= self.horizon or not self.feasible(state, tick, (mode,)):
            return None
        for _, nxt, moves in self.children(state, tick, (mode,)):
            tail = self.known(nxt, tick + 1, mode)
            if tail is not None:
                plan = (moves,) + tail
                self.solutions[mode][key] = plan
                return plan
        self.failed[mode].add(key)
        # Bound memory independently of the number of reachable joint states.
        if len(self.failed[mode]) > 180000:
            self.failed[mode].clear()
        return None

    def contingent(self, state, tick):
        self.check_time()
        if tick >= self.announce:
            plans = [None, None]
            # Try the tighter maintenance calendar first.
            order = sorted(range(2), key=lambda m: -sum(self.distance(i, s, tick, m)
                                                       for i, s in enumerate(state)))
            for mode in order:
                plans[mode] = self.known(state, tick, mode)
                if plans[mode] is None:
                    return None
            return (), plans
        state = self.service(state, tick, 0)
        if all(s[3] == 2 for s in state):
            return (), [(), ()]
        key = (tick, state)
        if key in self.failed[2] or not self.feasible(state, tick, (0, 1)):
            return None
        for _, nxt, moves in self.children(state, tick, (0, 1)):
            answer = self.contingent(nxt, tick + 1)
            if answer is not None:
                prefix, branches = answer
                return (moves,) + prefix, branches
        self.failed[2].add(key)
        return None

    def solve(self):
        if self.selected is None:
            return self.contingent(self.initial, self.start)
        plan = self.known(self.initial, self.start, self.selected)
        return ((), [plan, plan]) if plan is not None else None

    def commands(self, moves):
        return {cart: self.names[target] for cart, target in zip(self.ids, moves) if target != -1}


def main():
    sys.setrecursionlimit(10000)
    dispatch = Dispatch()
    prefix, branches, planner, origin = (), None, None, 0
    started = time.monotonic()
    while True:
        view = dispatch.observe()
        if 'result' in view:
            return
        if branches is None:
            planner = Planner(view, max(0.05, 26.0 - (time.monotonic() - started)))
            origin = view['tick']
            try:
                answer = planner.solve()
            except OutOfTime:
                answer = None
            if answer is not None:
                prefix, branches = answer
            else:
                # A bounded-search fallback still respects all reservations.
                # Reconsider with the revealed calendar on the next observation.
                modes = (0, 1) if view['selected'] is None and view.get('notice') else (view['selected'] or 0,)
                choices = planner.children(planner.initial, view['tick'], modes)
                dispatch.step(planner.commands(choices[0][2]) if choices else {})
                continue
        offset = view['tick'] - origin
        if offset < len(prefix):
            moves = prefix[offset]
        else:
            mode = view['selected'] or 0
            branch = branches[mode]
            offset -= len(prefix)
            moves = branch[offset] if offset < len(branch) else (-1,) * len(planner.ids)
        dispatch.step(planner.commands(moves))


if __name__ == '__main__':
    main()
