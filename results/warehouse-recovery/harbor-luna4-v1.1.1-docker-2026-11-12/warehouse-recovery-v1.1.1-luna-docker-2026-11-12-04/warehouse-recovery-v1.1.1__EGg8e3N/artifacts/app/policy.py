"""Return the cart to its surveyed dock using tags, odometry, and lidar."""

import heapq
import math
import sys

from warehouse_sim.client import CartClient


TAU = 2.0 * math.pi
CELL = 0.20


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clamp(x, low, high):
    return max(low, min(high, x))


def tag_pose(layout, readings):
    """Recover a global pose from the surveyed marker observations."""
    by_name = {tag.name: tag for tag in layout.tags}
    found = []
    for reading in readings:
        tag = by_name.get(reading.name)
        if tag is None:
            continue
        heading = wrap(tag.heading - reading.relative_heading_rad)
        bearing = heading + reading.bearing_rad
        x = tag.x - reading.range_m * math.cos(bearing)
        y = tag.y - reading.range_m * math.sin(bearing)
        found.append((x, y, heading))
    if not found:
        return None
    sx = sum(math.cos(v[2]) for v in found)
    sy = sum(math.sin(v[2]) for v in found)
    heading = math.atan2(sy, sx)
    return (sum(v[0] for v in found) / len(found),
            sum(v[1] for v in found) / len(found), heading)


def ray_range(layout, x, y, heading, relative):
    angle = heading + relative
    for step in range(1, 61):
        distance = step * 0.08
        if not layout.free(x + distance * math.cos(angle),
                           y + distance * math.sin(angle)):
            return round(distance, 2)
    return 4.8


def initial_pose(layout, reading):
    best = None
    best_score = float("inf")
    for pose in layout.starts:
        score = 0.0
        for i, measured in enumerate(reading.lidar_m):
            predicted = ray_range(layout, pose.x, pose.y, pose.heading,
                                 i * TAU / 16.0)
            # A small number of beams may see an unmapped temporary object.
            score += min(1.2, abs(predicted - measured))
        if score < best_score:
            best_score = score
            best = (pose.x, pose.y, pose.heading)
    return best or (layout.dock.x, layout.dock.y, layout.dock.heading)


class Estimator:
    def __init__(self, layout, first):
        self.layout = layout
        self.pose = initial_pose(layout, first)
        self.scale = 0.76
        self.last = first
        self.scale_anchor = None

    def update(self, reading):
        odom = reading.odometry_m - self.last.odometry_m
        turn = reading.gyro_heading_rad - self.last.gyro_heading_rad
        x, y, heading = self.pose
        mid = heading + turn * 0.5
        distance = odom * self.scale
        predicted = (x + distance * math.cos(mid),
                     y + distance * math.sin(mid),
                     wrap(heading + turn))
        measured = tag_pose(self.layout, reading.tags)
        if measured is not None:
            # Learn the local rolling scale from nearly straight tag-to-tag runs.
            if self.scale_anchor is None:
                self.scale_anchor = (measured[0], measured[1],
                                     reading.odometry_m, measured[2])
            ax, ay, ao, ah = self.scale_anchor
            od = reading.odometry_m - ao
            if abs(od) > 0.35 and abs(wrap(measured[2] - ah)) < 0.14:
                observed = math.hypot(measured[0] - ax, measured[1] - ay)
                estimate = observed / abs(od)
                if 0.48 < estimate < 1.02:
                    self.scale = clamp(0.75 * self.scale + 0.25 * estimate,
                                       0.52, 0.98)
                self.scale_anchor = (measured[0], measured[1],
                                     reading.odometry_m, measured[2])
            self.pose = measured
        else:
            self.pose = predicted
        self.last = reading
        return self.pose


