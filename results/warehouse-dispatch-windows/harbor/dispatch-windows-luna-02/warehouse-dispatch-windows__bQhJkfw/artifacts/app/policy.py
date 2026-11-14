"""Deadline-aware dispatch for the maintenance shift simulator."""

from heapq import heappop, heappush

from client import Dispatch


WAIT = object()


def lane(a, b):
    return tuple(sorted((a, b)))


def make_router(view):
    """Build adjacency and a time-aware earliest-arrival search."""
    adjacency = {}
    durations = {}
    for a, b, duration in view['lanes']:
        edge = lane(a, b)
        durations[edge] = duration
        adjacency.setdefault(a, []).append((b, duration, edge))
        adjacency.setdefault(b, []).append((a, duration, edge))
    for cart in view['carts']:
        for node in (cart['at'], cart['pickup'], cart['delivery']):
            adjacency.setdefault(node, [])
    for edges in adjacency.values():
        edges.sort(key=lambda item: item[0])

    now = view['tick']
    active_closed = {lane(*edge) for edge in view['closed']}
    future_events = []
    notice = view.get('notice')
    selected = view.get('selected')
    if notice is not None and selected is not None:
        future_events = notice['orders'][selected]

    def is_closed(edge, tick):
        if tick == now and edge in active_closed:
            return True
        for event in future_events:
            if 'lane' in event and lane(*event['lane']) == edge:
                if event['start'] <= tick < event['end']:
                    return True
        return False

    def earliest(start, start_tick, goal, deadline):
        """Return the first action and earliest arrival time, or (None, inf)."""
        if start == goal:
            return None, start_tick
        queue = [(start_tick, start)]
        seen = {(start, start_tick): None}
        first_action = {(start, start_tick): None}

        while queue:
            tick, node = heappop(queue)
            if node == goal:
                return first_action[(node, tick)], tick
            if tick >= deadline:
                continue

            # Waiting is a legal action and lets routes pass temporary closures.
            wait_state = (node, tick + 1)
            if wait_state not in seen:
                seen[wait_state] = (node, tick)
                first_action[wait_state] = WAIT if tick == start_tick else first_action[(node, tick)]
                heappush(queue, (tick + 1, node))

            for neighbor, duration, edge in adjacency.get(node, ()):
                arrival = tick + duration
                if arrival > deadline or is_closed(edge, tick):
                    continue
                state = (neighbor, arrival)
                if state in seen:
                    continue
                seen[state] = (node, tick)
                first_action[state] = neighbor if tick == start_tick else first_action[(node, tick)]
                heappush(queue, (arrival, neighbor))

        return None, float('inf')

    return adjacency, durations, earliest, is_closed


def static_distances(adjacency):
    """All-pairs shortest travel times, used to rank urgent carts."""
    result = {}
    for source in adjacency:
        distances = {source: 0}
        queue = [(0, source)]
        while queue:
            cost, node = heappop(queue)
            if cost != distances[node]:
                continue
            for neighbor, duration, _ in adjacency[node]:
                candidate = cost + duration
                if candidate < distances.get(neighbor, float('inf')):
                    distances[neighbor] = candidate
                    heappush(queue, (candidate, neighbor))
        result[source] = distances
    return result


def shortest_path(adjacency, start, goal):
    if start == goal:
        return [start]
    distances = {start: 0}
    previous = {}
    queue = [(0, start)]
    while queue:
        cost, node = heappop(queue)
        if cost != distances[node]:
            continue
        if node == goal:
            break
        for neighbor, duration, _ in adjacency.get(node, ()):
            candidate = cost + duration
            if candidate < distances.get(neighbor, float('inf')):
                distances[neighbor] = candidate
                previous[neighbor] = node
                heappush(queue, (candidate, neighbor))
    if goal not in distances:
        return []
    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    return list(reversed(path))


def choose_moves(view):
    carts = view['carts']
    now = view['tick']
    adjacency, durations, earliest, is_closed = make_router(view)
    distances = static_distances(adjacency)

    # A delivered cart stays on the map. Prefer carts that need to pass a bay
    # another job will eventually occupy, so the bay does not become a plug.
    route_nodes = []
    for cart in carts:
        at = cart['to'] if cart['to'] is not None else cart['at']
        nodes = set()
        if cart['stage'] == 0:
            first_leg = shortest_path(adjacency, at, cart['pickup'])
            second_leg = shortest_path(adjacency, cart['pickup'], cart['delivery'])
            nodes.update(first_leg[1:])
            nodes.update(second_leg[1:])
        elif cart['stage'] == 1:
            nodes.update(shortest_path(adjacency, at, cart['delivery'])[1:])
        route_nodes.append(nodes)

    critical = [0] * len(carts)
    for i, cart in enumerate(carts):
        if cart['stage'] == 2:
            continue
        for j, other in enumerate(carts):
            if i != j and other['stage'] != 2 and other['delivery'] in route_nodes[i]:
                critical[i] += 1

    # Rank by estimated remaining work relative to each deadline.
    def urgency(index, cart):
        at = cart['to'] if cart['to'] is not None else cart['at']
        travel_left = cart['remaining'] if cart['to'] is not None else 0
        if cart['stage'] == 0:
            first = distances.get(at, {}).get(cart['pickup'], 10**6)
            second = distances.get(cart['pickup'], {}).get(cart['delivery'], 10**6)
            work = travel_left + first + second
        elif cart['stage'] == 1:
            work = travel_left + distances.get(at, {}).get(cart['delivery'], 10**6)
        else:
            work = 0
        slack = cart['deadline'] - now - work
        return slack - 5 * critical[index], slack, cart['deadline'], cart['id']

    occupied = {cart['at'] for cart in carts if cart['to'] is None}
    reserved_destinations = {cart['to'] for cart in carts if cart['to'] is not None}
    busy_lanes = {lane(cart['at'], cart['to']) for cart in carts if cart['to'] is not None}
    moves = {}

    ordered = [cart for _, cart in sorted(enumerate(carts), key=lambda item: urgency(*item))]
    for cart in ordered:
        if cart['to'] is not None or cart['stage'] == 2:
            continue

        goal = cart['pickup'] if cart['stage'] == 0 else cart['delivery']
        if cart['at'] == goal:
            # A parked cart at its current service node is waiting for an open bay.
            continue

        candidates = []
        # Consider every legal first lane, then estimate its best continuation.
        for neighbor, duration, edge in adjacency.get(cart['at'], ()):
            if is_closed(edge, now):
                continue
            if neighbor in occupied or neighbor in reserved_destinations:
                continue
            if edge in busy_lanes:
                continue
            arrival = now + duration
            _, finish = earliest(neighbor, arrival, goal, cart['deadline'])
            candidates.append((finish, neighbor, edge))

        # Waiting may be best when a lane opens soon or another cart must clear.
        _, wait_finish = earliest(cart['at'], now + 1, goal, cart['deadline'])
        candidates.append((wait_finish, WAIT, None))
        candidates.sort(key=lambda item: (item[0], item[1] is WAIT,
                                         '' if item[1] is WAIT else item[1]))

        for _, target, edge in candidates:
            if target is WAIT:
                break
            # These checks include moves already selected for this same batch.
            if target in reserved_destinations or edge in busy_lanes:
                continue
            moves[cart['id']] = target
            reserved_destinations.add(target)
            busy_lanes.add(edge)
            break

    return moves


if __name__ == '__main__':
    dispatch = Dispatch()
    while True:
        observation = dispatch.observe()
        if 'result' in observation:
            break
        dispatch.step(choose_moves(observation))
