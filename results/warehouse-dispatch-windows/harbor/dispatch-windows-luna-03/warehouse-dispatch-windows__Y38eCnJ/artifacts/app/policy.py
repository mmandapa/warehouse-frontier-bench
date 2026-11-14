"""Deadline-aware dispatcher for the maintenance shift simulator."""

from functools import lru_cache

from client import Dispatch


def choose_moves(view):
    carts = view['carts']
    lanes = {}
    neighbors = {}
    for a, b, duration in view['lanes']:
        edge = tuple(sorted((a, b)))
        lanes[edge] = duration
        neighbors.setdefault(a, []).append(b)
        neighbors.setdefault(b, []).append(a)

    # Static travel-time lower bounds guide the search and prune states that
    # cannot reach a remaining delivery deadline, even on an unobstructed map.
    nodes = set(neighbors)
    distance = {a: {b: (0 if a == b else float('inf')) for b in nodes}
                for a in nodes}
    for (a, b), duration in lanes.items():
        distance[a][b] = min(distance[a][b], duration)
        distance[b][a] = min(distance[b][a], duration)
    for middle in nodes:
        for a in nodes:
            for b in nodes:
                distance[a][b] = min(distance[a][b],
                                     distance[a][middle] + distance[middle][b])

    ids = [cart['id'] for cart in carts]
    jobs = [(cart['pickup'], cart['delivery'], cart['deadline']) for cart in carts]
    notice = view.get('notice')
    orders = notice['orders'] if notice else [[]]
    announce = notice['announce_tick'] if notice else 0
    selected = view.get('selected')
    now = view['tick']

    # A cart state is (parked node, reserved destination, ticks remaining, stage).
    initial = tuple((c['at'], c['to'], c['remaining'], c['stage']) for c in carts)
    current_closed = {tuple(sorted(edge)) for edge in view.get('closed', [])}
    current_paused = set(view.get('paused', []))
    calendars = []
    for order in orders:
        closed_events = []
        paused_events = []
        for event in order:
            interval = (event['start'], event['end'])
            if 'lane' in event:
                closed_events.append((tuple(sorted(event['lane'])), *interval))
            else:
                paused_events.append((event['bay'], *interval))
        calendars.append((closed_events, paused_events))

    def states_at(state, tick, order_index):
        # Service occurs at each boundary before the dispatcher acts.
        if tick == now:
            paused = current_paused
        else:
            paused_events = calendars[order_index][1] if order_index is not None else ()
            paused = {node for node, start, end in paused_events if start <= tick < end}
        result = []
        for i, (at, dest, left, stage) in enumerate(state):
            if dest is None and at not in paused:
                pickup, delivery, _ = jobs[i]
                if stage == 0 and at == pickup:
                    stage = 1
                elif stage == 1 and at == delivery:
                    stage = 2
            result.append((at, dest, left, stage))
        return tuple(result)

    def closure_at(tick, order_index):
        if tick == now:
            return current_closed
        if order_index is None:
            return set()
        return {edge for edge, start, end in calendars[order_index][0]
                if start <= tick < end}

    # The search explores all simultaneous move batches, respecting the
    # simulator's start-of-tick occupancy and lane reservation rules.
    def actions(state, tick, order_index):
        occupied = {at for at, dest, _, _ in state if dest is None}
        reserved_destinations = {dest for _, dest, _, _ in state if dest is not None}
        busy_lanes = {tuple(sorted((at, dest)))
                      for at, dest, _, _ in state if dest is not None}
        closed = closure_at(tick, order_index)

        choices = []
        for i, (at, dest, _, _) in enumerate(state):
            if dest is not None:
                choices.append((None,))
                continue
            options = [target for target in neighbors.get(at, ())
                       if target not in occupied and target not in reserved_destinations
                       and tuple(sorted((at, target))) not in busy_lanes
                       and tuple(sorted((at, target))) not in closed]
            # Try progress moves before waiting; feasibility still considers
            # every legal choice, including waits and alternate routes.
            pickup, delivery, _ = jobs[i]
            goal = pickup if state[i][3] == 0 else delivery if state[i][3] == 1 else None
            if goal is not None:
                options.sort(key=lambda n: (lanes[tuple(sorted((at, n)))] + distance[n][goal], n))
            choices.append((*options, None))

        # Search tighter-deadline carts first when constructing a batch.
        order = sorted(range(len(carts)), key=lambda i: (jobs[i][2], i))
        batch = [None] * len(carts)

        def build(k, destinations, used_lanes):
            if k == len(order):
                yield tuple(batch)
                return
            i = order[k]
            at, dest, _, _ = state[i]
            for target in choices[i]:
                if target is None:
                    batch[i] = None
                    yield from build(k + 1, destinations, used_lanes)
                    continue
                edge = tuple(sorted((at, target)))
                if target in destinations or edge in used_lanes:
                    continue
                batch[i] = target
                yield from build(k + 1, destinations | {target}, used_lanes | {edge})
            batch[i] = None

        yield from build(0, set(), set())

    def advance(state, batch):
        result = []
        for i, (at, dest, left, stage) in enumerate(state):
            target = batch[i]
            if dest is not None:
                if left == 1:
                    result.append((dest, None, 0, stage))
                else:
                    result.append((at, dest, left - 1, stage))
            elif target is None:
                result.append((at, None, 0, stage))
            else:
                duration = lanes[tuple(sorted((at, target)))]
                if duration == 1:
                    result.append((target, None, 0, stage))
                else:
                    result.append((at, target, duration - 1, stage))
        return tuple(result)

    def finished_or_late(state, tick):
        if all(stage == 2 for _, _, _, stage in state):
            return True, True
        for i, (at, dest, remaining, stage) in enumerate(state):
            if stage == 2:
                continue
            if jobs[i][2] <= tick:
                return True, False
            position = dest if dest is not None else at
            travel = remaining if dest is not None else 0
            if stage == 0:
                pickup, delivery, deadline = jobs[i]
                travel += distance[position][pickup] + distance[pickup][delivery]
            else:
                travel += distance[position][jobs[i][1]]
                deadline = jobs[i][2]
            if tick + travel > deadline:
                return True, False
        return False, False

    @lru_cache(maxsize=None)
    def can_finish(state, tick, order_index):
        state = states_at(state, tick, order_index)
        terminal, success = finished_or_late(state, tick)
        if terminal:
            return success
        for batch in actions(state, tick, order_index):
            following = advance(state, batch)
            following = states_at(following, tick + 1, order_index)
            if can_finish(following, tick + 1, order_index):
                return True
        return False

    @lru_cache(maxsize=None)
    def robust_finish(state, tick):
        # At the announcement boundary, bay closures can affect service
        # before this tick's decision, so normalize separately per order.
        if tick >= announce:
            return all(can_finish(state, tick, i) for i in range(len(orders)))
        state = states_at(state, tick, None)
        terminal, success = finished_or_late(state, tick)
        if terminal:
            return success
        for batch in actions(state, tick, None):
            following = advance(state, batch)
            if robust_finish(following, tick + 1):
                return True
        return False

    def wire_batch(batch):
        return {ids[i]: target for i, target in enumerate(batch) if target is not None}

    state = states_at(initial, now, selected)
    if selected is not None:
        for batch in actions(state, now, selected):
            following = states_at(advance(state, batch), now + 1, selected)
            if can_finish(following, now + 1, selected):
                return wire_batch(batch)
        return {}

    for batch in actions(state, now, None):
        following = advance(state, batch)
        if robust_finish(following, now + 1):
            return wire_batch(batch)
    return {}


if __name__ == '__main__':
    dispatch = Dispatch()
    while True:
        observation = dispatch.observe()
        if 'result' in observation:
            break
        dispatch.step(choose_moves(observation))
