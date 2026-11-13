"""Calibrate the cart from encoder, gyro, and camera measurements."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
RETENTION = 0.82


# The varied commands cover both response directions and keep the cart turning
# while its load rises and falls.  The first fifteen ticks provide one camera
# fix; the second fix closes the full calibration trajectory.
CALIBRATION = [
    (0.38, 0.77), (-0.82, 0.35), (0.56, -0.91), (0.93, 0.46),
    (-0.43, -0.74), (0.70, 0.91), (-0.96, 0.28), (0.45, -0.62),
    (-0.67, -0.94), (0.81, 0.54), (-0.38, 0.88), (0.99, -0.47),
    (-0.75, 0.63), (0.52, 0.96), (-0.91, -0.51), (0.66, -0.83),
    (-0.55, 0.44), (0.89, 0.72), (-0.98, -0.36), (0.34, 0.57),
    (-0.72, 0.93), (0.77, -0.69), (-0.46, -0.86), (0.95, 0.39),
    (-0.61, 0.81), (0.49, -0.97), (-0.88, -0.58), (0.73, 0.48),
    (-0.33, 0.99), (0.86, -0.76),
]


def solve_linear(matrix, vector):
    """Solve a small dense system with pivoted Gaussian elimination."""
    n = len(vector)
    a = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-18:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor:
                for j in range(col, n + 1):
                    a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def least_squares(rows, values, ridge=0.0):
    n = len(rows[0])
    gram = [[0.0] * n for _ in range(n)]
    rhs = [0.0] * n
    for row, value in zip(rows, values):
        for i in range(n):
            rhs[i] += row[i] * value
            for j in range(n):
                gram[i][j] += row[i] * row[j]
    if ridge:
        for i in range(n):
            gram[i][i] += ridge
    coeff = solve_linear(gram, rhs)
    if coeff is None:
        return [0.0] * n, float("inf")
    error = 0.0
    for row, value in zip(rows, values):
        residual = sum(x * y for x, y in zip(row, coeff)) - value
        error += residual * residual
    return coeff, error


def applied_commands(sent, lag):
    return [(0.0, 0.0) if i < lag else sent[i - lag]
            for i in range(len(sent))]


def find_lag(sent, encoder_readings):
    best = None
    for lag in range(4):
        applied = applied_commands(sent, lag)
        previous = [0.0, 0.0]
        error = 0.0
        for reading, command in zip(encoder_readings, applied):
            for wheel in range(2):
                measured = (reading[wheel] - previous[wheel]) / DT
                residual = measured - command[wheel]
                error += residual * residual
                previous[wheel] = reading[wheel]
        if best is None or error < best[0]:
            best = error, lag
    return best[1]


def wheel_rows(commands, deadbands):
    rows = []
    for left, right in commands:
        lp, ln = max(left - deadbands[0], 0.0), max(-left - deadbands[0], 0.0)
        rp, rn = max(right - deadbands[1], 0.0), max(-right - deadbands[1], 0.0)
        # right minus left angular response, followed by the gyro bias term.
        rows.append([-lp, ln, rp, -rn, TRACK])
    return rows


def fit_wheels(commands, gyro_readings):
    increments = []
    prior = 0.0
    for reading in gyro_readings:
        increments.append((reading - prior) * TRACK / DT)
        prior = reading

    def evaluate(db_left, db_right):
        rows = wheel_rows(commands, (db_left, db_right))
        return least_squares(rows, increments)

    # Coarse search gives a reliable basin; the two deadbands are then refined
    # independently while all gains and the gyro bias are refit each time.
    best = (float("inf"), 0.15, 0.15)
    for i in range(81):
        dl = 0.08 + 0.002 * i
        for j in range(81):
            dr = 0.08 + 0.002 * j
            _, error = evaluate(dl, dr)
            if error < best[0]:
                best = (error, dl, dr)
    _, dl, dr = best
    for _ in range(3):
        lo, hi = max(0.08, dl - 0.0022), min(0.24, dl + 0.0022)
        candidates = [lo + (hi - lo) * i / 44 for i in range(45)]
        dl = min(candidates, key=lambda x: evaluate(x, dr)[1])
        lo, hi = max(0.08, dr - 0.0022), min(0.24, dr + 0.0022)
        candidates = [lo + (hi - lo) * i / 44 for i in range(45)]
        dr = min(candidates, key=lambda x: evaluate(dl, x)[1])

    coeff, _ = evaluate(dl, dr)
    # Parameters are ordered [left+, left-, right+, right-, bias].
    gains = ((max(0.65, min(1.05, coeff[0])), max(0.65, min(1.05, coeff[1])),),
             (max(0.65, min(1.05, coeff[2])), max(0.65, min(1.05, coeff[3])))
    return (dl, dr), gains, coeff[4]


def wheel_response(command, deadband, gains):
    gain = gains[0] if command >= 0.0 else gains[1]
    magnitude = max(abs(command) - deadband, 0.0)
    return math.copysign(gain * magnitude, command) if magnitude else 0.0


def trajectory(commands, deadbands, gains, slip):
    """Return per-tick nominal motion and poses, using a candidate parameter set."""
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    positions = []
    details = []
    for tick, (left, right) in enumerate(commands, 1):
        load = RETENTION * load + (1.0 - RETENTION) * (abs(left) + abs(right)) / 2.0
        vl = wheel_response(left, deadbands[0], gains[0])
        vr = wheel_response(right, deadbands[1], gains[1])
        center = (vl + vr) / 2.0
        turn = DT * (vr - vl) / TRACK
        half = turn / 2.0
        scale = math.sin(half) / half if half else 1.0
        direction = 0 if center >= 0.0 else 1
        base_slip, load_slip = slip[direction]
        distance = DT * center * (1.0 + base_slip + load_slip * load)
        pose[0] += distance * scale * math.cos(pose[2] + half)
        pose[1] += distance * scale * math.sin(pose[2] + half)
        pose[2] = (pose[2] + turn + math.pi) % (2.0 * math.pi) - math.pi
        positions.append(tuple(pose))
        details.append((center, load, turn, scale))
    return positions, details


def fit_slip(commands, deadbands, gains, cameras):
    """Fit forward/reverse base and load slip from the two camera positions."""
    # First use zero slips to obtain headings and the known nominal translation
    # vectors.  Slip scales translation, but has no effect on heading.
    positions, details = trajectory(commands, deadbands, gains,
                                    ((0.0, 0.0), (0.0, 0.0)))
    rows = []
    values = []
    for tick_count, observed in cameras:
        # Columns are forward base/load and reverse base/load.  Each camera
        # contributes independent x and y equations.
        sums = [[0.0, 0.0] for _ in range(4)]
        baseline_x = baseline_y = 0.0
        # Recover each tick's heading from the preceding nominal poses.
        for i in range(tick_count):
            center, load, turn, scale = details[i]
            heading = positions[i - 1][2] if i else 0.0
            half = turn / 2.0
            vx = DT * center * scale * math.cos(heading + half)
            vy = DT * center * scale * math.sin(heading + half)
            baseline_x += vx
            baseline_y += vy
            direction = 0 if center >= 0.0 else 1
            base_col, load_col = (0, 1) if direction == 0 else (2, 3)
            sums[base_col][0] += vx
            sums[base_col][1] += vy
            sums[load_col][0] += vx * load
            sums[load_col][1] += vy * load
        for axis in range(2):
            rows.append([sums[col][axis] for col in range(4)])
            values.append(observed[axis] - (baseline_x if axis == 0 else baseline_y))

    # Enforce the physical parameter ranges with a small bounded coordinate
    # descent.  This also handles a nearly dependent camera geometry safely.
    lower = [-0.12, -0.62, -0.12, -0.62]
    upper = [0.14, -0.12, 0.14, -0.12]
    params = [(lower[i] + upper[i]) / 2.0 for i in range(4)]
    col_norm = [sum(row[i] * row[i] for row in rows) for i in range(4)]
    for _ in range(400):
        max_change = 0.0
        for j in range(4):
            if col_norm[j] < 1e-20:
                continue
            residuals = [values[k] - sum(rows[k][i] * params[i] for i in range(4))
                         for k in range(len(rows))]
            delta = sum(rows[k][j] * residuals[k] for k in range(len(rows))) / col_norm[j]
            updated = min(upper[j], max(lower[j], params[j] + delta))
            max_change = max(max_change, abs(updated - params[j]))
            params[j] = updated
        if max_change < 1e-12:
            break
    return ((params[0], params[1]), (params[2], params[3]))


def forecast_pose(sequence, lag, deadbands, gains, slip):
    pending = [(0.0, 0.0)] * lag
    commands = []
    for pair in sequence:
        pending.append((float(pair[0]), float(pair[1])))
        commands.append(pending.pop(0))
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    for left, right in commands:
        load = RETENTION * load + (1.0 - RETENTION) * (abs(left) + abs(right)) / 2.0
        vl = wheel_response(left, deadbands[0], gains[0])
        vr = wheel_response(right, deadbands[1], gains[1])
        center = (vl + vr) / 2.0
        direction = 0 if center >= 0.0 else 1
        base_slip, load_slip = slip[direction]
        distance = DT * center * (1.0 + base_slip + load_slip * load)
        turn = DT * (vr - vl) / TRACK
        half = turn / 2.0
        scale = math.sin(half) / half if half else 1.0
        pose[0] += distance * scale * math.cos(pose[2] + half)
        pose[1] += distance * scale * math.sin(pose[2] + half)
        pose[2] = (pose[2] + turn + math.pi) % (2.0 * math.pi) - math.pi
    return pose


def main():
    bay = BayClient()
    sent = []
    encoders = []
    gyros = []
    camera_fixes = []
    for tick, command in enumerate(CALIBRATION, 1):
        reading = bay.drive(*command)
        sent.append(command)
        encoders.append(reading["encoders_m"])
        gyros.append(reading["gyro_rad"])
        if tick in (15, 30):
            camera_fixes.append((tick, bay.camera()))

    lag = find_lag(sent, encoders)
    actual_commands = applied_commands(sent, lag)
    deadbands, gains, _gyro_bias = fit_wheels(actual_commands, gyros)
    slip = fit_slip(actual_commands, deadbands, gains, camera_fixes)

    sequences = bay.forecast_commands()
    poses = [forecast_pose(sequence, lag, deadbands, gains, slip)
             for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
