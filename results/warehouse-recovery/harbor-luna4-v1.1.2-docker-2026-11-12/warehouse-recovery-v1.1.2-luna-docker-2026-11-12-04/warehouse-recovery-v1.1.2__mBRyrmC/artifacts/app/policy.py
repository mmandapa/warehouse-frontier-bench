"""Map and sensor driven controller for the warehouse cart."""

import heapq
import math

from warehouse_sim.client import CartClient


STEP = 0.20
TAU = 2.0 * math.pi


def wrap(angle):
    return (angle + math.pi) % TAU - math.pi


def tag_pose(layout, readings):
    """Recover a global pose from the surveyed positions of visible tags."""
    estimates = []
    for reading in readings:
        tag = next((item for item in layout.tags if item.name == reading.name), None)
        if tag is None:
            continue
        heading = wrap(tag.heading - reading.relative_heading_rad)
        bearing = heading + reading.bearing_rad
        estimates.append((tag.x - reading.range_m * math.cos(bearing),
                          tag.y - reading.range_m * math.sin(bearing), heading))
    if not estimates:
        return None
    base_h = estimates[0][2]
    return (sum(p[0] for p in estimates) / len(estimates),
            sum(p[1] for p in estimates) / len(estimates),
            wrap(base_h + sum(wrap(p[2] - base_h) for p in estimates) / len(estimates)))


class Grid:
    def __init__(self, layout):
        self.layout = layout
        self.step = STEP
        self.x0 = min(r.left for r in layout.aisles) - 0.5
        self.y0 = min(r.bottom for r in layout.aisles) - 0.5
        self.nx = int(math.ceil((max(r.right for r in layout.aisles) - self.x0) / STEP)) + 1
        self.ny = int(math.ceil((max(r.top for r in layout.aisles) - self.y0) / STEP)) + 1
        self.valid = bytearray(self.nx * self.ny)
        self.blocked = bytearray(self.nx * self.ny)
        # Keep extra clearance around the cart to absorb grid discretization and
        # small localization errors.
        ring = [(0.38 * math.cos(i * TAU / 24), 0.38 * math.sin(i * TAU / 24))
                for i in range(24)]
        for iy in range(self.ny):
            y = self.y0 + iy * STEP
            for ix in range(self.nx):
                x = self.x0 + ix * STEP
                if layout.free(x, y) and all(layout.free(x + dx, y + dy) for dx, dy in ring):
                    self.valid[self.key(ix, iy)] = 1

    def key(self, ix, iy):
        return iy * self.nx + ix

    def ij(self, key):
        return key % self.nx, key // self.nx

    def xy(self, key):
        ix, iy = self.ij(key)
        return self.x0 + ix * STEP, self.y0 + iy * STEP

    def nearest(self, x, y, allow_blocked=False):
        ci = int(round((x - self.x0) / STEP))
        cj = int(round((y - self.y0) / STEP))
        best = None
        bestd = 1e9
        for radius in range(0, 18):
            found = False
            for iy in range(max(0, cj - radius), min(self.ny, cj + radius + 1)):
                for ix in range(max(0, ci - radius), min(self.nx, ci + radius + 1)):
                    if max(abs(ix - ci), abs(iy - cj)) != radius:
                        continue
                    key = self.key(ix, iy)
                    if self.valid[key] and (allow_blocked or not self.blocked[key]):
                        px, py = self.xy(key)
                        d = (px - x) ** 2 + (py - y) ** 2
                        if d < bestd:
                            best, bestd = key, d
                            found = True
            if found:
                return best
        return best

    def add_lidar(self, pose, ranges):
        px, py, heading = pose
        changed = set()
        for index, distance in enumerate(ranges):
            if distance >= 4.79:
                continue
            angle = heading + index * TAU / 16
            ex = px + distance * math.cos(angle)
            ey = py + distance * math.sin(angle)
            # Endpoints outside the surveyed free space are expected aisle
            # boundaries or shelves already represented by the static map.
            if not self.layout.free(ex, ey):
                continue
            ci = int(round((ex - self.x0) / STEP))
            cj = int(round((ey - self.y0) / STEP))
            radius = 0.48
            cells = int(math.ceil(radius / STEP))
            for iy in range(max(0, cj - cells), min(self.ny, cj + cells + 1)):
                for ix in range(max(0, ci - cells), min(self.nx, ci + cells + 1)):
                    key = self.key(ix, iy)
                    if not self.valid[key] or self.blocked[key]:
                        continue
                    x, y = self.xy(key)
                    if (x - ex) ** 2 + (y - ey) ** 2 <= radius ** 2:
                        self.blocked[key] = 1
                        changed.add(key)
        return changed

    def plan(self, start, goal):
        source = self.nearest(*start)
        target = self.nearest(*goal)
        if source is None or target is None:
            return None
        if source == target:
            return [source]
        gx, gy = self.ij(target)
        sx, sy = self.ij(source)
        queue = [(math.hypot(gx - sx, gy - sy), 0.0, source)]
        costs = {source: 0.0}
        parent = {}
        directions = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                      (1, 1, 1.414214), (1, -1, 1.414214),
                      (-1, 1, 1.414214), (-1, -1, 1.414214))
        while queue:
            _, cost, node = heapq.heappop(queue)
            if cost != costs.get(node):
                continue
            if node == target:
                path = [node]
                while node in parent:
                    node = parent[node]
                    path.append(node)
                path.reverse()
                return path
            ix, iy = self.ij(node)
            for dx, dy, step_cost in directions:
                nx, ny = ix + dx, iy + dy
                if not (0 <= nx < self.nx and 0 <= ny < self.ny):
                    continue
                nxt = self.key(nx, ny)
                if not self.valid[nxt] or self.blocked[nxt]:
                    continue
                if dx and dy:
                    side1, side2 = self.key(ix + dx, iy), self.key(ix, iy + dy)
                    if (not self.valid[side1] or self.blocked[side1] or
                            not self.valid[side2] or self.blocked[side2]):
                        continue
                new_cost = cost + step_cost
                if new_cost < costs.get(nxt, 1e30):
                    costs[nxt] = new_cost
                    parent[nxt] = node
                    heuristic = math.hypot(gx - nx, gy - ny)
                    heapq.heappush(queue, (new_cost + heuristic, new_cost, nxt))
        return None

    def smooth(self, path):
        if not path:
            return []

        def visible(a, b):
            ax, ay = self.xy(a)
            bx, by = self.xy(b)
            dist = math.hypot(bx - ax, by - ay)
            samples = max(1, int(math.ceil(dist / (STEP * 0.45))))
            for j in range(samples + 1):
                f = j / samples
                ix = int(round((ax + (bx - ax) * f - self.x0) / STEP))
                iy = int(round((ay + (by - ay) * f - self.y0) / STEP))
                if not (0 <= ix < self.nx and 0 <= iy < self.ny):
                    return False
                key = self.key(ix, iy)
                if not self.valid[key] or self.blocked[key]:
                    return False
            return True

        result = [path[0]]
        index = 0
        while index < len(path) - 1:
            furthest = index + 1
            limit = min(len(path) - 1, index + 45)
            for candidate in range(index + 2, limit + 1):
                if visible(path[index], path[candidate]):
                    furthest = candidate
                else:
                    break
            result.append(path[furthest])
            index = furthest
        return result


