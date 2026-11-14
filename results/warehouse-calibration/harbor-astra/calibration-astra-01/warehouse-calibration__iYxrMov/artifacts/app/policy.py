"""Identify wheel response and load-dependent slip in a 30-tick bay run."""

import math

from client import BayClient
from motion import CartParameters, DT, TRACK_M, forecast, wheel_response


# The curved paths make the displacement at different motor loads point in
# different directions, so each camera supplies two independent slip equations.
FORWARD = [
    (0.0, 1.0), (0.0, 0.4), (0.4, 0.0), (1.0, 0.0),
    (1.0, 0.0), (1.0, 0.0), (1.0, 0.0), (1.0, 0.0),
    (1.0, 0.0), (1.0, 0.4), (1.0, 1.0), (1.0, 1.0), (1.0, 1.0),
]
REVERSE = [
    (-1.0, -1.0), (-1.0, -1.0), (-1.0, 0.0), (-1.0, 0.0),
    (-1.0, 0.0), (0.0, 0.0), (-1.0, 0.0), (-0.4, 0.0),
    (-1.0, 0.0), (0.0, -0.4), (-1.0, 0.0), (-1.0, 0.0), (0.0, -1.0),
    (-1.0, 0.0), (-1.0, 0.0), (-1.0, 0.0),
]


def fit_slip(a, b, displacement):
    """Two-variable bounded least squares, including all boundary minima."""
    def dot(u, v):
        return sum(x * y for x, y in zip(u, v))

    def clip(x, lo, hi):
        return min(hi, max(lo, x))

    candidates = []
    determinant = a[0] * b[1] - a[1] * b[0]
    if abs(determinant) > 1e-12:
        alpha = (displacement[0] * b[1] - displacement[1] * b[0]) / determinant
        beta = (a[0] * displacement[1] - a[1] * displacement[0]) / determinant
        if .88 <= alpha <= 1.14 and -.62 <= beta <= -.12:
            candidates.append((alpha, beta))
    for alpha in (.88, 1.14):
        residual = [displacement[j] - alpha * a[j] for j in range(2)]
        beta = clip(dot(b, residual) / max(dot(b, b), 1e-20), -.62, -.12)
        candidates.append((alpha, beta))
    for beta in (-.62, -.12):
        residual = [displacement[j] - beta * b[j] for j in range(2)]
        alpha = clip(dot(a, residual) / max(dot(a, a), 1e-20), .88, 1.14)
        candidates.append((alpha, beta))
    return min(candidates, key=lambda p: sum(
        (p[0] * a[j] + p[1] * b[j] - displacement[j]) ** 2 for j in range(2)))


def calibrate(bay):
    commands = [(0.0, 0.0)] + FORWARD + REVERSE
    readings = []
    lag = None
    first_pose = None
    split = None
    for tick, (left, right) in enumerate(commands, 1):
        reading = bay.drive(left, right)
        readings.append(reading)
        # The first nonzero command is sent on tick two.
        if lag is None and any(abs(v) > 1e-8 for v in reading['encoders_m']):
            lag = tick - 2
        if lag is not None and tick == 14 + lag:
            first_pose = bay.camera()
            split = tick
    last_pose = bay.camera()

    # Absolute camera heading removes gyro bias; unwrap using the initial
    # stationary gyro sample, whose bias estimate is already very accurate.
    initial_bias = readings[0]['gyro_rad'] / DT
    gyro_total = readings[-1]['gyro_rad']
    heading_estimate = gyro_total - len(readings) * DT * initial_bias
    unwrapped = last_pose[2] + 2 * math.pi * round(
        (heading_estimate - last_pose[2]) / (2 * math.pi))
    bias = (gyro_total - unwrapped) / (len(readings) * DT)

    applied = [(0.0, 0.0)] * lag + commands[:len(commands) - lag]
    samples = [[[], []], [[], []]]
    previous_gyro = 0.0
    for command, reading in zip(applied, readings):
        difference = (reading['gyro_rad'] - previous_gyro) / DT - bias
        previous_gyro = reading['gyro_rad']
        for wheel in range(2):
            value = command[wheel]
            if value and command[1 - wheel] == 0:
                speed = difference * TRACK_M * (-1 if wheel == 0 else 1)
                samples[wheel][int(value < 0)].append((abs(value), abs(speed)))

    deadbands = []
    gains = [[], []]
    for wheel in range(2):
        estimates = []
        for direction in range(2):
            points = samples[wheel][direction]
            low = [v for u, v in points if u == .4]
            high = [v for u, v in points if u == 1.0]
            lo, hi = sum(low) / len(low), sum(high) / len(high)
            gain = (hi - lo) / .6
            estimates.append(.4 - lo / gain)
        deadband = sum(estimates) / 2
        deadbands.append(deadband)
        for direction in range(2):
            points = samples[wheel][direction]
            gains[direction].append(sum((u - deadband) * v for u, v in points)
                                    / sum((u - deadband) ** 2 for u, v in points))

    # Accumulate the coefficients of (1 + base_slip) and load_slip for
    # each measured displacement. Load and heading do not depend on slip.
    bases = [[[0.0, 0.0], [0.0, 0.0]] for _ in range(2)]
    load = heading = 0.0
    for index, (left, right) in enumerate(applied):
        load = .82 * load + .18 * (abs(left) + abs(right)) / 2
        vl = wheel_response(left, deadbands[0], gains[0][0], gains[1][0])
        vr = wheel_response(right, deadbands[1], gains[0][1], gains[1][1])
        turn = DT * (vr - vl) / TRACK_M
        half = turn / 2
        distance = DT * (vl + vr) / 2 * (math.sin(half) / half if half else 1.0)
        vector = (distance * math.cos(heading + half), distance * math.sin(heading + half))
        a, b = bases[int(index >= split)]
        for j in range(2):
            a[j] += vector[j]
            b[j] += vector[j] * load
        heading += turn
    forward = fit_slip(*bases[0], first_pose[:2])
    reverse = fit_slip(*bases[1], [last_pose[j] - first_pose[j] for j in range(2)])
    return CartParameters(lag, tuple(deadbands), tuple(gains[0]), tuple(gains[1]),
                          forward[0] - 1, reverse[0] - 1, bias, forward[1], reverse[1])


def main():
    bay = BayClient()
    parameters = calibrate(bay)
    sequences = bay.forecast_commands()
    bay.submit([forecast(parameters, commands) for commands in sequences])


if __name__ == '__main__':
    main()
