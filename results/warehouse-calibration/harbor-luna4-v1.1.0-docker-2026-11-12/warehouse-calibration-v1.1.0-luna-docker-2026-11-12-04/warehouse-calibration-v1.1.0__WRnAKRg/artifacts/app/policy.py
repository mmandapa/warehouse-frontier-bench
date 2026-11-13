"""Calibrate the cart from delayed encoder, gyro, and camera readings."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
K_TURN = DT / TRACK
TAU = 2.0 * math.pi


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def solve(a, b):
    """Small dense linear solve with partial pivoting."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-18:
            return [0.0] * n
        m[col], m[pivot] = m[pivot], m[col]
        scale = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= scale
        for r in range(n):
            if r == col:
                continue
            scale = m[r][col]
            for j in range(col, n + 1):
                m[r][j] -= scale * m[col][j]
    return [m[i][n] for i in range(n)]


def command_plan():
    # Five amplitudes in each wheel/direction expose the deadband and slope.
    levels = (0.18, 0.27, 0.46, 0.70, 0.96)
    commands = []
    for a in levels:
        commands.extend(((a, 0.0), (0.0, -a)))
    for a in levels:
        commands.extend(((-a, 0.0), (0.0, a)))
    # Varied forward and reverse arcs give the two camera poses leverage on
    # both directions' base slip and load response.
    commands.extend(((0.90, 0.40), (0.35, 0.95), (0.72, 0.50), (0.45, 0.90)))
    commands.extend(((-0.90, -0.40), (-0.35, -0.95), (-0.72, -0.50)))
    commands.extend(((0.0, 0.0),) * 3)
    return commands


def infer_lag(commands, encoders):
    best = None
    for lag in range(4):
        totals = [0.0, 0.0]
        error = 0.0
        for t, reading in enumerate(encoders, 1):
            src = t - lag - 1
            applied = commands[src] if src >= 0 else (0.0, 0.0)
            for w in range(2):
                totals[w] += DT * applied[w]
                error += abs(round(totals[w], 6) - reading[w])
        if best is None or error < best[0]:
            best = (error, lag)
    return best[1]


def camera_heading_unwrapped(camera_h, gyro_h):
    return camera_h + round((gyro_h - camera_h) / TAU) * TAU


def fit_wheels(applied, gyro, cameras):
    # Camera heading observes physical turn, so it gives a very accurate gyro
    # bias estimate before fitting the wheel responses.
    weighted_num = 0.0
    weighted_den = 0.0
    cam_headings = {}
    for tick, pose in cameras.items():
        h = camera_heading_unwrapped(pose[2], gyro[tick - 1])
        cam_headings[tick] = h
        scale = DT * tick
        weighted_num += scale * (gyro[tick - 1] - h)
        weighted_den += scale * scale
    bias = weighted_num / weighted_den if weighted_den else 0.0

    targets = [gyro[i] - gyro[i - 1] if i else gyro[0] for i in range(len(gyro))]
    targets = [v - DT * bias for v in targets]

    def features(c, d, left):
        if c >= 0.0:
            excess = max(c - d, 0.0)
            # Columns are left forward, left reverse, right forward, right reverse.
            return (-K_TURN * excess, 0.0, 0.0, 0.0) if left else (0.0, 0.0, K_TURN * excess, 0.0)
        excess = max(-c - d, 0.0)
        return (0.0, K_TURN * excess, 0.0, 0.0) if left else (0.0, 0.0, 0.0, -K_TURN * excess)

    def evaluate(dl, dr):
        rows = []
        ys = []
        cumulative = [0.0] * 4
        camera_ticks = set(cameras)
        for i, (left, right) in enumerate(applied, 1):
            fl = features(left, dl, True)
            fr = features(right, dr, False)
            row = tuple(fl[j] + fr[j] for j in range(4))
            rows.append(row)
            ys.append(targets[i - 1])
            for j in range(4):
                cumulative[j] += row[j]
            if i in camera_ticks:
                rows.append(tuple(cumulative))
                ys.append(cam_headings[i])

        normal = [[0.0] * 4 for _ in range(4)]
        rhs = [0.0] * 4
        for row, y in zip(rows, ys):
            for j in range(4):
                rhs[j] += row[j] * y
                for k in range(4):
                    normal[j][k] += row[j] * row[k]
        gains = solve(normal, rhs)
        err = 0.0
        for row, y in zip(rows, ys):
            pred = sum(row[j] * gains[j] for j in range(4))
            err += (pred - y) ** 2
        for g in gains:
            if g < 0.65:
                err += ((0.65 - g) * 0.02) ** 2
            elif g > 1.05:
                err += ((g - 1.05) * 0.02) ** 2
        return err, gains

    best = (float("inf"), 0.16, 0.16, [0.85] * 4)
    # A coarse grid finds the deadband basin; the fine pass resolves it well
    # below the heading tolerance.
    for i in range(81):
        dl = 0.08 + 0.002 * i
        for j in range(81):
            dr = 0.08 + 0.002 * j
            err, gains = evaluate(dl, dr)
            if err < best[0]:
                best = (err, dl, dr, gains)
    center_l, center_r = best[1], best[2]
    for i in range(-20, 21):
        dl = min(0.24, max(0.08, center_l + i * 0.0001))
        for j in range(-20, 21):
            dr = min(0.24, max(0.08, center_r + j * 0.0001))
            err, gains = evaluate(dl, dr)
            if err < best[0]:
                best = (err, dl, dr, gains)
    _, dl, dr, gains = best
    # Lf, Lr, Rf, Rr -> per-wheel forward/reverse.
    return dl, dr, (gains[0], gains[2]), (gains[1], gains[3]), bias


