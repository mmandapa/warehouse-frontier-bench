"""Identify wheel dynamics and load-dependent slip, then replay forecasts."""

import math

from client import BayClient
from motion import CartParameters, DT, TRACK_M, LOAD_RETENTION, forecast, wheel_response


# Isolated commands identify both forward gains and deadbands. The following
# arc puts low- and high-load displacement along different spatial directions,
# so one camera supplies two independent slip equations.
FORWARD = [
    (1.0, 0.0), (0.3, 0.0), (0.0, 0.3), (0.0, 1.0),
    (0.3, 1.0), (0.3, 1.0), (0.3, 1.0), (0.3, 1.0),
    (0.3, 1.0), (0.3, 1.0), (0.6, 1.0), (1.0, 1.0), (1.0, 1.0),
]
# The reverse arc begins under load, unloads during its turn, then accelerates.
# This separates reverse base slip from reverse load slip as well.
REVERSE = [
    (-1.0, -1.0), (-0.6, -1.0), (0.0, -1.0), (0.0, -1.0),
    (0.0, -1.0), (0.0, -0.3), (0.0, -0.6), (0.0, -0.6),
    (0.0, -0.6), (0.0, -0.6), (0.0, -1.0), (0.0, -1.0), (-0.6, -1.0),
]


def least_squares(rows, values):
    """Solve a small, full-rank least-squares system with partial pivoting."""
    n = len(rows[0])
    a = [[sum(row[i] * row[j] for row in rows) for j in range(n)]
         + [sum(row[i] * value for row, value in zip(rows, values))]
         for i in range(n)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda j: abs(a[j][i]))
        a[i], a[pivot] = a[pivot], a[i]
        divisor = a[i][i]
        for j in range(i, n + 1):
            a[i][j] /= divisor
        for k in range(n):
            if k != i:
                scale = a[k][i]
                for j in range(i, n + 1):
                    a[k][j] -= scale * a[i][j]
    return [a[i][-1] for i in range(n)]


def fit_wheels(applied, readings):
    # Fit accumulated gyro rather than its differences: rounding errors then
    # remain independent, instead of being amplified by differencing.
    rows, values = [], []
    cumulative = [0.0] * 5
    for tick, ((left, right), gyro) in enumerate(zip(applied, readings), 1):
        if left < 0 or right < 0:
            break
        row = [-left, float(left > 0), right, -float(right > 0), TRACK_M]
        cumulative = [a + b for a, b in zip(cumulative, row)]
        rows.append(cumulative[:])
        values.append(gyro * TRACK_M / DT)
    gl, il, gr, ir, bias = least_squares(rows, values)
    deadbands = (il / gl, ir / gr)

    rows, values = [], []
    cumulative = [0.0, 0.0]
    known = 0.0
    for tick, ((left, right), gyro) in enumerate(zip(applied, readings), 1):
        if left >= 0 and right >= 0:
            known += gr * max(right - deadbands[1], 0.0)
            known -= gl * max(left - deadbands[0], 0.0)
        else:
            cumulative[0] += max(-left - deadbands[0], 0.0)
            cumulative[1] -= max(-right - deadbands[1], 0.0)
            rows.append(cumulative[:])
            values.append(gyro * TRACK_M / DT - known - tick * TRACK_M * bias)
    reverse = least_squares(rows, values)
    return deadbands, (gl, gr), tuple(reverse), bias


def displacement_basis(commands, deadbands, forward, reverse):
    """Return spatial coefficients for (1 + slip) and load slip per sign."""
    heading = load = 0.0
    basis = [[0.0] * 4 for _ in range(2)]
    snapshots = []
    for left, right in commands:
        load = LOAD_RETENTION * load + (1 - LOAD_RETENTION) * (abs(left) + abs(right)) / 2
        vl = wheel_response(left, deadbands[0], forward[0], reverse[0])
        vr = wheel_response(right, deadbands[1], forward[1], reverse[1])
        turn = DT * (vr - vl) / TRACK_M
        half = turn / 2
        distance = DT * (vl + vr) / 2 * (math.sin(half) / half if half else 1.0)
        column = 0 if vl + vr >= 0 else 2
        for axis, direction in enumerate((math.cos(heading + half), math.sin(heading + half))):
            component = distance * direction
            basis[axis][column] += component
            basis[axis][column + 1] += component * load
        heading += turn
        snapshots.append([row[:] for row in basis])
    return snapshots


