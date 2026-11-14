"""Survey-map and lidar based controller for the warehouse cart."""

import heapq
import math

from warehouse_sim.client import CartClient


TAU = 2.0 * math.pi
STEP = 0.35
RADIUS = 0.28


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def mean_angle(values):
    return math.atan2(sum(math.sin(a) for a in values), sum(math.cos(a) for a in values))


class Controller:
    def __init__(self, cart):
        self.cart = cart
        self.map = cart.layout
        self.goal = self.map.dock
        self.scale = 0.85
        self.pose = None
        self.last = None
        self.dynamic = set()
        self.nav_target = None
        self.nav_dynamic_count = 0

        self.minx = min(r.left for r in self.map.aisles)
        self.maxx = max(r.right for r in self.map.aisles)
        self.miny = min(r.bottom for r in self.map.aisles)
        self.maxy = max(r.top for r in self.map.aisles)
        self.nx = int(math.ceil((self.maxx - self.minx) / STEP)) + 1
        self.ny = int(math.ceil((self.maxy - self.miny) / STEP)) + 1
        self.valid = bytearray(self.nx * self.ny)
        self._build_grid()

    def xy(self, idx):
        i, j = idx % self.nx, idx // self.nx
        return self.minx + i * STEP, self.miny + j * STEP

    def cell(self, x, y):
        i = int(round((x - self.minx) / STEP))
        j = int(round((y - self.miny) / STEP))
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return j * self.nx + i
        return None

    def _build_grid(self):
        # Leave a small margin around the circular footprint so a grid route
        # remains clear even when it passes diagonally between aisle edges.
        samples = [(0.65 * math.cos(k * TAU / 16), 0.65 * math.sin(k * TAU / 16))
                   for k in range(16)]
        for j in range(self.ny):
            y = self.miny + j * STEP
            for i in range(self.nx):
                x = self.minx + i * STEP
                if self.map.free(x, y) and all(self.map.free(x + dx, y + dy) for dx, dy in samples):
                    self.valid[j * self.nx + i] = 1

    def _tag_pose(self, reading):
        tag = next((t for t in self.map.tags if t.name == reading.name), None)
        if tag is None:
            return None
        heading = wrap(tag.heading - reading.relative_heading_rad)
        bearing = heading + reading.bearing_rad
        x = tag.x - reading.range_m * math.cos(bearing)
        y = tag.y - reading.range_m * math.sin(bearing)
        return x, y, heading

    def _initialize(self, obs):
        estimates = [e for r in obs.tags if (e := self._tag_pose(r)) is not None]
        if estimates:
            self.pose = (sum(e[0] for e in estimates) / len(estimates),
                         sum(e[1] for e in estimates) / len(estimates),
                         mean_angle([e[2] for e in estimates]))
        else:
            # Match the initial scan against the surveyed start alternatives.
            # This also resolves the case where the cart begins facing away
            # from every marker, so the camera has no readings yet.
            def predicted(pose):
                ranges = []
                for k in range(16):
                    a = pose.heading + k * TAU / 16
                    dx, dy = 0.08 * math.cos(a), 0.08 * math.sin(a)
                    value = 4.8
                    for n in range(1, 61):
                        if not self.map.free(pose.x + dx * n, pose.y + dy * n):
                            value = n * 0.08
                            break
                    ranges.append(value)
                return ranges

            def score(pose):
                guess = predicted(pose)
                # A short unexpected lidar return can be a temporary object;
                # clipping errors makes the remaining map geometry decisive.
                return sum(min(1.2, abs(a - b)) for a, b in zip(guess, obs.lidar_m))

            best = min(self.map.starts, key=score)
            self.pose = (best.x, best.y, best.heading)
        self.last = obs

    def _update_pose(self, obs):
        if self.pose is None:
            self._initialize(obs)
            return
        old = self.last
        dx_odom = obs.odometry_m - old.odometry_m
        dtheta = obs.gyro_heading_rad - old.gyro_heading_rad
        x, y, heading = self.pose
        mid = heading + dtheta * 0.5
        travel = dx_odom * self.scale
        x += travel * math.cos(mid)
        y += travel * math.sin(mid)
        heading = wrap(heading + dtheta)

        estimates = [e for r in obs.tags if (e := self._tag_pose(r)) is not None]
        if estimates:
            tx = sum(e[0] for e in estimates) / len(estimates)
            ty = sum(e[1] for e in estimates) / len(estimates)
            th = mean_angle([e[2] for e in estimates])
            # Calibrate forward traction over straight, sufficiently long
            # marker-to-marker motion. Avoid using turning or reversed spans.
            if not hasattr(self, "cal_anchor"):
                self.cal_anchor = (tx, ty, obs.odometry_m, obs.gyro_heading_rad)
            ax, ay, ao, ag = self.cal_anchor
            od = obs.odometry_m - ao
            turn = obs.gyro_heading_rad - ag
            if abs(turn) > 0.25 or od < -0.05:
                self.cal_anchor = (tx, ty, obs.odometry_m, obs.gyro_heading_rad)
            elif od > 0.65:
                ratio = math.hypot(tx - ax, ty - ay) / od
                if 0.45 < ratio < 1.15:
                    self.scale = max(0.55, min(1.0, 0.65 * self.scale + 0.35 * ratio))
                self.cal_anchor = (tx, ty, obs.odometry_m, obs.gyro_heading_rad)
            self.pose = (tx, ty, th)
        else:
            self.pose = (x, y, heading)
        self.last = obs

    def _record_lidar(self, obs):
        x, y, heading = self.pose
        for k, distance in enumerate(obs.lidar_m):
            if distance >= 4.79:
                continue
            angle = heading + k * TAU / 16
            hx = x + distance * math.cos(angle)
            hy = y + distance * math.sin(angle)
            # Surveyed walls already constrain the route. A hit inside known
            # free floor is a temporary object and should be inflated by the
            # cart radius plus a little localization margin.
            if (not self.map.free(hx, hy) or
                    not all(self.map.free(hx + 0.10 * math.cos(q * TAU / 8),
                                          hy + 0.10 * math.sin(q * TAU / 8)) for q in range(8))):
                continue
            ir = int(math.ceil(0.58 / STEP))
            ci = self.cell(hx, hy)
            if ci is None:
                continue
            cx, cy = ci % self.nx, ci // self.nx
            for dj in range(-ir, ir + 1):
                for di in range(-ir, ir + 1):
                    i, j = cx + di, cy + dj
                    if 0 <= i < self.nx and 0 <= j < self.ny:
                        px, py = self.minx + i * STEP, self.miny + j * STEP
                        if (px - hx) ** 2 + (py - hy) ** 2 <= 0.58 ** 2 and self.valid[j * self.nx + i]:
                            self.dynamic.add(j * self.nx + i)

    def _nearest_cell(self, x, y):
        direct = self.cell(x, y)
        if direct is not None and self.valid[direct] and direct not in self.dynamic:
            return direct
        best = None
        best_d = float("inf")
        i0 = int(round((x - self.minx) / STEP))
        j0 = int(round((y - self.miny) / STEP))
        for rad in range(1, 12):
            for j in range(max(0, j0 - rad), min(self.ny, j0 + rad + 1)):
                for i in range(max(0, i0 - rad), min(self.nx, i0 + rad + 1)):
                    idx = j * self.nx + i
                    if not self.valid[idx] or idx in self.dynamic:
                        continue
                    px, py = self.xy(idx)
                    d = (px - x) ** 2 + (py - y) ** 2
                    if d < best_d:
                        best, best_d = idx, d
            if best is not None:
                return best
        return best

    def _path(self):
        sx, sy, _ = self.pose
        start = self._nearest_cell(sx, sy)
        goal = self._nearest_cell(self.goal.x, self.goal.y)
        if start is None or goal is None:
            return []
        if start == goal:
            return [start]

        def heuristic(idx):
            x, y = idx % self.nx, idx // self.nx
            gx, gy = goal % self.nx, goal // self.nx
            dx, dy = abs(x - gx), abs(y - gy)
            return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)

        frontier = [(heuristic(start), 0.0, start)]
        cost = {start: 0.0}
        parent = {}
        directions = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                      (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
                      (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)))
        while frontier:
            _, g, here = heapq.heappop(frontier)
            if here == goal:
                break
            if g != cost.get(here):
                continue
            ix, iy = here % self.nx, here // self.nx
            for dx, dy, step_cost in directions:
                xx, yy = ix + dx, iy + dy
                if not (0 <= xx < self.nx and 0 <= yy < self.ny):
                    continue
                nxt = yy * self.nx + xx
                if not self.valid[nxt] or nxt in self.dynamic:
                    continue
                if dx and dy:
                    side1, side2 = iy * self.nx + xx, yy * self.nx + ix
                    if (not self.valid[side1] or not self.valid[side2] or
                            side1 in self.dynamic or side2 in self.dynamic):
                        continue
                ng = g + step_cost
                if ng < cost.get(nxt, float("inf")):
                    cost[nxt] = ng
                    parent[nxt] = here
                    heapq.heappush(frontier, (ng + heuristic(nxt), ng, nxt))
        if goal not in cost:
            return []
        path = [goal]
        while path[-1] != start:
            path.append(parent[path[-1]])
        path.reverse()
        return path

    def _waypoint(self, path):
        if not path:
            return self.goal.x, self.goal.y
        points = [self.xy(i) for i in path]
        if len(points) == 1:
            return self.goal.x, self.goal.y
        # Collapse only truly collinear grid steps. A route can move in the
        # same general direction while turning around aisle junctions.
        first = (round((points[1][0] - points[0][0]) / STEP),
                 round((points[1][1] - points[0][1]) / STEP))
        chosen = points[1]
        for k in range(2, len(points)):
            direction = (round((points[k][0] - points[k - 1][0]) / STEP),
                         round((points[k][1] - points[k - 1][1]) / STEP))
            if direction != first:
                break
            chosen = points[k]
        if chosen == points[-1]:
            return self.goal.x, self.goal.y
        return chosen

    def _turn_action(self, error):
        mag = min(0.18, max(0.055, 0.9 * abs(error)))
        sign = 1.0 if error > 0 else -1.0
        self.cart.command(-sign * mag, sign * mag)

    def _travel_action(self, target, obs):
        x, y, heading = self.pose
        dx, dy = target[0] - x, target[1] - y
        distance = math.hypot(dx, dy)
        if distance < 1e-5:
            self.cart.command(0.0, 0.0)
            return
        desired = math.atan2(dy, dx)
        err = wrap(desired - heading)
        if abs(err) > 0.16:
            self._turn_action(err)
            return
        # The close forward beams are a last-second brake while the global
        # grid incorporates the lidar obstacle for the next route search.
        if min(obs.lidar_m[15], obs.lidar_m[0], obs.lidar_m[1]) < 0.52:
            self.cart.command(0.0, 0.0)
            return
        speed = min(0.42, max(0.11, distance * 0.55))
        if abs(err) > 0.025:
            correction = max(-0.14, min(0.14, err * 0.55))
        else:
            correction = 0.0
        self.cart.command(speed - correction, speed + correction)

    def run(self):
        obs = self.cart.observe(expose=True)
        self._initialize(obs)
        settled = False
        for _ in range(2050):
            self._record_lidar(obs)
            x, y, heading = self.pose
            distance = math.hypot(self.goal.x - x, self.goal.y - y)
            heading_error = wrap(self.goal.heading - heading)

            # Stop, evaluate the settled pose, then make small corrections.
            if settled:
                if distance <= 0.19 and abs(heading_error) <= 0.095:
                    # A small heading correction may still be draining through
                    # the two-tick actuator queue. Flush it before finishing.
                    self.cart.command(0.0, 0.0, ticks=3)
                    obs = self.cart.observe(expose=True)
                    self._update_pose(obs)
                    x, y, heading = self.pose
                    distance = math.hypot(self.goal.x - x, self.goal.y - y)
                    heading_error = wrap(self.goal.heading - heading)
                    if distance <= 0.19 and abs(heading_error) <= 0.095:
                        self.cart.finish()
                        return
                    continue
                if distance > 0.19:
                    target = (self.goal.x, self.goal.y)
                    self._travel_action(target, obs)
                    settled = False
                else:
                    if abs(heading_error) <= 0.095:
                        self.cart.command(0.0, 0.0, ticks=3)
                        obs = self.cart.observe(expose=True)
                        self._update_pose(obs)
                        continue
                    self._turn_action(heading_error)
                obs = self.cart.observe(expose=True)
                self._update_pose(obs)
                continue

            # Close to the dock: fully stop before checking the final pose.
            if distance <= 0.12:
                self.cart.command(0.0, 0.0, ticks=3)
                obs = self.cart.observe(expose=True)
                self._update_pose(obs)
                settled = True
                continue

            if (self.nav_target is None or len(self.dynamic) != self.nav_dynamic_count or
                    math.hypot(self.nav_target[0] - x, self.nav_target[1] - y) < 0.18):
                path = self._path()
                self.nav_target = self._waypoint(path)
                self.nav_dynamic_count = len(self.dynamic)
            target = self.nav_target
            self._travel_action(target, obs)
            obs = self.cart.observe(expose=True)
            self._update_pose(obs)

        self.cart.command(0.0, 0.0, ticks=3)
        self.cart.finish()


if __name__ == "__main__":
    controller = Controller(CartClient())
    controller.run()
