"""Deadline-aware dispatch for the maintenance practice shifts."""

from functools import lru_cache
import heapq

from client import Dispatch


def edge(a, b):
    return tuple(sorted((a, b)))


def choose(view):
    if 'result' in view:
        return {}

    tick = view['tick']
    carts = view['carts']
    lanes = view['lanes']
    notice = view.get('notice')
    announce = notice['announce_tick'] if notice else tick
    durations = {edge(a, b): d for a, b, d in lanes}
    neighbors = {}
    for a, b, _ in lanes:
        neighbors.setdefault(a, []).append(b)
        neighbors.setdefault(b, []).append(a)

    # Uninterrupted shortest travel times make a useful admissible deadline bound.
    nodes = set(neighbors)
    distances = {}
    for source in nodes:
        dist = {source: 0}
        queue = [(0, source)]
        while queue:
            cost, here = heapq.heappop(queue)
            if cost != dist[here]:
                continue
            for there in neighbors[here]:
                candidate = cost + durations[edge(here, there)]
                if candidate < dist.get(there, 10**9):
                    dist[there] = candidate
                    heapq.heappush(queue, (candidate, there))
        distances[source] = dist

    orders = notice['orders'] if notice else [[], []]

    def event_state(at_tick, order):
        """Return future closures and paused bays for one selected calendar."""
        closed = set()
        paused = set()
        if notice and order is not None and at_tick >= announce:
            for event in orders[order]:
                if event['start'] <= at_tick < event['end']:
                    if 'lane' in event:
                        closed.add(edge(*event['lane']))
                    elif 'bay' in event:
                        paused.add(event['bay'])
        return closed, paused

    def service(state, paused):
        changed = []
        for i, (at, dest, left, stage) in enumerate(state):
            if dest is None and at not in paused:
                cart = carts[i]
                if stage == 0 and at == cart['pickup']:
                    stage = 1
                elif stage == 1 and at == cart['delivery']:
                    stage = 2
            changed.append((at, dest, left, stage))
        return tuple(changed)

    state = tuple((c['at'], c['to'], c['remaining'], c['stage']) for c in carts)
    # The observation is already serviced for this tick. Its active state is
    # authoritative even if the policy was started in the middle of a shift.
    current_closed = {edge(*e) for e in view['closed']}
    current_paused = set(view['paused'])
    current_selected = view.get('selected')

    def lower_bound(i, entry):
        at, dest, left, stage = entry
        if stage == 2:
            return 0
        pos_cost = left + distances.get(dest, {}).get(carts[i]['delivery'], 10**6) if dest is not None else None
        if stage == 0:
            if dest is None:
                pos_cost = distances.get(at, {}).get(carts[i]['pickup'], 10**6)
            first = pos_cost
            return first + distances.get(carts[i]['pickup'], {}).get(carts[i]['delivery'], 10**6)
        if dest is None:
            return distances.get(at, {}).get(carts[i]['delivery'], 10**6)
        return pos_cost

    def expired(at_tick, state_now):
        for i, entry in enumerate(state_now):
            if entry[3] != 2 and at_tick + lower_bound(i, entry) > carts[i]['deadline']:
                return True
            if entry[3] != 2 and at_tick >= carts[i]['deadline']:
                return True
        return False

    def actions(at_tick, state_now, order):
        # The current observation includes all active events. Future events
        # come from the chosen notice calendar.
        if at_tick == tick:
            closed = current_closed
        else:
            closed, _ = event_state(at_tick, order)

        occupied = {at for at, dest, _, _ in state_now if dest is None}
        reserved = {dest for _, dest, _, _ in state_now if dest is not None}
        busy = {edge(at, dest) for at, dest, _, _ in state_now if dest is not None}
        choices = []
        for i, (at, dest, _, _) in enumerate(state_now):
            if dest is not None:
                choices.append((None,))
                continue
            options = [None]
            for there in neighbors.get(at, ()):
                e = edge(at, there)
                if e not in closed and there not in occupied and there not in reserved and e not in busy:
                    options.append(there)
            choices.append(tuple(options))

        batch = [None] * len(state_now)

        def generate(i, claimed_nodes, claimed_edges):
            if i == len(state_now):
                yield tuple(batch)
                return
            at, dest, _, _ = state_now[i]
            for target in choices[i]:
                if target is None:
                    batch[i] = None
                    yield from generate(i + 1, claimed_nodes, claimed_edges)
                    continue
                e = edge(at, target)
                if target in claimed_nodes or e in claimed_edges:
                    continue
                batch[i] = target
                yield from generate(i + 1, claimed_nodes | {target}, claimed_edges | {e})
            batch[i] = None

        result = list(generate(0, set(reserved), set(busy)))

        def advance(moves):
            started = []
            for i, (at, dest, left, stage) in enumerate(state_now):
                target = moves[i]
                if target is not None:
                    started.append((at, target, durations[edge(at, target)], stage))
                else:
                    started.append((at, dest, left, stage))
            after = []
            for at, dest, left, stage in started:
                if dest is None:
                    after.append((at, None, 0, stage))
                elif left == 1:
                    after.append((dest, None, 0, stage))
                else:
                    after.append((at, dest, left - 1, stage))
            return tuple(after)

        def rank(moves):
            after = advance(moves)
            next_t = at_tick + 1
            if next_t == announce and order is None:
                # Score the safer of the two immediate service outcomes.
                variants = []
                for selected in range(len(orders)):
                    _, paused = event_state(next_t, selected)
                    v = service(after, paused)
                    variants.append((sum(lower_bound(j, x) for j, x in enumerate(v)), v))
                future = min(s for s, _ in variants)
            else:
                _, paused = event_state(next_t, order)
                future = sum(lower_bound(j, x) for j, x in enumerate(service(after, paused)))
            # Moving carts with shorter remaining work first tends to expose
            # useful branches early; the full search still checks every batch.
            return (future, -sum(x is not None for x in moves))

        result.sort(key=rank)
        return result

    @lru_cache(maxsize=None)
    def feasible(at_tick, state_now, order):
        if all(entry[3] == 2 for entry in state_now):
            return True
        if expired(at_tick, state_now):
            return False

        # At the announcement boundary the current state splits into two
        # calendars. Earlier decisions must work for both.
        if order is None and at_tick >= announce:
            for selected in range(len(orders)):
                _, paused = event_state(at_tick, selected)
                branch = service(state_now, paused)
                if not feasible(at_tick, branch, selected):
                    return False
            return True

        if at_tick >= max(c['deadline'] for c in carts):
            return False
        for moves in actions(at_tick, state_now, order):
            after = []
            for i, (at, dest, left, stage) in enumerate(state_now):
                target = moves[i]
                if target is not None:
                    after.append((at, target, durations[edge(at, target)], stage))
                else:
                    after.append((at, dest, left, stage))
            advanced = []
            for at, dest, left, stage in after:
                if dest is None:
                    advanced.append((at, None, 0, stage))
                elif left == 1:
                    advanced.append((dest, None, 0, stage))
                else:
                    advanced.append((at, dest, left - 1, stage))
            advanced = tuple(advanced)
            next_tick = at_tick + 1

            if order is None and next_tick == announce:
                possible = True
                for selected in range(len(orders)):
                    _, paused = event_state(next_tick, selected)
                    branch = service(advanced, paused)
                    if not feasible(next_tick, branch, selected):
                        possible = False
                        break
                if possible:
                    return True
            else:
                _, paused = event_state(next_tick, order)
                next_state = service(advanced, paused)
                if feasible(next_tick, next_state, order):
                    return True
        return False

    if all(entry[3] == 2 for entry in state):
        return {}

    # Pick the first action from a complete schedule. With an unknown order,
    # feasibility checks both calendars at the announcement boundary.
    search_order = current_selected
    chosen = None
    for moves in actions(tick, state, search_order):
        advanced = []
        for i, (at, dest, left, stage) in enumerate(state):
            target = moves[i]
            if target is not None:
                advanced.append((at, target, durations[edge(at, target)], stage))
            else:
                advanced.append((at, dest, left, stage))
        next_state = []
        for at, dest, left, stage in advanced:
            if dest is None:
                next_state.append((at, None, 0, stage))
            elif left == 1:
                next_state.append((dest, None, 0, stage))
            else:
                next_state.append((at, dest, left - 1, stage))
        next_tick = tick + 1
        next_state = tuple(next_state)
        if search_order is None and next_tick == announce:
            ok = True
            for selected in range(len(orders)):
                _, paused = event_state(next_tick, selected)
                branch = service(next_state, paused)
                if not feasible(next_tick, branch, selected):
                    ok = False
                    break
            if ok:
                chosen = moves
                break
        else:
            _, paused = event_state(next_tick, search_order)
            branch = service(next_state, paused)
            if feasible(next_tick, branch, search_order):
                chosen = moves
                break

    if chosen is None:
        # The supplied schedules are feasible. This fallback keeps the wire
        # valid if a different shift has no complete plan from its current state.
        chosen = tuple(None for _ in carts)
    return {carts[i]['id']: target for i, target in enumerate(chosen) if target is not None}


def main():
    dispatch = Dispatch()
    while True:
        view = dispatch.observe()
        if 'result' in view:
            return
        dispatch.step(choose(view))


if __name__ == '__main__':
    main()