def fit_slip(matrix, displacement):
    """Constrained fit using the published physical parameter bounds."""
    x, lx = matrix[0]
    y, ly = matrix[1]
    dx, dy = displacement
    determinant = x * ly - y * lx
    a = (dx * ly - dy * lx) / determinant
    b = (x * dy - y * dx) / determinant
    if .88 <= a <= 1.14 and -.62 <= b <= -.12:
        return a - 1, b
    candidates = []
    for a in (.88, 1.14):
        b = max(-.62, min(-.12, (lx * (dx - a * x) + ly * (dy - a * y)) / (lx * lx + ly * ly)))
        candidates.append((a, b))
    for b in (-.62, -.12):
        a = max(.88, min(1.14, (x * (dx - b * lx) + y * (dy - b * ly)) / (x * x + y * y)))
        candidates.append((a, b))
    a, b = min(candidates, key=lambda v: (x * v[0] + lx * v[1] - dx) ** 2
               + (y * v[0] + ly * v[1] - dy) ** 2)
    return a - 1, b


def calibration_tail(lag, deadbands, forward, reverse):
    """Use ticks saved by a short delay to improve camera conditioning."""
    if lag == 3:
        return [(0.0, 0.0)] * 3
    commands = FORWARD + REVERSE
    basis = displacement_basis(commands, deadbands, forward, reverse)[-1]
    x, lx = basis[0][2:]
    y, ly = basis[1][2:]
    heading = load = 0.0
    for left, right in commands:
        load = LOAD_RETENTION * load + (1 - LOAD_RETENTION) * (abs(left) + abs(right)) / 2
        vl = wheel_response(left, deadbands[0], forward[0], reverse[0])
        vr = wheel_response(right, deadbands[1], forward[1], reverse[1])
        heading += DT * (vr - vl) / TRACK_M

    options = []
    for left in (0.0, -0.3, -0.6, -1.0):
        for right in (0.0, -0.3, -0.6, -1.0):
            vl = wheel_response(left, deadbands[0], forward[0], reverse[0])
            vr = wheel_response(right, deadbands[1], forward[1], reverse[1])
            turn = DT * (vr - vl) / TRACK_M
            half = turn / 2
            distance = DT * (vl + vr) / 2 * (math.sin(half) / half if half else 1.0)
            options.append(((left, right), -(left + right) / 2, turn, distance))

    best_score, best_path = float('inf'), None

    def search(remaining, heading, load, x, y, lx, ly, path):
        nonlocal best_score, best_path
        if remaining == 0:
            determinant = x * ly - y * lx
            if abs(determinant) < 1e-12:
                return
            # Larger commands travel farther, so high-load extrapolation
            # deserves more weight than low-speed motion.
            score = max(weight * math.hypot(ly - effort * y, effort * x - lx)
                        / abs(determinant)
                        for effort, weight in ((.3, .2), (.6, .5), (1.0, .9)))
            if score < best_score:
                best_score, best_path = score, path
            return
        for command, effort, turn, distance in options:
            new_load = LOAD_RETENTION * load + (1 - LOAD_RETENTION) * effort
            dx = distance * math.cos(heading + turn / 2)
            dy = distance * math.sin(heading + turn / 2)
            search(remaining - 1, heading + turn, new_load,
                   x + dx, y + dy, lx + new_load * dx, ly + new_load * dy,
                   path + [command])

    search(3 - lag, heading, load, x, y, lx, ly, [])
    return best_path + [(0.0, 0.0)] * lag


def calibrate(bay):
    commands = [(0.0, 0.0)] + FORWARD + REVERSE
    lag = None
    readings = []
    first_pose = None
    for tick, command in enumerate(commands, 1):
        observation = bay.drive(*command)
        readings.append(observation['gyro_rad'])
        if lag is None and any(observation['encoders_m']):
            lag = tick - 2
        if lag is not None and tick == 1 + len(FORWARD) + lag:
            first_pose = bay.camera()
            first_tick = tick
    applied = ([(0.0, 0.0)] * lag + commands)[:len(commands)]
    deadbands, forward, reverse, _ = fit_wheels(applied, readings)
    tail = calibration_tail(lag, deadbands, forward, reverse)
    for command in tail:
        readings.append(bay.drive(*command)['gyro_rad'])
    commands += tail
    last_pose = bay.camera()
    applied = ([(0.0, 0.0)] * lag + commands)[:len(commands)]
    deadbands, forward, reverse, bias = fit_wheels(applied, readings)
    bases = displacement_basis(applied, deadbands, forward, reverse)
    forward_slip, forward_load = fit_slip(
        [row[:2] for row in bases[first_tick - 1]], first_pose[:2])
    reverse_slip, reverse_load = fit_slip(
        [row[2:] for row in bases[-1]],
        [last_pose[i] - first_pose[i] for i in range(2)])
    return CartParameters(lag, deadbands, forward, reverse,
                          forward_slip, reverse_slip, bias, forward_load, reverse_load)


def main():
    bay = BayClient()
    settings = calibrate(bay)
    sequences = bay.forecast_commands()
    bay.submit([forecast(settings, commands) for commands in sequences])


if __name__ == '__main__':
    main()
