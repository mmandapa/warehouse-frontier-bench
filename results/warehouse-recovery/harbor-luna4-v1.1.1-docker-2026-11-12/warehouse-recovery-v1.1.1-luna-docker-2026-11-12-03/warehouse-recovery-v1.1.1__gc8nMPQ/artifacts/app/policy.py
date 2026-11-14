"""Survey-map and sensor based controller for the warehouse cart."""

import heapq
import math

from warehouse_sim.client import CartClient


TRACK = 0.56
TAU = 2.0 * math.pi


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def node(x, y):
    return (round(float(x), 2), round(float(y), 2))


def build_graph(layout):
    """Recover centerline endpoints from the surveyed aisle rectangles."""
    graph = {}

    def add_edge(a, b):
        if a == b:
            return
        graph.setdefault(a, {})[b] = distance(a, b)
        graph.setdefault(b, {})[a] = distance(a, b)

    for r in layout.aisles:
        w, h = r.right - r.left, r.top - r.bottom
        if w > h * 1.3:
            half = h / 2.0
            y = (r.bottom + r.top) / 2.0
            add_edge(node(r.left + half, y), node(r.right - half, y))
        elif h > w * 1.3:
            half = w / 2.0
            x = (r.left + r.right) / 2.0
            add_edge(node(x, r.bottom + half), node(x, r.top - half))

    # Surveyed starts and the dock are guaranteed to lie at aisle junctions.
    # Snapping absorbs the two-decimal rectangle reconstruction rounding.
    def nearest(p):
        return min(graph, key=lambda q: distance(q, (p.x, p.y)))

    return graph, nearest


def map_ray(layout, x, y, heading):
    step = 0.08
    for k in range(1, 61):
        d = k * step
        px, py = x + d * math.cos(heading), y + d * math.sin(heading)
        free = any(r.contains(px, py) for r in layout.aisles) and not any(
            r.contains(px, py) for r in layout.shelves
        )
        if not free:
            return round(d, 2)
    return 4.8


def pose_from_tags(layout, readings):
    if not readings:
        return None
    by_name = {t.name: t for t in layout.tags}
    estimates = []
    for reading in readings:
        tag = by_name.get(reading.name)
        if tag is None:
            continue
        heading = wrap(tag.heading - reading.relative_heading_rad)
        bearing = heading + reading.bearing_rad
        x = tag.x - reading.range_m * math.cos(bearing)
        y = tag.y - reading.range_m * math.sin(bearing)
        estimates.append((x, y, heading))
    if not estimates:
        return None
    # The readings are rounded by the simulator. Medians keep one edge-of-view
    # measurement from dominating when several markers are visible.
    hs = [e[2] for e in estimates]
    h = math.atan2(sum(math.sin(v) for v in hs), sum(math.cos(v) for v in hs))
    xs, ys = sorted(e[0] for e in estimates), sorted(e[1] for e in estimates)
    mid = len(estimates) // 2
    if len(estimates) % 2:
        x, y = xs[mid], ys[mid]
    else:
        x, y = (xs[mid - 1] + xs[mid]) / 2, (ys[mid - 1] + ys[mid]) / 2
    return x, y, h


def initial_pose(layout, reading):
    tagged = pose_from_tags(layout, reading.tags)
    if tagged is not None:
        return tagged
    # The initial pose is one of the surveyed candidates. Compare the full
    # static-map lidar signature, trimming mismatches caused by hidden clutter.
    best, best_score = None, float("inf")
    for candidate in layout.starts:
        errors = []
        for i, measured in enumerate(reading.lidar_m):
            angle = candidate.heading + i * TAU / 16.0
            predicted = map_ray(layout, candidate.x, candidate.y, angle)
            errors.append(abs(measured - predicted))
        errors.sort()
        score = sum(errors[:12]) / 12.0
        if score < best_score:
            best, best_score = candidate, score
    return best.x, best.y, best.heading


class State:
    def __init__(self, layout, first_reading):
        self.layout = layout
        self.x, self.y, self.heading = initial_pose(layout, first_reading)
        self.last_odo = first_reading.odometry_m
        self.last_gyro = first_reading.gyro_heading_rad
        self.scale = 0.8
        self.raw_dx = self.raw_dy = 0.0
        self.cal_anchor = None
        fixed = pose_from_tags(layout, first_reading.tags)
        if fixed is not None:
            self.x, self.y, self.heading = fixed
            self.cal_anchor = (self.x, self.y)
        self.reading = first_reading

    def update(self, reading):
        d = reading.odometry_m - self.last_odo
        turn = reading.gyro_heading_rad - self.last_gyro
        mid = self.heading + turn / 2.0
        raw_dx, raw_dy = d * math.cos(mid), d * math.sin(mid)
        self.raw_dx += raw_dx
        self.raw_dy += raw_dy
        self.x += self.scale * raw_dx
        self.y += self.scale * raw_dy
        self.heading = wrap(self.heading + turn)

        fixed = pose_from_tags(self.layout, reading.tags)
        if fixed is not None:
            fx, fy, fh = fixed
            if self.cal_anchor is not None:
                vx, vy = self.raw_dx, self.raw_dy
                denom = vx * vx + vy * vy
                actual_x, actual_y = fx - self.cal_anchor[0], fy - self.cal_anchor[1]
                if denom > 0.8 * 0.8:
                    ratio = (actual_x * vx + actual_y * vy) / denom
                    if 0.45 <= ratio <= 1.05:
                        self.scale = 0.5 * self.scale + 0.5 * ratio
                        self.cal_anchor = (fx, fy)
                        self.raw_dx = self.raw_dy = 0.0
            else:
                self.cal_anchor = (fx, fy)
            self.x, self.y, self.heading = fx, fy, fh

        self.last_odo = reading.odometry_m
        self.last_gyro = reading.gyro_heading_rad
        self.reading = reading


