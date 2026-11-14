"""Contingent, reservation-aware dispatch planning (standard library only)."""
from array import array
import heapq
import itertools
import time

from client import Dispatch


INF = 10 ** 9


class Warehouse:
    def __init__(self, view, stop):
        self.stop = stop
        self.tick = view['tick']
        self.carts = view['carts']
        self.count = len(self.carts)
        self.names = sorted({n for a, b, _ in view['lanes'] for n in (a, b)} |
                            {c[k] for c in self.carts for k in ('at', 'pickup', 'delivery')})
        self.index = {n: i for i, n in enumerate(self.names)}
        self.n = len(self.names)
        self.pick = [self.index[c['pickup']] for c in self.carts]
        self.drop = [self.index[c['delivery']] for c in self.carts]
        self.deadline = [c['deadline'] for c in self.carts]
        self.horizon = max(self.deadline)
        self.announce = (view.get('notice') or {}).get('announce_tick', self.tick)
        # Each location is either a node or one tick of a directed lane traversal.
        self.options = [[] for _ in self.names]
        self.occupied = [1 << i for i in range(self.n)]
        self.busy = [0] * self.n
        self.transit = {}
        self.edge_index = {}
        for edge, (a, b, duration) in enumerate(view['lanes']):
            a, b = self.index[a], self.index[b]
            bit = 1 << edge
            self.edge_index[tuple(sorted((a, b)))] = bit
            for origin, target in ((a, b), (b, a)):
                previous = target
                for remaining in range(1, duration):
                    loc = len(self.options)
                    self.transit[origin, target, remaining] = loc
                    self.options.append([(previous, 0, 0, -1)])
                    self.occupied.append(1 << target)
                    self.busy.append(bit)
                    previous = loc
                self.options[origin].append((previous, 1 << target, bit, target))
        for node in range(self.n):
            self.options[node].insert(0, (node, 0, 0, -1))
        self.locations = len(self.options)
        orders = (view.get('notice') or {}).get('orders', [[], []])
        if len(orders) == 1:
            orders = orders * 2
        self.closed = []
        self.paused = []
        for events in orders:
            closed = [0] * (self.horizon + 1)
            paused = [0] * (self.horizon + 1)
            for event in events:
                if 'lane' in event:
                    a, b = (self.index[n] for n in event['lane'])
                    bit = self.edge_index[tuple(sorted((a, b)))]
                    schedule = closed
                else:
                    bit = 1 << self.index[event['bay']]
                    schedule = paused
                for t in range(max(0, event['start']), min(self.horizon + 1, event['end'])):
                    schedule[t] |= bit
            # The observation is authoritative for the current boundary.
            closed[self.tick] = sum({self.edge_index[tuple(sorted(self.index[n] for n in pair))]
                                     for pair in view['closed']})
            paused[self.tick] = sum(1 << self.index[n] for n in set(view['paused']))
            self.closed.append(closed)
            self.paused.append(paused)
        self.tables = [[self.lower_bounds(world, i) for i in range(self.count)]
                       for world in range(2)]
        self.initial = self.encode(view)
        self.failed = [set(), set()]

    def encode(self, view):
        result = []
        for c in view['carts']:
            at = self.index[c['at']]
            loc = at if c['to'] is None else self.transit[at, self.index[c['to']], c['remaining']]
            result.append(loc * 3 + c['stage'])
        return tuple(result)

    def service(self, code, cart, tick, world):
        loc, stage = divmod(code, 3)
        if loc < self.n and not (self.paused[world][tick] & (1 << loc)):
            if stage == 0 and loc == self.pick[cart]:
                stage = 1
            elif stage == 1 and loc == self.drop[cart]:
                stage = 2
        return loc * 3 + stage

    def normalize(self, state, tick, world):
        return tuple(self.service(code, i, tick, world) for i, code in enumerate(state))

    def lower_bounds(self, world, cart):
        """Exact earliest delivery times for one cart, ignoring other carts."""
        deadline = self.deadline[cart]
        width = self.locations * 2
        table = [None] * (deadline + 1)
        pickup, delivery = self.pick[cart], self.drop[cart]
        for tick in range(deadline, self.tick - 1, -1):
            row = array('i', [INF]) * width
            following = table[tick + 1] if tick < deadline else None
            closed, paused = self.closed[world][tick], self.paused[world][tick]
            for loc, options in enumerate(self.options):
                open_bay = loc < self.n and not (paused & (1 << loc))
                for stage in (1, 0):
                    if open_bay and stage == 1 and loc == delivery:
                        value = tick
                    elif open_bay and stage == 0 and loc == pickup:
                        value = row[loc * 2 + 1]
                    elif following is None:
                        value = INF
                    else:
                        value = min((following[nxt * 2 + stage]
                                     for nxt, _, edge, _ in options if not edge & closed), default=INF)
                    row[loc * 2 + stage] = value
            table[tick] = row
        return table

    def estimate(self, state, tick, world):
        total = 0
        for i, code in enumerate(state):
            loc, stage = divmod(code, 3)
            if stage == 2:
                continue
            if tick > self.deadline[i]:
                return INF
            if world == -1:
                end = max(self.tables[w][i][tick][loc * 2 + stage] for w in (0, 1))
            else:
                end = self.tables[world][i][tick][loc * 2 + stage]
            if end == INF:
                return INF
            total += end - tick
        return total

    def successors(self, state, tick, world):
        if tick >= self.horizon:
            return
        occupied = busy = 0
        for code in state:
            loc = code // 3
            occupied |= self.occupied[loc]
            busy |= self.busy[loc]
        # Before the announcement both calendars have identical active events.
        active_world = max(world, 0)
        closed = self.closed[active_world][tick]
        next_tick = tick + 1
        choices = []
        for i, code in enumerate(state):
            loc, stage = divmod(code, 3)
            options = []
            for nxt, target, edge, command in self.options[loc]:
                if target & occupied or edge & (busy | closed):
                    continue
                newcode = nxt * 3 + stage
                # At the announcement keep the raw state; each branch services it.
                if world != -1 or next_tick < self.announce:
                    newcode = self.service(newcode, i, next_tick, active_world)
                newloc, newstage = divmod(newcode, 3)
                remaining = 0
                if newstage != 2:
                    if next_tick > self.deadline[i]:
                        continue
                    if world == -1:
                        end = max(self.tables[w][i][next_tick][newloc * 2 + newstage]
                                  for w in (0, 1))
                    else:
                        end = self.tables[world][i][next_tick][newloc * 2 + newstage]
                    if end == INF:
                        continue
                    remaining = end - next_tick
                options.append((newcode, target, edge, command, remaining))
            if not options:
                return
            choices.append(options)
        next_state = [0] * self.count
        commands = [-1] * self.count

        def combine(i, destinations, lanes, heuristic, extra):
            if i == self.count:
                yield tuple(next_state), tuple(commands), heuristic, extra
                return
            for code, target, edge, command, remaining in choices[i]:
                if target & destinations or edge & lanes:
                    continue
                next_state[i] = code
                commands[i] = command
                # Slightly prefer leaving completed carts parked when possible.
                penalty = 0.02 if state[i] % 3 == 2 and command >= 0 else 0
                yield from combine(i + 1, destinations | target, lanes | edge,
                                   heuristic + remaining, extra + penalty)
        yield from combine(0, 0, 0, 0, 0)

    def moves(self, commands):
        return {c['id']: self.names[command]
                for c, command in zip(self.carts, commands) if command >= 0}


