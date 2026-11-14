"""Calibrate a cart from encoder, gyro, and camera observations."""

import math

from client import BayClient
from motion import CartParameters, DT, TRACK_M, LOAD_RETENTION, forecast, wheel_response, wrap


PROBES = [
    (0.36, 0.0), (0.0, 0.64), (-0.92, 0.0), (0.0, -0.36),
    (0.64, 0.0), (0.0, 0.92), (-0.36, 0.0), (0.0, -0.92),
    (0.92, 0.0), (0.0, 0.36), (-0.64, 0.0), (0.0, -0.64),
]

# The last eighteen commands continue the calibration path. Curved runs make
# the two camera observations sensitive to slip in both directions.
PATH = ([(0.55, 0.95)] * 6 + [(-0.95, -0.55)] * 6 +
        [(0.45, 0.80)] * 3 + [(-0.75, -0.40)] * 3)


def solve(a, b):
    """Solve a small dense linear system with pivoting."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(m[row][col]))
        if abs(m[pivot][col]) < 1e-14:
            return [0.0] * n
        m[col], m[pivot] = m[pivot], m[col]
        scale = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            scale = m[row][col]
            for j in range(col, n + 1):
                m[row][j] -= scale * m[col][j]
    return [m[i][n] for i in range(n)]


def least_squares(rows, values, columns):
    normal = [[0.0] * columns for _ in range(columns)]
    rhs = [0.0] * columns
    for row, value in zip(rows, values):
        for i in range(columns):
            rhs[i] += row[i] * value
            for j in range(columns):
                normal[i][j] += row[i] * row[j]
    return solve(normal, rhs)


def applied_from_encoders(readings):
    result = []
    previous = [0.0, 0.0]
    for reading in readings:
        current = reading["encoders_m"]
        pair = []
        for side in range(2):
            # Commands are specified to hundredths; this removes the small
            # differencing noise from the rounded cumulative encoder values.
            pair.append(round((current[side] - previous[side]) / DT, 5))
        result.append(tuple(pair))
        previous = current
    return result


def fit_wheel(samples, side):
    """Fit one wheel's shared deadband and directional gains from gyro ticks."""
    factor = (-1.0 if side == 0 else 1.0) * DT / TRACK_M
    best = None
    for step in range(641):
        deadband = 0.08 + step * 0.00025
        rows, ys = [], []
        for command, gyro_delta in samples:
            qf = max(command - deadband, 0.0) if command > 0 else 0.0
            qr = min(command + deadband, 0.0) if command < 0 else 0.0
            rows.append([qf, qr, 1.0])
            ys.append(gyro_delta)
        coeff = least_squares(rows, ys, 3)
        error = sum((sum(x * y for x, y in zip(row, coeff)) - value) ** 2
                    for row, value in zip(rows, ys))
        if best is None or error < best[0]:
            best = (error, deadband, coeff)
    _, deadband, coeff = best
    forward_gain = coeff[0] / factor
    reverse_gain = coeff[1] / factor
    bias = coeff[2] / DT
    # Stay inside the documented physical ranges if measurement quantization
    # nudges a fit slightly over an endpoint.
    deadband = min(0.24, max(0.08, deadband))
    forward_gain = min(1.05, max(0.65, forward_gain))
    reverse_gain = min(1.05, max(0.65, reverse_gain))
    return deadband, forward_gain, reverse_gain, bias


