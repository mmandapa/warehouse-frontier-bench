"""Survey and sensor driven controller for the warehouse cart."""

import math

from warehouse_sim.client import CartClient


TRACK = 0.56
DT = 0.2


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Localizer:
    def __init__(self, cart, survey, first):
        self.survey = survey
        self.starts = survey.starts
        self.rows = sorted({pose.y for pose in survey.starts})
        self.x = self.y = None
        self.theta0 = self.starts[0].heading if self.starts else 0.0
        self.heading_offset = self.theta0
        self.theta = self.theta0
        self.heading_integral = 0.0
        self.scale = 0.82
        self.last_odom = first.odometry_m
        self.last_gyro = first.gyro_heading_rad
        self.calib_abs = None
        self.lidar = first.lidar_m
        self.tick = first.tick
        self._abs_from_reading(first)

    def _tag_pose(self, reading):
        entries = []
        by_name = {tag.name: tag for tag in self.survey.tags}
        for seen in reading.tags:
            tag = by_name.get(seen.name)
            if tag is None:
                continue
            angle = wrap(tag.heading - seen.relative_heading_rad)
            bearing = angle + seen.bearing_rad
            x = tag.x - seen.range_m * math.cos(bearing)
            y = tag.y - seen.range_m * math.sin(bearing)
            entries.append((x, y, angle, seen.name))
        if not entries:
            return None
        # Readings are rounded by the simulator. Prefer a consistent group if
        # more than one marker happens to be visible.
        x = sum(e[0] for e in entries) / len(entries)
        y = sum(e[1] for e in entries) / len(entries)
        cs = sum(math.cos(e[2]) for e in entries)
        sn = sum(math.sin(e[2]) for e in entries)
        return x, y, math.atan2(sn, cs), entries[0][3]

    def _abs_from_reading(self, reading):
        pose = self._tag_pose(reading)
        if pose is None:
            return False
        x, y, theta, name = pose

        # Learn the wheel-to-floor distance ratio from long, straight pieces
        # between absolute marker fixes. The first fix also has a known survey
        # start at the same row.
        if self.calib_abs is None:
            start = None
            for candidate in self.starts:
                if abs(candidate.y - y) < 1.0:
                    start = candidate
                    break
            if start is not None and abs(reading.odometry_m) > 0.7:
                estimate = abs(x - start.x) / abs(reading.odometry_m)
                if 0.35 < estimate < 1.15:
                    self.scale = estimate
            self.calib_abs = (x, y, reading.odometry_m, reading.gyro_heading_rad)
        else:
            ox, oy, odom, gyro = self.calib_abs
            ds = abs(reading.odometry_m - odom)
            turn = abs(wrap(reading.gyro_heading_rad - gyro))
            displacement = math.hypot(x - ox, y - oy)
            if ds > 0.8 and turn < 0.18 and displacement > 0.2:
                estimate = displacement / ds
                if 0.35 < estimate < 1.15:
                    self.scale = 0.35 * self.scale + 0.65 * estimate
                self.calib_abs = (x, y, reading.odometry_m, reading.gyro_heading_rad)
            elif turn >= 0.18:
                self.calib_abs = (x, y, reading.odometry_m, reading.gyro_heading_rad)

        self.x, self.y = x, y
        self.heading_offset = wrap(theta - reading.gyro_heading_rad)
        self.theta = theta
        self.last_odom = reading.odometry_m
        self.last_gyro = reading.gyro_heading_rad
        self.tick = reading.tick
        self.last_name = name
        return True

    def update(self, reading):
        odom_delta = reading.odometry_m - self.last_odom
        gyro_delta = reading.gyro_heading_rad - self.last_gyro
        old_heading = self.theta
        self.theta = wrap(self.heading_offset + reading.gyro_heading_rad)
        if self.x is not None and abs(odom_delta) > 1e-10:
            # Integrate distance at the midpoint heading. Gyro reports actual
            # ground rotation, while wheel odometry supplies signed travel.
            mid = old_heading + gyro_delta * 0.5
            distance = odom_delta * self.scale
            self.x += distance * math.cos(mid)
            self.y += distance * math.sin(mid)
        self.last_odom = reading.odometry_m
        self.last_gyro = reading.gyro_heading_rad
        self.tick = reading.tick
        self.lidar = reading.lidar_m
        self._abs_from_reading(reading)

    def row_from_marker(self):
        name = getattr(self, "last_name", "")
        try:
            index = int(name.rsplit("-", 1)[1])
            if 0 <= index < len(self.rows):
                return index
        except (ValueError, IndexError):
            pass
        return min(range(len(self.rows)), key=lambda i: abs(self.y - self.rows[i]))


