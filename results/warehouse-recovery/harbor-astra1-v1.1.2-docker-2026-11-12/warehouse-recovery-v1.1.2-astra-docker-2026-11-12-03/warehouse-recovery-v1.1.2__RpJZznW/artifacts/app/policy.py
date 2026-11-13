"""Marker/gyro localization, aisle routing, and delay-aware wheel control."""
import heapq
import math
from warehouse_sim.client import CartClient

TAU = 2 * math.pi

def wrap(a):
    return (a + math.pi) % TAU - math.pi

def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0., min(1., ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / max(1e-12, dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)

class Controller:
    def __init__(self):
        self.cart = CartClient()
        self.map = self.cart.layout
        self.tags = {t.name: t for t in self.map.tags}
        self.r = self.cart.observe(expose=True)
        self.pose = None
        self.offset = 0.
        self.gains = [.85, .85]
        self.history = []
        self.lags = {0, 1, 2}
        self.obstacles = []
        self.last_fix = None
        self.fix()
        self.build_graph()

    def fix(self):
        r = self.r
        if not r.tags:
            return False
        poses = []
        for t in r.tags:
            tag = self.tags[t.name]
            h = wrap(tag.heading - t.relative_heading_rad)
            poses.append((tag.x - t.range_m*math.cos(h+t.bearing_rad),
                          tag.y - t.range_m*math.sin(h+t.bearing_rad), h))
        x = sum(p[0] for p in poses)/len(poses)
        y = sum(p[1] for p in poses)/len(poses)
        h = poses[0][2]
        self.offset = wrap(h-r.gyro_heading_rad)
        self.pose = (x, y, h)
        return True

    def step(self, left, right):
        old, old_pose = self.r, self.pose
        old_tag = bool(old.tags)
        self.history.append((left, right))
        self.cart.command(left, right)
        self.r = self.cart.observe(expose=True)
        r = self.r
        ds = r.odometry_m-old.odometry_m
        dw = r.odometry_heading_rad-old.odometry_heading_rad
        dg = r.gyro_heading_rad-old.gyro_heading_rad
        u = (ds/.2-dw*1.4, ds/.2+dw*1.4)
        for lag in tuple(self.lags):
            index = len(self.history)-1-lag
            expected = self.history[index] if index >= 0 else (0, 0)
            if max(abs(expected[j]-u[j]) for j in (0, 1)) > .001:
                self.lags.remove(lag)
        # Gyro constrains wheel gains even when the camera cannot see a tag.
        gl, gr = self.gains
        residual = dg*2.8-(u[1]*gr-u[0]*gl)
        norm = u[0]*u[0]+u[1]*u[1]
        if norm > .02:
            gl -= .7*residual*u[0]/norm
            gr += .7*residual*u[1]/norm
        if old_pose:
            length = (u[0]*gl+u[1]*gr)*.1
            if abs(dg) > 1e-6:
                length *= math.sin(dg/2)/(dg/2)
            h = old_pose[2]+dg/2
            self.pose = (old_pose[0]+length*math.cos(h), old_pose[1]+length*math.sin(h),
                         wrap(old_pose[2]+dg))
        fixed = self.fix()
        if fixed and old_tag and old_pose:
            mid = old_pose[2]+dg/2
            length = ((self.pose[0]-old_pose[0])*math.cos(mid)+
                      (self.pose[1]-old_pose[1])*math.sin(mid))
            if abs(dg) > 1e-6:
                length /= math.sin(dg/2)/(dg/2)
            linear = length/.2
            actual = (linear-dg*1.4, linear+dg*1.4)
            if abs(u[0]) > .10:
                gl = .25*gl+.75*actual[0]/u[0]
            if abs(u[1]) > .10:
                gr = .25*gr+.75*actual[1]/u[1]
        self.gains = [max(.25, min(1.05, gl)), max(.25, min(1.05, gr))]
        return fixed

    def stop(self):
        for _ in range(3):
            self.step(0., 0.)

    def predicted(self):
        x, y, h = self.pose
        lag = max(self.lags) if self.lags else 2
        if lag:
            for l, r in self.history[-lag:]:
                l *= self.gains[0]
                r *= self.gains[1]
                turn = (r-l)/.56*.2
                length = (r+l)*.1
                if abs(turn) > 1e-6:
                    length *= math.sin(turn/2)/(turn/2)
                x += length*math.cos(h+turn/2)
                y += length*math.sin(h+turn/2)
                h += turn
        return (x, y, wrap(h))

    def drive(self, v, w):
        l = (v-.28*w)/self.gains[0]
        r = (v+.28*w)/self.gains[1]
        scale = max(1., abs(l), abs(r))
        self.step(l/scale, r/scale)

    def free(self, x, y):
        return self.map.free(x, y)

    def segment_clear(self, a, b, dynamic=True):
        if dynamic and any(point_segment(p, a, b) < .60 for p in self.obstacles):
            return False
        n = max(1, math.ceil(distance(a, b)/.3))
        for i in range(n+1):
            x = a[0]+(b[0]-a[0])*i/n
            y = a[1]+(b[1]-a[1])*i/n
            if not all(self.free(x+dx, y+dy) for dx,dy in ((0,0),(.36,0),(-.36,0),(0,.36),(0,-.36))):
                return False
        return True

    def build_graph(self):
        lanes = []
        points = set()
        for r in self.map.aisles:
            if r.right-r.left >= r.top-r.bottom:
                y = (r.top+r.bottom)/2
                half = (r.top-r.bottom)/2
                a,b = (r.left+half,y),(r.right-half,y)
                lanes.append((True,y,r.left,r.right))
            else:
                x = (r.left+r.right)/2
                half = (r.right-r.left)/2
                a,b = (x,r.bottom+half),(x,r.top-half)
                lanes.append((False,x,r.bottom,r.top))
            points.update((a,b))
        for h,y,x0,x1 in lanes:
            if not h:
                continue
            for v,x,y0,y1 in lanes:
                if not v and x0 <= x <= x1 and y0 <= y <= y1:
                    points.add((x,y))
        for p in (*self.map.starts, self.map.dock):
            points.add((p.x,p.y))
        self.nodes = sorted(points)
        self.goal = self.nodes.index((self.map.dock.x,self.map.dock.y))
        self.edges = [[] for p in self.nodes]
        for h,c,lo,hi in lanes:
            indices = [i for i,p in enumerate(self.nodes) if abs(p[1 if h else 0]-c)<1e-5 and lo<=p[0 if h else 1]<=hi]
            indices.sort(key=lambda i:self.nodes[i][0 if h else 1])
            for a,b in zip(indices,indices[1:]):
                if self.segment_clear(self.nodes[a],self.nodes[b],False):
                    d = distance(self.nodes[a],self.nodes[b])
                    self.edges[a].append((b,d))
                    self.edges[b].append((a,d))

    def detect(self):
        if self.pose is None:
            return
        x,y,h = self.pose
        for i,ran in enumerate(self.r.lidar_m):
            if ran >= 4.79:
                continue
            angle = h+i*TAU/16
            p = (x+ran*math.cos(angle),y+ran*math.sin(angle))
            # A surveyed wall is not a temporary obstruction. Allow quantization.
            if not all(self.free(p[0]+dx,p[1]+dy) for dx,dy in ((0,0),(.18,0),(-.18,0),(0,.18),(0,-.18))):
                continue
            if all(distance(p,q)>.20 for q in self.obstacles):
                self.obstacles.append(p)

    def route(self):
        here = self.pose[:2]
        n = len(self.nodes)
        costs = {n:0.}
        previous = {}
        queue = [(0.,n)]
        while queue:
            cost,i = heapq.heappop(queue)
            if cost != costs[i]:
                continue
            if i == self.goal:
                path = []
                while i != n:
                    path.append(self.nodes[i])
                    i = previous[i]
                return path[::-1]
            if i == n:
                candidates = [(j,distance(here,p)) for j,p in enumerate(self.nodes)
                              if (abs(here[0]-p[0])<.4 or abs(here[1]-p[1])<.4)
                              and self.segment_clear(here,p)]
            else:
                candidates = [(j,d) for j,d in self.edges[i]
                              if not any(point_segment(p,self.nodes[i],self.nodes[j])<.60 for p in self.obstacles)]
            for j,d in candidates:
                new = cost+d
                if new < costs.get(j,float('inf')):
                    costs[j] = new
                    previous[j] = i
                    heapq.heappush(queue,(new,j))
        return []

    def move(self, target):
        for _ in range(600):
            if self.r.tick >= self.cart.tick_limit-15:
                return False
            self.detect()
            if any(point_segment(p,self.pose,target)<.60 for p in self.obstacles):
                self.stop()
                return False
            x,y,h = self.predicted()
            d = math.hypot(target[0]-x,target[1]-y)
            if d < .065:
                self.stop()
                if distance(self.pose,target)<.13:
                    return True
                continue
            error = wrap(math.atan2(target[1]-y,target[0]-x)-h)
            w = max(-1.3,min(1.3,2.5*error))
            v = min(.78,1.6*d)*max(0.,math.cos(error))
            if abs(error)>.40:
                v = 0.
            # Speed limit by available stopping distance, including actuator lag.
            front = min(self.r.lidar_m[0],self.r.lidar_m[1],self.r.lidar_m[15])
            v = min(v,max(0.,(front-.55)*1.1))
            self.drive(v,w)
        return False

    def run(self):
        # Rotate at low speed until a uniquely named surveyed marker is visible.
        for _ in range(100):
            if self.pose is not None:
                break
            self.step(-.24,.24)
        self.stop()
        if self.pose is None:
            self.cart.finish()
            return
        attempts = 0
        while self.r.tick < self.cart.tick_limit-25 and attempts<100:
            self.detect()
            path = self.route()
            if not path:
                break
            reroute = False
            for p in path:
                if distance(self.pose,p)<.12:
                    continue
                if not self.move(p):
                    reroute = True
                    break
            if not reroute and distance(self.pose,(self.map.dock.x,self.map.dock.y)) < .14:
                break
            attempts += 1
        if distance(self.pose,(self.map.dock.x,self.map.dock.y))<.20:
            for _ in range(90):
                if self.r.tick >= self.cart.tick_limit-5:
                    break
                error = wrap(self.map.dock.heading-self.predicted()[2])
                if abs(error)<.025:
                    self.stop()
                    if abs(wrap(self.map.dock.heading-self.pose[2]))<.055:
                        break
                else:
                    self.drive(0.,max(-1.2,min(1.2,2.5*error)))
        self.stop()
        self.cart.finish()

if __name__ == '__main__':
    Controller().run()