def fit_slip(applied, cameras, params):
    dl, dr, fwd, rev, _bias = params
    columns = [[], [], [], []]
    base = [0.0, 0.0]
    x = y = heading = load = 0.0
    checkpoints = {}
    for tick, (left, right) in enumerate(applied, 1):
        wl = (fwd[0] if left >= 0 else rev[0]) * math.copysign(max(abs(left) - dl, 0.0), left) if left else 0.0
        wr = (fwd[1] if right >= 0 else rev[1]) * math.copysign(max(abs(right) - dr, 0.0), right) if right else 0.0
        center = (wl + wr) * 0.5
        load = 0.82 * load + 0.18 * (abs(left) + abs(right)) * 0.5
        turn = K_TURN * (wr - wl)
        half = turn * 0.5
        arc = math.sin(half) / half if half else 1.0
        ds = DT * center * arc
        vx = ds * math.cos(heading + half)
        vy = ds * math.sin(heading + half)
        forward = center >= 0.0
        if forward:
            columns[0].append((vx, vy))
            columns[1].append((vx * load, vy * load))
            columns[2].append((0.0, 0.0))
            columns[3].append((0.0, 0.0))
        else:
            columns[0].append((0.0, 0.0))
            columns[1].append((0.0, 0.0))
            columns[2].append((vx, vy))
            columns[3].append((vx * load, vy * load))
        base[0] += vx
        base[1] += vy
        heading = wrap(heading + turn)
        if tick in cameras:
            checkpoints[tick] = (base[0], base[1], [sum(columns[j][i][0] for i in range(tick)) for j in range(4)],
                                 [sum(columns[j][i][1] for i in range(tick)) for j in range(4)])

    # Each camera contributes x and y equations for [forward base, forward
    # load, reverse base, reverse load] slip.
    rows = []
    ys = []
    for tick, pose in cameras.items():
        bx, by, cx, cy = checkpoints[tick]
        rows.append(cx)
        ys.append(pose[0] - bx)
        rows.append(cy)
        ys.append(pose[1] - by)
    normal = [[0.0] * 4 for _ in range(4)]
    rhs = [0.0] * 4
    for row, target in zip(rows, ys):
        for j in range(4):
            rhs[j] += row[j] * target
            for k in range(4):
                normal[j][k] += row[j] * row[k]
    prior = (0.01, -0.37, 0.01, -0.37)
    # Camera coordinates are rounded to millimeters, so keep weakly observed
    # combinations near the middle of the documented parameter ranges.
    strength = max(1e-12, sum(normal[i][i] for i in range(4)) * 1e-6)
    for j in range(4):
        normal[j][j] += strength
        rhs[j] += strength * prior[j]
    slip = solve(normal, rhs)
    return (min(0.14, max(-0.12, slip[0])),
            min(-0.12, max(-0.62, slip[1])),
            min(0.14, max(-0.12, slip[2])),
            min(-0.12, max(-0.62, slip[3])))


def predict(commands, lag, params, slip):
    dl, dr, fwd, rev, _bias = params
    sf, lf, sr, lr = slip
    pending = [(0.0, 0.0)] * lag
    x = y = heading = load = 0.0
    for left, right in commands:
        pending.append((left, right))
        left, right = pending.pop(0)
        wl = (fwd[0] if left >= 0 else rev[0]) * math.copysign(max(abs(left) - dl, 0.0), left) if left else 0.0
        wr = (fwd[1] if right >= 0 else rev[1]) * math.copysign(max(abs(right) - dr, 0.0), right) if right else 0.0
        center = (wl + wr) * 0.5
        load = 0.82 * load + 0.18 * (abs(left) + abs(right)) * 0.5
        slip_base, slip_load = (sf, lf) if center >= 0.0 else (sr, lr)
        ds = DT * center * (1.0 + slip_base + slip_load * load)
        turn = K_TURN * (wr - wl)
        half = turn * 0.5
        arc = math.sin(half) / half if half else 1.0
        x += ds * arc * math.cos(heading + half)
        y += ds * arc * math.sin(heading + half)
        heading = wrap(heading + turn)
    return [x, y, heading]


def main():
    bay = BayClient()
    commands = command_plan()
    encoders = []
    gyro = []
    cameras = {}
    for tick, (left, right) in enumerate(commands, 1):
        reading = bay.drive(left, right)
        encoders.append(reading["encoders_m"])
        gyro.append(reading["gyro_rad"])
        if tick in (20, 30):
            cameras[tick] = bay.camera()

    lag = infer_lag(commands, encoders)
    applied = [(0.0, 0.0)] * lag + commands[:30 - lag]
    # The list above has exactly 30 entries; queued commands beyond tick 30
    # are irrelevant to calibration and to each forecast endpoint.
    params = fit_wheels(applied, gyro, cameras)
    slip = fit_slip(applied, cameras, params)

    sequences = bay.forecast_commands()
    poses = [predict(seq, lag, params, slip) for seq in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
