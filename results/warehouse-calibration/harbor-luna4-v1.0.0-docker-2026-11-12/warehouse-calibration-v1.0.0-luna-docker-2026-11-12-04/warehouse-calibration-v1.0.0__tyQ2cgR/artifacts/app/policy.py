"""Calibrate the cart from delayed command, gyro, and camera readings."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56


def wrap(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def response(command, deadband, forward_gain, reverse_gain):
    gain = forward_gain if command >= 0.0 else reverse_gain
    return gain * math.copysign(max(abs(command) - deadband, 0.0), command)


def fit_line(points):
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    variance = sum((x - mean_x) ** 2 for x, _ in points)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / variance
    return slope, mean_y - slope * mean_x


def fit_wheel(points):
    positive = [sample for sample in points if sample[0] > 0.0]
    negative = [sample for sample in points if sample[0] < 0.0]

    forward_gain, forward_intercept = fit_line(positive)
    reverse_gain, reverse_intercept = fit_line(negative)
    forward_deadband = -forward_intercept / forward_gain
    reverse_deadband = reverse_intercept / reverse_gain

    # The model shares one deadband between directions. Averaging the two
    # independently measured offsets reduces the effect of rounded readings.
    deadband = (forward_deadband + reverse_deadband) / 2.0
    deadband = min(0.24, max(0.08, deadband))
    forward_gain = min(1.05, max(0.65, forward_gain))
    reverse_gain = min(1.05, max(0.65, reverse_gain))
    return deadband, forward_gain, reverse_gain


def snap_command(value, possible):
    # Encoder integrals are rounded to 1e-6 m, so a command delta is accurate
    # to about 2.5e-5. Snapping recovers the exact command sent to the bay.
    return min(possible, key=lambda command: abs(command - value))


def predict(commands, lag, deadbands, forward_gains, reverse_gains, slips):
    pending = [(0.0, 0.0)] * lag
    x = y = heading = 0.0
    for left, right in commands:
        pending.append((left, right))
        applied_left, applied_right = pending.pop(0)
        left_speed = response(
            applied_left, deadbands[0], forward_gains[0], reverse_gains[0]
        )
        right_speed = response(
            applied_right, deadbands[1], forward_gains[1], reverse_gains[1]
        )
        center_speed = (left_speed + right_speed) / 2.0
        slip = slips[0] if center_speed >= 0.0 else slips[1]
        distance = DT * center_speed * (1.0 + slip)
        turn = DT * (right_speed - left_speed) / TRACK
        half_turn = turn / 2.0
        arc_scale = math.sin(half_turn) / half_turn if turn else 1.0
        x += distance * arc_scale * math.cos(heading + half_turn)
        y += distance * arc_scale * math.sin(heading + half_turn)
        heading = wrap(heading + turn)
    return [x, y, heading]


def main():
    bay = BayClient()

    # The first three and final five zero commands make every probe observable
    # for any allowed delay (0 through 3 ticks).
    calibration = [(0.0, 0.0)] * 3
    calibration += [
        (0.4, 0.0),
        (0.7, 0.0),
        (1.0, 0.0),
        (0.0, 1.0),
        (0.0, 0.7),
        (0.0, 0.4),
        (-0.4, 0.0),
        (-0.7, 0.0),
        (-1.0, 0.0),
        (0.0, -1.0),
        (0.0, -0.7),
        (0.0, -0.4),
    ]
    calibration += [(0.0, 0.0)] * 5

    readings = [bay.drive(left, right) for left, right in calibration]
    camera = bay.camera()

    # Recover the applied command pairs from the differences of cumulative
    # encoder integrals. The lag is then a short alignment search.
    choices = sorted({0.0, *(left for left, _ in calibration), *(right for _, right in calibration)})
    applied = []
    previous = [0.0, 0.0]
    for reading in readings:
        pair = []
        for wheel in range(2):
            measured = (reading["encoders_m"][wheel] - previous[wheel]) / DT
            pair.append(snap_command(measured, choices))
            previous[wheel] = reading["encoders_m"][wheel]
        applied.append(tuple(pair))

    lag_errors = []
    for lag in range(4):
        error = 0.0
        for tick, actual in enumerate(applied):
            source = tick - lag
            expected = calibration[source] if source >= 0 else (0.0, 0.0)
            error += (actual[0] - expected[0]) ** 2 + (actual[1] - expected[1]) ** 2
        lag_errors.append(error)
    lag = min(range(4), key=lag_errors.__getitem__)

    # The camera's physical heading and final gyro reading give the constant
    # gyro bias. Our probe sequence turns by far less than one full revolution.
    bias = wrap(readings[-1]["gyro_rad"] - camera[2]) / (DT * len(readings))

    wheel_samples = [[], []]
    turns = []
    previous_gyro = 0.0
    for reading, (left_command, right_command) in zip(readings, applied):
        gyro_delta = reading["gyro_rad"] - previous_gyro
        previous_gyro = reading["gyro_rad"]
        turn = gyro_delta - DT * bias
        turns.append(turn)
        if left_command != 0.0:
            speed = -TRACK * turn / DT
            wheel_samples[0].append((left_command, speed))
        if right_command != 0.0:
            speed = TRACK * turn / DT
            wheel_samples[1].append((right_command, speed))

    wheel_fits = [fit_wheel(samples) for samples in wheel_samples]
    deadbands = [fit[0] for fit in wheel_fits]
    forward_gains = [fit[1] for fit in wheel_fits]
    reverse_gains = [fit[2] for fit in wheel_fits]

    # The camera's final x/y position is a linear combination of the forward
    # and reverse slip scales. The measured gyro increments provide each arc's
    # heading, while the fitted wheel curves provide its center speed.
    forward_x = forward_y = reverse_x = reverse_y = 0.0
    heading = 0.0
    for (left_command, right_command), turn in zip(applied, turns):
        left_speed = response(
            left_command, deadbands[0], forward_gains[0], reverse_gains[0]
        )
        right_speed = response(
            right_command, deadbands[1], forward_gains[1], reverse_gains[1]
        )
        center_speed = (left_speed + right_speed) / 2.0
        half_turn = turn / 2.0
        arc_scale = math.sin(half_turn) / half_turn if turn else 1.0
        distance = DT * center_speed * arc_scale
        dx = distance * math.cos(heading + half_turn)
        dy = distance * math.sin(heading + half_turn)
        if center_speed >= 0.0:
            forward_x += dx
            forward_y += dy
        else:
            reverse_x += dx
            reverse_y += dy
        heading += turn

    determinant = forward_x * reverse_y - forward_y * reverse_x
    if abs(determinant) > 1e-8:
        forward_scale = (camera[0] * reverse_y - camera[1] * reverse_x) / determinant
        reverse_scale = (forward_x * camera[1] - forward_y * camera[0]) / determinant
        forward_slip = forward_scale - 1.0
        reverse_slip = reverse_scale - 1.0
    else:
        # This calibration path is designed to make the two columns distinct;
        # retain a stable estimate if an unexpectedly degenerate path occurs.
        forward_slip = reverse_slip = 0.0
    forward_slip = min(0.15, max(-0.30, forward_slip))
    reverse_slip = min(0.15, max(-0.30, reverse_slip))

    sequences = bay.forecast_commands()
    poses = [
        predict(
            commands,
            lag,
            deadbands,
            forward_gains,
            reverse_gains,
            (forward_slip, reverse_slip),
        )
        for commands in sequences
    ]
    bay.submit(poses)


if __name__ == "__main__":
    main()
