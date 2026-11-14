"""Return the cart to its surveyed dock."""

import math

from warehouse_sim.client import CartClient


TAU = 2.0 * math.pi
TRACK = 0.56
DT = 0.2


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def mean_angle(values):
    s = sum(math.sin(v) for v in values)
    c = sum(math.cos(v) for v in values)
    return math.atan2(s, c)


class Controller:
    def __init__(self, cart):
        self.cart = cart
        self.map = cart.layout
        self.pose = None
        self.odom = 0.0
        self.odo_heading = 0.0
        self.gyro = 0.0
        self.tick = 0
        self.scale = 0.8
        self.gain_diff = 0.0
        self.anchor = None
        self.straight_heading = None
        self.node_xs, self.node_ys = self._grid()
        self.nodes = [(x, y) for x in self.node_xs for y in self.node_ys
                      if self.map.free(x, y)]
        self.edges = {}
        self.blocked = set()
        self._build_edges()

    def _grid(self):
        xs, ys = [], []
        for r in self.map.aisles:
            w, h = r.right - r.left, r.top - r.bottom
            if h > w:
                xs.append((r.left + r.right) * 0.5)
            elif w > h:
                ys.append((r.bottom + r.top) * 0.5)
        return self._unique(xs), self._unique(ys)

    @staticmethod
    def _unique(values):
        result = []
        for v in sorted(values):
            if not result or abs(v - result[-1]) > 0.15:
                result.append(v)
        return result

    def _free_line(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = max(1, int(math.ceil(math.hypot(dx, dy) / 0.2)))
        return all(self.map.free(a[0] + dx * i / n, a[1] + dy * i / n)
                   for i in range(n + 1))

    def _key(self, a, b):
        return tuple(sorted((a, b)))

    def _build_edges(self):
        for y in self.node_ys:
            row = [(x, y) for x in self.node_xs if (x, y) in self.nodes]
            for a, b in zip(row, row[1:]):
                if self._free_line(a, b):
                    self.edges.setdefault(a, []).append((b, math.dist(a, b)))
                    self.edges.setdefault(b, []).append((a, math.dist(a, b)))
        for x in self.node_xs:
            col = [(x, y) for y in self.node_ys if (x, y) in self.nodes]
            for a, b in zip(col, col[1:]):
                if self._free_line(a, b):
                    self.edges.setdefault(a, []).append((b, math.dist(a, b)))
                    self.edges.setdefault(b, []).append((a, math.dist(a, b)))

    def _tag_pose(self, reading):
        tags = {tag.name: tag for tag in self.map.tags}
        candidates = []
        for item in reading.tags:
            tag = tags.get(item.name)
            if tag is None:
                continue
            heading = wrap(tag.heading - item.relative_heading_rad)
            bearing = heading + item.bearing_rad
            x = tag.x - item.range_m * math.cos(bearing)
            y = tag.y - item.range_m * math.sin(bearing)
            candidates.append((x, y, heading))
        if not candidates:
            return None
        return (sum(p[0] for p in candidates) / len(candidates),
                sum(p[1] for p in candidates) / len(candidates),
                mean_angle([p[2] for p in candidates]))

    def observe(self, expose=True):
        reading = self.cart.observe(expose=expose)
        tag_pose = self._tag_pose(reading)
        if self.pose is None:
            if tag_pose is not None:
                self.pose = list(tag_pose)
            self.odom = reading.odometry_m
            self.odo_heading = reading.odometry_heading_rad
            self.gyro = reading.gyro_heading_rad
            self.tick = reading.tick
            return reading

        dodo = reading.odometry_m - self.odom
        dodoh = reading.odometry_heading_rad - self.odo_heading
        dtheta = reading.gyro_heading_rad - self.gyro
        elapsed = max(0, reading.tick - self.tick) * DT
        if elapsed > 0.0:
            avg = dodo / elapsed
            wheel_delta = dodoh * TRACK / elapsed
            left_wheel = avg - wheel_delta * 0.5
            right_wheel = avg + wheel_delta * 0.5
            # Equal wheel commands reveal the drive's left/right gain mismatch.
            # Feed it forward on straight runs so heading feedback does not
            # need to accumulate a large cross-track error first.
            if abs(right_wheel - left_wheel) < 0.015 and abs(avg) > 0.04:
                measured_diff = dtheta * TRACK / (elapsed * avg)
                if -0.75 < measured_diff < 0.75:
                    self.gain_diff = 0.65 * self.gain_diff + 0.35 * measured_diff
        mid = self.pose[2] + dtheta * 0.5
        ds = dodo * self.scale
        self.pose[0] += ds * math.cos(mid)
        self.pose[1] += ds * math.sin(mid)
        self.pose[2] = wrap(self.pose[2] + dtheta)
        self.odom = reading.odometry_m
        self.odo_heading = reading.odometry_heading_rad
        self.gyro = reading.gyro_heading_rad
        self.tick = reading.tick

        if tag_pose is not None:
            if self.anchor is not None and self.straight_heading is not None:
                ax, ay, ah, ao = self.anchor
                od = reading.odometry_m - ao
                if abs(od) > 0.75 and abs(wrap(tag_pose[2] - ah)) < 0.18:
                    traveled = ((tag_pose[0] - ax) * math.cos(ah) +
                                (tag_pose[1] - ay) * math.sin(ah))
                    ratio = traveled / od
                    if 0.45 < ratio < 1.05:
                        self.scale = max(0.53, min(0.98, 0.55 * self.scale + 0.45 * ratio))
                    self.anchor = (tag_pose[0], tag_pose[1], tag_pose[2], reading.odometry_m)
            self.pose = list(tag_pose)
        return reading

    def drain(self):
        self.cart.command(0.0, 0.0, 3)
        return self.observe()

    def scan_for_pose(self):
        reading = self.observe()
        if self.pose is not None:
            return
        # A slow full turn brings any nearby surveyed marker into the camera.
        for _ in range(100):
            self.cart.command(-0.12, 0.12, 1)
            reading = self.observe()
            if self.pose is not None:
                self.drain()
                return
        self.drain()
        if self.pose is not None:
            return
        # The supplied possible starts are all aisle intersections. Use the
        # best lidar match if a marker happened to be occluded during the scan.
        self._localize_from_map(reading)

    def _localize_from_map(self, reading):
        best = None
        headings = [i * math.pi / 8 for i in range(16)]
        candidates = list(self.map.starts) + [
            type(self.map.starts[0])(x, y, 0.0) for x, y in self.nodes
        ]
        for p in candidates:
            for heading in headings:
                err = 0.0
                for i, measured in enumerate(reading.lidar_m):
                    a = heading + i * TAU / 16
                    d = min(4.8, self._ray_map(p.x, p.y, a))
                    err += abs(d - measured)
                if best is None or err < best[0]:
                    best = (err, p.x, p.y, heading)
        if best is not None:
            self.pose = [best[1], best[2], best[3]]

    def _ray_map(self, x, y, angle):
        for step in range(1, 61):
            d = step * 0.08
            if not self.map.free(x + d * math.cos(angle), y + d * math.sin(angle)):
                return d
        return 4.8

    def turn_to(self, target):
        target = wrap(target)
        for _ in range(160):
            err = wrap(target - self.pose[2])
            ae = abs(err)
            if ae < 0.045:
                self.drain()
                if abs(wrap(target - self.pose[2])) < 0.10:
                    return True
                continue
            speed = 0.24 if ae > 0.55 else (0.11 if ae > 0.20 else 0.045)
            sign = 1.0 if err > 0 else -1.0
            self.cart.command(-sign * speed, sign * speed, 1)
            self.observe()
        self.drain()
        return abs(wrap(target - self.pose[2])) < 0.15

    def _obstacle_ahead(self, reading, remaining):
        # Side beams allow for a cart-width obstacle that the center beam
        # could narrowly miss. Normal aisle walls are farther than this.
        near = min(reading.lidar_m[15], reading.lidar_m[0], reading.lidar_m[1])
        return remaining > 1.0 and near < 0.78

    def move_to(self, target, watch=True):
        dx, dy = target[0] - self.pose[0], target[1] - self.pose[1]
        length = math.hypot(dx, dy)
        if length < 0.10:
            self.drain()
            return True
        heading = math.atan2(dy, dx)
        self.turn_to(heading)
        self.straight_heading = heading
        self.anchor = (self.pose[0], self.pose[1], self.pose[2], self.odom)
        stalled = 0
        previous = math.inf
        for _ in range(550):
            reading = self.observe()
            dx, dy = target[0] - self.pose[0], target[1] - self.pose[1]
            remaining = dx * math.cos(heading) + dy * math.sin(heading)
            lateral = -dx * math.sin(heading) + dy * math.cos(heading)
            if remaining <= 0.065:
                self.straight_heading = None
                self.drain()
                return True
            if watch and self._obstacle_ahead(reading, remaining):
                self.straight_heading = None
                self.drain()
                return False
            if remaining > previous - 0.002:
                stalled += 1
            else:
                stalled = 0
            previous = remaining
            if stalled > 45:
                self.straight_heading = None
                self.drain()
                return False
            speed = 0.42 if remaining > 1.2 else (0.27 if remaining > 0.42 else 0.12)
            path_correction = max(-0.30, min(0.30,
                                     math.atan2(lateral, max(0.8, remaining))))
            desired_heading = wrap(heading + path_correction)
            error = wrap(desired_heading - self.pose[2])
            feedforward = -self.gain_diff * speed / max(0.9, 2.0 * self.scale)
            correction = max(-0.25, min(0.25, feedforward + 0.8 * error))
            left = max(-0.7, min(0.7, speed - correction))
            right = max(-0.7, min(0.7, speed + correction))
            self.cart.command(left, right, 1)
        self.straight_heading = None
        self.drain()
        return False

    def dijkstra(self, source, destination):
        dist = {source: 0.0}
        prev = {}
        todo = set(self.nodes)
        while todo:
            u = min(todo, key=lambda n: dist.get(n, math.inf))
            if dist.get(u, math.inf) == math.inf:
                break
            todo.remove(u)
            if u == destination:
                break
            for v, length in self.edges.get(u, ()):
                if v not in todo or self._key(u, v) in self.blocked:
                    continue
                nd = dist[u] + length
                if nd < dist.get(v, math.inf):
                    dist[v], prev[v] = nd, u
        if destination not in dist:
            return None, math.inf
        path = [destination]
        while path[-1] != source:
            path.append(prev[path[-1]])
        path.reverse()
        return path, dist[destination]

    def choose_source(self, destination):
        choices = []
        x, y = self.pose[:2]
        nearest = min(self.nodes, key=lambda n: math.dist((x, y), n))
        if math.dist((x, y), nearest) < 0.35:
            path, _ = self.dijkstra(nearest, destination)
            return nearest, path
        for node in self.nodes:
            if abs(y - node[1]) < 0.82 and self._free_line((x, y), node):
                choices.append((node, math.hypot(x - node[0], y - node[1])))
            if abs(x - node[0]) < 0.82 and self._free_line((x, y), node):
                choices.append((node, math.hypot(x - node[0], y - node[1])))
        if not choices:
            node = min(self.nodes, key=lambda n: math.dist((x, y), n))
            choices.append((node, math.dist((x, y), node)))
        best = None
        for node, connector in choices:
            path, cost = self.dijkstra(node, destination)
            score = connector + cost + 0.01 * connector
            if path is not None and (best is None or score < best[0]):
                best = (score, node, path)
        return best[1], best[2]

    def run(self):
        self.scan_for_pose()
        if self.pose is None:
            self.cart.finish()
            return

        dock = (self.map.dock.x, self.map.dock.y)
        destination = min(self.nodes, key=lambda n: math.dist(n, dock))
        source, path = self.choose_source(destination)
        if math.dist(self.pose[:2], source) > 0.12:
            if not self.move_to(source):
                # A temporary obstruction in the initial aisle: settle at the
                # nearest graph point that is still directly reachable.
                source = min(self.nodes, key=lambda n: math.dist(self.pose[:2], n))
                self.move_to(source, watch=False)
                path, _ = self.dijkstra(source, destination)
        while path:
            for index in range(1, len(path)):
                a, b = path[index - 1], path[index]
                if self._key(a, b) in self.blocked:
                    continue
                if not self.move_to(b):
                    self.blocked.add(self._key(a, b))
                    # Back out along the aisle that was just found blocked.
                    self.move_to(a, watch=False)
                    path, _ = self.dijkstra(a, destination)
                    break
            else:
                path = []

        # The dock is at a graph endpoint; make a short final position
        # correction before setting its required heading.
        if math.dist(self.pose[:2], dock) > 0.06:
            self.move_to(dock, watch=False)
        self.turn_to(self.map.dock.heading)
        self.drain()
        self.cart.finish()


if __name__ == "__main__":
    Controller(CartClient()).run()
