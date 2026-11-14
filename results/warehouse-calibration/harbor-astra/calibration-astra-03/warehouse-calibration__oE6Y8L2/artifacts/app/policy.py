"""Identify wheel dynamics, then measure directional slip at changing loads."""

import math

from client import BayClient
from motion import CartParameters, DT, LOAD_RETENTION, TRACK_M, forecast, wheel_response


# The first run excites both forward wheel slopes and offsets. Its changing
# curvature and load give independent position measurements of the two slip
# terms. The reverse run sheds load while turning for the same reason.
FORWARD = [
    (1, 0), (.4, 0), (0, .4), (0, 1), (0, 1), (0, 1), (0, 1),
    (0, 1), (0, 1), (0, 1), (1, 1), (1, 1), (1, 1),
]
REVERSE = [
    (-1, -1), (-1, -1), (-1, -1), (-1, -1), (-1, 0), (-1, 0),
    (-1, 0), (-1, 0), (0, 0), (-1, 0), (-1, 0), (-1, -.4), (0, -1),
]


def least_squares(rows, targets):
    """Solve these small, full-rank calibration systems with pivoting."""
    n = len(rows[0])
    matrix = [[sum(row[i] * row[j] for row in rows) for j in range(n)]
              + [sum(row[i] * y for row, y in zip(rows, targets))]
              for i in range(n)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda j: abs(matrix[j][i]))
        matrix[i], matrix[pivot] = matrix[pivot], matrix[i]
        scale = matrix[i][i]
        matrix[i] = [x / scale for x in matrix[i]]
        for j in range(n):
            if j != i:
                scale = matrix[j][i]
                matrix[j] = [x - scale * y for x, y in zip(matrix[j], matrix[i])]
    return [row[-1] for row in matrix]


def fit_slip(matrix, displacement):
    """Fit scale and load slope, respecting the supplied parameter bounds."""
    a, b = matrix[0]
    c, d = matrix[1]
    x, y = displacement
    det = a * d - b * c
    scale = (d * x - b * y) / det
    slope = (a * y - c * x) / det
    if .88 <= scale <= 1.14 and -.62 <= slope <= -.12:
        return scale - 1, slope
    candidates = []
    for scale in (.88, 1.14):
        slope = (b * (x - a * scale) + d * (y - c * scale)) / (b*b + d*d)
        candidates.append((scale, max(-.62, min(-.12, slope))))
    for slope in (-.62, -.12):
        scale = (a * (x - b * slope) + c * (y - d * slope)) / (a*a + c*c)
        candidates.append((max(.88, min(1.14, scale)), slope))
    scale, slope = min(candidates, key=lambda p:
                       (a*p[0] + b*p[1] - x)**2 + (c*p[0] + d*p[1] - y)**2)
    return scale - 1, slope


def calibrate(bay):
    commands = [(0, 0)] + FORWARD + REVERSE
    records = []
    cameras = []
    lag = None
    tick = 0
    while lag is None or tick < len(commands) + lag:
        command = commands[tick] if tick < len(commands) else (0, 0)
        reading = bay.drive(*command)
        records.append(reading)
        tick += 1
        if lag is None and any(abs(x) > 1e-5 for x in reading['encoders_m']):
            lag = tick - 2  # First nonzero command was sent on tick two.
        if lag is not None and tick in (1 + len(FORWARD) + lag, len(commands) + lag):
            cameras.append((tick, bay.camera()))

    # Camera headings remove the gyro's constant bias. Unwrap using the first
    # stationary reading, which already estimates the bias to a few microradians.
    initial_bias = records[0]['gyro_rad'] / DT
    bias_numerator = bias_denominator = 0.
    for tick, pose in cameras:
        elapsed = tick * DT
        gyro = records[tick - 1]['gyro_rad']
        turns = round((gyro - initial_bias * elapsed - pose[2]) / (2 * math.pi))
        bias_numerator += elapsed * (gyro - pose[2] - turns * 2 * math.pi)
        bias_denominator += elapsed * elapsed
    bias = bias_numerator / bias_denominator

    # Encoders integrate commands, not wheel speeds. Their differences recover
    # exactly which commands were applied, including the command delay.
    applied = []
    angular = []
    previous_encoders = (0., 0.)
    previous_gyro = 0.
    for reading in records:
        applied.append(tuple(round((v - old) / DT, 6)
                             for v, old in zip(reading['encoders_m'], previous_encoders)))
        angular.append(((reading['gyro_rad'] - previous_gyro) / DT - bias) * TRACK_M)
        previous_encoders = reading['encoders_m']
        previous_gyro = reading['gyro_rad']

    rows, targets = [], []
    for (left, right), speed_difference in zip(applied, angular):
        if left >= 0 and right >= 0 and (left or right):
            rows.append([-left, float(left > 0), right, -float(right > 0)])
            targets.append(speed_difference)
    gl, offset_l, gr, offset_r = least_squares(rows, targets)
    deadbands = (offset_l / gl, offset_r / gr)
    rows, targets = [], []
    for (left, right), speed_difference in zip(applied, angular):
        if left <= 0 and right <= 0 and (left or right):
            rows.append([max(-left - deadbands[0], 0), -max(-right - deadbands[1], 0)])
            targets.append(speed_difference)
    reverse_gains = tuple(least_squares(rows, targets))

    # With wheel responses known, position is linear in (1 + base slip) and
    # load slip. Integrate their two displacement vectors for each camera run.
    matrices = [[[0., 0.], [0., 0.]] for _ in range(2)]
    heading = load = 0.
    for (left, right) in applied:
        load = LOAD_RETENTION * load + (1 - LOAD_RETENTION) * (abs(left) + abs(right)) / 2
        vl = wheel_response(left, deadbands[0], gl, reverse_gains[0])
        vr = wheel_response(right, deadbands[1], gr, reverse_gains[1])
        turn = DT * (vr - vl) / TRACK_M
        distance = DT * (vl + vr) / 2
        half = turn / 2
        arc = math.sin(half) / half if half else 1.
        dx = distance * arc * math.cos(heading + half)
        dy = distance * arc * math.sin(heading + half)
        matrix = matrices[0 if distance >= 0 else 1]
        matrix[0][0] += dx
        matrix[0][1] += dx * load
        matrix[1][0] += dy
        matrix[1][1] += dy * load
        heading += turn
    first = cameras[0][1]
    last = cameras[1][1]
    forward_slip, forward_load = fit_slip(matrices[0], first[:2])
    reverse_slip, reverse_load = fit_slip(matrices[1], [last[0] - first[0], last[1] - first[1]])
    return CartParameters(lag, deadbands, (gl, gr), reverse_gains,
                          forward_slip, reverse_slip, bias, forward_load, reverse_load)


def main():
    bay = BayClient()
    settings = calibrate(bay)
    sequences = bay.forecast_commands()
    bay.submit([forecast(settings, sequence) for sequence in sequences])


if __name__ == '__main__':
    main()
