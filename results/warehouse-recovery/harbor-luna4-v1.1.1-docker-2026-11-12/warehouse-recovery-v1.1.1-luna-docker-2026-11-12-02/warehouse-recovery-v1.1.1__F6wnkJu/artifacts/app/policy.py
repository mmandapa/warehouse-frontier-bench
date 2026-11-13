"""Return the warehouse cart to its surveyed dock."""

import heapq
import math

from warehouse_sim.client import CartClient


STEP = 0.25
TAU = 2.0 * math.pi
TRACK = 0.56


def wrap(angle):
    return (angle + math.pi) % TAU - math.pi


def clamp(value, low, high):
    return max(low, min(high, value))


def pose_from_tags(layout, readings):
    known = {tag.name: tag for tag in layout.tags}
    estimates = []
    for reading in readings:
        tag = known.get(reading.name)
        if tag is None:
            continue
        heading = wrap(tag.heading - reading.relative_heading_rad)
        bearing = heading + reading.bearing_rad
        x = tag.x - reading.range_m * math.cos(bearing)
        y = tag.y - reading.range_m * math.sin(bearing)
        estimates.append((x, y, heading))
    if not estimates:
        return None
    x = sum(p[0] for p in estimates) / len(estimates)
    y = sum(p[1] for p in estimates) / len(estimates)
    sx = sum(math.cos(p[2]) for p in estimates)
    sy = sum(math.sin(p[2]) for p in estimates)
    return x, y, math.atan2(sy, sx)


def predicted_lidar(layout, pose):
    values = []
    for ray in range(16):
        angle = pose.heading + ray * TAU / 16.0
        dx, dy = math.cos(angle) * 0.08, math.sin(angle) * 0.08
        distance = 4.8
        for index in range(1, 61):
            if not layout.free(pose.x + dx * index, pose.y + dy * index):
                distance = index * 0.08
                break
        values.append(distance)
    return values


class Localizer:
    def __init__(self, layout):
        self.layout = layout
        self.x = self.y = self.heading = 0.0
        self.scale = 0.82
        self.odo = self.gyro = 0.0
        self.last_tag = None
        self.initialized = False

    def initialize(self, reading):
        tagged = pose_from_tags(self.layout, reading.tags)
        if tagged is not None:
            self.x, self.y, self.heading = tagged
        else:
            best = None
            for candidate in self.layout.starts:
                expected = predicted_lidar(self.layout, candidate)
                # A temporary obstruction can shorten a few rays, so use a
                # bounded loss when comparing the surveyed start poses.
                score = sum(min(abs(a - b), 1.25)
                            for a, b in zip(reading.lidar_m, expected))
                if best is None or score < best[0]:
                    best = (score, candidate)
            candidate = best[1]
            self.x, self.y, self.heading = candidate.x, candidate.y, candidate.heading
        self.odo = reading.odometry_m
        self.gyro = reading.gyro_heading_rad
        self.initialized = True
        if tagged is not None:
            self.last_tag = (tagged[0], tagged[1], reading.odometry_m,
                             reading.gyro_heading_rad)

    def update(self, reading):
        tagged = pose_from_tags(self.layout, reading.tags)
        dodo = reading.odometry_m - self.odo
        dtheta = reading.gyro_heading_rad - self.gyro
        mid = self.heading + 0.5 * dtheta
        distance = dodo * self.scale
        factor = 1.0 if abs(dtheta) < 1e-8 else math.sin(0.5 * dtheta) / (0.5 * dtheta)
        self.x += distance * factor * math.cos(mid)
        self.y += distance * factor * math.sin(mid)
        self.heading = wrap(self.heading + dtheta)

        if tagged is not None:
            if self.last_tag is not None:
                tx, ty, to, tg = self.last_tag
                odometer_run = reading.odometry_m - to
                ground_turn = reading.gyro_heading_rad - tg
                displacement = math.hypot(tagged[0] - tx, tagged[1] - ty)
                if abs(ground_turn) < 0.18 and abs(odometer_run) > 0.035:
                    measured = displacement / abs(odometer_run)
                    if 0.42 < measured < 1.08:
                        self.scale = 0.75 * self.scale + 0.25 * measured
            self.x, self.y, self.heading = tagged
            self.last_tag = (tagged[0], tagged[1], reading.odometry_m,
                             reading.gyro_heading_rad)

        self.odo = reading.odometry_m
        self.gyro = reading.gyro_heading_rad


