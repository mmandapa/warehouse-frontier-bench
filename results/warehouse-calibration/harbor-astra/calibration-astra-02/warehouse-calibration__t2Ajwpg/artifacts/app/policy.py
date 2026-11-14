"""Identify wheel response and load-dependent slip in two curved maneuvers."""

import math

from client import BayClient
from motion import CartParameters, DT, TRACK_M, LOAD_RETENTION, forecast, wrap


# Each phase contains two magnitudes for each wheel. The changing curvature
# and effort make base slip and load slip independently observable in x and y.
FORWARD = [
    (0, .4), (0, 1), (.4, 0), (1, 0), (1, 0), (1, 0),
    (1, .4), (1, 0), (1, .4), (1, .4), (1, 1), (1, 1), (1, 1),
]
REVERSE = [
    (-1, -1), (0, -1), (0, -1), (0, -1), (0, -1), (0, -.4),
    (0, -.7), (0, -1), (-.4, 0), (0, -1), (0, -1), (0, -1), (-1, 0),
]


def solve(matrix, target):
    """Small dense system, with partial pivoting."""
    a = [list(row) + [value] for row, value in zip(matrix, target)]
    n = len(a)
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        if abs(scale) < 1e-14:
            raise ValueError("Unobservable calibration")
        for j in range(col, n + 1):
            a[col][j] /= scale
        for row in range(n):
            if row != col:
                scale = a[row][col]
                for j in range(col, n + 1):
                    a[row][j] -= scale * a[col][j]
    return [row[-1] for row in a]


def least_squares(rows, targets):
    n = len(rows[0])
    normal = [[sum(row[i] * row[j] for row in rows)
               for j in range(n)] for i in range(n)]
    rhs = [sum(row[i] * value for row, value in zip(rows, targets))
           for i in range(n)]
    return solve(normal, rhs)


def fit_wheels(samples, bias):
    # Linear initial fit: gain and intercept for each wheel/direction.
    rows, targets = [], []
    for commands, gyro_delta in samples:
        row = [0.0] * 8
        for wheel, command in enumerate(commands):
            if command:
                direction = 0 if command > 0 else 1
                index = 4 * wheel + 2 * direction
                sign = (1 if wheel else -1) * (1 if command > 0 else -1)
                row[index] = sign * abs(command)
                row[index + 1] = sign
        rows.append(row)
        targets.append((gyro_delta / DT - bias) * TRACK_M)
    linear = least_squares(rows, targets)
    # Enforce the physical constraint that each wheel shares one deadband.
    gains = [linear[i] for i in (0, 2, 4, 6)]
    deadbands = [(-linear[4*w+1] / gains[2*w]
                  - linear[4*w+3] / gains[2*w+1]) / 2 for w in range(2)]
    for _ in range(3):
        jacobian, residuals = [], []
        for (commands, _), target in zip(samples, targets):
            row = [0.0] * 6
            predicted = 0.0
            for wheel, command in enumerate(commands):
                if command:
                    index = 2 * wheel + (command < 0)
                    sign = (1 if wheel else -1) * (1 if command > 0 else -1)
                    excess = abs(command) - deadbands[wheel]
                    predicted += sign * gains[index] * excess
                    row[index] = sign * excess
                    row[4 + wheel] = -sign * gains[index]
            jacobian.append(row)
            residuals.append(target - predicted)
        update = least_squares(jacobian, residuals)
        gains = [v + d for v, d in zip(gains, update[:4])]
        deadbands = [v + d for v, d in zip(deadbands, update[4:])]
    return deadbands, gains


def fit_slip(basis, displacement):
    """Fit (1 + base slip, load coefficient), respecting known bounds."""
    limits = ((.88, 1.14), (-.62, -.12))
    raw = solve(basis, displacement)
    candidates = []
    if all(lo <= value <= hi for value, (lo, hi) in zip(raw, limits)):
        return raw
    # A box-constrained quadratic has its minimum inside or on an edge.
    for fixed in range(2):
        free = 1 - fixed
        for bound in limits[fixed]:
            denom = sum(row[free] ** 2 for row in basis)
            value = sum(row[free] * (y - row[fixed] * bound)
                        for row, y in zip(basis, displacement)) / denom
            trial = [0.0, 0.0]
            trial[fixed] = bound
            trial[free] = max(limits[free][0], min(limits[free][1], value))
            error = sum((sum(a*b for a, b in zip(row, trial)) - y) ** 2
                        for row, y in zip(basis, displacement))
            candidates.append((error, trial))
    return min(candidates)[1]


def calibrate(bay):
    commands = [(0, 0)] + FORWARD + REVERSE
    samples, cameras = [], []
    previous_encoder = [0.0, 0.0]
    previous_gyro = 0.0
    lag = None
    tick = 0
    while lag is None or tick < len(commands) + lag:
        command = commands[tick] if tick < len(commands) else (0, 0)
        reading = bay.drive(*command)
        tick += 1
        applied = tuple((now - before) / DT for now, before
                        in zip(reading['encoders_m'], previous_encoder))
        # Suppress floating-point cancellation in the cumulative encoders.
        applied = tuple(round(value, 6) for value in applied)
        samples.append((applied, reading['gyro_rad'] - previous_gyro))
        previous_encoder = reading['encoders_m']
        previous_gyro = reading['gyro_rad']
        if lag is None and any(applied):
            lag = tick - 2
        if lag is not None and tick in (1 + len(FORWARD) + lag, len(commands) + lag):
            cameras.append((tick, bay.camera(), previous_gyro))

    # Physical camera heading removes gyro bias, including after a full turn.
    bias = sum(DT*t * wrap(gyro - pose[2]) for t, pose, gyro in cameras)
    bias /= sum((DT*t) ** 2 for t, _, _ in cameras)
    deadbands, gains = fit_wheels(samples, bias)

    load = heading = 0.0
    basis = [[0.0, 0.0], [0.0, 0.0]]
    prior_position = (0.0, 0.0)
    slips = []
    camera_index = 0
    for tick, (applied, gyro_delta) in enumerate(samples, 1):
        load = LOAD_RETENTION * load + (1 - LOAD_RETENTION) * sum(map(abs, applied)) / 2
        speeds = []
        for wheel, command in enumerate(applied):
            gain = gains[2*wheel + (command < 0)]
            speeds.append(gain * math.copysign(max(abs(command) - deadbands[wheel], 0), command))
        turn = gyro_delta - DT * bias
        half = turn / 2
        distance = DT * sum(speeds) / 2 * (math.sin(half) / half if half else 1)
        dx = distance * math.cos(heading + half)
        dy = distance * math.sin(heading + half)
        for row, delta in zip(basis, (dx, dy)):
            row[0] += delta
            row[1] += delta * load
        heading += turn
        if tick == cameras[camera_index][0]:
            pose = cameras[camera_index][1]
            displacement = [pose[i] - prior_position[i] for i in range(2)]
            slips.append(fit_slip(basis, displacement))
            basis = [[0.0, 0.0], [0.0, 0.0]]
            prior_position = pose[:2]
            camera_index += 1
            if camera_index == len(cameras):
                break
    return CartParameters(
        lag, tuple(deadbands), (gains[0], gains[2]), (gains[1], gains[3]),
        slips[0][0] - 1, slips[1][0] - 1, bias, slips[0][1], slips[1][1],
    )


def main():
    bay = BayClient()
    settings = calibrate(bay)
    sequences = bay.forecast_commands()
    bay.submit([forecast(settings, sequence) for sequence in sequences])


if __name__ == '__main__':
    main()