def predicted_lidar(layout, pose):
    values = []
    for ray in range(16):
        a = pose.heading + ray * TAU / 16
        distance = 0.08
        while distance <= 4.8:
            if not layout.free(pose.x + distance * math.cos(a),
                               pose.y + distance * math.sin(a)):
                break
            distance += 0.08
        values.append(min(4.8, round(distance / 0.08) * 0.08))
    return values


def initial_pose(layout, reading):
    from_tags = tag_pose(layout, reading.tags)
    if from_tags is not None:
        nearest = min(layout.starts,
                      key=lambda p: (p.x - from_tags[0]) ** 2 + (p.y - from_tags[1]) ** 2)
        return nearest.x, nearest.y, nearest.heading
    # The initial pose is one of the surveyed starts. Static map ray lengths
    # distinguish the rows; unknown obstructions can shorten, but not lengthen,
    # the predicted rays.
    best, best_score = layout.starts[0], 1e100
    for candidate in layout.starts:
        predicted = predicted_lidar(layout, candidate)
        score = 0.0
        for actual, expected in zip(reading.lidar_m, predicted):
            delta = actual - expected
            if delta > 0.12:
                score += 30.0 * delta * delta
            elif delta < -0.12:
                score += 0.08 * delta * delta
        if score < best_score:
            best, best_score = candidate, score
    return best.x, best.y, best.heading


def drive_command(pose, target, final_heading=None):
    x, y, heading = pose
    tx, ty = target
    dx, dy = tx - x, ty - y
    distance = math.hypot(dx, dy)
    if final_heading is not None and distance <= 0.12:
        error = wrap(final_heading - heading)
        omega = max(-0.75, min(0.75, 1.8 * error))
        turn = omega * 0.28
        return -turn, turn, distance, abs(error)
    desired = math.atan2(dy, dx) if distance > 1e-6 else heading
    error = wrap(desired - heading)
    if abs(error) > 0.75:
        omega = max(-0.72, min(0.72, 1.8 * error))
        turn = omega * 0.28
        return -turn, turn, distance, abs(error)
    speed = min(0.62, 0.95 * distance)
    speed *= max(0.0, math.cos(error))
    omega = max(-0.8, min(0.8, 1.7 * error))
    left = speed - omega * 0.28
    right = speed + omega * 0.28
    peak = max(abs(left), abs(right), 0.8)
    if peak > 0.8:
        left *= 0.8 / peak
        right *= 0.8 / peak
    return left, right, distance, abs(error)