class Grid:
    def __init__(self, layout):
        self.layout = layout
        min_x = min(rect.left for rect in layout.aisles)
        max_x = max(rect.right for rect in layout.aisles)
        min_y = min(rect.bottom for rect in layout.aisles)
        max_y = max(rect.top for rect in layout.aisles)
        self.x0 = math.floor(min_x / STEP) * STEP - 0.5
        self.y0 = math.floor(min_y / STEP) * STEP - 0.5
        self.nx = int(math.ceil((max_x - self.x0 + 0.5) / STEP)) + 1
        self.ny = int(math.ceil((max_y - self.y0 + 0.5) / STEP)) + 1
        self.free = [bytearray(self.nx) for _ in range(self.ny)]
        # A small margin around the circular cart footprint makes routes
        # robust to localization and lidar quantization error.
        offsets = [(0.34 * math.cos(i * TAU / 16.0),
                    0.34 * math.sin(i * TAU / 16.0)) for i in range(16)]
        for iy in range(self.ny):
            y = self.y0 + iy * STEP
            row = self.free[iy]
            for ix in range(self.nx):
                x = self.x0 + ix * STEP
                if layout.free(x, y) and all(layout.free(x + dx, y + dy)
                                             for dx, dy in offsets):
                    row[ix] = 1
        self.blocked = set()
        self.dock = layout.dock

    def xy(self, node):
        iy, ix = divmod(node, self.nx)
        return self.x0 + ix * STEP, self.y0 + iy * STEP

    def index(self, x, y):
        ix = int(round((x - self.x0) / STEP))
        iy = int(round((y - self.y0) / STEP))
        if ix < 0 or ix >= self.nx or iy < 0 or iy >= self.ny:
            return None
        return iy * self.nx + ix

    def node_free(self, node):
        if node is None:
            return False
        iy, ix = divmod(node, self.nx)
        return 0 <= iy < self.ny and 0 <= ix < self.nx and bool(self.free[iy][ix])

    def closest_node(self, x, y, avoid_dynamic=False):
        center = self.index(x, y)
        if center is not None and self.node_free(center) and (
                not avoid_dynamic or center not in self.blocked):
            return center
        ix0 = int(round((x - self.x0) / STEP))
        iy0 = int(round((y - self.y0) / STEP))
        best = None
        for radius in range(1, 25):
            for iy in range(max(0, iy0 - radius), min(self.ny, iy0 + radius + 1)):
                for ix in range(max(0, ix0 - radius), min(self.nx, ix0 + radius + 1)):
                    if max(abs(ix - ix0), abs(iy - iy0)) != radius:
                        continue
                    node = iy * self.nx + ix
                    if self.node_free(node) and (not avoid_dynamic or node not in self.blocked):
                        nx, ny = self.xy(node)
                        d2 = (nx - x) ** 2 + (ny - y) ** 2
                        if best is None or d2 < best[0]:
                            best = (d2, node)
            if best is not None:
                return best[1]
        return None

    def update_lidar(self, pose, ranges):
        inflation = 0.56
        cells = int(math.ceil(inflation / STEP))
        for ray, distance in enumerate(ranges):
            if distance >= 4.76:
                continue
            angle = pose[2] + ray * TAU / 16.0
            hx = pose[0] + distance * math.cos(angle)
            hy = pose[1] + distance * math.sin(angle)
            # Mapped walls and shelves lie outside the surveyed free space.
            # Endpoints inside it are evidence of an uncharted obstruction.
            if not self.layout.free(hx, hy):
                continue
            ix0 = int(round((hx - self.x0) / STEP))
            iy0 = int(round((hy - self.y0) / STEP))
            for iy in range(max(0, iy0 - cells), min(self.ny, iy0 + cells + 1)):
                cy = self.y0 + iy * STEP
                for ix in range(max(0, ix0 - cells), min(self.nx, ix0 + cells + 1)):
                    cx = self.x0 + ix * STEP
                    if (cx - hx) ** 2 + (cy - hy) ** 2 <= inflation * inflation:
                        if self.free[iy][ix]:
                            self.blocked.add(iy * self.nx + ix)

    def segment_clear(self, a, b, *, dynamic=True, skip_start=0.0):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        count = max(1, int(math.ceil(length / (STEP * 0.4))))
        for i in range(count + 1):
            along = length * i / count
            if along < skip_start:
                continue
            x, y = a[0] + dx * i / count, a[1] + dy * i / count
            node = self.index(x, y)
            if not self.node_free(node):
                return False
            if dynamic and node in self.blocked:
                return False
        return True

    def plan(self, start_pose):
        start = self.closest_node(start_pose[0], start_pose[1])
        goal = self.closest_node(self.dock.x, self.dock.y)
        if start is None or goal is None:
            return None

        # The current cell may be marked by the conservative lidar inflation.
        # It is still a valid A* source; all subsequent cells must be clear.
        costs = {start: 0.0}
        came_from = {}
        gx, gy = self.xy(goal)
        sx, sy = self.xy(start)

        def heuristic(node):
            x, y = self.xy(node)
            return math.hypot(gx - x, gy - y)

        queue = [(heuristic(start), 0.0, start)]
        found = False
        while queue:
            _, cost, node = heapq.heappop(queue)
            if cost != costs.get(node):
                continue
            if node == goal:
                found = True
                break
            iy, ix = divmod(node, self.nx)
            for oy in (-1, 0, 1):
                ny = iy + oy
                if ny < 0 or ny >= self.ny:
                    continue
                for ox in (-1, 0, 1):
                    if ox == 0 and oy == 0:
                        continue
                    nx = ix + ox
                    if nx < 0 or nx >= self.nx or not self.free[ny][nx]:
                        continue
                    nxt = ny * self.nx + nx
                    if nxt != start and nxt in self.blocked:
                        continue
                    if ox and oy:
                        if not (self.free[iy][nx] and self.free[ny][ix]):
                            continue
                        side1, side2 = iy * self.nx + nx, ny * self.nx + ix
                        if side1 in self.blocked or side2 in self.blocked:
                            continue
                    step_cost = STEP * (1.41421356237 if ox and oy else 1.0)
                    new_cost = cost + step_cost
                    if new_cost < costs.get(nxt, float("inf")):
                        costs[nxt] = new_cost
                        came_from[nxt] = node
                        heapq.heappush(queue, (new_cost + heuristic(nxt), new_cost, nxt))
        if not found:
            return None

        nodes = [goal]
        while nodes[-1] != start:
            nodes.append(came_from[nodes[-1]])
        nodes.reverse()
        raw = [self.xy(node) for node in nodes]
        if math.hypot(raw[0][0] - start_pose[0], raw[0][1] - start_pose[1]) > 0.03:
            raw.insert(0, (start_pose[0], start_pose[1]))
        else:
            raw[0] = (start_pose[0], start_pose[1])
        if math.hypot(raw[-1][0] - self.dock.x, raw[-1][1] - self.dock.y) > 0.01:
            raw.append((self.dock.x, self.dock.y))
        else:
            raw[-1] = (self.dock.x, self.dock.y)

        # Pull visible waypoints across straight aisle sections while keeping
        # every sampled point inside the clearance map and outside obstacles.
        result = [raw[0]]
        i = 0
        while i < len(raw) - 1:
            chosen = i + 1
            for j in range(len(raw) - 1, i, -1):
                if self.segment_clear(raw[i], raw[j], dynamic=True,
                                      skip_start=0.12 if i == 0 else 0.0):
                    chosen = j
                    break
            result.append(raw[chosen])
            i = chosen
        return result

    def route_blocked(self, route, index, pose):
        if not route:
            return True
        previous = (pose[0], pose[1])
        for i in range(index, len(route)):
            point = route[i]
            skip = 0.12 if i == index or (index == 0 and i == 1) else 0.0
            if not self.segment_clear(previous, point, dynamic=True,
                                      skip_start=skip):
                return True
            previous = point
        return False


