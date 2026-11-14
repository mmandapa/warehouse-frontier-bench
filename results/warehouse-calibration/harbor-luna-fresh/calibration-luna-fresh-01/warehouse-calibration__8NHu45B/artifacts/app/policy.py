from client import BayClient
import math


DT = 0.2
TRACK = 0.56
RETENTION = 0.82

# These commands keep each travel direction for one camera interval.  The
# right wheel is usually driven harder, which gives the camera a changing
# direction of travel as well as a changing motor load.
CAL = [
    (0.30, 0.90), (0.40, 0.95), (0.55, 0.98), (0.65, 0.92),
    (0.75, 0.99), (0.32, 0.78), (0.45, 0.88), (0.60, 0.95),
    (0.70, 0.98), (0.35, 0.72), (0.50, 0.85), (0.62, 0.94),
    (0.77, 0.99), (0.42, 0.80), (0.58, 0.90),
    (-0.30, -0.55), (-0.38, -0.62), (-0.45, -0.70),
    (-0.50, -0.78), (-0.32, -0.72), (-0.42, -0.85),
    (-0.55, -0.92), (-0.62, -0.98), (-0.35, -0.80),
    (-0.48, -0.94), (-0.65, -0.99), (-0.72, -0.90),
] + [(0.0, 0.0)] * 3


