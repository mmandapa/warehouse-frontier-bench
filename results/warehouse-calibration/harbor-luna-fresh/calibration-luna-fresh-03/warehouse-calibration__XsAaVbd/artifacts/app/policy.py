from client import BayClient
import math


DT = 0.2
TRACK = 0.56
RETENTION = 0.82


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def make_calibration():
    commands = [(0.0, 0.0)]
    levels = (0.40, 1.0)
    # Test each wheel independently, so the gyro gives its speed directly.
    commands.extend((v, 0.0) for v in levels)
    commands.extend((0.0, v) for v in reversed(levels))
    # Bend through a wide arc while keeping the center speed forward. This
    # makes the two camera coordinates distinguish base slip from load slip.
    commands.extend([(0.28, 0.95)] * 9)
    # Let the motor load decay before measuring the reverse response.
    commands.extend([(0.0, 0.0)] * 3)
    commands.extend((v, 0.0) for v in (-x for x in levels))
    commands.extend((0.0, v) for v in (-x for x in reversed(levels)))
    # The reverse arc gives the second direction its own load and heading span.
    commands.extend([(-1.0, 0.0)] * 9)
    return commands


def infer_lag(commands, encoders):
    # Encoder integrals contain the queued commands themselves, independent of
    # deadband and traction. Use their rounded cumulative values to find delay.
    best_lag, best_score = 0, float("inf")
    for lag in range(4):
        total = [0.0, 0.0]
        score = 0.0
        for t, reading in enumerate(encoders):
            src = t - lag
            if src >= 0:
                total[0] += DT * commands[src][0]
                total[1] += DT * commands[src][1]
            for j in range(2):
                err = round(total[j], 6) - reading[j]
                score += err * err
        if score < best_score:
            best_lag, best_score = lag, score
    return best_lag


def solve_deadband(samples):
    # samples contain (signed command, signed wheel speed).
    best = None
    for n in range(1601):
        db = 0.08 + 0.0001 * n
        gains = []
        error = 0.0
        for sign in (1, -1):
            xx = []
            yy = []
            for command, speed in samples:
                if command * sign > 0:
                    xx.append(math.copysign(max(abs(command) - db, 0.0), command))
                    yy.append(speed)
            den = sum(x * x for x in xx)
            gain = sum(x * y for x, y in zip(xx, yy)) / den if den else 0.85
            gain = min(1.05, max(0.65, gain))
            gains.append(gain)
            error += sum((y - gain * x) ** 2 for x, y in zip(xx, yy))
        if best is None or error < best[0]:
            best = error, db, gains[0], gains[1]
    return best[1], best[2], best[3]


def applied_commands(commands, lag):
    return [(commands[t - lag] if t >= lag else (0.0, 0.0))
            for t in range(len(commands))]


def wheel_speeds(applied, deadbands, forward, reverse):
    out = []
    for pair in applied:
        row = []
        for j, command in enumerate(pair):
            gain = forward[j] if command >= 0 else reverse[j]
            row.append(gain * math.copysign(max(abs(command) - deadbands[j], 0.0), command)
                       if command else 0.0)
        out.append(row)
    return out


def linear_slip_fit(commands, applied, speeds, cameras, params):
    # Position is linear in [forward base slip, reverse base slip,
    # forward load slip, reverse load slip] when wheel responses are known.
    p_index = {1: (0, 2), -1: (1, 3)}
    # Accumulate separate x/y coefficient vectors for each camera pose.
    camera_by_tick = {tick: pose for tick, pose in cameras}
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    pending = [(0.0, 0.0)] * params[0]
    sums = [[0.0] * 4 for _ in range(2)]
    plains = [0.0, 0.0]
    rows, targets = [], []
    for t, commanded in enumerate(commands, 1):
        pending.append(commanded)
        app = pending.pop(0)
        left, right = speeds[t - 1]
        center = (left + right) / 2.0
        turn = DT * (right - left) / TRACK
        effort = (abs(app[0]) + abs(app[1])) / 2.0
        load = RETENTION * load + (1.0 - RETENTION) * effort
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        scale = DT * center * arc
        angle = pose[2] + half
        vec = (scale * math.cos(angle), scale * math.sin(angle))
        direction = 1 if center >= 0 else -1
        bi, li = p_index[direction]
        for axis in range(2):
            sums[axis][bi] += vec[axis]
            sums[axis][li] += load * vec[axis]
            plains[axis] += vec[axis]
        pose[0] += vec[0]
        pose[1] += vec[1]
        pose[2] = wrap(pose[2] + turn)
        if t in camera_by_tick:
            measured = camera_by_tick[t]
            for axis in range(2):
                rows.append(sums[axis][:])
                targets.append(measured[axis] - plains[axis])

    lo = [-0.12, -0.12, -0.62, -0.62]
    hi = [0.14, 0.14, -0.12, -0.12]
    mid = [(a + b) / 2.0 for a, b in zip(lo, hi)]
    # Coordinate minimization of the bounded regularized least-squares fit.
    mat = [[0.0] * 4 for _ in range(4)]
    vec = [0.0] * 4
    for row, target in zip(rows, targets):
        for i in range(4):
            vec[i] += row[i] * target
            for j in range(4):
                mat[i][j] += row[i] * row[j]
    ridge = 1e-7
    for i in range(4):
        mat[i][i] += ridge
        vec[i] += ridge * mid[i]
    fit = mid[:]
    for _ in range(500):
        max_change = 0.0
        for i in range(4):
            if mat[i][i] <= 1e-14:
                continue
            value = (vec[i] - sum(mat[i][j] * fit[j] for j in range(4) if j != i)) / mat[i][i]
            value = min(hi[i], max(lo[i], value))
            max_change = max(max_change, abs(value - fit[i]))
            fit[i] = value
        if max_change < 1e-10:
            break
    return fit