def turn_command(error, maximum=0.20):
    magnitude = min(maximum, max(0.025, abs(error) * 0.25))
    return (-magnitude, magnitude) if error > 0 else (magnitude, -magnitude)


def main():
    cart = CartClient()
    layout = cart.layout
    localizer = Localizer(layout)
    grid = Grid(layout)
    reading = cart.observe(expose=True)
    localizer.initialize(reading)
    pose = (localizer.x, localizer.y, localizer.heading)
    grid.update_lidar(pose, reading.lidar_m)
    route = grid.plan(pose)
    route_index = 0
    settle_ticks = 0

    for _ in range(cart.tick_limit):
        if route is None:
            route = grid.plan(pose)
            if route is None:
                # A conservative endpoint may briefly close a narrow turn;
                # rebuild the transient layer from recent sensor evidence.
                grid.blocked.clear()
                route = grid.plan(pose)
        if route is None:
            settle_ticks = 0
            cart.command(0.0, 0.0)
            reading = cart.observe(expose=True)
            localizer.update(reading)
            pose = (localizer.x, localizer.y, localizer.heading)
            grid.update_lidar(pose, reading.lidar_m)
            continue

        dock = layout.dock
        distance_to_dock = math.hypot(dock.x - pose[0], dock.y - pose[1])
        heading_error = wrap(dock.heading - pose[2])

        if distance_to_dock <= 0.19 and abs(heading_error) <= 0.10:
            cart.command(0.0, 0.0)
            settle_ticks += 1
            reading = cart.observe(expose=True)
            localizer.update(reading)
            pose = (localizer.x, localizer.y, localizer.heading)
            grid.update_lidar(pose, reading.lidar_m)
            distance_to_dock = math.hypot(dock.x - pose[0], dock.y - pose[1])
            heading_error = wrap(dock.heading - pose[2])
            if (settle_ticks >= 3 and distance_to_dock <= 0.22
                    and abs(heading_error) <= 0.12):
                cart.finish()
                return
            continue

        settle_ticks = 0
        if grid.route_blocked(route, route_index, pose):
            route = grid.plan(pose)
            route_index = 0
            if route is None:
                grid.blocked.clear()
                route = grid.plan(pose)
            if route is None:
                cart.command(0.0, 0.0)
                reading = cart.observe(expose=True)
                localizer.update(reading)
                pose = (localizer.x, localizer.y, localizer.heading)
                grid.update_lidar(pose, reading.lidar_m)
                continue

        if route:
            while route_index < len(route) - 1:
                wx, wy = route[route_index]
                if math.hypot(wx - pose[0], wy - pose[1]) > 0.24:
                    break
                route_index += 1
            if route_index < len(route):
                target = route[route_index]
            else:
                target = (dock.x, dock.y)
        else:
            target = (dock.x, dock.y)

        # The final few centimeters are handled as a stationary heading
        # alignment so the cart can meet the dock's specified orientation.
        if distance_to_dock < 0.12:
            left, right = turn_command(heading_error, maximum=0.16)
            cart.command(left, right)
        else:
            dx, dy = target[0] - pose[0], target[1] - pose[1]
            target_distance = math.hypot(dx, dy)
            if target_distance < 0.06:
                dx, dy = dock.x - pose[0], dock.y - pose[1]
                target_distance = math.hypot(dx, dy)
            desired_heading = math.atan2(dy, dx)
            error = wrap(desired_heading - pose[2])
            if abs(error) > 0.23:
                left, right = turn_command(error)
            else:
                speed = min(0.55, max(0.07, 0.72 * (target_distance - 0.10)))
                if target_distance < 0.25:
                    speed = min(speed, 0.18)
                if abs(error) > 0.10:
                    speed *= max(0.35, 1.0 - abs(error))
                angular = clamp(1.5 * error, -0.42, 0.42)
                differential = angular * TRACK * 0.5
                left = clamp(speed - differential, -1.0, 1.0)
                right = clamp(speed + differential, -1.0, 1.0)
            cart.command(left, right)

        reading = cart.observe(expose=True)
        localizer.update(reading)
        pose = (localizer.x, localizer.y, localizer.heading)
        grid.update_lidar(pose, reading.lidar_m)

    cart.finish()


if __name__ == "__main__":
    main()
