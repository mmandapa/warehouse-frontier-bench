"""Calibrate the cart from encoder, gyro, and camera measurements."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
RETENTION = 0.82

# The levels are deliberately spread across the whole deadband range.  Swapping
# the wheel levels also gives the gyro independent information about both
# wheel gains.  All commands in a block have the same sign, so its camera
# displacement measures one slip direction at a time.
FORWARD = [
    (0.18, 0.88), (0.28, 0.98), (0.42, 0.72), (0.62, 0.90),
    (0.88, 0.28), (0.98, 0.18), (0.72, 0.42), (0.90, 0.62),
    (0.18, 0.42), (0.42, 0.18), (0.62, 0.98), (0.98, 0.62),
]
REVERSE = [(-r, -l) for l, r in FORWARD]
COMMANDS = FORWARD + [(0.0, 0.0)] * 3 + REVERSE + [(0.0, 0.0)] * 3


def solve(matrix, vector):
    """Solve a small dense linear system by pivoted elimination."""
    n = len(vector)
    a = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-14:
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


def fit_for_deadbands(samples, deadbands):
    # Parameter order: left forward/reverse gain, right forward/reverse gain,
    # then gyro bias.
    n = 5
    normal = [[0.0] * n for _ in range(n)]
    rhs = [0.0] * n
    scale = DT / TRACK
    for left, right, gyro_delta in samples:
        row = [0.0] * n
        for wheel, command in enumerate((left, right)):
            if command == 0.0:
                continue
            direction = 0 if command > 0.0 else 1
            amount = max(abs(command) - deadbands[wheel], 0.0)
            response = math.copysign(amount, command)
            index = wheel * 2 + direction
            row[index] += (-scale if wheel == 0 else scale) * response
        row[4] = DT
        for i in range(n):
            rhs[i] += row[i] * gyro_delta
            for j in range(n):
                normal[i][j] += row[i] * row[j]
    params = solve(normal, rhs)
    if params is None:
        return float("inf"), None
    # The physical parameter ranges are known.  Clamping only matters for a
    # poorly conditioned boundary candidate and keeps its simulation valid.
    gains = [min(1.05, max(0.65, p)) for p in params[:4]]
    bias = min(0.06, max(-0.06, params[4]))
    fitted = gains + [bias]
    error = 0.0
    for left, right, gyro_delta in samples:
        predicted = DT * bias
        for wheel, command in enumerate((left, right)):
            if command:
                direction = 0 if command > 0.0 else 1
                response = math.copysign(max(abs(command) - deadbands[wheel], 0.0), command)
                predicted += DT / TRACK * (1.0 if wheel else -1.0) * fitted[wheel * 2 + direction] * response
        error += (gyro_delta - predicted) ** 2
    return error, fitted


def fit_wheel_model(samples):
    best_error = float("inf")
    best_db = (0.16, 0.16)
    best_fit = None
    # A coarse grid locates the basin; a fine grid then resolves the deadbands
    # to substantially better precision than the rounded sensor readings.
    coarse = [0.08 + i * 0.004 for i in range(41)]
    for left_db in coarse:
        for right_db in coarse:
            error, params = fit_for_deadbands(samples, (left_db, right_db))
            if error < best_error:
                best_error, best_db, best_fit = error, (left_db, right_db), params
    left_values = [min(0.24, max(0.08, best_db[0] - 0.004 + i * 0.0001)) for i in range(81)]
    right_values = [min(0.24, max(0.08, best_db[1] - 0.004 + i * 0.0001)) for i in range(81)]
    for left_db in left_values:
        for right_db in right_values:
            error, params = fit_for_deadbands(samples, (left_db, right_db))
            if error < best_error:
                best_error, best_db, best_fit = error, (left_db, right_db), params
    return best_db, best_fit


def wheel_response(command, deadband, forward_gain, reverse_gain):
    gain = forward_gain if command >= 0.0 else reverse_gain
    return gain * math.copysign(max(abs(command) - deadband, 0.0), command)


def fit_slip(target, basis, load_basis):
    """Fit base slip and load coefficient from a measured 2-D displacement."""
    ax, ay = basis
    bx, by = load_basis
    tx, ty = target
    aa = ax * ax + ay * ay
    ab = ax * bx + ay * by
    bb = bx * bx + by * by
    at = ax * tx + ay * ty
    bt = bx * tx + by * ty
    det = aa * bb - ab * ab
    if det < 1e-10:
        # Near-straight probes make the two effects hard to distinguish.  A
        # small prior toward the middle of the stated range avoids wild fits.
        ridge = 1e-5
        aa += ridge
        bb += ridge
        at += ridge * 0.01
        bt += ridge * -0.37
        det = aa * bb - ab * ab
    if det <= 1e-14:
        slip, load_slip = 0.01, -0.37
    else:
        slip = (at * bb - bt * ab) / det
        load_slip = (bt * aa - at * ab) / det
    slip = min(0.14, max(-0.12, slip))
    load_slip = min(-0.12, max(-0.62, load_slip))
    return slip, load_slip


def calibrate_pose_data(applied, cameras, wheel, deadbands):
    left_f, left_r, right_f, right_r, _bias = wheel
    load = 0.0
    heading = 0.0
    forward_base = [0.0, 0.0]
    forward_load = [0.0, 0.0]
    reverse_base = [0.0, 0.0]
    reverse_load = [0.0, 0.0]
    first_heading = None
    for tick, (left, right) in enumerate(applied):
        effort = (abs(left) + abs(right)) * 0.5
        load = RETENTION * load + (1.0 - RETENTION) * effort
        vl = wheel_response(left, deadbands[0], left_f, left_r)
        vr = wheel_response(right, deadbands[1], right_f, right_r)
        center = (vl + vr) * 0.5
        turn = DT * (vr - vl) / TRACK
        half = turn * 0.5
        arc = math.sin(half) / half if half else 1.0
        direction = 1 if center >= 0.0 else -1
        if tick < 15:
            angle = heading + half
        elif tick == 15:
            first_heading = cameras[0][2]
            heading = first_heading
            angle = heading + half
        else:
            angle = heading + half
        v = (DT * center * arc * math.cos(angle), DT * center * arc * math.sin(angle))
        if direction >= 0:
            base, loaded = forward_base, forward_load
        else:
            base, loaded = reverse_base, reverse_load
        base[0] += v[0]
        base[1] += v[1]
        loaded[0] += load * v[0]
        loaded[1] += load * v[1]
        heading += turn
        if tick == 14:
            first_heading = cameras[0][2]
            heading = first_heading

    cam1, cam2 = cameras
    forward_target = (cam1[0] - forward_base[0], cam1[1] - forward_base[1])
    f_slip, f_load = fit_slip(forward_target, forward_base, forward_load)
    reverse_target = (cam2[0] - cam1[0] - reverse_base[0], cam2[1] - cam1[1] - reverse_base[1])
    r_slip, r_load = fit_slip(reverse_target, reverse_base, reverse_load)
    return f_slip, r_slip, f_load, r_load


def predict(commands, lag, deadbands, wheel, slips):
    left_f, left_r, right_f, right_r, _bias = wheel
    forward_slip, reverse_slip, forward_load_slip, reverse_load_slip = slips
    pending = [(0.0, 0.0)] * lag
    x = y = heading = load = 0.0
    for left, right in commands:
        pending.append((left, right))
        applied_left, applied_right = pending.pop(0)
        effort = (abs(applied_left) + abs(applied_right)) * 0.5
        load = RETENTION * load + (1.0 - RETENTION) * effort
        vl = wheel_response(applied_left, deadbands[0], left_f, left_r)
        vr = wheel_response(applied_right, deadbands[1], right_f, right_r)
        center = (vl + vr) * 0.5
        slip = forward_slip if center >= 0.0 else reverse_slip
        load_slip = forward_load_slip if center >= 0.0 else reverse_load_slip
        distance = DT * center * (1.0 + slip + load_slip * load)
        turn = DT * (vr - vl) / TRACK
        half = turn * 0.5
        arc = math.sin(half) / half if half else 1.0
        x += distance * arc * math.cos(heading + half)
        y += distance * arc * math.sin(heading + half)
        heading += turn
        heading = (heading + math.pi) % (2.0 * math.pi) - math.pi
    return [x, y, heading]


def main():
    bay = BayClient()
    encoder_readings = []
    gyro_readings = []
    cameras = []
    for tick, (left, right) in enumerate(COMMANDS):
        measurement = bay.drive(left, right)
        encoder_readings.append(measurement["encoders_m"])
        gyro_readings.append(measurement["gyro_rad"])
        if tick == 14:
            cameras.append(bay.camera())
    cameras.append(bay.camera())

    # Recover the delayed command actually applied on each tick from the
    # cumulative command integrals.  Calibration commands use hundredths, so
    # snapping removes only encoder rounding noise.
    applied = []
    previous = [0.0, 0.0]
    for reading in encoder_readings:
        pair = []
        for wheel in range(2):
            value = round((reading[wheel] - previous[wheel]) / DT, 2)
            if abs(value) < 0.005:
                value = 0.0
            pair.append(value)
        applied.append(tuple(pair))
        previous = reading
    lag = 0
    for tick, pair in enumerate(applied):
        if pair != (0.0, 0.0):
            lag = tick
            break

    samples = []
    previous_gyro = 0.0
    for (left, right), current_gyro in zip(applied, gyro_readings):
        samples.append((left, right, current_gyro - previous_gyro))
        previous_gyro = current_gyro
    deadbands, wheel = fit_wheel_model(samples)
    slips = calibrate_pose_data(applied, cameras, wheel, deadbands)

    sequences = bay.forecast_commands()
    poses = [predict(commands, lag, deadbands, wheel, slips) for commands in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
