"""Contingent, deadline-constrained dispatch using only the standard library."""

from client import Dispatch
import sys
import time


INF = 10 ** 9


class SearchTimeout(Exception):
    pass


class Planner:
    def __init__(self, observation, stop):
        self.stop = stop
        self.jobs = observation['carts']
        self.count = len(self.jobs)
        self.nodes = sorted({v for a, b, _ in observation['lanes'] for v in (a, b)} |
                            {c[k] for c in self.jobs for k in ('start', 'pickup', 'delivery')})
        self.index = {v: i for i, v in enumerate(self.nodes)}
        n = len(self.nodes)
        self.pickup = [self.index[c['pickup']] for c in self.jobs]
        self.delivery = [self.index[c['delivery']] for c in self.jobs]
        self.deadlines = [c['deadline'] for c in self.jobs]
        self.horizon = max(self.deadlines)
        sys.setrecursionlimit(max(sys.getrecursionlimit(), self.horizon * 2 + 200))
        self.announce = (observation.get('notice') or {}).get('announce_tick', 0)
        self.adj = [[] for _ in self.nodes]
        self.edges = {}
        # A position is either a parked node or a directed lane with time left.
        self.positions = [(v, -1, 0, -1) for v in range(n)]
        self.position_index = {(v, -1, 0): v for v in range(n)}
        durations = {tuple(sorted((a, b))): duration
                     for a, b, duration in observation['lanes']}
        for edge, ((a, b), duration) in enumerate(durations.items()):
            a, b = self.index[a], self.index[b]
            self.edges[frozenset((a, b))] = edge
            for origin, target in ((a, b), (b, a)):
                for left in range(1, duration):
                    self.position_index[origin, target, left] = len(self.positions)
                    self.positions.append((origin, target, left, edge))
                first = target if duration == 1 else self.position_index[origin, target, duration - 1]
                self.adj[origin].append((target, duration, edge, first))
        self.next_position = []
        for origin, target, left, edge in self.positions:
            self.next_position.append(origin if target == -1 else
                                      target if left == 1 else
                                      self.position_index[origin, target, left - 1])
        self.closed = [[0] * (self.horizon + 1) for _ in range(3)]
        self.paused = [[0] * (self.horizon + 1) for _ in range(3)]
        notice = observation.get('notice')
        if notice:
            for mode, order in enumerate(notice['orders']):
                for event in order:
                    for tick in range(max(0, event['start']), min(self.horizon + 1, event['end'])):
                        if 'lane' in event:
                            edge = self.edges[frozenset(self.index[v] for v in event['lane'])]
                            self.closed[mode][tick] |= 1 << edge
                        else:
                            self.paused[mode][tick] |= 1 << self.index[event['bay']]
        # Include the observed state even if there is no maintenance notice.
        tick = observation['tick']
        for mode in range(3):
            for a, b in observation.get('closed', []):
                self.closed[mode][tick] |= 1 << self.edges[frozenset((self.index[a], self.index[b]))]
            for v in observation.get('paused', []):
                self.paused[mode][tick] |= 1 << self.index[v]
        self.bounds = [self.make_bounds(mode) for mode in range(2)]
        # Before revelation, each cart must be individually viable in both worlds.
        self.bounds.append([
            [[max(a, b) for a, b in zip(row0, row1)]
             for row0, row1 in zip(cart0, cart1)]
            for cart0, cart1 in zip(self.bounds[0], self.bounds[1])])
        self.failed = [set(), set(), set()]
        self.policy = [{}, {}, {}]
        self.visits = 0

    def make_bounds(self, mode):
        """Exact single-cart earliest finish times, ignoring other carts."""
        result = []
        n = len(self.nodes)
        size = len(self.positions) * 3
        for cart in range(self.count):
            deadline = self.deadlines[cart]
            rows = [[INF] * size for _ in range(self.horizon + 1)]
            for tick in range(self.horizon, -1, -1):
                row = rows[tick]
                for p in range(len(self.positions)):
                    row[p * 3 + 2] = tick
                if tick > deadline:
                    continue
                for stage in (1, 0):
                    for node in range(n):
                        code = node * 3 + stage
                        goal = self.delivery[cart] if stage else self.pickup[cart]
                        if node == goal and not (self.paused[mode][tick] >> node & 1):
                            row[code] = tick if stage else row[node * 3 + 1]
                            continue
                        best = rows[tick + 1][code] if tick < deadline else INF
                        for target, duration, edge, _ in self.adj[node]:
                            arrival = tick + duration
                            if arrival <= deadline and not (self.closed[mode][tick] >> edge & 1):
                                best = min(best, rows[arrival][target * 3 + stage])
                        row[code] = best
                for p in range(n, len(self.positions)):
                    _, target, left, _ = self.positions[p]
                    arrival = tick + left
                    if arrival <= deadline:
                        row[p * 3] = rows[arrival][target * 3]
                        row[p * 3 + 1] = rows[arrival][target * 3 + 1]
            result.append(rows)
        return result

    def read_state(self, observation):
        state = []
        for c in observation['carts']:
            at = self.index[c['at']]
            target = -1 if c['to'] is None else self.index[c['to']]
            state.append(self.position_index[at, target, c['remaining']] * 3 + c['stage'])
        return tuple(state)

    def service(self, state, tick, mode):
        paused = self.paused[mode][tick]
        result = list(state)
        for i, code in enumerate(state):
            p, stage = divmod(code, 3)
            at, target, _, _ = self.positions[p]
            if stage != 2 and target == -1 and not (paused >> at & 1):
                if at == (self.pickup[i] if stage == 0 else self.delivery[i]):
                    result[i] += 1
        return tuple(result)

    def successors(self, tick, state, mode):
        occupied = reserved = busy = 0
        for code in state:
            at, target, _, edge = self.positions[code // 3]
            if target == -1:
                occupied |= 1 << at
            else:
                reserved |= 1 << target
                busy |= 1 << edge
        unavailable = occupied | reserved
        next_tick = tick + 1
        paused = self.paused[mode][next_tick]
        choices = []
        # Scores only order complete search; they never discard feasible moves.
        for i, code in enumerate(state):
            p, stage = divmod(code, 3)
            at, target, _, _ = self.positions[p]
            options = [(-1, self.next_position[p], 0, 0)]
            if target == -1:
                for dest, _, edge, first in self.adj[at]:
                    if not (unavailable >> dest & 1 or (busy | self.closed[mode][tick]) >> edge & 1):
                        options.append((dest, first, 1 << dest, 1 << edge))
            filtered = []
            for action, next_p, dest_bit, edge_bit in options:
                new_stage = stage
                node, dest, _, _ = self.positions[next_p]
                # At the announcement service will be applied independently in each world.
                if not (mode == 2 and next_tick >= self.announce):
                    if stage != 2 and dest == -1 and not (paused >> node & 1):
                        if node == (self.pickup[i] if stage == 0 else self.delivery[i]):
                            new_stage += 1
                next_code = next_p * 3 + new_stage
                finish = self.bounds[mode][i][next_tick][next_code]
                if finish >= INF:
                    continue
                slack = max(1, self.deadlines[i] - tick)
                score = (0 if stage == 2 else (finish - next_tick) / slack)
                score -= 0.025 * (new_stage - stage)
                if action != -1:
                    score += 0.003 if stage == 2 else -0.0001
                filtered.append((score, action, next_code, dest_bit, edge_bit))
            if not filtered:
                return []
            choices.append(filtered)
        combined = []
        actions = [-1] * self.count
        next_state = [0] * self.count

        def combine(i, destinations, lanes, score):
            if i == self.count:
                combined.append((score, tuple(next_state), tuple(actions)))
                return
            for cost, action, code, dest_bit, edge_bit in choices[i]:
                if destinations & dest_bit or lanes & edge_bit:
                    continue
                actions[i] = action
                next_state[i] = code
                combine(i + 1, destinations | dest_bit, lanes | edge_bit, score + cost)

        combine(0, 0, 0, 0.0)
        combined.sort(key=lambda entry: entry[0])
        return combined

    def solve(self, tick, state, mode):
        self.visits += 1
        if self.visits % 256 == 0 and time.monotonic() >= self.stop:
            raise SearchTimeout
        if all(code % 3 == 2 for code in state):
            return True
        key = (tick, state)
        if key in self.policy[mode]:
            return True
        if key in self.failed[mode]:
            return False
        if any(self.bounds[mode][i][tick][code] >= INF for i, code in enumerate(state)):
            return False
        if mode == 2 and tick >= self.announce:
            # Nature chooses here. Both continuations must succeed.
            for selected in (0, 1):
                branch = self.service(state, tick, selected)
                if not self.solve(tick, branch, selected):
                    self.failed[mode].add(key)
                    return False
            return True
        if tick >= self.horizon:
            return False
        for _, following, actions in self.successors(tick, state, mode):
            if self.solve(tick + 1, following, mode):
                self.policy[mode][key] = actions
                return True
        self.failed[mode].add(key)
        # Bound memo storage while retaining correctness (eviction only repeats work).
        if len(self.failed[mode]) > 250000:
            self.failed[mode].clear()
        return False

    def moves(self, actions):
        return {self.jobs[i]['id']: self.nodes[target]
                for i, target in enumerate(actions) if target != -1}


def main():
    dispatch = Dispatch()
    planner = None
    started = time.monotonic()
    while True:
        observation = dispatch.observe()
        if 'result' in observation:
            return
        tick = observation['tick']
        mode = observation.get('selected')
        if mode is None:
            mode = 2 if observation.get('notice') else 0
        if planner is None:
            planner = Planner(observation, started + 25.0)
        state = planner.read_state(observation)
        key = (tick, state)
        try:
            if key not in planner.policy[mode] and time.monotonic() < planner.stop:
                planner.solve(tick, state, mode)
        except SearchTimeout:
            pass
        actions = planner.policy[mode].get(key)
        if actions is None:
            # A bounded fallback still uses legal batches and calendar-aware bounds.
            successors = planner.successors(tick, state, mode)
            actions = successors[0][2] if successors else (-1,) * planner.count
        dispatch.step(planner.moves(actions))


if __name__ == '__main__':
    main()
