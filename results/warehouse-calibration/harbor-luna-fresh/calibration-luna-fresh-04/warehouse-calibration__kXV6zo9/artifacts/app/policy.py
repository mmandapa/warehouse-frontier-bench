"""Calibrate the cart from its encoder, gyro, and camera observations."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
RETENTION = 0.82

# The two halves excite each wheel in both response directions, at several
# command magnitudes and with unequal left/right commands for gyro leverage.
CALIBRATION = [
    (0.20, 0.35), (0.35, 0.20), (0.55, 0.80), (0.80, 0.55),
    (0.95, 0.65), (0.65, 0.95), (0.28, 0.70), (0.70, 0.28),
    (0.88, 0.97), (0.97, 0.88), (0.42, 0.90), (0.90, 0.42),
    (0.24, 0.53), (0.53, 0.24), (0.75, 0.96),
    (-0.20, -0.35), (-0.35, -0.20), (-0.55, -0.80), (-0.80, -0.55),
    (-0.95, -0.65), (-0.65, -0.95), (-0.28, -0.70), (-0.70, -0.28),
    (-0.88, -0.97), (-0.97, -0.88), (-0.42, -0.90), (-0.90, -0.42),
    (-0.24, -0.53), (-0.53, -0.24), (-0.75, -0.96),
]

# Parameter order: two deadbands, forward gains L/R, reverse gains L/R,
# forward/reverse slip, forward/reverse load coefficient, gyro bias.
BOUNDS = (
    (0.08, 0.24), (0.08, 0.24),
    (0.65, 1.05), (0.65, 1.05), (0.65, 1.05), (0.65, 1.05),
    (-0.12, 0.14), (-0.12, 0.14),
    (-0.62, -0.12), (-0.62, -0.12),
    (-0.06, 0.06),
)


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def wheel(command, deadband, forward_gain, reverse_gain):
    gain = forward_gain if command >= 0.0 else reverse_gain
    mag = max(abs(command) - deadband, 0.0)
    return gain * (mag if command >= 0.0 else -mag)


def parameterize(q):
    return [lo + (hi - lo) * min(1.0, max(0.0, v))
            for v, (lo, hi) in zip(q, BOUNDS)]


def initial_q(values):
    return [(v - lo) / (hi - lo) for v, (lo, hi) in zip(values, BOUNDS)]


def simulate(commands, lag, p, keep_trace=False):
    dl, dr, fl, fr, rl, rr, slip_f, slip_r, load_f, load_r, bias = p
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    gyro = 0.0
    trace = []
    pending_gyro = []
    for i in range(len(commands)):
        j = i - lag
        left, right = commands[j] if j >= 0 else (0.0, 0.0)
        effort = (abs(left) + abs(right)) * 0.5
        load = RETENTION * load + (1.0 - RETENTION) * effort
        vl = wheel(left, dl, fl, rl)
        vr = wheel(right, dr, fr, rr)
        center = (vl + vr) * 0.5
        slip = slip_f if center >= 0.0 else slip_r
        load_slip = load_f if center >= 0.0 else load_r
        distance = DT * center * (1.0 + slip + load_slip * load)
        turn = DT * (vr - vl) / TRACK
        half = 0.5 * turn
        arc = math.sin(half) / half if half else 1.0
        heading = pose[2]
        pose[0] += distance * arc * math.cos(heading + half)
        pose[1] += distance * arc * math.sin(heading + half)
        pose[2] = wrap(heading + turn)
        gyro += turn + DT * bias
        trace.append((pose[0], pose[1], pose[2], gyro))
    return trace if keep_trace else trace[-1][:3]


def lag_from_encoders(commands, encoders):
    best_lag, best_score = 0, float("inf")
    for lag in range(4):
        sums = [0.0, 0.0]
        score = 0.0
        for i, observed in enumerate(encoders):
            j = i - lag
            applied = commands[j] if j >= 0 else (0.0, 0.0)
            for side in range(2):
                sums[side] += DT * applied[side]
                error = observed[side] - sums[side]
                score += error * error
        if score < best_score:
            best_lag, best_score = lag, score
    return best_lag


def residuals(q, lag, gyro_obs, camera_obs):
    trace = simulate(CALIBRATION, lag, parameterize(q), keep_trace=True)
    result = []
    # Readings are rounded to six decimal places; these scales also keep the
    # fit sensitive to the small bias and wheel-response differences.
    for row, observed in zip(trace, gyro_obs):
        result.append((row[3] - observed) / 0.00001)
    for tick, observed in camera_obs:
        row = trace[tick - 1]
        result.extend(((row[0] - observed[0]) / 0.001,
                       (row[1] - observed[1]) / 0.001,
                       wrap(row[2] - observed[2]) / 0.00001))
    return result


def solve_linear(a, b):
    """Solve a small dense system using pivoted Gaussian elimination."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-24:
            return [0.0] * n
        m[col], m[pivot] = m[pivot], m[col]
        scale = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= scale
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if factor:
                for j in range(col, n + 1):
                    m[r][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def fit(lag, gyro_obs, camera_obs):
    def cost(q):
        r = residuals(q, lag, gyro_obs, camera_obs)
        return sum(v * v for v in r)

    starts = [
        [0.5] * len(BOUNDS),
        initial_q([0.12, 0.21, 0.78, 0.97, 0.92, 0.72, 0.02, -0.04,
                   -0.43, -0.25, 0.01]),
        initial_q([0.21, 0.12, 0.97, 0.78, 0.72, 0.92, -0.04, 0.08,
                   -0.23, -0.53, -0.02]),
    ]
    # A few fixed, well-spread starts help with the deadband's piecewise-linear
    # response while keeping the policy deterministic.
    starts.extend([
        initial_q([0.09, 0.23, 0.70, 1.00, 1.00, 0.70, 0.10, -0.08,
                   -0.18, -0.58, 0.045]),
        initial_q([0.23, 0.09, 1.00, 0.70, 0.70, 1.00, -0.09, 0.12,
                   -0.58, -0.17, -0.045]),
    ])
    best_q, best_cost = starts[0], float("inf")
    for start in starts:
        q = [min(1.0, max(0.0, v)) for v in start]
        value = cost(q)
        damping = 1e-3
        for _ in range(65):
            base = residuals(q, lag, gyro_obs, camera_obs)
            n, m = len(q), len(base)
            jac = [[0.0] * n for _ in range(m)]
            step = 1e-5
            for col in range(n):
                qp, qm = q[:], q[:]
                qp[col] = min(1.0, q[col] + step)
                qm[col] = max(0.0, q[col] - step)
                rp = residuals(qp, lag, gyro_obs, camera_obs)
                rm = residuals(qm, lag, gyro_obs, camera_obs)
                width = qp[col] - qm[col]
                if width == 0.0:
                    continue
                for row in range(m):
                    jac[row][col] = (rp[row] - rm[row]) / width
            normal = [[0.0] * n for _ in range(n)]
            gradient = [0.0] * n
            for row, rv in enumerate(base):
                jr = jac[row]
                for a in range(n):
                    gradient[a] += jr[a] * rv
                    for b in range(a, n):
                        normal[a][b] += jr[a] * jr[b]
            for a in range(n):
                for b in range(a):
                    normal[a][b] = normal[b][a]
                normal[a][a] += damping * max(normal[a][a], 1.0)
            delta = solve_linear(normal, [-v for v in gradient])
            trial = [min(1.0, max(0.0, q[i] + delta[i])) for i in range(n)]
            trial_cost = cost(trial)
            if trial_cost < value:
                improvement = value - trial_cost
                q, value = trial, trial_cost
                damping = max(damping * 0.3, 1e-9)
                if improvement < 1e-8:
                    break
            else:
                damping = min(damping * 10.0, 1e12)
                if damping >= 1e12:
                    break
        if value < best_cost:
            best_q, best_cost = q, value
    return parameterize(best_q)


def main():
    bay = BayClient()
    encoder_obs = []
    gyro_obs = []
    camera_obs = []
    for tick, pair in enumerate(CALIBRATION, 1):
        reading = bay.drive(*pair)
        encoder_obs.append(reading["encoders_m"])
        gyro_obs.append(reading["gyro_rad"])
        if tick in (15, 30):
            camera_obs.append((tick, bay.camera()))

    lag = lag_from_encoders(CALIBRATION, encoder_obs)
    params = fit(lag, gyro_obs, camera_obs)
    sequences = bay.forecast_commands()
    poses = [simulate(commands, lag, params) for commands in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