class Search:
    """Weighted joint-state A*, with resumable work limits."""
    def __init__(self, warehouse, state, tick, world):
        self.w = warehouse
        self.world = world
        if world >= 0:
            state = warehouse.normalize(state, tick, world)
        self.root = (tick, state)
        self.serial = itertools.count()
        self.heap = []
        self.best = {self.root: 0}
        self.parents = {self.root: None}
        self.expanded = 0
        h = warehouse.estimate(state, tick, world)
        if h < INF and (world == -1 or self.root not in warehouse.failed[world]):
            heapq.heappush(self.heap, (2.5 * h, h, next(self.serial), 0, self.root))

    def path(self, key):
        path = []
        while self.parents[key] is not None:
            key, commands = self.parents[key]
            path.append(commands)
        path.reverse()
        return path

    def run(self, limit):
        end = self.expanded + limit
        while self.heap and self.expanded < end:
            if time.monotonic() >= self.w.stop:
                return 'pending', None
            _, _, _, g, key = heapq.heappop(self.heap)
            if self.best.get(key) != g:
                continue
            tick, state = key
            if all(code % 3 == 2 for code in state):
                return 'solved', (key, self.path(key))
            if self.world == -1 and tick >= self.w.announce:
                return 'branch', (key, self.path(key))
            self.expanded += 1
            unfinished = sum(code % 3 != 2 for code in state)
            for newstate, commands, h, extra in self.w.successors(state, tick, self.world):
                newkey = (tick + 1, newstate)
                if self.world >= 0 and newkey in self.w.failed[self.world]:
                    continue
                newg = g + unfinished + extra
                if newg >= self.best.get(newkey, INF):
                    continue
                self.best[newkey] = newg
                self.parents[newkey] = (key, commands)
                heapq.heappush(self.heap, (newg + 2.5 * h, h, next(self.serial), newg, newkey))
            # Avoid exhausting the shift's address space on a very large frontier.
            if len(self.best) > 160000:
                return 'large', None
        if self.heap:
            return 'pending', None
        if self.world >= 0:
            failed = self.w.failed[self.world]
            if len(failed) + len(self.best) <= 100000:
                failed.update(self.best)
            else:
                failed.add(self.root)
        return 'impossible', None


