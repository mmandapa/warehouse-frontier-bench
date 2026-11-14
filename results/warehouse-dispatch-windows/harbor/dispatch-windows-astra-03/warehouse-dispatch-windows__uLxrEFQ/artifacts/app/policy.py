"""Contingent, reservation-aware dispatch using only the standard library.

Before the announcement, a shared schedule must have a feasible continuation
under *each* calendar. After it, only the announced continuation is executed.
Single-cart time-expanded shortest paths prune the joint feasibility search.
"""

from time import monotonic

from client import Dispatch


INF = 10**9


class Plan:
    __slots__ = ('tick', 'state', 'moves', 'next')

    def __init__(self, tick, state, moves, following):
        self.tick, self.state = tick, state
        self.moves, self.next = moves, following


class Branch:
    __slots__ = ('choices',)

    def __init__(self, choices):
        self.choices = choices


class SearchTimeout(Exception):
    pass


class Planner:
    def __init__(self, observation, stop):
        self.stop = stop
        self.calls = 0
        self.carts = observation['carts']
        self.count = len(self.carts)
        self.start_tick = observation['tick']
        self.horizon = max(c['deadline'] for c in self.carts)
        notice = observation.get('notice')
        self.announce = notice['announce_tick'] if notice else 0
        orders = notice['orders'] if notice else [[], []]
        names = {n for a, b, _ in observation['lanes'] for n in (a, b)}
        for c in self.carts:
            names.update((c['start'], c['pickup'], c['delivery'], c['at']))
        self.names = sorted(names)
        self.node = {name: i for i, name in enumerate(self.names)}
        n = len(self.names)
        self.pickups = [self.node[c['pickup']] for c in self.carts]
        self.deliveries = [self.node[c['delivery']] for c in self.carts]
        self.deadlines = [c['deadline'] for c in self.carts]
        self.adj = [[] for _ in range(n)]
        # Location records: origin, destination (-1 if parked), ticks left,
        # reserved destination bit, reserved lane bit, next location.
        self.locations = [(i, -1, 0, 1 << i, 0, i) for i in range(n)]
        self.transit = {}
        self.edge_ids = {}
        for eid, (a, b, duration) in enumerate(observation['lanes']):
            a, b = self.node[a], self.node[b]
            self.edge_ids[tuple(sorted((a, b)))] = eid
            for u, v in ((a, b), (b, a)):
                previous = v
                for remaining in range(1, duration):
                    loc = len(self.locations)
                    self.transit[u, v, remaining] = loc
                    self.locations.append((u, v, remaining, 1 << v,
                                           1 << eid, previous))
                    previous = loc
                self.adj[u].append((v, previous, 1 << eid, duration))
        self.size = len(self.locations) * 3
        self.closed, self.paused = [], []
        for events in orders:
            closed = [0] * (self.horizon + 1)
            paused = [0] * (self.horizon + 1)
            for e in events:
                if 'lane' in e:
                    a, b = (self.node[x] for x in e['lane'])
                    mask = 1 << self.edge_ids[tuple(sorted((a, b)))]
                    target = closed
                else:
                    mask = 1 << self.node[e['bay']]
                    target = paused
                for t in range(max(0, e['start']), min(self.horizon + 1, e['end'])):
                    target[t] |= mask
            # The observation is authoritative about currently active service.
            for a, b in observation['closed']:
                edge = tuple(sorted((self.node[a], self.node[b])))
                closed[self.start_tick] |= 1 << self.edge_ids[edge]
            for bay in observation['paused']:
                paused[self.start_tick] |= 1 << self.node[bay]
            self.closed.append(closed)
            self.paused.append(paused)
        self.distance = [[INF] * n for _ in range(n)]
        for u in range(n):
            self.distance[u][u] = 0
            for v, _, _, d in self.adj[u]:
                self.distance[u][v] = min(self.distance[u][v], d)
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    self.distance[i][j] = min(self.distance[i][j],
                                             self.distance[i][k] + self.distance[k][j])
        self.failed = [set(), set(), set()]
        self.success = [{}, {}]
        self.bounds = [[self.make_bounds(i, mode) for i in range(self.count)]
                       for mode in range(2)]

    def state_from(self, observation):
        result = []
        for cart in observation['carts']:
            at = self.node[cart['at']]
            if cart['to'] is None:
                loc = at
            else:
                loc = self.transit[at, self.node[cart['to']], cart['remaining']]
            result.append(3 * loc + cart['stage'])
        return tuple(result)

    def service_one(self, i, value, paused):
        loc, stage = divmod(value, 3)
        at, dest, _, _, _, _ = self.locations[loc]
        if dest == -1 and not (paused & (1 << at)):
            if stage == 0 and at == self.pickups[i]:
                return value + 1
            if stage == 1 and at == self.deliveries[i]:
                return value + 1
        return value

    def serviced(self, state, tick, mode):
        paused = self.paused[mode][tick]
        return tuple(self.service_one(i, x, paused) for i, x in enumerate(state))

    def make_bounds(self, i, mode):
        """Earliest completion, ignoring other carts; INF means impossible.

        Entries accept states immediately before boundary service. Thus arrival
        at an opening bay or precisely at the deadline is handled exactly.
        """
        deadline = self.deadlines[i]
        table = [[INF] * self.size for _ in range(self.horizon + 1)]
        for t in range(self.horizon, self.start_tick - 1, -1):
            row = table[t]
            for x in range(self.size):
                value = self.service_one(i, x, self.paused[mode][t])
                loc, stage = divmod(value, 3)
                if stage == 2:
                    row[x] = t
                    continue
                if t >= deadline:
                    continue
                at, dest, _, _, _, following = self.locations[loc]
                nxt = table[t + 1]
                best = nxt[following * 3 + stage]
                if dest == -1:
                    for _, arrival, edge, _ in self.adj[at]:
                        if not edge & self.closed[mode][t]:
                            best = min(best, nxt[arrival * 3 + stage])
                row[x] = best
        return table

    def distance_left(self, i, value):
        loc, stage = divmod(value, 3)
        if stage == 2:
            return 0
        at, dest, remaining, _, _, _ = self.locations[loc]
        if dest != -1:
            at = dest
        if stage == 0:
            return (remaining + self.distance[at][self.pickups[i]] +
                    self.distance[self.pickups[i]][self.deliveries[i]])
        return remaining + self.distance[at][self.deliveries[i]]

    def candidates(self, state, tick, mode):
        modes = (0, 1) if mode == -1 else (mode,)
        occupied = busy = 0
        for x in state:
            record = self.locations[x // 3]
            occupied |= record[3]
            busy |= record[4]
        options = []
        for i, x in enumerate(state):
            loc, stage = divmod(x, 3)
            at, dest, _, _, _, following = self.locations[loc]
            choices = [(following * 3 + stage, -1, 0, 0)]
            if dest == -1:
                for target, arrival, edge, _ in self.adj[at]:
                    bit = 1 << target
                    if bit & occupied or edge & busy:
                        continue
                    if any(edge & self.closed[m][tick] for m in modes):
                        continue
                    choices.append((arrival * 3 + stage, target, bit, edge))
            ranked = []
            for value, target, bit, edge in choices:
                finishes = [self.bounds[m][i][tick + 1][value] for m in modes]
                if max(finishes) == INF:
                    continue
                normalized = [self.service_one(i, value, self.paused[m][tick + 1])
                              for m in modes]
                # Favor delivery and progress, while leaving completed carts
                # parked unless their movement helps another cart's schedule.
                finish_score = sum(f if v % 3 != 2 else tick + 1
                                   for f, v in zip(finishes, normalized))
                distance_score = sum(self.distance_left(i, v) for v in normalized)
                score = (finish_score, distance_score,
                         int(stage == 2 and target != -1), int(target != -1))
                ranked.append((score, value, target, bit, edge))
            if not ranked:
                return []
            ranked.sort()
            options.append(ranked)
        # Enumerate only compatible combinations, then rank joint successors.
        candidates = []
        following = [0] * self.count
        moves = {}

        def combine(i, reserved, lanes, score):
            if i == self.count:
                candidates.append((score, tuple(following), moves.copy()))
                return
            for cost, value, target, bit, edge in options[i]:
                if bit & reserved or edge & lanes:
                    continue
                following[i] = value
                if target != -1:
                    moves[self.carts[i]['id']] = self.names[target]
                combine(i + 1, reserved | bit, lanes | edge,
                        tuple(a + b for a, b in zip(score, cost)))
                if target != -1:
                    del moves[self.carts[i]['id']]

        combine(0, 0, 0, (0, 0, 0, 0))
        candidates.sort(key=lambda c: c[0])
        return candidates

    def search(self, state, tick, mode):
        self.calls += 1
        if self.calls % 128 == 1 and monotonic() >= self.stop:
            raise SearchTimeout
        if mode == -1 and tick >= self.announce:
            choices = []
            for selected in range(2):
                solution = self.search(state, tick, selected)
                if solution is False:
                    return False
                choices.append(solution)
            return Branch(choices)
        state = self.serviced(state, tick, max(mode, 0))
        if all(x % 3 == 2 for x in state):
            return None
        key = (tick, state)
        cache = self.failed[mode]
        if key in cache:
            return False
        if mode != -1 and key in self.success[mode]:
            return self.success[mode][key]
        modes = (0, 1) if mode == -1 else (mode,)
        if tick >= self.horizon or any(self.bounds[m][i][tick][x] == INF
                                      for m in modes for i, x in enumerate(state)):
            return False
        for _, following, moves in self.candidates(state, tick, mode):
            continuation = self.search(following, tick + 1, mode)
            if continuation is not False:
                solution = Plan(tick, state, moves, continuation)
                if mode != -1:
                    self.success[mode][key] = solution
                return solution
        # Bound memory without changing correctness: forgotten failures can
        # simply be explored again if necessary.
        if len(cache) >= 200000:
            cache.clear()
        cache.add(key)
        return False


def main():
    dispatch = Dispatch()
    plan = None
    planner = None
    stop = monotonic() + 27.0
    while True:
        observation = dispatch.observe()
        if 'result' in observation:
            return
        while isinstance(plan, Branch):
            plan = plan.choices[observation['selected']]
        if (planner is None or plan is None or plan is False or
                plan.tick != observation['tick'] or
                plan.state != planner.state_from(observation)):
            planner = Planner(observation, stop)
            selected = observation.get('selected')
            mode = selected if selected is not None else (-1 if observation.get('notice') else 0)
            try:
                plan = planner.search(planner.state_from(observation), observation['tick'], mode)
            except SearchTimeout:
                plan = False
            while isinstance(plan, Branch):
                plan = plan.choices[observation['selected']]
        if plan is None or plan is False:
            dispatch.step({})
        else:
            dispatch.step(plan.moves)
            plan = plan.next


if __name__ == '__main__':
    main()