class Controller:
    def __init__(self, cart, layout):
        self.cart = cart
        self.layout = layout
        first = cart.observe(expose=True)
        self.state = State(layout, first)
        self.graph, self.nearest_node = build_graph(layout)
        self.blocked = set()
        self.goal = self.nearest_node(layout.dock)

    def observe_step(self, left=0.0, right=0.0):
        self.cart.command(left, right)
        self.state.update(self.cart.observe(expose=True))

    def flush(self):
        # Two zero commands drain the maximum actuator queue; a third tick
        # ensures the last applied wheel command is also zero.
        for _ in range(3):
            self.observe_step()

    def rotate_to(self, target):
        for _ in range(180):
            err = wrap(target - self.state.heading)
            if abs(err) < 0.025:
                self.flush()
                if abs(wrap(target - self.state.heading)) < 0.055:
                    return True
                continue
            omega = clamp(1.35 * err, -0.48, 0.48)
            half_diff = omega * TRACK / 2.0
            self.observe_step(-half_diff, half_diff)
        self.flush()
        return abs(wrap(target - self.state.heading)) < 0.12

    def obstruction_ahead(self, target):
        dx, dy = target[0] - self.state.x, target[1] - self.state.y
        remaining = math.hypot(dx, dy)
        if remaining < 1.0:
            return False
        if abs(wrap(math.atan2(dy, dx) - self.state.heading)) > 0.30:
            return False
        measured = self.state.reading.lidar_m[0]
        expected = map_ray(self.layout, self.state.x, self.state.y, self.state.heading)
        return measured < 3.3 and measured + 0.9 < expected and measured + 0.65 < remaining

    def drive_to(self, target):
        """Drive to a point, returning False if a mapped lane is obstructed."""
        for _ in range(600):
            dx, dy = target[0] - self.state.x, target[1] - self.state.y
            remaining = math.hypot(dx, dy)
            if remaining < 0.105:
                self.flush()
                if distance((self.state.x, self.state.y), target) < 0.17:
                    return True
                continue

            if self.obstruction_ahead(target):
                self.flush()
                return False

            desired = math.atan2(dy, dx)
            error = wrap(desired - self.state.heading)
            if abs(error) > 0.75:
                self.flush()
                self.rotate_to(desired)
                continue

            if remaining > 1.4:
                speed = 0.55
            elif remaining > 0.65:
                speed = 0.36
            elif remaining > 0.28:
                speed = 0.21
            else:
                speed = 0.12
            if abs(error) > 0.32:
                speed = min(speed, 0.24)
            omega = clamp(1.25 * error, -0.48, 0.48)
            half_diff = omega * TRACK / 2.0
            left = clamp(speed - half_diff, -1.0, 1.0)
            right = clamp(speed + half_diff, -1.0, 1.0)
            self.observe_step(left, right)
        self.flush()
        return distance((self.state.x, self.state.y), target) < 0.22

    def shortest_path(self, start):
        queue = [(0.0, start)]
        dist = {start: 0.0}
        prev = {}
        while queue:
            cost, here = heapq.heappop(queue)
            if cost != dist.get(here):
                continue
            if here == self.goal:
                break
            for there, length in self.graph.get(here, {}).items():
                edge = frozenset((here, there))
                if edge in self.blocked:
                    continue
                new_cost = cost + length
                if new_cost < dist.get(there, float("inf")):
                    dist[there] = new_cost
                    prev[there] = here
                    heapq.heappush(queue, (new_cost, there))
        if self.goal not in dist:
            return None
        path = [self.goal]
        while path[-1] != start:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    def return_to_dock(self):
        current = self.nearest_node(type("P", (), {"x": self.state.x, "y": self.state.y})())
        # The initial candidate is a graph endpoint. If it was displaced by
        # more than a small amount, first settle at the nearest centerline node.
        if distance((self.state.x, self.state.y), current) > 0.22:
            self.drive_to(current)

        for _ in range(24):
            path = self.shortest_path(current)
            if path is None:
                return False
            reroute = False
            for nxt in path[1:]:
                source = current
                if not self.drive_to(nxt):
                    self.blocked.add(frozenset((source, nxt)))
                    # Backtrack to the known junction before searching again.
                    if not self.drive_to(source):
                        return False
                    current = source
                    reroute = True
                    break
                current = nxt
            if reroute:
                continue
            break
        else:
            return False

        dock_xy = (self.layout.dock.x, self.layout.dock.y)
        for _ in range(5):
            if distance((self.state.x, self.state.y), dock_xy) > 0.075:
                if not self.drive_to(dock_xy):
                    return False
            self.rotate_to(self.layout.dock.heading)
            self.flush()
            if (distance((self.state.x, self.state.y), dock_xy) <= 0.17 and
                    abs(wrap(self.layout.dock.heading - self.state.heading)) <= 0.08):
                return True
        return False


if __name__ == "__main__":
    cart = CartClient()
    controller = Controller(cart, cart.layout)
    controller.return_to_dock()
    cart.finish()