def plan(warehouse, selected):
    w = warehouse
    if selected is not None or w.tick >= w.announce:
        search = Search(w, w.initial, w.tick, selected if selected is not None else 0)
        status, result = search.run(1000000)
        if status == 'solved':
            return result[1], None
        return None, None

    prefix = Search(w, w.initial, w.tick, -1)
    deferred = []
    prefix_done = False
    while time.monotonic() < w.stop:
        if not prefix_done:
            status, result = prefix.run(2000)
            if status == 'solved':
                return result[1], None
            if status == 'branch':
                (tick, state), shared = result
                deferred.append([tick, state, shared, [None, None], 400])
            elif status in ('impossible', 'large'):
                prefix_done = True
        # Try each candidate with a bounded amount of work, so one difficult
        # continuation cannot prevent considering a different early dispatch.
        if deferred:
            item = deferred.pop(0)
            tick, state, shared, plans, batch = item
            possible = True
            for world in (0, 1):
                if plans[world] is not None:
                    continue
                search = Search(w, state, tick, world)
                status, result = search.run(batch)
                if status == 'solved':
                    plans[world] = result[1]
                elif status in ('impossible', 'large'):
                    possible = False
                # Retain successful plans, but release unfinished frontiers.
                # Retrying with a larger allowance bounds memory independently
                # of the number of announcement states under consideration.
                del search
                if not possible:
                    break
            if possible:
                if all(p is not None for p in plans):
                    return shared, plans
                item[4] = batch * 4
                deferred.append(item)
        if prefix_done and not deferred:
            break
    return None, None


def main():
    dispatch = Dispatch()
    view = dispatch.observe()
    if 'result' in view:
        return
    started = time.monotonic()
    w = Warehouse(view, started + 24.0)
    shared, branches = plan(w, view.get('selected'))
    commands = shared or []
    offset = view['tick']
    while 'result' not in view:
        tick = view['tick']
        if branches is not None and tick >= w.announce:
            commands = branches[view['selected']]
            offset = tick
            branches = None
        index = tick - offset
        if index >= len(commands):
            # Normally the complete contingent plan covers the shift. Replan
            # from the observed state if a calendar was absent or changed.
            w = Warehouse(view, started + 28.0)
            commands, branches = plan(w, view.get('selected'))
            commands = commands or []
            offset = tick
            index = 0
        move = w.moves(commands[index]) if index < len(commands) else {}
        dispatch.step(move)
        view = dispatch.observe()


if __name__ == '__main__':
    main()