def wheel_command(cart, localizer, left, right):
    # One-tick feedback keeps wheel lag and grip changes observable.
    cart.command(clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0), ticks=1)
    localizer.update(cart.observe(expose=True))


def steer(localizer, target_heading, velocity):
    """Convert signed forward speed and heading correction to wheel speeds."""
    error = wrap(target_heading - localizer.theta)
    omega = clamp(2.0 * error, -1.35, 1.35)
    left = velocity - omega * TRACK * 0.5
    right = velocity + omega * TRACK * 0.5
    return left, right


def go_to(cart, loc, x, y, tolerance=0.07, limit=450):
    for _ in range(limit):
        if loc.x is None:
            return False
        dx, dy = x - loc.x, y - loc.y
        distance = math.hypot(dx, dy)
        if distance <= tolerance:
            return True
        target = math.atan2(dy, dx)
        error = wrap(target - loc.theta)
        if abs(error) > 0.24:
            velocity = 0.0
            omega = clamp(2.0 * error, -1.25, 1.25)
            loc.heading_integral = 0.0
            left, right = -omega * TRACK * 0.5, omega * TRACK * 0.5
        else:
            velocity = clamp(1.1 * distance, 0.10, 0.82)
            loc.heading_integral = clamp(loc.heading_integral + 1.0 * error * DT,
                                         -0.9, 0.9)
            omega = clamp(1.8 * error + loc.heading_integral, -0.8, 0.8)
            left = velocity - omega * TRACK * 0.5
            right = velocity + omega * TRACK * 0.5
        wheel_command(cart, loc, left, right)
    return loc.x is not None and math.hypot(x - loc.x, y - loc.y) <= 0.18


def turn_to(cart, loc, heading, limit=100):
    for _ in range(limit):
        error = wrap(heading - loc.theta)
        if abs(error) < 0.035:
            return True
        omega = clamp(2.2 * error, -1.6, 1.6)
        wheel_command(cart, loc, -omega * TRACK * 0.5, omega * TRACK * 0.5)
    return abs(wrap(heading - loc.theta)) < 0.12


