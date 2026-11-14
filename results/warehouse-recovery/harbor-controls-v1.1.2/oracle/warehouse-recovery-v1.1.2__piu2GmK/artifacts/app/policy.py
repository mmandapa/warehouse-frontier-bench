"""Observation-only reference for the surveyed warehouse."""

from heapq import heappop, heappush
import math

from warehouse_sim.client import CartClient
from warehouse_sim.world import Pose, TRACK_M, wrap


MAX_REPLANS = None


class RouteBlocked(RuntimeError):
    pass


class MotionFailed(RuntimeError):
    pass


def clamp(value, bound):
    return max(-bound, min(bound, value))


def map_graph(aisles):
    graph = {}
    for rect in aisles:
        width, height = rect.right - rect.left, rect.top - rect.bottom
        if width > height:
            mid = (rect.bottom + rect.top) / 2
            points = ((rect.left + height / 2, mid), (rect.right - height / 2, mid))
        else:
            mid = (rect.left + rect.right) / 2
            points = ((mid, rect.bottom + width / 2), (mid, rect.top - width / 2))
        a, b = (tuple(round(value, 5) for value in point) for point in points)
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)
    return graph


def route(graph, start, dock, closed):
    queue = [(0.0, (start,))]
    seen = set()
    while queue:
        cost, path = heappop(queue)
        here = path[-1]
        if here in seen:
            continue
        if here == dock:
            return path
        seen.add(here)
        for there in graph[here]:
            if there not in seen and frozenset((here, there)) not in closed:
                heappush(queue, (cost + math.dist(here, there), (*path, there)))
    raise MotionFailed("no route remains")


class Navigator:
    def __init__(self, client):
        self.client = client
        self.markers = {tag.name: tag for tag in client.layout.tags}
        self.previous = client.observe()
        self.heading_zero = client.layout.starts[0].heading
        self.pose = None

    def observe(self):
        obs = self.client.observe(expose=True)
        heading = wrap(self.heading_zero + obs.gyro_heading_rad)
        if obs.tags:
            reading = min(obs.tags, key=lambda tag: tag.range_m)
            marker = self.markers[reading.name]
            heading = wrap(marker.heading - reading.relative_heading_rad)
            self.heading_zero = wrap(heading - obs.gyro_heading_rad)
            bearing = heading + reading.bearing_rad
            self.pose = Pose(marker.x - reading.range_m * math.cos(bearing),
                             marker.y - reading.range_m * math.sin(bearing), heading)
        elif self.pose is not None:
            travel = .78 * (obs.odometry_m - self.previous.odometry_m)
            midpoint = self.pose.heading + wrap(heading - self.pose.heading) / 2
            self.pose = Pose(self.pose.x + travel * math.cos(midpoint),
                             self.pose.y + travel * math.sin(midpoint), heading)
        self.previous = obs
        return obs, heading

    def stop(self):
        self.client.command(0, 0, ticks=3)
        return self.observe()

    def drive(self, speed, rotation):
        left = speed - rotation * TRACK_M / 2
        right = speed + rotation * TRACK_M / 2
        scale = max(1, abs(left), abs(right))
        self.client.command(left / scale, right / scale, ticks=2)

    def turn(self, target):
        _, heading = self.observe()
        for _ in range(95):
            error = wrap(target - heading)
            if abs(error) < .040:
                _, heading = self.stop()
                if abs(wrap(target - heading)) < .047:
                    return
            else:
                self.drive(0, clamp(2.5 * error, 1.55))
                _, heading = self.observe()
        raise MotionFailed("turn did not settle")

    def localize(self):
        for offset in (0, math.pi / 2, math.pi, -math.pi / 2):
            if self.pose is not None:
                return
            self.turn(offset)
        if self.pose is None:
            raise MotionFailed("no surveyed marker visible")

    def go(self, target, *, detect=False, tolerance=.085):
        self.observe()
        pose = self.pose
        if math.dist((pose.x, pose.y), target) < tolerance:
            return
        self.turn(math.atan2(target[1] - pose.y, target[0] - pose.x))
        obs, _ = self.observe()
        steering_bias = 0.0
        for _ in range(370):
            pose = self.pose
            dx, dy = target[0] - pose.x, target[1] - pose.y
            distance = math.hypot(dx, dy)
            if distance < tolerance:
                obs, _ = self.stop()
                if math.dist((self.pose.x, self.pose.y), target) < tolerance + .015:
                    return
                continue
            error = wrap(math.atan2(dy, dx) - pose.heading)
            if detect and abs(error) < .32 and distance > 1.20 and obs.lidar_m[0] < 1.04:
                self.stop()
                raise RouteBlocked
            speed = min(.91, 1.45 * distance) * max(0, math.cos(error))
            if abs(error) > .95:
                speed = 0.0
            steering_bias = clamp(steering_bias + .40 * error, .85)
            self.drive(speed, clamp(2.45 * error + steering_bias, 1.25))
            obs, _ = self.observe()
        raise MotionFailed("waypoint did not converge")


def main():
    client = CartClient()
    layout = client.layout
    cart = Navigator(client)
    try:
        cart.localize()
        graph = map_graph(layout.aisles)
        here = min(graph, key=lambda p: math.dist(p, (cart.pose.x, cart.pose.y)))
        dock = (layout.dock.x, layout.dock.y)
        closed = set()
        while here != dock:
            for following in route(graph, here, dock, closed)[1:]:
                try:
                    cart.go(following, detect=True)
                except RouteBlocked:
                    if MAX_REPLANS is not None and len(closed) >= MAX_REPLANS:
                        raise MotionFailed("replan limit")
                    closed.add(frozenset((here, following)))
                    cart.go(here)
                    break
                here = following
        cart.turn(layout.dock.heading)
        cart.stop()
    except MotionFailed:
        pass
    client.finish()


if __name__ == "__main__":
    main()
