"""Map based navigation for the warehouse cart."""

import heapq
import math
import sys

from warehouse_sim.client import CartClient


TAU = 2.0 * math.pi
STEP = 0.20
GRID = int(round(1.0 / STEP))


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Navigator:
    def __init__(self, cart):
        self.cart = cart
        self.map = cart.layout
        self.dock = self.map.dock
        self.scale = 0.80
        self.dynamic = set()
        self.bounds = (0, 200, 0, 150)
        self.static = set()
        self._build_static_grid()
        self.pose = None
        self.prev = None
        self.path = []
        self.waypoint = 0
        self.need_plan = True
        self.stopped = True

    def xy(self, cell):
        return cell[0] * STEP, cell[1] * STEP

    def cell(self, x, y):
        return int(round(x / STEP)), int(round(y / STEP))

    def _safe_world(self, x, y):
        # Keep a little more clearance than the cart's 28 cm radius.  Sampling
        # around the whole footprint also handles corners where aisle boxes join.
        if not self.map.free(x, y):
            return False
        radius = 0.38
        for i in range(24):
            a = TAU * i / 24
            if not self.map.free(x + radius * math.cos(a), y + radius * math.sin(a)):
                return False
        return True

    def _build_static_grid(self):
        raw = set()
        for ix in range(1, 200):
            x = ix * STEP
            for iy in range(1, 150):
                y = iy * STEP
                if self.map.free(x, y):
                    raw.add((ix, iy))
        # Inflate map walls by roughly 40 cm, so grid paths keep the full cart
        # footprint clear with room for the 20 cm grid quantization.
        offsets = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)
                   if dx * dx + dy * dy <= 5]
        for ix, iy in raw:
            if all((ix + dx, iy + dy) in raw for dx, dy in offsets):
                self.static.add((ix, iy))

    def _raycast_map(self, x, y, heading):
        dx, dy = math.cos(heading) * 0.08, math.sin(heading) * 0.08
        for i in range(1, 61):
            if not self.map.free(x + dx * i, y + dy * i):
                return round(i * 0.08, 2)
        return 4.8

    def _tag_pose(self, reading, reference_heading):
        if not reading.tags:
            return None
        known = {tag.name: tag for tag in self.map.tags}
        estimates = []
        for item in reading.tags:
            tag = known.get(item.name)
            if tag is None:
                continue
            wrapped_h = wrap(tag.heading - item.relative_heading_rad)
            heading = wrapped_h + TAU * round((reference_heading - wrapped_h) / TAU)
            direction = heading + item.bearing_rad
            x = tag.x - item.range_m * math.cos(direction)
            y = tag.y - item.range_m * math.sin(direction)
            estimates.append((x, y, heading))
        if not estimates:
            return None
        # Nearby tags are independently rounded; a robust mean avoids letting a
        # marginal, far-away tag dominate the localization.
        x = sum(p[0] for p in estimates) / len(estimates)
        y = sum(p[1] for p in estimates) / len(estimates)
        h = sum(p[2] for p in estimates) / len(estimates)
        return x, y, h

    def _initial_pose(self, reading):
        reference = 0.0
        tagged = self._tag_pose(reading, reference)
        if tagged is not None:
            return tagged
        best, best_score = None, float("inf")
        for start in self.map.starts:
            score = 0.0
            for i, measured in enumerate(reading.lidar_m):
                expected = self._raycast_map(start.x, start.y, start.heading + i * TAU / 16)
                # Short unexpected returns may be an unmapped obstruction.
                score += min(1.2, abs(expected - measured))
            if score < best_score:
                best, best_score = start, score
        return best.x, best.y, best.heading

    def _localize(self, reading):
        if self.prev is None:
            self.pose = self._initial_pose(reading)
            tagged = self._tag_pose(reading, self.pose[2])
            if tagged is not None:
                self.pose = tagged
            self.prev = reading
            return

        prev = self.prev
        dh = reading.gyro_heading_rad - prev.gyro_heading_rad
        dcommand = reading.odometry_m - prev.odometry_m
        old_h = self.pose[2]
        distance = dcommand * self.scale
        mid = old_h + dh * 0.5
        sinc = 1.0 if abs(dh) < 1e-7 else math.sin(dh * 0.5) / (dh * 0.5)
        x = self.pose[0] + distance * sinc * math.cos(mid)
        y = self.pose[1] + distance * sinc * math.sin(mid)
        h = old_h + dh
        tagged = self._tag_pose(reading, h)
        if tagged is not None:
            tx, ty, th = tagged
            if abs(dh) < 0.16 and abs(dcommand) > 0.30:
                along = ((tx - self.pose[0]) * math.cos(old_h)
                         + (ty - self.pose[1]) * math.sin(old_h))
                ratio = along / dcommand
                if 0.50 <= ratio <= 1.02:
                    self.scale = clamp(0.70 * self.scale + 0.30 * ratio, 0.50, 1.02)
            # Tag fixes are absolute and remove accumulated wheel slip.
            x, y, h = tx, ty, th
        self.pose = (x, y, h)
        self.prev = reading

    def _learn_obstacles(self, reading):
        x, y, h = self.pose
        added = False
        # The route controller faces along its next aisle segment.  Three
        # forward beams catch obstructions on that segment while avoiding
        # ambiguous returns at the edges of distant shelves.
        for i in (15, 0, 1):
            distance = reading.lidar_m[i]
            if distance >= 4.55:
                continue
            angle = h + i * TAU / 16
            expected = self._raycast_map(x, y, angle)
            if distance < expected - 0.40:
                # The lidar return is the near face of an unmapped object. Grow
                # it by the cart radius plus a grid/pose margin.
                ex = x + distance * math.cos(angle)
                ey = y + distance * math.sin(angle)
                cx, cy = self.cell(ex, ey)
                radius_cells = int(math.ceil(0.55 / STEP))
                for ix in range(cx - radius_cells, cx + radius_cells + 1):
                    for iy in range(cy - radius_cells, cy + radius_cells + 1):
                        if (ix - cx) ** 2 + (iy - cy) ** 2 <= radius_cells ** 2:
                            p = (ix, iy)
                            if p not in self.dynamic:
                                self.dynamic.add(p)
                                added = True
        if added:
            self.need_plan = True

    def _available(self, cell):
        return cell in self.static and cell not in self.dynamic

    def _nearest_available(self, x, y):
        cx, cy = self.cell(x, y)
        for radius in range(0, 8):
            candidates = []
            for ix in range(cx - radius, cx + radius + 1):
                for iy in range(cy - radius, cy + radius + 1):
                    if max(abs(ix - cx), abs(iy - cy)) != radius:
                        continue
                    if self._available((ix, iy)):
                        px, py = self.xy((ix, iy))
                        candidates.append(((px - x) ** 2 + (py - y) ** 2, (ix, iy)))
            if candidates:
                return min(candidates)[1]
        return None

    def _astar(self, start, goal):
        if not self._available(goal):
            # The surveyed dock should be clear; tolerate a grid-rounding edge.
            goal = self._nearest_available(self.dock.x, self.dock.y)
            if goal is None:
                return []
        if start == goal:
            return [start]
        g_score = {start: 0.0}
        parent = {}
        h0 = math.hypot(goal[0] - start[0], goal[1] - start[1])
        heap = [(h0, 0.0, start)]
        neighbors = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                     (1, 1, 1.4143), (1, -1, 1.4143), (-1, 1, 1.4143), (-1, -1, 1.4143))
        while heap:
            _, cost, node = heapq.heappop(heap)
            if cost != g_score.get(node):
                continue
            if node == goal:
                result = [node]
                while node in parent:
                    node = parent[node]
                    result.append(node)
                result.reverse()
                return result
            for dx, dy, weight in neighbors:
                nxt = (node[0] + dx, node[1] + dy)
                if not self._available(nxt):
                    continue
                if dx and dy and (not self._available((node[0] + dx, node[1]))
                                  or not self._available((node[0], node[1] + dy))):
                    continue
                new_cost = cost + weight
                if new_cost < g_score.get(nxt, float("inf")):
                    g_score[nxt] = new_cost
                    parent[nxt] = node
                    heuristic = math.hypot(goal[0] - nxt[0], goal[1] - nxt[1])
                    heapq.heappush(heap, (new_cost + heuristic, new_cost, nxt))
        return []

    def _segment_safe(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = max(1, int(math.ceil(math.hypot(dx, dy) / 0.10)))
        for i in range(n + 1):
            t = i / n
            cell = self.cell(a[0] + dx * t, a[1] + dy * t)
            if not self._available(cell):
                return False
        return True

    def _smooth(self, cells):
        if not cells:
            return []
        points = [self.xy(c) for c in cells]
        result = [points[0]]
        i = 0
        while i < len(points) - 1:
            j = len(points) - 1
            while j > i + 1 and not self._segment_safe(points[i], points[j]):
                j -= 1
            result.append(points[j])
            i = j
        return result

    def _plan(self):
        start = self._nearest_available(self.pose[0], self.pose[1])
        gx, gy = self.cell(self.dock.x, self.dock.y)
        goal = (gx, gy)
        if start is None:
            self.path = []
            return False
        cells = self._astar(start, goal)
        if not cells:
            self.path = []
            return False
        route = self._smooth(cells)
        # Replace the grid endpoint with the exact surveyed dock coordinate.
        if route:
            route[-1] = (self.dock.x, self.dock.y)
        self.path = route
        self.waypoint = 0
        while self.waypoint < len(self.path) - 1:
            if math.hypot(self.path[self.waypoint][0] - self.pose[0],
                          self.path[self.waypoint][1] - self.pose[1]) > 0.16:
                break
            self.waypoint += 1
        self.need_plan = False
        self.stopped = True
        return True

    def _sense(self):
        reading = self.cart.observe(expose=True)
        self._localize(reading)
        self._learn_obstacles(reading)
        self.reading = reading
        return reading

    def _move(self, left, right, ticks=1):
        self.cart.command(float(clamp(left, -1.0, 1.0)),
                          float(clamp(right, -1.0, 1.0)), ticks=ticks)
        return self._sense()

    def _turn_command(self, error):
        # Approximate inverse differential drive; gyro feedback closes the loop.
        magnitude = clamp(0.32 * abs(error), 0.10, 0.40)
        return (-math.copysign(magnitude, error), math.copysign(magnitude, error))

    def run(self):
        reading = self._sense()
        while self.prev.tick < self.cart.tick_limit:
            if self.need_plan or not self.path:
                if not self._plan():
                    # A transiently blocked nearest cell is handled by backing
                    # toward a nearby clear grid point before replanning.
                    self._move(-0.16, -0.16, 1)
                    continue

            # At the final dock, rotate only after arriving at its coordinates.
            if self.waypoint >= len(self.path):
                target = (self.dock.x, self.dock.y)
                final = True
            else:
                target = self.path[self.waypoint]
                final = self.waypoint == len(self.path) - 1

            x, y, h = self.pose
            dx, dy = target[0] - x, target[1] - y
            distance = math.hypot(dx, dy)

            if final and distance <= 0.13:
                heading_error = wrap(self.dock.heading - h)
                if abs(heading_error) <= 0.035:
                    # Three stationary ticks flush the maximum two-tick actuator lag.
                    if not self.stopped or self.prev.tick == 0:
                        reading = self._move(0.0, 0.0, 3)
                        self.stopped = True
                        continue
                    # Confirm pose after the stop; a visible tag can correct the
                    # last few centimeters before grading.
                    if math.hypot(self.dock.x - self.pose[0], self.dock.y - self.pose[1]) <= 0.19:
                        self.cart.finish()
                        return
                else:
                    if not self.stopped:
                        self._move(0.0, 0.0, 3)
                        self.stopped = True
                        continue
                    left, right = self._turn_command(heading_error)
                    self._move(left, right, 2 if abs(heading_error) > 0.5 else 1)
                    self.stopped = False
                    continue

            if distance <= 0.20:
                # Settle the drive queue before a sharp aisle turn.
                if not self.stopped:
                    self._move(0.0, 0.0, 3)
                    self.stopped = True
                    continue
                if not final:
                    self.waypoint += 1
                    continue

            desired = math.atan2(dy, dx)
            heading_error = wrap(desired - h)
            if abs(heading_error) > 0.48:
                if not self.stopped:
                    self._move(0.0, 0.0, 3)
                    self.stopped = True
                    continue
                left, right = self._turn_command(heading_error)
                self._move(left, right, 2 if abs(heading_error) > 0.5 else 1)
                self.stopped = False
                continue

            # Low speed leaves room to stop when lidar discovers an unseen
            # obstacle.  Heading feedback also corrects unequal wheel gains.
            speed = min(0.46, max(0.14, 0.75 * distance))
            if distance < 0.40:
                speed = min(speed, 0.22)
            correction = clamp(1.35 * heading_error, -0.18, 0.18)
            if self.reading.lidar_m[0] < 0.90:
                # Do not continue into a close forward return while the next
                # observation gives the planner a chance to route around it.
                self._move(0.0, 0.0, 3)
                self.stopped = True
                continue
            if distance > 1.2 and self.reading.lidar_m[0] > 1.6:
                batch = 3
            elif distance > 0.48 and self.reading.lidar_m[0] > 1.0:
                batch = 2
            else:
                batch = 1
            self._move(speed - correction, speed + correction, batch)
            self.stopped = False


def main():
    cart = CartClient()
    Navigator(cart).run()


if __name__ == "__main__":
    main()
