"""Calibrate the cart, then simulate each requested command sequence."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
TAU = 2.0 * math.pi

# Four isolated wheel commands identify the two linear branches of each
# wheel's response curve. The short opposing-wheel turn puts the reverse
# measurements at a different heading, which makes the two slip values
# observable from the final camera position.
CALIBRATION = [
    (0.43, 0.0),
    (0.91, 0.0),
    (0.0, 0.47),
    (0.0, 0.93),
    (-0.88, 0.88),
    (-0.88, 0.88),
    (-0.88, 0.88),
    (-0.45, 0.0),
    (-0.95, 0.0),
    (0.0, -0.49),
    (0.0, -0.97),
    (0.0, 0.0),
    (0.0, 0.0),
    (0.0, 0.0),
]

PROBES = {
    (0.43, 0.0): (0, 0),
    (0.91, 0.0): (0, 1),
    (-0.45, 0.0): (0, 2),
    (-0.95, 0.0): (0, 3),
    (0.0, 0.47): (1, 0),
    (0.0, 0.93): (1, 1),
    (0.0, -0.49): (1, 2),
    (0.0, -0.97): (1, 3),
}


def wrap(angle):
    return (angle + math.pi) % TAU - math.pi


def wheel_response(command, deadband, forward_gain, reverse_gain):
    gain = forward_gain if command >= 0.0 else reverse_gain
    amount = max(abs(command) - deadband, 0.0)
    return gain * math.copysign(amount, command)


def fit_line(points):
    (x0, y0), (x1, y1) = points
    slope = (y1 - y0) / (x1 - x0)
    intercept = y0 - slope * x0
    return slope, intercept


def recover_lag(readings):
    """Match rounded encoder integrals against each allowed delay."""
    matches = []
    for lag in range(4):
        sums = [0.0, 0.0]
        exact = True
        for tick, reading in enumerate(readings, 1):
            command_index = tick - lag - 1
            applied = CALIBRATION[command_index] if command_index >= 0 else (0.0, 0.0)
            sums[0] += DT * applied[0]
            sums[1] += DT * applied[1]
            expected = [round(sums[0], 6), round(sums[1], 6)]
            if expected != reading:
                exact = False
                break
        if exact:
            matches.append(lag)
    if matches:
        return matches[0]
    # This should not be needed with the supplied noiseless encoder, but a
    # least-error fallback avoids making a protocol failure on a tie at a
    # decimal rounding boundary.
    scored = []
    for lag in range(4):
        sums = [0.0, 0.0]
        error = 0.0
        for tick, reading in enumerate(readings, 1):
            command_index = tick - lag - 1
            applied = CALIBRATION[command_index] if command_index >= 0 else (0.0, 0.0)
            sums[0] += DT * applied[0]
            sums[1] += DT * applied[1]
            error += sum((round(sums[i], 6) - reading[i]) ** 2 for i in range(2))
        scored.append((error, lag))
    return min(scored)[1]


def solve_slips(camera_pose, lag, deadbands, forward_gains, reverse_gains):
    """Solve the two linear camera-position equations for the slips."""
    heading = 0.0
    forward_x = forward_y = 0.0
    reverse_x = reverse_y = 0.0
    for tick in range(len(CALIBRATION)):
        command_index = tick - lag
        left, right = CALIBRATION[command_index] if command_index >= 0 else (0.0, 0.0)
        left_speed = wheel_response(left, deadbands[0], forward_gains[0], reverse_gains[0])
        right_speed = wheel_response(right, deadbands[1], forward_gains[1], reverse_gains[1])
        center = (left_speed + right_speed) / 2.0
        turn = DT * (right_speed - left_speed) / TRACK
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        distance = DT * center * arc
        dx = distance * math.cos(heading + half)
        dy = distance * math.sin(heading + half)
        if center >= 0.0:
            forward_x += dx
            forward_y += dy
        else:
            reverse_x += dx
            reverse_y += dy
        heading = wrap(heading + turn)

    target_x = camera_pose[0] - forward_x - reverse_x
    target_y = camera_pose[1] - forward_y - reverse_y
    determinant = forward_x * reverse_y - forward_y * reverse_x
    if abs(determinant) < 1e-10:
        # The chosen calibration turn keeps the two vectors well separated.
        # Retain valid physical values if an exceptionally rounded fit lands
        # close to the singular case.
        return 0.0, 0.0
    forward_slip = (target_x * reverse_y - target_y * reverse_x) / determinant
    reverse_slip = (forward_x * target_y - forward_y * target_x) / determinant
    return (max(-0.30, min(0.15, forward_slip)),
            max(-0.30, min(0.15, reverse_slip)))


def simulate(commands, lag, deadbands, forward_gains, reverse_gains,
             forward_slip, reverse_slip):
    pending = [(0.0, 0.0)] * lag
    x = y = heading = 0.0
    for command in commands:
        pending.append((float(command[0]), float(command[1])))
        left, right = pending.pop(0)
        left_speed = wheel_response(left, deadbands[0], forward_gains[0], reverse_gains[0])
        right_speed = wheel_response(right, deadbands[1], forward_gains[1], reverse_gains[1])
        center = (left_speed + right_speed) / 2.0
        slip = forward_slip if center >= 0.0 else reverse_slip
        distance = DT * center * (1.0 + slip)
        turn = DT * (right_speed - left_speed) / TRACK
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        x += distance * arc * math.cos(heading + half)
        y += distance * arc * math.sin(heading + half)
        heading = wrap(heading + turn)
    return [x, y, heading]


def main():
    bay = BayClient()
    encoder_readings = []
    gyro_readings = []
    for left, right in CALIBRATION:
        reading = bay.drive(left, right)
        encoder_readings.append(reading["encoders_m"])
        gyro_readings.append(reading["gyro_rad"])

    camera_pose = bay.camera()
    lag = recover_lag(encoder_readings)

    # The camera gives wrapped physical heading. Comparing it with the biased
    # gyro total recovers the constant bias over the calibration interval.
    gyro_total = gyro_readings[-1]
    bias = wrap(gyro_total - camera_pose[2]) / (DT * len(CALIBRATION))

    response_points = [[[], []], [[], []]]  # wheel, sign branch
    for tick, gyro in enumerate(gyro_readings):
        command_index = tick - lag
        applied = CALIBRATION[command_index] if command_index >= 0 else (0.0, 0.0)
        probe = PROBES.get(applied)
        if probe is None:
            continue
        previous_gyro = gyro_readings[tick - 1] if tick else 0.0
        turn = (gyro - previous_gyro) - DT * bias
        speed_difference = turn * TRACK / DT  # right speed minus left speed
        wheel, probe_index = probe
        command = applied[wheel]
        speed = -speed_difference if wheel == 0 else speed_difference
        branch = 0 if probe_index < 2 else 1
        response_points[wheel][branch].append((command, speed))

    deadbands = [0.0, 0.0]
    forward_gains = [0.0, 0.0]
    reverse_gains = [0.0, 0.0]
    for wheel in range(2):
        positive_gain, positive_intercept = fit_line(response_points[wheel][0])
        negative_gain, negative_intercept = fit_line(response_points[wheel][1])
        positive_deadband = -positive_intercept / positive_gain
        negative_deadband = negative_intercept / negative_gain
        deadbands[wheel] = (positive_deadband + negative_deadband) / 2.0
        forward_gains[wheel] = positive_gain
        reverse_gains[wheel] = negative_gain

    forward_slip, reverse_slip = solve_slips(
        camera_pose, lag, deadbands, forward_gains, reverse_gains
    )
    sequences = bay.forecast_commands()
    poses = [simulate(sequence, lag, deadbands, forward_gains, reverse_gains,
                      forward_slip, reverse_slip) for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