class Grid:
    def __init__(self, layout):
        self.layout = layout
        self.x0 = min(r.left for r in layout.aisles) - 0.6
        self.y0 = min(r.bottom for r in layout.aisles) - 0.6
        self.nx = int(math.ceil((max(r.right for r in layout.aisles) - self.x0) / CELL)) + 1
        self.ny = int(math.ceil((max(r.top for r in layout.aisles) - self.y0) / CELL)) + 1
        self.static = bytearray(self.nx * self.ny)
        self.dynamic = bytearray(self.nx * self.ny)
        self.dynamic_bins = set()
        self._ring = tuple((0.315 * math.cos(i * TAU / 16.0),
                            0.315 * math.sin(i * TAU / 16.0)) for i in range(16))
        for iy in range(self.ny):
            y = self.y0 + iy * CELL
            for ix in range(self.nx):
                x = self.x0 + ix * CELL
                if self.clear_static(x, y):
                    self.static[iy * self.nx + ix] = 1
        self.inflation = []
        max_cells = int(math.ceil(0.50 / CELL))
        for dy in range(-max_cells, max_cells + 1):
            for dx in range(-max_cells, max_cells + 1):
                if math.hypot(dx * CELL, dy * CELL) <= 0.50:
                    self.inflation.append((dx, dy))
        self.neighbors = ((1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10),
                          (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14))

    def clear_static(self, x, y):
        if not self.layout.free(x, y):
            return False
        return all(self.layout.free(x + dx, y + dy) for dx, dy in self._ring)

    def coords(self, ix, iy):
        return self.x0 + ix * CELL, self.y0 + iy * CELL

    def index(self, x, y):
        ix = int(round((x - self.x0) / CELL))
        iy = int(round((y - self.y0) / CELL))
        if ix < 0 or iy < 0 or ix >= self.nx or iy >= self.ny:
            return None
        return ix, iy

    def add_scan(self, pose, ranges):
        x, y, heading = pose
        new = 0
        for i, distance in enumerate(ranges):
            if distance >= 4.79:
                continue
            angle = heading + i * TAU / 16.0
            ox = x + distance * math.cos(angle)
            oy = y + distance * math.sin(angle)
            if not self.layout.free(ox, oy):
                continue
            cell = self.index(ox, oy)
            if cell is None or cell in self.dynamic_bins:
                continue
            self.dynamic_bins.add(cell)
            cx, cy = cell
            for dx, dy in self.inflation:
                ix, iy = cx + dx, cy + dy
                if 0 <= ix < self.nx and 0 <= iy < self.ny:
                    pos = iy * self.nx + ix
                    if self.static[pos]:
                        self.dynamic[pos] = 1
            new += 1
        return new

    def nearest_free(self, x, y):
        cell = self.index(x, y)
        if cell is None:
            return None
        ix0, iy0 = cell
        if self.static[iy0 * self.nx + ix0] and not self.dynamic[iy0 * self.nx + ix0]:
            return cell
        for radius in range(1, 16):
            best = None
            best_d = float("inf")
            for iy in range(max(0, iy0 - radius), min(self.ny, iy0 + radius + 1)):
                for ix in range(max(0, ix0 - radius), min(self.nx, ix0 + radius + 1)):
                    if max(abs(ix - ix0), abs(iy - iy0)) != radius:
                        continue
                    pos = iy * self.nx + ix
                    if self.static[pos] and not self.dynamic[pos]:
                        px, py = self.coords(ix, iy)
                        d = (px - x) ** 2 + (py - y) ** 2
                        if d < best_d:
                            best, best_d = (ix, iy), d
            if best is not None:
                return best
        return None

    def path(self, start_xy, goal_xy):
        start = self.nearest_free(*start_xy)
        goal = self.nearest_free(*goal_xy)
        if start is None or goal is None:
            return None
        start_id = start[1] * self.nx + start[0]
        goal_id = goal[1] * self.nx + goal[0]
        if start_id == goal_id:
            return [self.coords(*start)]

        def heuristic(ix, iy):
            dx, dy = abs(ix - goal[0]), abs(iy - goal[1])
            return 10 * (dx + dy) - 6 * min(dx, dy)

        costs = {start_id: 0}
        parents = {}
        heap = [(heuristic(*start), 0, start_id)]
        found = False
        while heap:
            _, cost, current = heapq.heappop(heap)
            if cost != costs.get(current):
                continue
            if current == goal_id:
                found = True
                break
            ix, iy = current % self.nx, current // self.nx
            for dx, dy, edge in self.neighbors:
                nx, ny = ix + dx, iy + dy
                if nx < 0 or ny < 0 or nx >= self.nx or ny >= self.ny:
                    continue
                nxt = ny * self.nx + nx
                if not self.static[nxt] or self.dynamic[nxt]:
                    continue
                if dx and dy:
                    a = iy * self.nx + nx
                    b = ny * self.nx + ix
                    if not self.static[a] or self.dynamic[a] or not self.static[b] or self.dynamic[b]:
                        continue
                nc = cost + edge
                if nc < costs.get(nxt, 10 ** 12):
                    costs[nxt] = nc
                    parents[nxt] = current
                    heapq.heappush(heap, (nc + heuristic(nx, ny), nc, nxt))
        if not found:
            return None
        ids = [goal_id]
        while ids[-1] != start_id:
            ids.append(parents[ids[-1]])
        ids.reverse()
        raw = [(self.x0 + (item % self.nx) * CELL,
                self.y0 + (item // self.nx) * CELL) for item in ids]
        return self.simplify(raw)

    def segment_clear(self, a, b):
        distance = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(math.ceil(distance / (CELL * 0.45))))
        for i in range(steps + 1):
            f = i / steps
            x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            cell = self.index(x, y)
            if cell is None:
                return False
            idx = cell[1] * self.nx + cell[0]
            if not self.static[idx] or self.dynamic[idx]:
                return False
            if not self.clear_static(x, y):
                return False
        return True

    def simplify(self, points):
        if len(points) <= 2:
            return points
        result = [points[0]]
        start = 0
        while start < len(points) - 1:
            end = len(points) - 1
            while end > start + 1 and not self.segment_clear(points[start], points[end]):
                end -= 1
            result.append(points[end])
            start = end
        return result


def controller():
    cart = CartClient()
    layout = cart.layout
    reading = cart.observe(expose=True)
    estimator = Estimator(layout, reading)
    grid = Grid(layout)
    dock = layout.dock
    route = None
    waypoint = 0
    planned_at = -100
    last_pose = estimator.pose

    while reading.tick < cart.tick_limit - 5:
        pose = estimator.update(reading)
        x, y, heading = pose
        new_obstacles = grid.add_scan(pose, reading.lidar_m)
        distance_goal = math.hypot(dock.x - x, dock.y - y)

        if (route is None or reading.tick - planned_at >= 12 or new_obstacles):
            route = grid.path((x, y), (dock.x, dock.y))
            waypoint = 0
            planned_at = reading.tick
            if route is None:
                # A fresh scan can temporarily make a narrow passage look blocked.
                cart.command(0.0, 0.0)
                reading = cart.observe(expose=True)
                continue

        # The grid route ends at a cell near the dock; drive the final short
        # segment directly to the surveyed pose.
        direct_to_dock = (distance_goal < 0.72 and
                          grid.segment_clear((x, y), (dock.x, dock.y)))
        if direct_to_dock:
            target = (dock.x, dock.y)
        else:
            while waypoint < len(route) - 1 and math.hypot(route[waypoint][0] - x,
                                                             route[waypoint][1] - y) < 0.32:
                waypoint += 1
            if waypoint >= len(route):
                target = (dock.x, dock.y)
            else:
                target = route[waypoint]

        distance = math.hypot(target[0] - x, target[1] - y)
        at_position = distance_goal <= 0.095
        if at_position:
            target_heading = wrap(dock.heading - heading)
            if abs(target_heading) <= 0.045:
                # Three stationary ticks clear every possible actuation lag.
                cart.command(0.0, 0.0, ticks=3)
                reading = cart.observe(expose=True)
                checked = estimator.update(reading)
                if (math.hypot(dock.x - checked[0], dock.y - checked[1]) <= 0.22 and
                        abs(wrap(dock.heading - checked[2])) <= 0.12):
                    cart.finish()
                    return
                continue
            turn_error = target_heading
            turn_rate = clamp(1.25 * turn_error, -0.43, 0.43)
            cart.command(-0.28 * turn_rate, 0.28 * turn_rate)
        else:
            desired = math.atan2(target[1] - y, target[0] - x)
            error = wrap(desired - heading)
            if abs(error) > 0.42:
                turn_rate = clamp(1.4 * error, -0.50, 0.50)
                cart.command(-0.28 * turn_rate, 0.28 * turn_rate)
            else:
                speed = 0.50 if distance > 1.0 and abs(error) < 0.18 else 0.34
                if distance < 0.24:
                    speed = 0.14
                # Slow down close to the dock and near a route corner.
                if distance_goal < 1.0:
                    speed = min(speed, 0.25)
                omega = clamp(1.35 * error, -0.50, 0.50)
                left = clamp(speed - 0.28 * omega, -0.75, 0.75)
                right = clamp(speed + 0.28 * omega, -0.75, 0.75)
                cart.command(left, right)

        reading = cart.observe(expose=True)

    # Try to leave the cart settled if the tick budget is nearly exhausted.
    cart.command(0.0, 0.0, ticks=3)
    cart.finish()


if __name__ == "__main__":
    controller()
