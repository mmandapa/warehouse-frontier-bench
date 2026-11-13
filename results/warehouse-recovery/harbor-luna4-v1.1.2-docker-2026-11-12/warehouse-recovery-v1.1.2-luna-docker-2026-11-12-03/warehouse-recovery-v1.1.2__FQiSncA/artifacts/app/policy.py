"""Survey-map and lidar based warehouse cart controller."""

import heapq
import math

from warehouse_sim.client import CartClient


TAU = 2.0 * math.pi
TRACK = 0.56
GRID = 0.4


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def tag_pose(layout, tags):
    """Recover global cart pose from the surveyed marker observations."""
    if not tags:
        return None
    hs = [wrap(next(t.heading for t in layout.tags if t.name == r.name) - r.relative_heading_rad)
          for r in tags]
    sx = sum(math.cos(h) for h in hs)
    sy = sum(math.sin(h) for h in hs)
    heading = math.atan2(sy, sx)
    xs, ys = [], []
    by_name = {t.name: t for t in layout.tags}
    for r in tags:
        t = by_name[r.name]
        a = heading + r.bearing_rad
        xs.append(t.x - r.range_m * math.cos(a))
        ys.append(t.y - r.range_m * math.sin(a))
    return (sum(xs) / len(xs), sum(ys) / len(ys), heading)


def static_ray(layout, x, y, heading):
    for k in range(1, 61):
        d = 0.08 * k
        if not layout.free(x + d * math.cos(heading), y + d * math.sin(heading)):
            return round(d, 2)
    return 4.8


def initial_pose(layout, reading):
    from_tags = tag_pose(layout, reading.tags)
    if from_tags is not None:
        return from_tags
    best, best_score = layout.starts[0], float("inf")
    for start in layout.starts:
        score = 0.0
        for i, observed in enumerate(reading.lidar_m):
            predicted = static_ray(layout, start.x, start.y, start.heading + i * TAU / 16)
            # Ignore unexpectedly short returns, which may be an unmapped obstruction.
            delta = max(0.0, predicted - observed)
            score += delta * delta
        if score < best_score:
            best, best_score = start, score
    return best.x, best.y, best.heading


def footprint_free(layout, x, y):
    if not layout.free(x, y):
        return False
    # The simulator checks the center and 16 points on the footprint boundary.
    for i in range(16):
        a = i * TAU / 16
        if not layout.free(x + 0.28 * math.cos(a), y + 0.28 * math.sin(a)):
            return False
    return True


def segment_free(layout, a, b, obstacles):
    x0, y0 = a
    x1, y1 = b
    length = math.hypot(x1 - x0, y1 - y0)
    n = max(1, int(length / 0.14) + 1)
    for i in range(n + 1):
        f = i / n
        x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        if not footprint_free(layout, x, y):
            return False
        for ox, oy in obstacles:
            if (x - ox) ** 2 + (y - oy) ** 2 < 0.55 ** 2:
                return False
    return True


