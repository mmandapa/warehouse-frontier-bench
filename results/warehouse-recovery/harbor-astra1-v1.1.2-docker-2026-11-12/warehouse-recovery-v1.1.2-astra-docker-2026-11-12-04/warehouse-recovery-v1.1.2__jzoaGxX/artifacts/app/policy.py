"""Sensor-localized, obstacle-aware warehouse docking controller."""
import heapq
import math
from warehouse_sim.client import CartClient

TAU = 2 * math.pi
STEP = .25


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clip(x, lo, hi):
    return max(lo, min(hi, x))


class Controller:
    def __init__(self):
        self.cart = CartClient()
        self.map = self.cart.layout
        self.tags = {t.name: t for t in self.map.tags}
        self.obs = self.cart.observe(expose=True)
        p = self.map.starts[0]
        self.x, self.y, self.h = p.x, p.y, p.heading
        self.localized = False
        self.gl = self.gr = .85
        self.lag = 2
        self.commands = []
        self.last_tag_pose = None
        self.update(self.obs)
        self.build_grid()
        self.path = []
        self.blocked = set()
        self.hits = set()

    def update(self, obs):
        old = self.obs
        ds = obs.odometry_m - old.odometry_m
        da = obs.odometry_heading_rad - old.odometry_heading_rad
        dh = obs.gyro_heading_rad - old.gyro_heading_rad
        dl, dr = ds - .28 * da, ds + .28 * da
        distance = (dl * self.gl + dr * self.gr) / 2
        sinc = math.sin(dh / 2) / (dh / 2) if abs(dh) > 1e-8 else 1
        self.x += distance * sinc * math.cos(self.h + dh / 2)
        self.y += distance * sinc * math.sin(self.h + dh / 2)
        self.h = wrap(self.h + dh)
        if obs.tags:
            poses = []
            for reading in obs.tags:
                tag = self.tags[reading.name]
                heading = wrap(tag.heading - reading.relative_heading_rad)
                angle = heading + reading.bearing_rad
                poses.append((tag.x - reading.range_m * math.cos(angle),
                              tag.y - reading.range_m * math.sin(angle), heading))
            x = sum(p[0] for p in poses) / len(poses)
            y = sum(p[1] for p in poses) / len(poses)
            h = poses[0][2]
            if self.last_tag_pose and self.last_tag_pose[3] == old.tick and abs(dh) < .6:
                px, py, ph, _ = self.last_tag_pose
                actual = ((x - px) * math.cos(ph + dh / 2) +
                          (y - py) * math.sin(ph + dh / 2)) / sinc
                al, ar = actual - .28 * dh, actual + .28 * dh
                if abs(dl) > .025:
                    self.gl = .25 * self.gl + .75 * clip(al / dl, .25, 1.05)
                if abs(dr) > .025:
                    self.gr = .25 * self.gr + .75 * clip(ar / dr, .25, 1.05)
            self.x, self.y, self.h = x, y, h
            self.localized = True
            self.last_tag_pose = (x, y, h, obs.tick)
        self.obs = obs

    def drive(self, left, right, ticks=1):
        left, right = clip(left, -1, 1), clip(right, -1, 1)
        self.cart.command(left, right, ticks)
        self.commands.extend([(left, right)] * ticks)
        self.commands = self.commands[-4:]
        self.update(self.cart.observe(expose=True))

    def stop(self):
        self.drive(0, 0, 3)

    def predict(self):
        x, y, h = self.x, self.y, self.h
        for l, r in (self.commands[-self.lag:] if self.lag else []):
            l, r = l * self.gl, r * self.gr
            dh = (r - l) * .2 / .56
            d = (l + r) * .1
            if abs(dh) > 1e-8:
                d *= math.sin(dh / 2) / (dh / 2)
            x += d * math.cos(h + dh / 2)
            y += d * math.sin(h + dh / 2)
            h = wrap(h + dh)
        return x, y, h

    def build_grid(self):
        self.xmin = math.floor(min(r.left for r in self.map.aisles)) - 1
        self.ymin = math.floor(min(r.bottom for r in self.map.aisles)) - 1
        self.nx = int((max(r.right for r in self.map.aisles) - self.xmin + 1) / STEP) + 1
        self.ny = int((max(r.top for r in self.map.aisles) - self.ymin + 1) / STEP) + 1
        self.free = set()
        self.cost = {}
        for j in range(self.ny):
            y = self.ymin + j * STEP
            for i in range(self.nx):
                x = self.xmin + i * STEP
                clearance = max(min(x-r.left, r.right-x, y-r.bottom, r.top-y)
                                for r in self.map.aisles)
                if clearance < .46:
                    continue
                if any(r.left-.46 <= x <= r.right+.46 and r.bottom-.46 <= y <= r.top+.46
                       for r in self.map.shelves):
                    continue
                k = j * self.nx + i
                self.free.add(k)
                self.cost[k] = 1 + .12 / max(.15, clearance - .28)

    def key(self, x, y):
        return round((y-self.ymin)/STEP) * self.nx + round((x-self.xmin)/STEP)

    def point(self, k):
        return self.xmin + (k % self.nx) * STEP, self.ymin + (k // self.nx) * STEP

    def map_obstacles(self):
        changed = False
        for i, distance in enumerate(self.obs.lidar_m):
            if distance >= 4.72:
                continue
            a = self.h + i * TAU / 16
            c, s = math.cos(a), math.sin(a)
            x, y = self.x + c * (distance + .04), self.y + s * (distance + .04)
            # Ignore returns explained by the survey, allowing for range quantization.
            if not all(self.map.free(x+dx, y+dy) for dx, dy in ((0,0),(.12,0),(-.12,0),(0,.12),(0,-.12))):
                continue
            hit = (round(x/.2), round(y/.2))
            if hit in self.hits:
                continue
            self.hits.add(hit)
            k = self.key(x, y)
            for dj in range(-3, 4):
                for di in range(-3, 4):
                    cell = k + dj*self.nx + di
                    cx, cy = self.point(cell)
                    if (cx-x)**2 + (cy-y)**2 < .57**2 and cell in self.free and cell not in self.blocked:
                        self.blocked.add(cell)
                        changed = True
        return changed

    def visible(self, a, b):
        d = math.hypot(b[0]-a[0], b[1]-a[1])
        n = max(1, math.ceil(d/.10))
        for i in range(n+1):
            f = i/n
            k = self.key(a[0] + f*(b[0]-a[0]), a[1]+f*(b[1]-a[1]))
            if k not in self.free or k in self.blocked:
                return False
        return True

    def plan(self):
        start = self.key(self.x, self.y)
        goal = self.key(self.map.dock.x, self.map.dock.y)
        allowed = self.free - self.blocked
        if start not in allowed:
            candidates = [k for k in allowed if math.dist(self.point(k), (self.x, self.y)) < .65]
            if not candidates:
                return False
            start = min(candidates, key=lambda k: math.dist(self.point(k), (self.x, self.y)))
        q = [(0, 0, start)]
        dist = {start: 0}
        prev = {}
        gx, gy = self.point(goal)
        while q:
            _, g, k = heapq.heappop(q)
            if g != dist[k]:
                continue
            if k == goal:
                route = [k]
                while k != start:
                    k = prev[k]
                    route.append(k)
                route.reverse()
                pts = [self.point(k) for k in route]
                pts[-1] = (self.map.dock.x, self.map.dock.y)
                # Retain enough clearance around corners when straightening the path.
                result = []
                anchor = (self.x, self.y)
                index = 0
                while index < len(pts):
                    far = index
                    for j in range(index+1, len(pts)):
                        if not self.visible(anchor, pts[j]):
                            break
                        far = j
                    result.append(pts[far])
                    anchor = pts[far]
                    index = far+1
                self.path = result
                return True
            for di, dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nb = k + di + dj*self.nx
                if nb not in allowed:
                    continue
                if di and dj and (k+di not in allowed or k+dj*self.nx not in allowed):
                    continue
                ng = g + (1.41421356 if di and dj else 1) * self.cost[nb]
                if ng < dist.get(nb, float('inf')):
                    dist[nb] = ng
                    prev[nb] = k
                    x, y = self.point(nb)
                    heuristic = math.hypot(x-gx, y-gy)/STEP
                    heapq.heappush(q, (ng+heuristic, ng, nb))
        self.path = []
        return False

    def wheels(self, v, w):
        l, r = (v-.28*w)/self.gl, (v+.28*w)/self.gr
        scale = max(1, abs(l), abs(r))
        return l/scale, r/scale

    def run(self):
        # A short rotation measures command latency and gives the camera a view.
        initial = self.obs
        detected = False
        for i in range(6):
            self.drive(-.25, .25)
            if not detected and abs(self.obs.gyro_heading_rad-initial.gyro_heading_rad) > .001:
                self.lag = min(2, i)
                detected = True
        self.stop()
        for _ in range(90):
            if self.localized:
                break
            self.drive(-.3, .3)
        self.stop()
        if not self.localized:
            self.cart.finish()
            return
        self.map_obstacles()
        self.plan()
        last_plan = self.obs.tick
        while self.obs.tick < self.cart.tick_limit - 8:
            changed = self.map_obstacles()
            if changed and (not self.path or not all(self.visible(a,b) for a,b in zip([(self.x,self.y)]+self.path, self.path))):
                self.stop()
                self.map_obstacles()
                self.plan()
                last_plan = self.obs.tick
            if not self.path:
                self.stop()
                if not self.plan():
                    break
            x, y, h = self.predict()
            dock = self.map.dock
            error = math.hypot(dock.x-self.x, dock.y-self.y)
            if error < .10:
                self.stop()
                if math.hypot(dock.x-self.x, dock.y-self.y) > .13:
                    self.plan()
                    continue
                for _ in range(100):
                    _, _, ph = self.predict()
                    e = wrap(dock.heading-ph)
                    if abs(e) < .025:
                        self.stop()
                        if abs(wrap(dock.heading-self.h)) < .045:
                            self.cart.finish()
                            return
                    self.drive(*self.wheels(0, clip(2.5*e, -.9, .9)))
                break
            while len(self.path) > 1 and math.hypot(self.path[0][0]-x, self.path[0][1]-y) < .16:
                self.path.pop(0)
            tx, ty = self.path[0]
            distance = math.hypot(tx-x, ty-y)
            angle = wrap(math.atan2(ty-y, tx-x)-h)
            v = min(.72, 1.6*distance) * max(0, math.cos(angle))**3
            if abs(angle) > .7:
                v = 0
            w = clip(2.8*angle, -1.2, 1.2)
            # Bound speed by the measured free space in the direction of motion.
            clearance = 4.8
            for i, r in enumerate(self.obs.lidar_m):
                a = wrap(i*TAU/16)
                if abs(a) < 1.4 and abs(r*math.sin(a)) < .40:
                    clearance = min(clearance, r*math.cos(a))
            v = min(v, max(0, (clearance-.48)/(.2*(self.lag+2))))
            if v < .025 and abs(angle) < .15 and distance > .25:
                self.stop()
                if self.obs.tick-last_plan > 8:
                    self.plan()
                    last_plan = self.obs.tick
                else:
                    self.drive(*self.wheels(0, .4))
                continue
            self.drive(*self.wheels(v, w))
        self.stop()
        self.cart.finish()


if __name__ == '__main__':
    Controller().run()
