"""Calibrate the cart, then predict each supplied command sequence."""

import math

from client import BayClient
from motion import CartParameters, DT, TRACK_M, forecast


# The first eight moves excite each wheel, direction, and amplitude by itself.
# The remaining moves make long forward and reverse arcs at different headings
# so the one camera observation can distinguish the two slip coefficients.
CALIBRATION = [
    (0.0, 0.45),
    (0.0, 0.95),
    (-0.45, 0.0),
    (-0.95, 0.0),
    (0.45, 0.0),
    (0.95, 0.0),
    (0.0, -0.45),
    (0.0, -0.95),
    (0.35, 0.95),
    (0.35, 0.95),
    (0.35, 0.95),
    (0.35, 0.95),
    (0.35, 0.95),
    (-0.95, -0.35),
    (-0.95, -0.35),
    (-0.95, -0.35),
    (-0.95, -0.35),
    (-0.95, -0.35),
    (-0.95, -0.35),
    (-0.95, -0.35),
]


def infer_delay(commands, encoder_rows):
    """Find which issued command appears in each tick's encoder increment."""
    best_lag = 0
    best_error = float("inf")
    previous = [0.0, 0.0]
    applied_rows = []
    for row in encoder_rows:
        current = row
        applied_rows.append([
            (current[i] - previous[i]) / DT for i in range(2)
        ])
        previous = current

    for lag in range(4):
        error = 0.0
        for tick, actual in enumerate(applied_rows):
            expected = commands[tick - lag] if tick >= lag else (0.0, 0.0)
            error += (actual[0] - expected[0]) ** 2
            error += (actual[1] - expected[1]) ** 2
        if error < best_error:
            best_error = error
            best_lag = lag
    return best_lag


def fit_wheel(observations):
    """Fit a shared deadband and separate forward/reverse wheel gains."""
    positive = [(u, speed) for u, speed in observations if u > 0.0]
    negative = [(u, speed) for u, speed in observations if u < 0.0]

    # For a fixed deadband, each direction is a one-parameter least-squares
    # fit through the origin: speed = gain * (command +/- deadband).
    def score(deadband):
        gains = []
        residual = 0.0
        for samples, offset in ((positive, -deadband), (negative, deadband)):
            den = sum((u + offset) ** 2 for u, _ in samples)
            gain = sum((u + offset) * speed for u, speed in samples) / den
            gains.append(gain)
            residual += sum(
                (speed - gain * (u + offset)) ** 2 for u, speed in samples
            )
        return residual, gains

    # The physical interval is narrow. A golden-section search avoids any
    # dependence on a third-party optimizer and is more accurate than the
    # rounded sensor readings require.
    lo, hi = 0.08, 0.24
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    x1 = hi - phi * (hi - lo)
    x2 = lo + phi * (hi - lo)
    f1 = score(x1)[0]
    f2 = score(x2)[0]
    for _ in range(64):
        if f1 <= f2:
            hi, x2, f2 = x2, x1, f1
            x1 = hi - phi * (hi - lo)
            f1 = score(x1)[0]
        else:
            lo, x1, f1 = x1, x2, f2
            x2 = lo + phi * (hi - lo)
            f2 = score(x2)[0]
    deadband = (lo + hi) / 2.0
    _, gains = score(deadband)
    return deadband, gains[0], gains[1]


def wheel_speed(command, deadband, forward_gain, reverse_gain):
    if command >= 0.0:
        return forward_gain * max(command - deadband, 0.0)
    return reverse_gain * min(command + deadband, 0.0)


def infer_slip(camera_pose, applied, wheel_params):
    """Use the camera endpoint to solve for forward and reverse slip."""
    deadbands, forward, reverse = wheel_params
    x_plus = y_plus = 0.0
    x_minus = y_minus = 0.0
    heading = 0.0

    for left, right in applied:
        vl = wheel_speed(left, deadbands[0], forward[0], reverse[0])
        vr = wheel_speed(right, deadbands[1], forward[1], reverse[1])
        center = (vl + vr) / 2.0
        turn = DT * (vr - vl) / TRACK_M
        half = turn / 2.0
        arc_scale = math.sin(half) / half if abs(half) > 1e-12 else 1.0
        dx = DT * center * arc_scale * math.cos(heading + half)
        dy = DT * center * arc_scale * math.sin(heading + half)
        if center >= 0.0:
            x_plus += dx
            y_plus += dy
        else:
            x_minus += dx
            y_minus += dy
        heading += turn

    target_x, target_y = camera_pose[0], camera_pose[1]
    determinant = x_plus * y_minus - x_minus * y_plus
    if abs(determinant) > 1e-9:
        forward_scale = (target_x * y_minus - x_minus * target_y) / determinant
        reverse_scale = (x_plus * target_y - target_x * y_plus) / determinant
    else:
        # This branch is only for a nearly straight path. Use the common scale
        # that best matches the observed displacement and keep it physical.
        px, py = x_plus + x_minus, y_plus + y_minus
        denom = px * px + py * py
        scale = ((target_x * px + target_y * py) / denom) if denom > 1e-12 else 0.925
        scale = min(1.15, max(0.70, scale))
        forward_scale = reverse_scale = scale

    forward_scale = min(1.15, max(0.70, forward_scale))
    reverse_scale = min(1.15, max(0.70, reverse_scale))
    return forward_scale - 1.0, reverse_scale - 1.0


def main():
    bay = BayClient()
    commands = CALIBRATION[:bay.tick_limit]
    encoder_rows = []
    gyro_rows = []
    for left, right in commands:
        reading = bay.drive(left, right)
        encoder_rows.append(reading["encoders_m"])
        gyro_rows.append(reading["gyro_rad"])

    camera_pose = bay.camera()
    sequences = bay.forecast_commands()

    lag = infer_delay(commands, encoder_rows)
    applied = []
    for tick in range(len(commands)):
        applied.append(commands[tick - lag] if tick >= lag else (0.0, 0.0))

    total_gyro = gyro_rows[-1] if gyro_rows else 0.0
    camera_heading = camera_pose[2]
    turns_total = camera_heading + 2.0 * math.pi * round(
        (total_gyro - camera_heading) / (2.0 * math.pi)
    )
    gyro_bias = (total_gyro - turns_total) / (DT * len(commands))

    observations = [[], []]
    previous_gyro = 0.0
    for tick, (left, right) in enumerate(applied):
        gyro_increment = gyro_rows[tick] - previous_gyro
        previous_gyro = gyro_rows[tick]
        turn = gyro_increment - DT * gyro_bias
        speed_difference = turn * TRACK_M / DT
        if left != 0.0 and right == 0.0:
            observations[0].append((left, -speed_difference))
        elif right != 0.0 and left == 0.0:
            observations[1].append((right, speed_difference))

    fitted = [fit_wheel(samples) for samples in observations]
    deadbands = (fitted[0][0], fitted[1][0])
    forward = (fitted[0][1], fitted[1][1])
    reverse = (fitted[0][2], fitted[1][2])
    wheel_params = (deadbands, forward, reverse)
    forward_slip, reverse_slip = infer_slip(camera_pose, applied, wheel_params)

    settings = CartParameters(
        lag=lag,
        deadbands=deadbands,
        forward_gains=forward,
        reverse_gains=reverse,
        forward_slip=forward_slip,
        reverse_slip=reverse_slip,
        gyro_bias=gyro_bias,
    )
    poses = [list(forecast(settings, sequence)) for sequence in sequences]
    bay.submit(poses)


if __name__ == "__main__":
    main()