def calibrate_wheels(applied, gyro_readings):
    increments = [gyro_readings[0]]
    increments.extend(gyro_readings[i] - gyro_readings[i - 1]
                      for i in range(1, len(gyro_readings)))
    samples = [[], []]
    # First twelve commands are isolated wheel probes. The first fifteen
    # applied ticks include all probes despite the unknown command delay.
    for tick, (left, right) in enumerate(applied[:15]):
        if (abs(left) > 0.25) != (abs(right) > 0.25):
            side = 0 if abs(left) > 0.25 else 1
            command = left if side == 0 else right
            samples[side].append((command, increments[tick]))
    fits = [fit_wheel(samples[i], i) for i in range(2)]
    deadbands = (fits[0][0], fits[1][0])
    forward = (fits[0][1], fits[1][1])
    reverse = (fits[0][2], fits[1][2])
    bias = sum(x[3] for x in fits) / 2.0

    # Refine the common gyro bias using every accumulated gyro reading and the
    # calibrated turn response. Cumulative readings average out rounding.
    turn_total = 0.0
    estimates = []
    for tick, (left, right) in enumerate(applied):
        vl = wheel_response(left, deadbands[0], forward[0], reverse[0])
        vr = wheel_response(right, deadbands[1], forward[1], reverse[1])
        turn_total += DT * (vr - vl) / TRACK_M
        estimates.append((gyro_readings[tick] - turn_total) / (DT * (tick + 1)))
    if estimates:
        estimates.sort()
        bias = estimates[len(estimates) // 2]
    return deadbands, forward, reverse, bias


def slip_features(applied, deadbands, forward, reverse, observations):
    """Build camera x/y equations linear in base slip and load slip."""
    rows = []
    values = []
    wanted = {tick: pose for tick, pose in observations}
    x = y = heading = load = 0.0
    total_fx = [0.0] * 4
    total_fy = [0.0] * 4
    for tick, (left, right) in enumerate(applied, 1):
        effort = (abs(left) + abs(right)) / 2.0
        load = LOAD_RETENTION * load + (1.0 - LOAD_RETENTION) * effort
        vl = wheel_response(left, deadbands[0], forward[0], reverse[0])
        vr = wheel_response(right, deadbands[1], forward[1], reverse[1])
        center = (vl + vr) / 2.0
        turn = DT * (vr - vl) / TRACK_M
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        scale = DT * center * arc
        dx = scale * math.cos(heading + half)
        dy = scale * math.sin(heading + half)
        direction = 0 if center >= 0.0 else 1
        # Columns: forward A, forward A*load-coefficient, reverse A,
        # reverse A*load-coefficient. "A" is one plus base slip.
        fx = [0.0] * 4
        fy = [0.0] * 4
        fx[2 * direction] = dx
        fx[2 * direction + 1] = dx * load
        fy[2 * direction] = dy
        fy[2 * direction + 1] = dy * load
        for i in range(4):
            total_fx[i] += fx[i]
            total_fy[i] += fy[i]
        x += dx
        y += dy
        heading = wrap(heading + turn)
        if tick in wanted:
            pose = wanted[tick]
            rows.extend((total_fx[:], total_fy[:]))
            values.extend((pose[0], pose[1]))
    return rows, values


def fit_slip(applied, deadbands, forward, reverse, observations):
    rows, values = slip_features(applied, deadbands, forward, reverse, observations)
    params = least_squares(rows, values, 4)
    # Map the linear A and A*c representation back to the physical parameters.
    out = []
    for offset in (0, 2):
        a = min(1.14, max(0.88, params[offset]))
        c = params[offset + 1] / params[offset] if abs(params[offset]) > 1e-8 else -0.35
        c = min(-0.12, max(-0.62, c))
        out.append((a - 1.0, c))
    return out[0], out[1]


def infer_lag(commands, applied, encoder_readings):
    best_lag, best_error = 0, float("inf")
    for lag in range(4):
        error = 0.0
        for tick, reading in enumerate(encoder_readings):
            totals = [0.0, 0.0]
            for i in range(tick + 1):
                source = i - lag
                if source >= 0:
                    totals[0] += DT * commands[source][0]
                    totals[1] += DT * commands[source][1]
            for side in range(2):
                error += abs(round(totals[side], 6) - reading["encoders_m"][side])
        if error < best_error:
            best_lag, best_error = lag, error
    return best_lag


def main():
    bay = BayClient()
    commands = PROBES + PATH
    encoder_readings = []
    gyro_readings = []
    observations = []
    for tick, (left, right) in enumerate(commands, 1):
        reading = bay.drive(left, right)
        encoder_readings.append(reading)
        gyro_readings.append(reading["gyro_rad"])
        if tick == 15:
            observations.append((tick, bay.camera()))
    observations.append((30, bay.camera()))

    applied = applied_from_encoders(encoder_readings)
    lag = infer_lag(commands, applied, encoder_readings)
    deadbands, forward, reverse, bias = calibrate_wheels(applied, gyro_readings)
    (forward_slip, forward_load), (reverse_slip, reverse_load) = fit_slip(
        applied, deadbands, forward, reverse, observations)
    settings = CartParameters(
        lag, deadbands, forward, reverse, forward_slip, reverse_slip, bias,
        forward_load, reverse_load,
    )

    sequences = bay.forecast_commands()
    poses = [list(forecast(settings, sequence)) for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
