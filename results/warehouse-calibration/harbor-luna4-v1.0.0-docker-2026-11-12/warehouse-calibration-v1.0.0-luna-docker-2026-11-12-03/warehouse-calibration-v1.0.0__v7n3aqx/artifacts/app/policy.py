"""Calibrate the cart from encoder, gyro, and camera measurements."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56


def mean(values):
    return sum(values) / len(values) if values else 0.0


def line_fit(points):
    """Return slope and intercept for a small list of (x, y) points."""
    xm = mean([p[0] for p in points])
    ym = mean([p[1] for p in points])
    xx = sum((x - xm) ** 2 for x, _ in points)
    if xx < 1e-15:
        return 0.85, -0.85 * 0.16
    slope = sum((x - xm) * (y - ym) for x, y in points) / xx
    return slope, ym - slope * xm


def wheel_parameters(applied, gyro, bias):
    """Estimate each wheel's forward/reverse gain and shared deadband."""
    result = [[None, None], [None, None]]  # [wheel][forward, reverse]
    factor = DT / TRACK
    for wheel in range(2):
        for direction in range(2):
            points = []
            for i, (left, right) in enumerate(applied):
                commands = (left, right)
                command = commands[wheel]
                if abs(command) < 1e-8 or (abs(commands[1 - wheel]) > 1e-8):
                    continue
                if (command > 0) != (direction == 0):
                    continue
                turn = gyro[i] - gyro[i - 1] if i else gyro[i]
                turn -= DT * bias
                speed = turn / factor if wheel == 1 else -turn / factor
                points.append((abs(command), abs(speed)))
            gain, intercept = line_fit(points)
            gain = min(1.05, max(0.65, gain))
            deadband = -intercept / gain
            deadband = min(0.24, max(0.08, deadband))
            result[wheel][direction] = (gain, deadband)
    return result


def response(command, params):
    if command == 0:
        return 0.0
    gain, deadband = params[0 if command > 0 else 1]
    return gain * math.copysign(max(abs(command) - deadband, 0.0), command)


def solve_slip(applied, params, camera_pose):
    """Fit the two slip factors to the camera's final x/y position."""
    heading = 0.0
    base_x = base_y = 0.0
    pos_x = pos_y = neg_x = neg_y = 0.0
    for left, right in applied:
        vl = response(left, params[0])
        vr = response(right, params[1])
        center = (vl + vr) * 0.5
        turn = DT * (vr - vl) / TRACK
        half = turn * 0.5
        arc = math.sin(half) / half if abs(half) > 1e-14 else 1.0
        distance = DT * center * arc
        dx = distance * math.cos(heading + half)
        dy = distance * math.sin(heading + half)
        base_x += dx
        base_y += dy
        if center >= 0:
            pos_x += dx
            pos_y += dy
        else:
            neg_x += dx
            neg_y += dy
        heading = (heading + turn + math.pi) % (2 * math.pi) - math.pi

    tx = camera_pose[0] - base_x
    ty = camera_pose[1] - base_y
    det = pos_x * neg_y - pos_y * neg_x
    if abs(det) > 1e-9:
        forward_slip = (tx * neg_y - ty * neg_x) / det
        reverse_slip = (pos_x * ty - pos_y * tx) / det
    else:
        # The designed probe path turns enough to avoid this normally. If
        # rounding or an unusual cart makes the basis nearly singular, use
        # the best one-dimensional projection for both directions.
        denom = pos_x * pos_x + pos_y * pos_y + neg_x * neg_x + neg_y * neg_y
        common = (tx * (pos_x + neg_x) + ty * (pos_y + neg_y)) / max(denom, 1e-12)
        forward_slip = reverse_slip = common
    return (min(0.15, max(-0.30, forward_slip)),
            min(0.15, max(-0.30, reverse_slip)))


def predict(commands, lag, params, slips):
    pending = [(0.0, 0.0)] * lag
    x = y = heading = 0.0
    for left, right in commands:
        pending.append((left, right))
        left, right = pending.pop(0)
        vl = response(left, params[0])
        vr = response(right, params[1])
        center = (vl + vr) * 0.5
        turn = DT * (vr - vl) / TRACK
        slip = slips[0] if center >= 0 else slips[1]
        distance = DT * center * (1.0 + slip)
        half = turn * 0.5
        arc = math.sin(half) / half if abs(half) > 1e-14 else 1.0
        x += distance * arc * math.cos(heading + half)
        y += distance * arc * math.sin(heading + half)
        heading = (heading + turn + math.pi) % (2 * math.pi) - math.pi
    return [x, y, heading]


def main():
    bay = BayClient()

    # The first nonzero encoder increment marks when command zero leaves the
    # delay queue. Distinct left wheel levels also serve as calibration data.
    commands = [
        (0.40, 0.0), (0.90, 0.0), (-0.40, 0.0), (-0.90, 0.0),
    ]
    readings = []
    previous_encoder = 0.0
    lag = None
    for tick, pair in enumerate(commands, 1):
        reading = bay.drive(*pair)
        readings.append(reading)
        encoder = reading["encoders_m"][0]
        if lag is None and abs(encoder - previous_encoder) > 1e-5:
            lag = tick - 1
        previous_encoder = encoder
    if lag is None:
        lag = 3

    # Three levels in each wheel/direction identify the affine response above
    # deadband. Grouping by direction also makes the camera slip fit well
    # conditioned because positive and negative travel occur at different
    # headings.
    probes = []
    for wheel, direction in ((0, 1), (1, 1), (0, -1), (1, -1)):
        for magnitude in (0.32, 0.65, 0.98):
            value = direction * magnitude
            probes.append((value, 0.0) if wheel == 0 else (0.0, value))
    probes.append((0.0, 0.0))
    commands.extend(probes)
    commands.extend([(0.0, 0.0)] * 3)  # flush every calibration command
    for pair in probes + [(0.0, 0.0)] * 3:
        readings.append(bay.drive(*pair))

    camera_pose = bay.camera()

    # Convert the known command history and recovered delay into the exact
    # applied history. The encoder readings are used only to identify delay.
    applied = []
    for i in range(len(commands)):
        source = i - lag
        applied.append(commands[source] if source >= 0 else (0.0, 0.0))
    gyro = [r["gyro_rad"] for r in readings]
    gyro_delta = [(gyro[i] - gyro[i - 1]) if i else gyro[0]
                  for i in range(len(gyro))]
    quiet = [gyro_delta[i] / DT for i, pair in enumerate(applied)
             if abs(pair[0]) < 1e-8 and abs(pair[1]) < 1e-8]
    bias = mean(quiet)

    params = wheel_parameters(applied, gyro, bias)
    # The camera gives an independent, more precise total-heading constraint
    # for gyro bias. Use the wheel fit to unwrap the camera heading.
    total_turn = 0.0
    for left, right in applied:
        total_turn += DT * (response(right, params[1]) -
                            response(left, params[0])) / TRACK
    camera_heading = camera_pose[2]
    unwrapped_camera = camera_heading + 2 * math.pi * round(
        (total_turn - camera_heading) / (2 * math.pi))
    camera_bias = (gyro[-1] - unwrapped_camera) / (DT * len(applied))
    if -0.06 <= camera_bias <= 0.06:
        bias = camera_bias
        params = wheel_parameters(applied, gyro, bias)

    slips = solve_slip(applied, params, camera_pose)
    sequences = bay.forecast_commands()
    poses = [predict(sequence, lag, params, slips) for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
