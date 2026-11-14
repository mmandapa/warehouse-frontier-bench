"""Estimate drive response and directional slip from one calibration."""

from dataclasses import replace

from client import BayClient
from motion import CartParameters, DT, TRACK_M, forecast

PROBES = (
    (0, 0),
    (.45, 0), (.90, 0), (-.45, 0), (-.90, 0),
    (0, .45), (0, .90), (0, -.45), (0, -.90),
    (.85, .65), (.85, .65), (.85, .65),
    (-.90, .90), (-.90, .90),
    (-.85, -.65), (-.85, -.65), (-.85, -.65),
    (0, 0), (0, 0), (0, 0),
    (.95, .95), (.95, .95), (.95, .95),
    (-.90, .90), (-.90, .90),
    (-.95, -.95), (-.95, -.95),
    (0, 0), (0, 0), (0, 0),
)
CHECKPOINTS = (20, 30)
SLIP_FIELDS = ("forward_slip", "reverse_slip", "forward_load_slip", "reverse_load_slip")


def estimate_drive(observations):
    applied = []
    differential = []
    last_encoders = [0, 0]
    last_gyro = 0
    bias = observations[0]["gyro_rad"] / DT
    for observation in observations:
        encoders = observation["encoders_m"]
        gyro = observation["gyro_rad"]
        applied.append(tuple(round((a - b) / DT, 5) for a, b in zip(encoders, last_encoders)))
        differential.append(TRACK_M * ((gyro - last_gyro) / DT - bias))
        last_encoders = encoders
        last_gyro = gyro
    lag = next(i for i, pair in enumerate(applied) if pair != (0, 0)) - 1

    def response(wheel, sign):
        values = {}
        for pair, difference in zip(applied, differential):
            command = pair[wheel]
            if pair[1 - wheel] == 0 and command * sign > 0:
                values[abs(command)] = difference * (2 * wheel - 1) * sign
        x0, x1 = sorted(values)
        gain = (values[x1] - values[x0]) / (x1 - x0)
        return gain, x0 - values[x0] / gain

    forward = [response(i, 1) for i in range(2)]
    reverse = [response(i, -1) for i in range(2)]
    return CartParameters(lag, tuple(row[1] for row in forward),
                          tuple(row[0] for row in forward), tuple(row[0] for row in reverse),
                          0, 0, bias)


def solve(matrix, target):
    rows = [list(row) + [value] for row, value in zip(matrix, target)]
    size = len(rows)
    for column in range(size):
        pivot = max(range(column, size), key=lambda i: abs(rows[i][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        if abs(scale) < 1e-9:
            raise ValueError("calibration measurements do not identify slip")
        rows[column] = [value / scale for value in rows[column]]
        for i, row in enumerate(rows):
            if i != column:
                scale = row[column]
                rows[i] = [a - scale * b for a, b in zip(row, rows[column])]
    return [row[-1] for row in rows]


def slip_system(settings, cameras):
    matrix, target = [], []
    for tick, camera in zip(CHECKPOINTS, cameras):
        commands = PROBES[:tick]
        base = forecast(settings, commands)
        unit_poses = [forecast(replace(settings, **{field: 1.0}), commands) for field in SLIP_FIELDS]
        for axis in range(2):
            matrix.append([pose[axis] - base[axis] for pose in unit_poses])
            target.append(camera[axis] - base[axis])
    return matrix, target


def estimate_slip(settings, cameras):
    matrix, target = slip_system(settings, cameras)
    return solve(matrix, target)


def main():
    bay = BayClient()
    observations, cameras = [], []
    for tick, command in enumerate(PROBES, 1):
        observations.append(bay.drive(*command))
        if tick in CHECKPOINTS:
            cameras.append(bay.camera())
    settings = estimate_drive(observations)
    slip = estimate_slip(settings, cameras)
    settings = replace(settings, **dict(zip(SLIP_FIELDS, slip)))
    bay.submit([forecast(settings, commands) for commands in bay.forecast_commands()])


if __name__ == "__main__":
    main()
