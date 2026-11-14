"""Calibrate the cart from encoder, gyro, and camera readings."""

import math

from client import BayClient


DT = 0.2
TRACK = 0.56
RETENTION = 0.82


def clamp(value, low, high):
    return min(high, max(low, value))


def wrap(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def identify_lag(commands, readings):
    """Choose the delay whose predicted command integrals match the encoders."""
    best_lag = 0
    best_error = float("inf")
    for lag in range(4):
        totals = [0.0, 0.0]
        error = 0.0
        for tick, reading in enumerate(readings):
            source = tick - lag
            applied = commands[source] if 0 <= source < len(commands) else (0.0, 0.0)
            totals[0] += DT * applied[0]
            totals[1] += DT * applied[1]
            observed = reading["encoders_m"]
            error += (totals[0] - observed[0]) ** 2 + (totals[1] - observed[1]) ** 2
        if error < best_error:
            best_error = error
            best_lag = lag
    return best_lag


def applied_history(commands, count, lag):
    result = []
    for tick in range(count):
        source = tick - lag
        result.append(commands[source] if 0 <= source < len(commands) else (0.0, 0.0))
    return result


def wheel_data(commands, readings, lag, bias):
    """Recover individual wheel speeds on ticks where only one wheel moves."""
    samples = [[], []]
    previous_gyro = 0.0
    for tick, reading in enumerate(readings):
        applied = commands[tick - lag] if 0 <= tick - lag < len(commands) else (0.0, 0.0)
        delta = reading["gyro_rad"] - previous_gyro
        previous_gyro = reading["gyro_rad"]
        turn = delta - DT * bias
        speed_difference = turn * TRACK / DT
        left, right = applied
        if abs(left) > 1e-8 and abs(right) < 1e-8:
            samples[0].append((left, -speed_difference))
        elif abs(right) > 1e-8 and abs(left) < 1e-8:
            samples[1].append((right, speed_difference))
    return samples


def fit_wheel(samples):
    """Fit a shared deadband and separate forward/reverse gains."""
    best = None
    # A fine one-dimensional search is stable despite six-decimal gyro rounding.
    for k in range(1601):
        deadband = 0.08 + 0.0001 * k
        gains = []
        error = 0.0
        for sign in (1, -1):
            numerator = 0.0
            denominator = 0.0
            selected = []
            for command, speed in samples:
                if sign == 1 and command > 0:
                    z = command - deadband
                elif sign == -1 and command < 0:
                    z = command + deadband
                else:
                    continue
                if sign * z <= 0:
                    continue
                numerator += z * speed
                denominator += z * z
                selected.append((z, speed))
            gain = numerator / denominator if denominator else 0.85
            gain = clamp(gain, 0.65, 1.05)
            gains.append(gain)
            error += sum((speed - gain * z) ** 2 for z, speed in selected)
        if best is None or error < best[0]:
            best = (error, deadband, gains[0], gains[1])
    return best[1], best[2], best[3]


def response(command, deadband, forward_gain, reverse_gain):
    if command >= 0.0:
        return forward_gain * max(command - deadband, 0.0)
    return reverse_gain * min(command + deadband, 0.0)


def segment_terms(applied, parameters, initial_heading=0.0, initial_load=0.0):
    """Return the no-slip and load-weighted displacement basis vectors."""
    deadbands, forward, reverse = parameters["deadbands"], parameters["forward"], parameters["reverse"]
    heading = initial_heading
    load = initial_load
    ax = ay = bx = by = 0.0
    for left, right in applied:
        load = RETENTION * load + (1.0 - RETENTION) * (abs(left) + abs(right)) / 2.0
        vl = response(left, deadbands[0], forward[0], reverse[0])
        vr = response(right, deadbands[1], forward[1], reverse[1])
        center = (vl + vr) / 2.0
        turn = DT * (vr - vl) / TRACK
        half = turn / 2.0
        scale = math.sin(half) / half if half else 1.0
        distance = DT * center * scale
        dx = distance * math.cos(heading + half)
        dy = distance * math.sin(heading + half)
        ax += dx
        ay += dy
        bx += dx * load
        by += dy * load
        heading += turn
    return (ax, ay), (bx, by), heading, load


def solve_slip(observed, base_vector, load_vector):
    """Solve observed = (1 + base slip) A + load slip B in least squares."""
    ax, ay = base_vector
    bx, by = load_vector
    tx, ty = observed[0] - ax, observed[1] - ay
    aa = ax * ax + ay * ay
    ab = ax * bx + ay * by
    bb = bx * bx + by * by
    at = ax * tx + ay * ty
    bt = bx * tx + by * ty
    determinant = aa * bb - ab * ab
    if determinant < 1e-12:
        # The regularized fallback favors the middle of the allowed range.
        reg = 1e-5
        aa += reg
        bb += reg
        determinant = aa * bb - ab * ab
    if determinant <= 1e-18:
        return 0.0, -0.37
    base = (at * bb - bt * ab) / determinant
    load_slip = (bt * aa - at * ab) / determinant
    return clamp(base, -0.12, 0.14), clamp(load_slip, -0.62, -0.12)


def predict(commands, parameters):
    lag = parameters["lag"]
    pending = [(0.0, 0.0)] * lag
    pose = [0.0, 0.0, 0.0]
    load = 0.0
    for command in commands:
        pending.append((float(command[0]), float(command[1])))
        left, right = pending.pop(0)
        load = RETENTION * load + (1.0 - RETENTION) * (abs(left) + abs(right)) / 2.0
        vl = response(left, parameters["deadbands"][0], parameters["forward"][0], parameters["reverse"][0])
        vr = response(right, parameters["deadbands"][1], parameters["forward"][1], parameters["reverse"][1])
        center = (vl + vr) / 2.0
        slip = parameters["slip_forward"] if center >= 0.0 else parameters["slip_reverse"]
        load_slip = parameters["load_forward"] if center >= 0.0 else parameters["load_reverse"]
        distance = DT * center * (1.0 + slip + load_slip * load)
        turn = DT * (vr - vl) / TRACK
        half = turn / 2.0
        scale = math.sin(half) / half if half else 1.0
        pose[0] += distance * scale * math.cos(pose[2] + half)
        pose[1] += distance * scale * math.sin(pose[2] + half)
        pose[2] = wrap(pose[2] + turn)
    return pose


def main():
    bay = BayClient()

    # Measure each wheel's curve at several amplitudes. Nine left-wheel probes
    # followed by three smaller right-wheel probes
    # create a curved path whose later, higher-load displacement points in a
    # different direction from its overall displacement.
    pattern = ([(value, 0.0) for value in (0.30, 0.63, 0.96)] * 3
               + [(0.0, value) for value in (0.30, 0.42, 0.54)])
    forward_commands = pattern
    reverse_commands = [(-left, -right) for left, right in pattern]
    flush = [(0.0, 0.0)] * 3
    calibration = forward_commands + flush + reverse_commands + flush

    readings = []
    for left, right in forward_commands + flush:
        readings.append(bay.drive(left, right))
    camera_forward = bay.camera()

    for left, right in reverse_commands + flush:
        readings.append(bay.drive(left, right))
    camera_reverse = bay.camera()

    lag = identify_lag(calibration, readings)
    bias = clamp(wrap(readings[14]["gyro_rad"] - camera_forward[2]) / (DT * 15), -0.06, 0.06)

    samples = wheel_data(calibration, readings, lag, bias)
    deadbands = []
    forward_gains = []
    reverse_gains = []
    for wheel_samples in samples:
        deadband, forward_gain, reverse_gain = fit_wheel(wheel_samples)
        deadbands.append(deadband)
        forward_gains.append(forward_gain)
        reverse_gains.append(reverse_gain)

    parameters = {
        "lag": lag,
        "deadbands": deadbands,
        "forward": forward_gains,
        "reverse": reverse_gains,
        "bias": bias,
    }

    all_applied = applied_history(calibration, len(readings), lag)
    first_applied = all_applied[:15]
    (af, bf, heading_at_camera, load_at_camera) = segment_terms(first_applied, parameters)
    parameters["slip_forward"], parameters["load_forward"] = solve_slip(
        camera_forward[:2], af, bf
    )

    second_applied = all_applied[15:]
    ar, br, _, _ = segment_terms(
        second_applied, parameters, camera_forward[2], load_at_camera
    )
    observed_reverse = (camera_reverse[0] - camera_forward[0],
                        camera_reverse[1] - camera_forward[1])
    parameters["slip_reverse"], parameters["load_reverse"] = solve_slip(
        observed_reverse, ar, br
    )

    sequences = bay.forecast_commands()
    bay.submit([predict(sequence, parameters) for sequence in sequences])


if __name__ == "__main__":
    main()
