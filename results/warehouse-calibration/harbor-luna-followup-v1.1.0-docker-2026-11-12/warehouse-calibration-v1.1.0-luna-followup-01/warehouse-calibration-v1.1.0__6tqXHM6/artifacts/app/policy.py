"""Calibrate the cart from encoder, gyro, and camera observations."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
RETENTION = 0.82

# Isolated wheel commands span both signs and several levels.  The later
# paired commands add translations at changing headings, speeds, and loads.
# The final zero commands let delayed commands drain.
PROBES = [
    (0.31, 0.0), (0.0, 0.31),
    (0.57, 0.0), (0.0, 0.57),
    (0.96, 0.0), (0.0, 0.96),
    (-0.31, 0.0), (0.0, -0.31),
    (-0.57, 0.0), (0.0, -0.57),
    (-0.96, 0.0), (0.0, -0.96),
    (0.36, 0.78), (0.82, 0.42), (-0.43, -0.88),
    (0.90, -0.90), (0.90, -0.90),
    (0.42, 0.42), (0.42, 0.42),
    (0.95, 0.95), (0.95, 0.95),
    (-0.42, -0.42), (-0.42, -0.42),
    (-0.95, -0.95), (-0.95, -0.95),
    (-0.90, 0.90), (-0.90, 0.90),
    (0.0, 0.0), (0.0, 0.0), (0.0, 0.0),
]


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def solve(a, b):
    """Solve a small dense linear system using pivoted elimination."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(m[row][col]))
        if abs(m[pivot][col]) < 1e-13:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        scale = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = m[row][col]
            if factor:
                for j in range(col, n + 1):
                    m[row][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def fit_wheels(applied, gyro):
    # The per-tick gyro rate is bias + (right speed - left speed) / track.
    rates = [gyro[0] / DT]
    for i in range(1, len(gyro)):
        rates.append((gyro[i] - gyro[i - 1]) / DT)

    best = None

    def consider(db_l, db_r):
        nonlocal best
        normal = [[0.0] * 5 for _ in range(5)]
        rhs = [0.0] * 5
        for (left, right), rate in zip(applied, rates):
            row = [1.0,
                   max(right - db_r, 0.0) / TRACK,
                   -max(-right - db_r, 0.0) / TRACK,
                   -max(left - db_l, 0.0) / TRACK,
                   max(-left - db_l, 0.0) / TRACK]
            for i in range(5):
                rhs[i] += row[i] * rate
                for j in range(5):
                    normal[i][j] += row[i] * row[j]
        co = solve(normal, rhs)
        if co is None or not all(0.645 <= v <= 1.055 for v in co[1:]):
            return
        err = 0.0
        for (left, right), rate in zip(applied, rates):
            pred = (co[0]
                    + co[1] * max(right - db_r, 0.0) / TRACK
                    - co[2] * max(-right - db_r, 0.0) / TRACK
                    - co[3] * max(left - db_l, 0.0) / TRACK
                    + co[4] * max(-left - db_l, 0.0) / TRACK)
            err += (pred - rate) ** 2
        if best is None or err < best[0]:
            best = (err, db_l, db_r, co)

    # Coarse search followed by a fine local grid handles the hinge at each
    # deadband without requiring an external optimizer.
    vals = [0.08 + i * 0.0025 for i in range(65)]
    for dl in vals:
        for dr in vals:
            consider(dl, dr)
    if best is None:
        return 0.16, 0.16, 0.85, 0.85, 0.85, 0.85, 0.0
    _, center_l, center_r, _ = best
    for dl_i in range(-25, 26):
        dl = min(0.24, max(0.08, center_l + dl_i * 0.0001))
        for dr_i in range(-25, 26):
            dr = min(0.24, max(0.08, center_r + dr_i * 0.0001))
            consider(dl, dr)
    _, db_l, db_r, co = best
    # Return order follows wheel order, then directions, and gyro bias.
    return db_l, db_r, co[3], co[4], co[1], co[2], co[0]


def response(command, deadband, forward, reverse):
    gain = forward if command >= 0.0 else reverse
    return gain * math.copysign(max(abs(command) - deadband, 0.0), command)


def applied_commands(commands, lag):
    return [commands[i - lag] if i >= lag else (0.0, 0.0)
            for i in range(len(commands))]


def find_lag(commands, encoders):
    increments = []
    previous = [0.0, 0.0]
    for value in encoders:
        increments.append(((value[0] - previous[0]) / DT,
                           (value[1] - previous[1]) / DT))
        previous = value
    scores = []
    for lag in range(4):
        error = 0.0
        for i, pair in enumerate(increments):
            expected = commands[i - lag] if i >= lag else (0.0, 0.0)
            error += (pair[0] - expected[0]) ** 2 + (pair[1] - expected[1]) ** 2
        scores.append(error)
    return min(range(4), key=lambda lag: scores[lag])


def fit_slip(applied, wheel, cameras):
    db_l, db_r, gl_f, gl_r, gr_f, gr_r, _bias = wheel
    load = 0.0
    heading = 0.0
    # Each camera contributes x and y equations in [1+slip_f, load_f,
    # 1+slip_r, load_r].
    rows = []
    for tick, (left, right) in enumerate(applied, 1):
        effort = (abs(left) + abs(right)) / 2.0
        load = RETENTION * load + (1.0 - RETENTION) * effort
        vl = response(left, db_l, gl_f, gl_r)
        vr = response(right, db_r, gr_f, gr_r)
        center = (vl + vr) / 2.0
        turn = DT * (vr - vl) / TRACK
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        scale = DT * center * arc
        qx = scale * math.cos(heading + half)
        qy = scale * math.sin(heading + half)
        col = 0 if center >= 0.0 else 2
        if tick <= max(cameras):
            rows.append((tick, col, (qx, qy, load)))
        heading = wrap(heading + turn)

    # Accumulate basis vectors up to each camera exposure.
    features = {tick: [0.0] * 4 for tick in cameras}
    for tick, col, (qx, qy, motor_load) in rows:
        for camera_tick in cameras:
            if tick <= camera_tick:
                features[camera_tick][col] += qx
                features[camera_tick][col + 1] += qx * motor_load
    # Use both coordinates from each reading.
    matrix = []
    target = []
    for tick, pose in cameras.items():
        f = features[tick]
        matrix.append(f[:])
        target.append(pose[0])
    y_features = {tick: [0.0] * 4 for tick in cameras}
    for tick, col, (qx, qy, motor_load) in rows:
        for camera_tick in cameras:
            if tick <= camera_tick:
                y_features[camera_tick][col] += qy
                y_features[camera_tick][col + 1] += qy * motor_load
    for tick, pose in cameras.items():
        matrix.append(y_features[tick][:])
        target.append(pose[1])

    bounds = [(0.88, 1.14), (-0.62, -0.12), (0.88, 1.14), (-0.62, -0.12)]
    result = solve(matrix, target)
    if result is not None and all(low <= v <= high
                                  for v, (low, high) in zip(result, bounds)):
        return result

    # Fall back to a bounded fit if rounding or a poorly conditioned path
    # pushes the exact four-equation solution outside the physical ranges.
    prior = [1.01, -0.37, 1.01, -0.37]
    normal = [[0.0] * 4 for _ in range(4)]
    rhs = [0.0] * 4
    for row, value in zip(matrix, target):
        for i in range(4):
            rhs[i] += row[i] * value
            for j in range(4):
                normal[i][j] += row[i] * row[j]
    ridge = 1e-7
    for i in range(4):
        normal[i][i] += ridge
        rhs[i] += ridge * prior[i]
    result = solve(normal, rhs) or prior
    return [min(high, max(low, value)) for value, (low, high) in zip(result, bounds)]


def predict(commands, lag, wheel, slip):
    db_l, db_r, gl_f, gl_r, gr_f, gr_r, bias = wheel
    scale_f, load_f, scale_r, load_r = slip
    queued = [(0.0, 0.0)] * lag
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    for command in commands:
        queued.append((float(command[0]), float(command[1])))
        left, right = queued.pop(0)
        load = RETENTION * load + (1.0 - RETENTION) * (abs(left) + abs(right)) / 2.0
        vl = response(left, db_l, gl_f, gl_r)
        vr = response(right, db_r, gr_f, gr_r)
        center = (vl + vr) / 2.0
        factor = (scale_f + load_f * load) if center >= 0.0 else (scale_r + load_r * load)
        distance = DT * center * factor
        turn = DT * (vr - vl) / TRACK
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        pose[0] += distance * arc * math.cos(pose[2] + half)
        pose[1] += distance * arc * math.sin(pose[2] + half)
        pose[2] = wrap(pose[2] + turn)
    return pose


def main():
    bay = BayClient()
    encoders = []
    gyros = []
    cameras = {}
    for tick, command in enumerate(PROBES, 1):
        reading = bay.drive(*command)
        encoders.append(reading["encoders_m"])
        gyros.append(reading["gyro_rad"])
        if tick == 15 or tick == 30:
            cameras[tick] = bay.camera()

    lag = find_lag(PROBES, encoders)
    applied = applied_commands(PROBES, lag)
    wheel = fit_wheels(applied, gyros)
    slip = fit_slip(applied, wheel, cameras)

    sequences = bay.forecast_commands()
    poses = [predict(sequence, lag, wheel, slip) for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