def main():
    cart = CartClient()
    layout = cart.layout
    grid = Grid(layout)
    observation = cart.observe(expose=True)
    pose = initial_pose(layout, observation)
    last_odo = observation.odometry_m
    last_gyro = observation.gyro_heading_rad
    scale = 0.84
    last_tag_odo = last_odo
    last_tag_pose = pose
    heading_since_tag = 0.0

    route = None
    route_index = 0
    waypoint_keys = []
    zero_ticks = 0

    for _ in range(cart.tick_limit - 3):
        if observation.tags:
            fixed = tag_pose(layout, observation.tags)
            if fixed is not None:
                dd_odo = observation.odometry_m - last_tag_odo
                if abs(heading_since_tag) < 0.22 and abs(dd_odo) > 0.35:
                    measured = math.hypot(fixed[0] - last_tag_pose[0],
                                          fixed[1] - last_tag_pose[1]) / abs(dd_odo)
                    if 0.45 <= measured <= 1.2:
                        scale = 0.65 * scale + 0.35 * measured
                pose = fixed
                last_tag_odo = observation.odometry_m
                last_tag_pose = fixed
                heading_since_tag = 0.0
        else:
            d_odo = observation.odometry_m - last_odo
            d_heading = observation.gyro_heading_rad - last_gyro
            mid_heading = pose[2] + d_heading * 0.5
            ds = scale * d_odo
            if abs(d_heading) < 1e-7:
                nx = pose[0] + ds * math.cos(mid_heading)
                ny = pose[1] + ds * math.sin(mid_heading)
            else:
                radius = ds / d_heading
                nx = pose[0] + radius * (math.sin(pose[2] + d_heading) - math.sin(pose[2]))
                ny = pose[1] - radius * (math.cos(pose[2] + d_heading) - math.cos(pose[2]))
            pose = (nx, ny, wrap(pose[2] + d_heading))
            heading_since_tag += abs(d_heading)
        last_odo = observation.odometry_m
        last_gyro = observation.gyro_heading_rad

        newly_blocked = grid.add_lidar(pose, observation.lidar_m)
        if route is None or not waypoint_keys:
            path = grid.plan(pose[:2], (layout.dock.x, layout.dock.y))
            if path is None:
                # Try again after the next sensor update if a transient range
                # endpoint conservatively occupied an essential grid cell.
                left = right = 0.0
            else:
                waypoint_keys = grid.smooth(path)
                route = path
                route_index = 1 if len(waypoint_keys) > 1 else 0
        elif newly_blocked:
            # Only pay for another search when new returns touch the remaining
            # route. Detections elsewhere are retained for a later search.
            remaining = set(route)
            if any(key in remaining for key in newly_blocked):
                path = grid.plan(pose[:2], (layout.dock.x, layout.dock.y))
                if path is not None:
                    route = path
                    waypoint_keys = grid.smooth(path)
                    route_index = 1 if len(waypoint_keys) > 1 else 0

        if route is None or not waypoint_keys:
            left = right = 0.0
            cart.command(left, right)
            observation = cart.observe(expose=True)
            continue

        # Skip smoothed corners already reached. The exact surveyed dock pose
        # is the final target after the nearest route-grid point.
        while route_index < len(waypoint_keys):
            wx, wy = grid.xy(waypoint_keys[route_index])
            if math.hypot(wx - pose[0], wy - pose[1]) < 0.24:
                route_index += 1
            else:
                break
        final_leg = route_index >= len(waypoint_keys)
        if final_leg:
            target = (layout.dock.x, layout.dock.y)
            final_heading = layout.dock.heading
        else:
            target = grid.xy(waypoint_keys[route_index])
            final_heading = None

        # A close return in the forward lidar arc indicates a missed or newly
        # appeared obstruction. Pause while the next observation updates the map.
        front = min(observation.lidar_m[i] for i in (15, 0, 1))
        to_target = wrap(math.atan2(target[1] - pose[1], target[0] - pose[0]) - pose[2])
        if abs(to_target) < 0.7 and front < 0.52:
            left = right = 0.0
        else:
            left, right, distance, heading_error = drive_command(pose, target, final_heading)
            if final_leg and distance <= 0.12 and heading_error <= 0.055:
                left = right = 0.0
                zero_ticks += 1
                if zero_ticks >= 3:
                    cart.command(0.0, 0.0)
                    cart.command(0.0, 0.0)
                    cart.command(0.0, 0.0)
                    cart.finish()
                    return
            else:
                zero_ticks = 0

        cart.command(left, right)
        observation = cart.observe(expose=True)

    cart.finish()


if __name__ == "__main__":
    main()
