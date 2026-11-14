"""Marker-localized, slip-adaptive navigation with an online obstacle map."""
import math
import heapq
from collections import deque
from warehouse_sim.client import CartClient


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def clip(a, lo, hi):
    return max(lo, min(hi, a))


class Controller:
    def __init__(self, cart):
        self.cart = cart
        self.layout = cart.layout
        self.tags = {t.name: t for t in self.layout.tags}
        self.gains = [.85, .85]
        self.commands = []
        self.lag = 0
        self.obs = cart.observe(expose=True)
        self.x, self.y, self.h = (self.layout.starts[0].x,
                                 self.layout.starts[0].y,
                                 self.layout.starts[0].heading)
        self.localized = False
        self.tag_pose(self.obs)
        self.origin_heading = self.h - self.obs.gyro_heading_rad
        self.step = .25
        self.x0 = math.floor(min(r.left for r in self.layout.aisles)) - 1
        self.y0 = math.floor(min(r.bottom for r in self.layout.aisles)) - 1
        self.nx = int((max(r.right for r in self.layout.aisles) - self.x0 + 1) / self.step) + 1
        self.ny = int((max(r.top for r in self.layout.aisles) - self.y0 + 1) / self.step) + 1
        self.raw = set()
        for j in range(self.ny):
            for i in range(self.nx):
                if self.layout.free(*self.point((i, j))):
                    self.raw.add((i, j))
        # Distance from the surveyed walls, in grid units.
        self.clearance = {}
        q = deque()
        for p in self.raw:
            if any((p[0]+di, p[1]+dj) not in self.raw for di,dj in ((1,0),(-1,0),(0,1),(0,-1))):
                self.clearance[p] = 1
                q.append(p)
        while q:
            p = q.popleft()
            d = self.clearance[p] + 1
            for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
                n = (p[0]+di,p[1]+dj)
                if n in self.raw and n not in self.clearance:
                    self.clearance[n] = d
                    q.append(n)
        ring = [(math.cos(k*math.pi/8)*.48, math.sin(k*math.pi/8)*.48) for k in range(16)]
        self.free = {p for p in self.raw if all(self.layout.free(self.point(p)[0]+dx,self.point(p)[1]+dy) for dx,dy in ring)}
        self.blocked = set()
        self.path = []
        self.goal = (self.layout.dock.x, self.layout.dock.y)

    def point(self, p):
        return self.x0+p[0]*self.step, self.y0+p[1]*self.step

    def cell(self, x, y):
        return round((x-self.x0)/self.step), round((y-self.y0)/self.step)

    def tag_pose(self, obs):
        if not obs.tags:
            return False
        estimates = []
        for reading in obs.tags:
            tag = self.tags[reading.name]
            h = wrap(tag.heading-reading.relative_heading_rad)
            a = h+reading.bearing_rad
            estimates.append((tag.x-reading.range_m*math.cos(a),
                              tag.y-reading.range_m*math.sin(a), h))
        self.x = sum(p[0] for p in estimates)/len(estimates)
        self.y = sum(p[1] for p in estimates)/len(estimates)
        self.h = estimates[0][2]
        self.localized = True
        return True

    @staticmethod
    def integrate(x, y, h, left, right, duration=.2):
        v = (left+right)/2
        dh = (right-left)/.56*duration
        scale = duration if abs(dh)<1e-8 else duration*math.sin(dh/2)/(dh/2)
        return x+v*scale*math.cos(h+dh/2), y+v*scale*math.sin(h+dh/2), wrap(h+dh)

    def drive(self, left, right):
        old = self.obs
        oldx, oldy, oldh = self.x,self.y,self.h
        had_tag = bool(old.tags)
        self.commands.append((left,right))
        self.cart.command(left,right)
        obs = self.cart.observe(expose=True)
        ds = obs.odometry_m-old.odometry_m
        da = obs.odometry_heading_rad-old.odometry_heading_rad
        dg = obs.gyro_heading_rad-old.gyro_heading_rad
        l = ds/.2-da*.56/.4
        r = ds/.2+da*.56/.4
        # Identify the command pipeline using the wheel encoders.
        errors = []
        for lag in range(3):
            cmd = self.commands[-1-lag] if len(self.commands)>lag else (0,0)
            errors.append(abs(l-cmd[0])+abs(r-cmd[1]))
        if errors[self.lag] > .002:
            self.lag = min(range(3), key=lambda i: errors[i])
        # Gyro supplies an independent constraint on the two traction gains.
        a,b = -l,r
        norm = a*a+b*b
        if norm > .01:
            residual = dg*.56/.2 - (a*self.gains[0]+b*self.gains[1])
            self.gains[0] = clip(self.gains[0]+.7*residual*a/norm,.25,1.05)
            self.gains[1] = clip(self.gains[1]+.7*residual*b/norm,.25,1.05)
        distance = (l*self.gains[0]+r*self.gains[1])*.1
        self.h = wrap(self.origin_heading+obs.gyro_heading_rad)
        self.x += distance*math.cos(oldh+dg/2)
        self.y += distance*math.sin(oldh+dg/2)
        if self.tag_pose(obs):
            self.origin_heading = self.h-obs.gyro_heading_rad
            if had_tag and abs(l)>.15 and abs(r)>.15:
                actual = ((self.x-oldx)*math.cos(oldh+dg/2)+(self.y-oldy)*math.sin(oldh+dg/2))/.2
                for i, g in enumerate(((actual-dg*.56/.4)/l,(actual+dg*.56/.4)/r)):
                    if .2 < g < 1.15:
                        self.gains[i] = .65*self.gains[i]+.35*clip(g,.25,1.02)
        self.obs = obs

    def predicted(self):
        x,y,h = self.x,self.y,self.h
        if self.lag:
            for l,r in self.commands[-self.lag:]:
                x,y,h = self.integrate(x,y,h,l*self.gains[0],r*self.gains[1])
        return x,y,h

    def stop(self):
        for _ in range(3):
            self.drive(0,0)

    def map_obstacles(self):
        changed = False
        for i,d in enumerate(self.obs.lidar_m):
            if d >= 4.79:
                continue
            a = self.h+i*math.pi/8
            # The first occupied lidar sample is at most 8 cm inside a surface.
            x,y = self.x+d*math.cos(a),self.y+d*math.sin(a)
            if not self.layout.free(x,y):
                continue
            # Ignore quantization at surveyed walls.
            if not all(self.layout.free(x+dx,y+dy) for dx,dy in ((.12,0),(-.12,0),(0,.12),(0,-.12))):
                continue
            c = self.cell(x,y)
            for di in range(-3,4):
                for dj in range(-3,4):
                    p = c[0]+di,c[1]+dj
                    px,py = self.point(p)
                    if (px-x)**2+(py-y)**2 < .59**2 and p in self.free and p not in self.blocked:
                        self.blocked.add(p)
                        changed = True
        return changed

    def valid(self, p):
        return p in self.free and p not in self.blocked

    def line_clear(self, a,b):
        distance = math.hypot(a[0]-b[0],a[1]-b[1])
        n = max(1,int(distance/.10)+1)
        return all(self.valid(self.cell(a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n)) for i in range(n+1))

    def plan(self):
        start = self.cell(self.x,self.y)
        goal = self.cell(*self.goal)
        if not self.valid(start):
            choices = [p for p in self.free if p not in self.blocked and math.hypot(self.point(p)[0]-self.x,self.point(p)[1]-self.y)<1.0]
            if not choices:
                return False
            start = min(choices,key=lambda p: math.hypot(self.point(p)[0]-self.x,self.point(p)[1]-self.y))
        if start == goal:
            self.path = [self.goal]
            return True
        def heuristic(p):
            return math.hypot(p[0]-goal[0],p[1]-goal[1])
        todo = [(heuristic(start),0,start)]
        cost = {start:0}
        parent = {}
        found = False
        while todo:
            _,g,p = heapq.heappop(todo)
            if g > cost[p]+1e-8:
                continue
            if p == goal:
                found = True
                break
            for di,dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                n = p[0]+di,p[1]+dj
                if not self.valid(n):
                    continue
                if di and dj and (not self.valid((p[0]+di,p[1])) or not self.valid((p[0],p[1]+dj))):
                    continue
                ng = g + math.hypot(di,dj)*(1+.9/max(1,self.clearance.get(n,1)-1))
                if ng < cost.get(n,1e20):
                    cost[n]=ng
                    parent[n]=p
                    heapq.heappush(todo,(ng+heuristic(n),ng,n))
        if not found:
            return False
        path = [goal]
        while path[-1] != start:
            path.append(parent[path[-1]])
        path = [self.point(p) for p in reversed(path)]
        path[0] = (self.x,self.y)
        path[-1] = self.goal
        # Keep modest straight segments so a changed map can be checked cheaply.
        simplified = []
        index = 0
        while index<len(path)-1:
            last = index+1
            for j in range(index+2,len(path)):
                if math.hypot(path[j][0]-path[index][0],path[j][1]-path[index][1])>3.0 or not self.line_clear(path[index],path[j]):
                    break
                last=j
            simplified.append(path[last])
            index=last
        self.path = simplified
        return True

    def wheels(self, v, omega):
        left = (v-.28*omega)/self.gains[0]
        right = (v+.28*omega)/self.gains[1]
        scale = max(1,abs(left)/.9,abs(right)/.9)
        return left/scale,right/scale

    def run(self):
        # A stationary scan disambiguates the possible starting lanes.
        for _ in range(65):
            if self.localized:
                break
            self.drive(-.22,.22)
        self.stop()
        if not self.localized:
            # Long repetitive aisles may put every marker beyond camera range.
            for _ in range(220):
                if self.localized or self.obs.lidar_m[0]<1.2:
                    break
                err = wrap(self.layout.starts[0].heading-self.h)
                self.drive(*self.wheels(.35 if abs(err)<.3 else 0,clip(2*err,-.7,.7)))
            self.stop()
        self.map_obstacles()
        self.plan()
        while self.obs.tick < self.cart.tick_limit-20:
            changed = self.map_obstacles()
            if changed and self.path:
                points = [(self.x,self.y)]+self.path
                if any(not self.line_clear(a,b) for a,b in zip(points,points[1:])):
                    self.stop()
                    self.map_obstacles()
                    self.path=[]
            if not self.path:
                if math.hypot(self.x-self.goal[0],self.y-self.goal[1])<.10:
                    break
                if not self.plan():
                    self.stop()
                    break
            x,y,h = self.predicted()
            target = self.path[0]
            d = math.hypot(target[0]-x,target[1]-y)
            if d < .09:
                if len(self.path) == 1:
                    self.stop()
                self.path.pop(0)
                continue
            desired = math.atan2(target[1]-y,target[0]-x)
            err = wrap(desired-h)
            omega = clip(2.5*err,-1.1,1.1)
            v = min(.65,1.4*d)
            if abs(err)>.40:
                v=0
            else:
                v *= max(0,1-abs(err)/.55)
            # A last-resort range guard also accounts for queued commands.
            if v>0 and min(self.obs.lidar_m[0],self.obs.lidar_m[1],self.obs.lidar_m[15])<.65:
                self.stop()
                self.map_obstacles()
                self.path=[]
                continue
            self.drive(*self.wheels(v,omega))
        self.stop()
        for _ in range(min(100,self.cart.tick_limit-self.obs.tick-4)):
            x,y,h = self.predicted()
            err = wrap(self.layout.dock.heading-h)
            if abs(err)<.025:
                break
            self.drive(*self.wheels(0,clip(2.3*err,-.9,.9)))
        self.stop()
        self.cart.finish()


if __name__ == '__main__':
    Controller(CartClient()).run()
