"""Online dispatcher for the maintenance shift simulator."""

import heapq
import json
import sys


def edge_key(a, b):
    return tuple(sorted((a, b)))


class Calendar:
    """A possible future work-order calendar, combined with the live view."""

    def __init__(self, view, events):
        self.tick = view['tick']
        self.closed_now = {edge_key(*edge) for edge in view['closed']}
        self.paused_now = set(view['paused'])
        self.events = events

    def closed(self, a, b, tick):
        key = edge_key(a, b)
        if tick == self.tick:
            return key in self.closed_now
        for event in self.events:
            if 'lane' in event and event['start'] <= tick < event['end']:
                if edge_key(*event['lane']) == key:
                    return True
        return False

    def paused(self, node, tick):
        if tick == self.tick:
            return node in self.paused_now
        return any('bay' in event and event['bay'] == node
                   and event['start'] <= tick < event['end']
                   for event in self.events)


def possible_calendars(view):
    notice = view.get('notice')
    selected = view.get('selected')
    if not notice:
        return [Calendar(view, [])]
    if selected is not None:
        return [Calendar(view, notice['orders'][selected])]
    return [Calendar(view, order) for order in notice['orders']]


def earliest_delivery(cart, start_node, start_tick, stage, calendar,
                      adjacency, horizon):
    """Find the earliest delivery time from a forced first action's endpoint."""
    # Time-expanded search is small (the warehouse has only a few carts and
    # each shift has a short deadline) and naturally handles closures and bays.
    queue = [(start_tick, start_node, stage)]
    seen = {(start_tick, start_node, stage)}
    while queue:
        tick, node, phase = heapq.heappop(queue)
        if phase == 0 and node == cart['pickup'] and not calendar.paused(node, tick):
            phase = 1
        if phase == 1 and node == cart['delivery'] and not calendar.paused(node, tick):
            return tick
        if tick >= horizon:
            continue

        # Staying is always legal and lets a cart wait out either a lane
        # closure or a service pause.
        wait_state = (tick + 1, node, phase)
        if wait_state not in seen:
            seen.add(wait_state)
            heapq.heappush(queue, wait_state)

        for neighbor, duration in adjacency[node]:
            if calendar.closed(node, neighbor, tick):
                continue
            arrival = tick + duration
            if arrival > horizon:
                continue
            next_phase = phase
            if next_phase == 0 and neighbor == cart['pickup'] and not calendar.paused(neighbor, arrival):
                next_phase = 1
            if next_phase == 1 and neighbor == cart['delivery'] and not calendar.paused(neighbor, arrival):
                return arrival
            state = (arrival, neighbor, next_phase)
            if state not in seen:
                seen.add(state)
                heapq.heappush(queue, state)
    return float('inf')


def make_horizon(view, lanes):
    latest = max(cart['deadline'] for cart in view['carts'])
    notice = view.get('notice') or {}
    for order in notice.get('orders', []):
        for event in order:
            latest = max(latest, event['end'])
    longest = max((duration for _, _, duration in lanes), default=1)
    node_count = len({node for a, b, _ in lanes for node in (a, b)})
    return max(view['tick'], latest) + (node_count + 1) * (longest + 1) + 8


def choose_moves(view):
    tick = view['tick']
    carts = view['carts']
    lanes = view['lanes']
    adjacency = {node: [] for a, b, _ in lanes for node in (a, b)}
    durations = {}
    for a, b, duration in lanes:
        adjacency[a].append((b, duration))
        adjacency[b].append((a, duration))
        durations[edge_key(a, b)] = duration

    calendars = possible_calendars(view)
    horizon = make_horizon(view, lanes)
    occupied = {cart['at'] for cart in carts if cart['to'] is None}
    reserved_nodes = {cart['to'] for cart in carts if cart['to'] is not None}
    busy_lanes = {edge_key(cart['at'], cart['to']) for cart in carts if cart['to'] is not None}

    # Handle carts with the tightest robust slack first. A cart with a route
    # that barely meets its deadline gets first choice of shared lanes/nodes.
    waiting_eta = {}
    for cart in carts:
        if cart['stage'] == 2:
            continue
        if cart['to'] is not None:
            continue
        values = [earliest_delivery(cart, cart['at'], tick + 1, cart['stage'],
                                    calendar, adjacency, horizon)
                  for calendar in calendars]
        waiting_eta[cart['id']] = max(values)

    def urgency(cart):
        eta = waiting_eta.get(cart['id'], float('inf'))
        slack = cart['deadline'] - eta if eta != float('inf') else float('-inf')
        return (slack, cart['deadline'], cart['id'])

    order = sorted((cart for cart in carts
                    if cart['stage'] != 2 and cart['to'] is None), key=urgency)
    moves = {}
    claimed_nodes = set(reserved_nodes)
    claimed_nodes.update(occupied)
    claimed_lanes = set(busy_lanes)

    for cart in order:
        origin = cart['at']
        choices = []

        # Waiting is a real option and is essential when the work order is not
        # announced yet: a short wait may preserve both possible routes.
        wait_values = [earliest_delivery(cart, origin, tick + 1, cart['stage'],
                                         calendar, adjacency, horizon)
                       for calendar in calendars]
        choices.append((max(wait_values), 1, None, None))

        for neighbor, duration in adjacency.get(origin, []):
            lane_id = edge_key(origin, neighbor)
            if neighbor in claimed_nodes or lane_id in claimed_lanes:
                continue
            if any(calendar.closed(origin, neighbor, tick) for calendar in calendars):
                continue
            arrival = tick + duration
            values = [earliest_delivery(cart, neighbor, arrival, cart['stage'],
                                        calendar, adjacency, horizon)
                      for calendar in calendars]
            # Sort by worst-case completion time; in a tie, moving forward is
            # useful when it doesn't consume a shared first-tick resource.
            choices.append((max(values), 0, neighbor, lane_id))

        choices.sort(key=lambda choice: (choice[0], choice[1],
                                          '' if choice[2] is None else choice[2]))
        _, _, target, lane_id = choices[0]
        if target is not None:
            moves[cart['id']] = target
            claimed_nodes.add(target)
            claimed_lanes.add(lane_id)

    return moves


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        view = json.loads(line)
        if 'result' in view:
            return
        moves = choose_moves(view)
        print(json.dumps({'moves': moves}, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