def simulate(commands, params):
    lag, deadbands, forward, reverse, slips, bias = params
    pending = [(0.0, 0.0)] * lag
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    for left_cmd, right_cmd in commands:
        pending.append((left_cmd, right_cmd))
        left_cmd, right_cmd = pending.pop(0)
        left = forward[0] if left_cmd >= 0 else reverse[0]
        right = forward[1] if right_cmd >= 0 else reverse[1]
        left = left * math.copysign(max(abs(left_cmd) - deadbands[0], 0.0), left_cmd) if left_cmd else 0.0
        right = right * math.copysign(max(abs(right_cmd) - deadbands[1], 0.0), right_cmd) if right_cmd else 0.0
        center = (left + right) / 2.0
        effort = (abs(left_cmd) + abs(right_cmd)) / 2.0
        load = RETENTION * load + (1.0 - RETENTION) * effort
        direction = 1 if center >= 0 else -1
        base = slips[0] if direction > 0 else slips[1]
        load_slip = slips[2] if direction > 0 else slips[3]
        distance = DT * center * (1.0 + base + load_slip * load)
        turn = DT * (right - left) / TRACK
        half = turn / 2.0
        arc = math.sin(half) / half if half else 1.0
        angle = pose[2] + half
        pose[0] += distance * arc * math.cos(angle)
        pose[1] += distance * arc * math.sin(angle)
        pose[2] = wrap(pose[2] + turn)
    return pose


def main():
    bay = BayClient()
    commands = make_calibration()
    encoders = []
    gyros = []
    cameras = []
    for tick, (left, right) in enumerate(commands, 1):
        result = bay.drive(left, right)
        encoders.append(result["encoders_m"])
        gyros.append(result["gyro_rad"])
        if tick == 14:
            cameras.append((tick, bay.camera()))
    cameras.append((30, bay.camera()))

    lag = infer_lag(commands, encoders)
    applied = applied_commands(commands, lag)
    # The initial zero command is applied as zero for every possible lag,
    # giving one clean gyro bias measurement before the cart moves.
    bias = gyros[0] / DT
    gyro_delta = [gyros[0]] + [gyros[i] - gyros[i - 1] for i in range(1, len(gyros))]
    samples = [[], []]
    for t, (left, right) in enumerate(applied):
        if left and not right:
            turn = gyro_delta[t] - DT * bias
            samples[0].append((left, -turn * TRACK / DT))
        elif right and not left:
            turn = gyro_delta[t] - DT * bias
            samples[1].append((right, turn * TRACK / DT))
    left_db, left_f, left_r = solve_deadband(samples[0])
    right_db, right_f, right_r = solve_deadband(samples[1])
    deadbands = [left_db, right_db]
    forward = [left_f, right_f]
    reverse = [left_r, right_r]
    speeds = wheel_speeds(applied, deadbands, forward, reverse)
    slips = linear_slip_fit(commands, applied, speeds, cameras, (lag,))

    sequences = bay.forecast_commands()
    params = (lag, deadbands, forward, reverse, slips, bias)
    bay.submit([simulate(sequence, params) for sequence in sequences])


if __name__ == "__main__":
    main()