def solve_linear(a, b):
    """Small dense linear system with pivoting."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-14:
            return [0.0] * n
        m[col], m[pivot] = m[pivot], m[col]
        d = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= d
        for r in range(n):
            if r == col:
                continue
            q = m[r][col]
            if q:
                for j in range(col, n + 1):
                    m[r][j] -= q * m[col][j]
    return [m[i][n] for i in range(n)]


def regress(rows, values, weights=None):
    n = len(rows[0])
    gram = [[0.0] * n for _ in range(n)]
    rhs = [0.0] * n
    if weights is None:
        weights = [1.0] * len(rows)
    for row, value, weight in zip(rows, values, weights):
        for i in range(n):
            rhs[i] += weight * row[i] * value
            for j in range(i, n):
                gram[i][j] += weight * row[i] * row[j]
    for i in range(n):
        for j in range(i):
            gram[i][j] = gram[j][i]
    return solve_linear(gram, rhs)


def qvalue(command, deadband):
    if command > 0:
        return max(command - deadband, 0.0)
    if command < 0:
        return -max(-command - deadband, 0.0)
    return 0.0


def gyro_fit(commands, gyros, camera_angles):
    # The five linear parameters are the four directional wheel gains and
    # the constant gyro bias.  Search only the two shared wheel deadbands.
    deltas = [gyros[0]] + [gyros[i] - gyros[i - 1] for i in range(1, len(gyros))]
    choices = [i / 1000.0 for i in range(80, 241)]

    def evaluate(db_left, db_right, include_camera=False):
        rows = []
        values = []
        weights = []
        scale = DT / TRACK
        for (left, right), observed in zip(commands, deltas):
            lf = qvalue(left, db_left) if left >= 0 else 0.0
            lr = qvalue(left, db_left) if left < 0 else 0.0
            rf = qvalue(right, db_right) if right >= 0 else 0.0
            rr = qvalue(right, db_right) if right < 0 else 0.0
            rows.append([-scale * lf, -scale * lr, scale * rf, scale * rr, DT])
            values.append(observed)
            weights.append(1.0)
        if include_camera:
            # Camera headings are wrapped; select the equivalent angle close
            # to the unwrapped gyro integral after removing its fitted bias.
            provisional = regress(rows, values, weights)
            for tick, angle in camera_angles:
                predicted = sum(
                    (row[0] * provisional[0] + row[1] * provisional[1] +
                     row[2] * provisional[2] + row[3] * provisional[3])
                    for row in rows[:tick]
                )
                target = angle + 2.0 * math.pi * round((predicted - angle) / (2.0 * math.pi))
                row_sum = [sum(row[j] for row in rows[:tick]) for j in range(4)] + [0.0]
                rows.append(row_sum)
                values.append(target)
                weights.append(1.0)
        params = regress(rows, values, weights)
        error = 0.0
        for row, value, weight in zip(rows, values, weights):
            residual = sum(a * b for a, b in zip(row, params)) - value
            error += weight * residual * residual
        return error, params

    # Search both deadbands together.  A one-at-a-time search can stall on a
    # narrow ridge because a gain increase partly compensates for a deadband
    # increase on each wheel.
    best_db = [0.16, 0.16]
    best_error, best_params = evaluate(*best_db, include_camera=True)
    for il in range(81):
        dl = 0.08 + il * 0.002
        for ir in range(81):
            dr = 0.08 + ir * 0.002
            error, params = evaluate(dl, dr, include_camera=True)
            if error < best_error:
                best_error, best_db, best_params = error, [dl, dr], params
    for _ in range(2):
        for wheel in range(2):
            center = best_db[wheel]
            lo = max(0.08, center - 0.003)
            hi = min(0.24, center + 0.003)
            for index in range(25):
                candidate = lo + (hi - lo) * index / 24.0
                trial = list(best_db)
                trial[wheel] = candidate
                error, params = evaluate(*trial, include_camera=True)
                if error < best_error:
                    best_error, best_db, best_params = error, trial, params
    # Camera heading gives an independent aggregate turn measurement.
    _, best_params = evaluate(best_db[0], best_db[1], include_camera=True)
    return best_db, best_params


def response(command, db, gain_forward, gain_reverse):
    gain = gain_forward if command >= 0 else gain_reverse
    return gain * qvalue(command, db)


def clamp(value, low, high):
    return max(low, min(high, value))


def fit_pair(columns, target):
    # Solve the two-dimensional camera equations for base and load slip.
    a, b = columns
    aa = a[0] * a[0] + a[1] * a[1]
    ab = a[0] * b[0] + a[1] * b[1]
    bb = b[0] * b[0] + b[1] * b[1]
    at = a[0] * target[0] + a[1] * target[1]
    bt = b[0] * target[0] + b[1] * target[1]
    det = aa * bb - ab * ab
    if abs(det) < 1e-12:
        # The chosen turning probes normally keep this well conditioned.  In
        # a nearly straight run, retain the prior for load slip and infer the
        # base factor from the displacement along the path.
        load_slip = -0.37
        base = (at - load_slip * ab) / max(aa, 1e-12)
        return base, load_slip
    return (at * bb - bt * ab) / det, (bt * aa - at * ab) / det


def calibrate_slip(commands, gains, deadbands, cameras):
    left_gain_f, left_gain_r, right_gain_f, right_gain_r, bias = gains
    load = 0.0
    heading = 0.0
    pose_x = pose_y = 0.0
    first_cols = [[0.0, 0.0], [0.0, 0.0]]
    all_terms = []
    for tick, (left, right) in enumerate(commands, 1):
        wl = response(left, deadbands[0], left_gain_f, left_gain_r)
        wr = response(right, deadbands[1], right_gain_f, right_gain_r)
        center = (wl + wr) / 2.0
        turn = DT * (wr - wl) / TRACK
        effort = (abs(left) + abs(right)) / 2.0
        load = RETENTION * load + (1.0 - RETENTION) * effort
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        direction = 0 if center >= 0 else 1
        factor = DT * center * arc
        vx = factor * math.cos(heading + half)
        vy = factor * math.sin(heading + half)
        all_terms.append((tick, direction, load, vx, vy, turn))
        if tick <= 15 and direction == 0:
            first_cols[0][0] += vx
            first_cols[0][1] += vy
            first_cols[1][0] += load * vx
            first_cols[1][1] += load * vy
        pose_x += vx
        pose_y += vy
        heading += turn

    cam1, cam2 = cameras
    forward_factor, forward_load = fit_pair(first_cols, cam1[:2])
    forward_slip = clamp(forward_factor - 1.0, -0.12, 0.14)
    forward_load = clamp(forward_load, -0.62, -0.12)

    # Camera two is relative to camera one.  Account for queued forward
    # commands that can still be applied after the first checkpoint.
    col_a = [0.0, 0.0]
    col_b = [0.0, 0.0]
    residual = [cam2[0] - cam1[0], cam2[1] - cam1[1]]
    for tick, direction, motor_load, vx, vy, turn in all_terms:
        if tick <= 15:
            continue
        if direction == 0:
            residual[0] -= vx * (1.0 + forward_slip + forward_load * motor_load)
            residual[1] -= vy * (1.0 + forward_slip + forward_load * motor_load)
        else:
            col_a[0] += vx
            col_a[1] += vy
            col_b[0] += motor_load * vx
            col_b[1] += motor_load * vy
    reverse_factor, reverse_load = fit_pair([col_a, col_b], residual)
    reverse_slip = clamp(reverse_factor - 1.0, -0.12, 0.14)
    reverse_load = clamp(reverse_load, -0.62, -0.12)
    return forward_slip, reverse_slip, forward_load, reverse_load


def predict(commands, lag, deadbands, gains, slips):
    pending = [(0.0, 0.0)] * lag
    x = y = heading = load = 0.0
    lf, lr, rf, rr, bias = gains
    sf, sr, kf, kr = slips
    for requested_left, requested_right in commands:
        pending.append((requested_left, requested_right))
        left, right = pending.pop(0)
        wl = response(left, deadbands[0], lf, lr)
        wr = response(right, deadbands[1], rf, rr)
        center = (wl + wr) / 2.0
        load = RETENTION * load + (1.0 - RETENTION) * (abs(left) + abs(right)) / 2.0
        direction_slip = sf if center >= 0 else sr
        load_slip = kf if center >= 0 else kr
        distance = DT * center * (1.0 + direction_slip + load_slip * load)
        turn = DT * (wr - wl) / TRACK
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        x += distance * arc * math.cos(heading + half)
        y += distance * arc * math.sin(heading + half)
        heading += turn
    # Use the same wrapped heading convention as the simulator.
    heading = (heading + math.pi) % (2.0 * math.pi) - math.pi
    return [x, y, heading]


def main():
    bay = BayClient()
    encoder_readings = []
    gyro_readings = []
    cameras = []
    for i, (left, right) in enumerate(CAL, 1):
        reading = bay.drive(left, right)
        encoder_readings.append(reading["encoders_m"])
        gyro_readings.append(reading["gyro_rad"])
        if i in (15, 30):
            cameras.append(bay.camera())

    # Encoder integrals are accumulated command values.  Their successive
    # differences reveal the delayed command actually applied on each tick.
    applied = []
    previous = [0.0, 0.0]
    for reading in encoder_readings:
        current = reading
        applied.append(((current[0] - previous[0]) / DT,
                        (current[1] - previous[1]) / DT))
        previous = current

    lag_scores = []
    for lag in range(4):
        error = 0.0
        for tick, actual in enumerate(applied):
            expected = CAL[tick - lag] if tick - lag >= 0 else (0.0, 0.0)
            error += abs(actual[0] - expected[0]) + abs(actual[1] - expected[1])
        lag_scores.append(error)
    lag = min(range(4), key=lambda value: lag_scores[value])

    deadbands, gains = gyro_fit(applied, gyro_readings,
                                [(15, cameras[0][2]), (30, cameras[1][2])])
    slips = calibrate_slip(applied, gains, deadbands, cameras)
    sequences = bay.forecast_commands()
    poses = [predict(sequence, lag, deadbands, gains, slips) for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