def plan(layout, position, obstacles):
    """A* through footprint-clear survey-map cells, then simplify the route."""
    minx = min(r.left for r in layout.aisles)
    maxx = max(r.right for r in layout.aisles)
    miny = min(r.bottom for r in layout.aisles)
    maxy = max(r.top for r in layout.aisles)
    nx = int(math.ceil((maxx - minx) / GRID)) + 1
    ny = int(math.ceil((maxy - miny) / GRID)) + 1

    def point(ix, iy):
        return (minx + ix * GRID, miny + iy * GRID)

    valid = set()
    for ix in range(nx):
        x = minx + ix * GRID
        for iy in range(ny):
            y = miny + iy * GRID
            if footprint_free(layout, x, y) and not any((x - ox) ** 2 + (y - oy) ** 2 < .55 ** 2
                                                         for ox, oy in obstacles):
                valid.add((ix, iy))

    sx, sy = position
    gx, gy = layout.dock.x, layout.dock.y
    starts = []
    goals = set()
    for cell in valid:
        p = point(*cell)
        dstart = math.hypot(p[0] - sx, p[1] - sy)
        if dstart <= 0.85 and segment_free(layout, (sx, sy), p, obstacles):
            starts.append((cell, dstart))
        if math.hypot(p[0] - gx, p[1] - gy) <= .85 and segment_free(layout, p, (gx, gy), obstacles):
            goals.add(cell)
    if not starts or not goals:
        return [(gx, gy)]

    heap = []
    cost = {}
    parent = {}
    for cell, d in starts:
        if d < cost.get(cell, float("inf")):
            cost[cell] = d
            heapq.heappush(heap, (d + math.hypot(point(*cell)[0] - gx, point(*cell)[1] - gy), d, cell))
            parent[cell] = None

    end = None
    while heap:
        _, g, cell = heapq.heappop(heap)
        if g != cost.get(cell):
            continue
        if cell in goals:
            end = cell
            break
        x, y = cell
        p0 = point(x, y)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (x + dx, y + dy)
            if nb not in valid:
                continue
            p1 = point(*nb)
            if not segment_free(layout, p0, p1, obstacles):
                continue
            ng = g + GRID
            if ng >= cost.get(nb, float("inf")):
                continue
            cost[nb] = ng
            parent[nb] = cell
            h = math.hypot(p1[0] - gx, p1[1] - gy)
            heapq.heappush(heap, (ng + h, ng, nb))
    if end is None:
        return [(gx, gy)]

    cells = []
    cur = end
    while cur is not None:
        cells.append(point(*cur))
        cur = parent[cur]
    cells.reverse()
    raw = [(sx, sy)] + cells + [(gx, gy)]
    # Keep aisle turns square; diagonal shortcuts are too sensitive to steering lag.
    out = []
    i = 0
    while i < len(raw) - 1:
        j = len(raw) - 1
        while j > i + 1:
            aligned = abs(raw[j][0] - raw[i][0]) < 1e-6 or abs(raw[j][1] - raw[i][1]) < 1e-6
            if aligned and segment_free(layout, raw[i], raw[j], obstacles):
                break
            j -= 1
        out.append(raw[j])
        i = j
    return out


def obstacle_returns(layout, reading, pose):
    """Return lidar hits that lie inside mapped free space, unlike map walls."""
    x, y, heading = pose
    found = []
    for i, observed in enumerate(reading.lidar_m):
        if observed >= 4.8:
            continue
        angle = heading + i * TAU / 16
        expected = static_ray(layout, x, y, angle)
        if observed + 0.13 >= expected:
            continue
        # Step just inside the measured surface to avoid classifying map boundaries.
        d = max(0.04, observed - 0.04)
        px, py = x + d * math.cos(angle), y + d * math.sin(angle)
        if layout.free(px, py):
            found.append((px, py))
    return found