def main():
    cart = CartClient()
    survey = cart.layout
    reading = cart.observe(expose=True)
    loc = Localizer(cart, survey, reading)

    # The surveyed start list gives the initial heading, but not which of the
    # repeated aisle rows the hand-moved cart occupies. Move toward the west
    # markers until one fixes both the row and the global pose.
    if not reading.tags:
        # Face the direction of travel so the west-facing camera can see the
        # marker before reaching the junction.
        turn_to(cart, loc, math.pi, limit=120)
        route_side = "west"
        if loc.lidar[0] < 4.2:
            turn_to(cart, loc, 0.0, limit=100)
            if loc.lidar[0] > 4.2:
                route_side = "east"
            else:
                turn_to(cart, loc, math.pi, limit=100)
        for _ in range(300):
            desired = math.pi if route_side == "west" else 0.0
            error = wrap(desired - loc.theta)
            loc.heading_integral = clamp(loc.heading_integral + 1.0 * error * DT,
                                         -0.9, 0.9)
            omega = clamp(1.8 * error + loc.heading_integral, -0.8, 0.8)
            speed = 0.68 if route_side == "east" else 0.55
            wheel_command(cart, loc, speed - omega * TRACK * 0.5,
                          speed + omega * TRACK * 0.5)
            if getattr(loc, "last_name", ""):
                break
            front = loc.lidar[0]
            if route_side == "west" and front < 4.2:
                turn_to(cart, loc, 0.0, limit=100)
                if loc.lidar[0] > 4.2:
                    route_side = "east"
                else:
                    turn_to(cart, loc, math.pi, limit=100)
            elif route_side == "east" and front < 4.2:
                turn_to(cart, loc, math.pi, limit=100)
                if loc.lidar[0] > 4.2:
                    route_side = "west"
                else:
                    turn_to(cart, loc, 0.0, limit=100)

    if loc.x is None or not getattr(loc, "last_name", ""):
        cart.command(0.0, 0.0, ticks=3)
        cart.finish()
        return

    if reading.tags:
        route_side = "east" if getattr(loc, "last_name", "").startswith("east-") else "west"

    row_index = loc.row_from_marker()
    current_y = loc.rows[row_index]
    dock = survey.dock

    # Use the clear end of the current aisle. If the west lidar view found a
    # temporary blockage, enter the destination row from the east; when the
    # dock is on the blocked row, cross an alternate row before returning via
    # the west junction.
    if route_side == "east":
        current_safe_y = current_y - 0.35
        go_to(cart, loc, loc.x, current_safe_y, tolerance=0.06)
        go_to(cart, loc, survey.right_junction_x, current_safe_y, tolerance=0.07)
        if abs(current_y - dock.y) < 0.2:
            alternate = min((y for y in loc.rows if abs(y - current_y) > 0.2),
                            key=lambda y: abs(y - current_y))
            alternate_safe_y = alternate - 0.35
            go_to(cart, loc, survey.right_junction_x, alternate_safe_y, tolerance=0.07)
            go_to(cart, loc, survey.left_junction_x, alternate_safe_y, tolerance=0.07)
            go_to(cart, loc, survey.left_junction_x, alternate, tolerance=0.06)
            go_to(cart, loc, survey.left_junction_x, dock.y, tolerance=0.07)
        elif abs(current_y - dock.y) > 0.2:
            dock_safe_y = dock.y - 0.35
            go_to(cart, loc, survey.right_junction_x, dock_safe_y, tolerance=0.07)
            go_to(cart, loc, survey.left_junction_x, dock_safe_y, tolerance=0.07)
            go_to(cart, loc, survey.left_junction_x, dock.y, tolerance=0.06)
    elif abs(current_y - dock.y) > 0.2:
        go_to(cart, loc, survey.left_junction_x, current_y, tolerance=0.07)
        go_to(cart, loc, survey.left_junction_x, dock.y, tolerance=0.07)
    go_to(cart, loc, dock.x, dock.y, tolerance=0.045, limit=360)
    turn_to(cart, loc, dock.heading)

    # The west-row marker (or an alternate dock marker) remains in front at
    # the final heading. Re-localize and make short corrections until the
    # surveyed dock pose is reached.
    for _ in range(100):
        if loc.x is None:
            break
        dx, dy = dock.x - loc.x, dock.y - loc.y
        distance = math.hypot(dx, dy)
        heading_error = wrap(dock.heading - loc.theta)
        if distance < 0.055 and abs(heading_error) < 0.035:
            break
        if abs(heading_error) >= 0.035:
            omega = clamp(2.0 * heading_error, -0.55, 0.55)
            wheel_command(cart, loc, -omega * TRACK * 0.5, omega * TRACK * 0.5)
        else:
            target = math.atan2(dy, dx)
            err = wrap(target - loc.theta)
            if abs(err) > 0.12:
                omega = clamp(2.0 * err, -0.55, 0.55)
                wheel_command(cart, loc, -omega * TRACK * 0.5, omega * TRACK * 0.5)
            else:
                speed = clamp(1.4 * distance, 0.06, 0.24)
                # Maintain the dock heading, reversing if the target lies
                # behind the cart so the visible marker stays in view.
                along = dx * math.cos(dock.heading) + dy * math.sin(dock.heading)
                velocity = math.copysign(speed, along)
                l, r = steer(loc, dock.heading, velocity)
                wheel_command(cart, loc, l, r)

    # Drain wheel lag, check the settled pose, and repeat small corrections if
    # the stop itself moved the cart.
    for _ in range(4):
        for _ in range(3):
            cart.command(0.0, 0.0, ticks=1)
            loc.update(cart.observe(expose=True))
        if loc.x is None:
            break
        position_error = math.hypot(dock.x - loc.x, dock.y - loc.y)
        heading_error = abs(wrap(dock.heading - loc.theta))
        if position_error <= 0.12 and heading_error <= 0.07:
            break
        if position_error > 0.06:
            go_to(cart, loc, dock.x, dock.y, tolerance=0.035, limit=80)
        turn_to(cart, loc, dock.heading, limit=60)
    cart.finish()


if __name__ == "__main__":
    main()
