"""Survey-based navigation with marker localization and online obstacle mapping."""
import heapq
import math
from warehouse_sim.client import CartClient

TAU = 2 * math.pi

def wrap(a):
    return (a + math.pi) % TAU - math.pi


class Controller:
    def __init__(self):
        self.cart = CartClient()
        self.map = self.cart.layout
        self.tags = {t.name: t for t in self.map.tags}
        self.obs = self.cart.observe(expose=True)
        self.x, self.y, self.h = self.map.starts[0].x, self.map.starts[0].y, self.map.starts[0].heading
        self.offset = self.h
        self.gl = self.gr = .8
        self.commands = []
        self.lag = 0
        self.localized = False
        self.fix(self.obs)
        self.step = .25
        self.xmin = math.floor(min(r.left for r in self.map.aisles) / self.step) * self.step
        self.ymin = math.floor(min(r.bottom for r in self.map.aisles) / self.step) * self.step
        self.nx = int((max(r.right for r in self.map.aisles) - self.xmin) / self.step) + 2
        self.ny = int((max(r.top for r in self.map.aisles) - self.ymin) / self.step) + 2
        self.build_grid()
        self.dynamic = set()

    def fix(self, obs):
        if obs.tags:
            poses = []
            for t in obs.tags:
                m = self.tags[t.name]
                h = wrap(m.heading - t.relative_heading_rad)
                poses.append((m.x - t.range_m * math.cos(h + t.bearing_rad),
                              m.y - t.range_m * math.sin(h + t.bearing_rad), h))
            self.x = sum(p[0] for p in poses) / len(poses)
            self.y = sum(p[1] for p in poses) / len(poses)
            self.h = poses[0][2]
            self.offset = self.h - obs.gyro_heading_rad
            self.localized = True

    def drive(self, l, r):
        old = self.obs
        self.cart.command(max(-1., min(1., l)), max(-1., min(1., r)))
        self.commands.append((l, r))
        o = self.cart.observe(expose=True)
        ds = o.odometry_m - old.odometry_m
        da = o.odometry_heading_rad - old.odometry_heading_rad
        al, ar = ds / .2 - da * .56 / .4, ds / .2 + da * .56 / .4
        # The gyro measures actual wheel differential even when the floor slips.
        target = (o.gyro_heading_rad - old.gyro_heading_rad) * .56 / .2
        err = target - (ar * self.gr - al * self.gl)
        norm = al * al + ar * ar
        if norm > .005:
            self.gl = max(.35, min(1.05, self.gl - .65 * err * al / norm))
            self.gr = max(.35, min(1.05, self.gr + .65 * err * ar / norm))
        turn = o.gyro_heading_rad - old.gyro_heading_rad
        dist = .1 * (al * self.gl + ar * self.gr)
        self.x += dist * math.cos(self.h + turn / 2)
        self.y += dist * math.sin(self.h + turn / 2)
        self.h = wrap(o.gyro_heading_rad + self.offset)
        self.obs = o
        self.fix(o)
        # Match applied encoder velocities against the command history.
        matches = [d for d in range(3) if len(self.commands) > d and
                   abs(self.commands[-1-d][0] - al) + abs(self.commands[-1-d][1] - ar) < .002]
        if len(matches) == 1:
            self.lag = matches[0]

    def predicted(self):
        x, y, h = self.x, self.y, self.h
        for l, r in self.commands[len(self.commands)-self.lag:] if self.lag else ():
            d = .1 * (l * self.gl + r * self.gr)
            a = .2 * (r * self.gr - l * self.gl) / .56
            x += d * math.cos(h + a / 2)
            y += d * math.sin(h + a / 2)
            h = wrap(h + a)
        return x, y, h

    def point(self, n):
        return self.xmin + (n % self.nx) * self.step, self.ymin + (n // self.nx) * self.step

    def cell(self, x, y):
        i, j = round((x-self.xmin)/self.step), round((y-self.ymin)/self.step)
        return j*self.nx+i

    def neighbors(self, n):
        i, j = n % self.nx, n // self.nx
        for dx, dy, cost in ((1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,1.4142),(1,-1,1.4142),(-1,1,1.4142),(-1,-1,1.4142)):
            if 0 <= i+dx < self.nx and 0 <= j+dy < self.ny:
                yield n + dx + dy*self.nx, cost

    def build_grid(self):
        size = self.nx*self.ny
        self.clearance = [100.] * size
        q = []
        for n in range(size):
            x, y = self.point(n)
            if not self.map.free(x,y):
                self.clearance[n] = 0.
                q.append((0., n))
        heapq.heapify(q)
        while q:
            d,n = heapq.heappop(q)
            if d != self.clearance[n] or d > 1.7:
                continue
            for k,c in self.neighbors(n):
                nd = d+c*self.step
                if nd < self.clearance[k]:
                    self.clearance[k] = nd
                    heapq.heappush(q,(nd,k))
        self.static = {n for n,d in enumerate(self.clearance) if d < .75}

    def map_obstacles(self):
        added = False
        for i,dist in enumerate(self.obs.lidar_m):
            if dist >= 4.79:
                continue
            a = self.h + i * TAU/16
            x, y = self.x + (dist-.04)*math.cos(a), self.y + (dist-.04)*math.sin(a)
            c = self.cell(x,y)
            if not 0 <= c < len(self.clearance) or not all(
                    self.map.free(x+dx,y+dy) for dx,dy in ((0,0),(.18,0),(-.18,0),(0,.18),(0,-.18))):
                continue
            ci, cj = c % self.nx, c // self.nx
            for di in range(-3,4):
                for dj in range(-3,4):
                    ni,nj = ci+di,cj+dj
                    if not (0 <= ni < self.nx and 0 <= nj < self.ny):
                        continue
                    n = nj*self.nx+ni
                    px,py = self.point(n)
                    if math.hypot(px-x,py-y) < .55 and n not in self.dynamic:
                        self.dynamic.add(n)
                        added = True
        return added

    def line_clear(self, p, q):
        d = math.hypot(q[0]-p[0], q[1]-p[1])
        steps = max(1, math.ceil(d/.1))
        for j in range(steps+1):
            t = j/steps
            n = self.cell(p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1]))
            if n in self.static or n in self.dynamic:
                return False
        return True

    def plan(self):
        start = self.cell(self.x,self.y)
        goal = self.cell(self.map.dock.x,self.map.dock.y)
        gx,gy = self.point(goal)
        q = [(0.,0.,start)]
        costs = {start:0.}
        prev = {}
        while q:
            _,d,n = heapq.heappop(q)
            if d != costs[n]:
                continue
            if n == goal:
                path = [n]
                while n != start:
                    n = prev[n]
                    path.append(n)
                pts = [self.point(n) for n in reversed(path)]
                pts[0] = (self.x,self.y)
                pts[-1] = (self.map.dock.x,self.map.dock.y)
                # Keep smoothing conservative: long shortcuts can shave corners.
                result = []
                i = 0
                while i < len(pts)-1:
                    j = i+1
                    while j+1 < len(pts) and self.line_clear(pts[i],pts[j+1]):
                        j += 1
                    result.append(pts[j])
                    i = j
                return result
            for k,c in self.neighbors(n):
                if k in self.static or k in self.dynamic:
                    continue
                if c > 1.1:
                    # Check diagonal sweeps directly, including both adjacent cells.
                    ix,iy = n%self.nx,n//self.nx
                    kx,ky = k%self.nx,k//self.nx
                    if (iy*self.nx+kx in self.static or ky*self.nx+ix in self.static or
                        iy*self.nx+kx in self.dynamic or ky*self.nx+ix in self.dynamic):
                        continue
                nd = d+c*self.step*(1+.20/max(.15,self.clearance[k]-.30)**2)
                if nd < costs.get(k,1e30):
                    costs[k]=nd
                    prev[k]=n
                    x,y = self.point(k)
                    heapq.heappush(q,(nd+math.hypot(x-gx,y-gy),nd,k))
        return []

    def wheels(self, v, w):
        l = (v-.28*w)/self.gl
        r = (v+.28*w)/self.gr
        scale = max(1.,abs(l),abs(r))
        return l/scale,r/scale

    def run(self):
        # Acquire an identifiable surveyed marker before global navigation.
        for _ in range(90):
            if self.localized:
                break
            self.drive(-.24,.24)
        for _ in range(3):
            self.drive(0.,0.)
        path = []
        aligning = False
        while self.obs.tick < self.cart.tick_limit-7:
            changed = self.map_obstacles()
            if changed and path:
                p = (self.x,self.y)
                for target in path:
                    if not self.line_clear(p,target):
                        path = []
                        break
                    p = target
            x,y,h = self.predicted()
            dock = self.map.dock
            distance = math.hypot(dock.x-x,dock.y-y)
            if distance < .10:
                aligning = True
            elif distance > .17:
                aligning = False
            if aligning:
                error = wrap(dock.heading-h)
                if abs(error) < .035:
                    for _ in range(4):
                        self.drive(0.,0.)
                    if math.hypot(dock.x-self.x,dock.y-self.y) < .15 and abs(wrap(dock.heading-self.h)) < .065:
                        self.cart.finish()
                        return
                else:
                    self.drive(*self.wheels(0.,max(-.8,min(.8,2.0*error))))
                continue
            if not path:
                path = self.plan()
                if not path:
                    self.drive(0.,0.)
                    continue
            while len(path)>1 and math.hypot(path[0][0]-x,path[0][1]-y) < .14:
                path.pop(0)
            tx,ty = path[0]
            d = math.hypot(tx-x,ty-y)
            error = wrap(math.atan2(ty-y,tx-x)-h)
            v = min(.78, .95*d)
            if abs(error) > .45:
                v = 0.
            else:
                v *= max(0.,1-abs(error)/.65)
            w = max(-1.05,min(1.05,2.2*error))
            # Lidar supplies an independent last-moment forward safety brake.
            if v > 0 and self.obs.lidar_m[0] < .65:
                v = 0.
                path = []
            self.drive(*self.wheels(v,w))
        for _ in range(3):
            if self.obs.tick < self.cart.tick_limit-1:
                self.drive(0.,0.)
        self.cart.finish()


if __name__ == '__main__':
    Controller().run()