def main():
    cart = CartClient()
    layout = cart.layout
    reading = cart.observe(expose=True)
    x, y, heading = initial_pose(layout, reading)
    obstacles = []
    route = plan(layout, (x, y), obstacles)
    waypoint = 0
    prev_odom = reading.odometry_m
    prev_gyro = reading.gyro_heading_rad
    last_tag_position = (x, y)
    since_tag_x = since_tag_y = 0.0
    distance_scale = 0.86
    zero_ticks = 0
    docking_orientation = False

    while reading.tick < 2090:
        # Gyro gives actual ground turn; wheel odometry gives signed distance.
        d_odom = reading.odometry_m - prev_odom
        d_heading = reading.gyro_heading_rad - prev_gyro
        mid = heading + 0.5 * d_heading
        sinc = 1.0 if abs(d_heading) < 1e-8 else math.sin(0.5 * d_heading) / (0.5 * d_heading)
        raw_dx = d_odom * sinc * math.cos(mid)
        raw_dy = d_odom * sinc * math.sin(mid)
        x += raw_dx * distance_scale
        y += raw_dy * distance_scale
        heading = wrap(heading + d_heading)
        since_tag_x += raw_dx
        since_tag_y += raw_dy
        prev_odom, prev_gyro = reading.odometry_m, reading.gyro_heading_rad

        sensed_pose = tag_pose(layout, reading.tags)
        if sensed_pose is not None:
            tx, ty, th = sensed_pose
            raw2 = since_tag_x * since_tag_x + since_tag_y * since_tag_y
            if raw2 > 0.35 ** 2:
                actual_x = tx - last_tag_position[0]
                actual_y = ty - last_tag_position[1]
                estimate = (actual_x * since_tag_x + actual_y * since_tag_y) / raw2
                if 0.5 <= estimate <= 1.2:
                    distance_scale = 0.65 * distance_scale + 0.35 * estimate
            x, y, heading = tx, ty, th
            last_tag_position = (tx, ty)
            since_tag_x = since_tag_y = 0.0

        pose = (x, y, heading)
        added = False
        for ox, oy in obstacle_returns(layout, reading, pose):
            if not any((ox - px) ** 2 + (oy - py) ** 2 < .45 ** 2 for px, py in obstacles):
                obstacles.append((ox, oy))
                added = True
        if added:
            route = plan(layout, (x, y), obstacles)
            waypoint = 0

        while waypoint < len(route) - 1 and math.hypot(route[waypoint][0] - x, route[waypoint][1] - y) < .13:
            waypoint += 1
        target = route[waypoint] if route else (layout.dock.x, layout.dock.y)
        distance = math.hypot(target[0] - x, target[1] - y)
        final_target = waypoint == len(route) - 1

        # At the dock, settle position and heading, then flush actuator lag.
        dock_distance = math.hypot(layout.dock.x - x, layout.dock.y - y)
        dock_heading_error = wrap(layout.dock.heading - heading)
        if final_target and dock_distance < .10 and abs(dock_heading_error) < .055:
            if zero_ticks < 4:
                cart.command(0.0, 0.0, 1)
                zero_ticks += 1
                reading = cart.observe(expose=True)
                continue
            if dock_distance < .18 and abs(dock_heading_error) < .10:
                cart.finish()
                return
        else:
            zero_ticks = 0

        if final_target:
            if dock_distance <= .075:
                docking_orientation = True
            elif docking_orientation and dock_distance > .18:
                docking_orientation = False
            if docking_orientation:
                # Align only after the position is close; then recheck for drift.
                v = 0.0
                omega = clamp(1.6 * dock_heading_error, -.42, .42)
            else:
                desired_direction = math.atan2(layout.dock.y - y, layout.dock.x - x)
                forward_error = wrap(desired_direction - heading)
                reverse = abs(forward_error) > math.pi / 2
                move_error = wrap(forward_error + (math.pi if reverse else 0.0))
                if abs(move_error) > .55:
                    v = 0.0
                else:
                    v = min(.22, max(.07, dock_distance * .65)) * (-1.0 if reverse else 1.0)
                omega = clamp(1.6 * move_error, -.42, .42)
        else:
            bearing = math.atan2(target[1] - y, target[0] - x)
            error = wrap(bearing - heading)
            if abs(error) > .72:
                v = 0.0
                omega = clamp(1.25 * error, -.52, .52)
            else:
                v = min(.46, max(.10, distance * .72)) * max(.28, math.cos(error))
                omega = clamp(1.65 * error, -.58, .58)

        left = v - omega * TRACK / 2.0
        right = v + omega * TRACK / 2.0
        scale = max(1.0, abs(left), abs(right))
        left, right = left / scale, right / scale
        cart.command(left, right, 1)
        reading = cart.observe(expose=True)

    cart.command(0.0, 0.0, 4)
    cart.finish()


if __name__ == "__main__":
    main()
