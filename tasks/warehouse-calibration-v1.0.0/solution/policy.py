"""Estimate drive response and directional slip from one calibration."""

from dataclasses import replace

from client import BayClient
from motion import CartParameters, DT, TRACK_M, forecast

# A zero command measures gyro drift. Isolated wheel pulses give two
# points per wheel and direction. The final arcs give independent
# position contributions from forward and reverse motion.
PROBES = (
    (0, 0),
    (.45, 0), (.90, 0), (-.45, 0), (-.90, 0),
    (0, .45), (0, .90), (0, -.45), (0, -.90),
    (.85, .65), (.85, .65), (.85, .65),
    (-.90, .90), (-.90, .90),
    (-.85, -.65), (-.85, -.65), (-.85, -.65),
    (0, 0), (0, 0), (0, 0),
)


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


def estimate_slip(settings, camera):
    x0, y0, _ = forecast(settings, PROBES)
    xf, yf, _ = forecast(replace(settings, forward_slip=1), PROBES)
    xr, yr, _ = forecast(replace(settings, reverse_slip=1), PROBES)
    a, b, c, d = xf - x0, xr - x0, yf - y0, yr - y0
    x, y = camera[0] - x0, camera[1] - y0
    determinant = a * d - b * c
    return (x * d - b * y) / determinant, (a * y - x * c) / determinant


def main():
    bay = BayClient()
    observations = [bay.drive(*command) for command in PROBES]
    settings = estimate_drive(observations)
    forward, reverse = estimate_slip(settings, bay.camera())
    settings = replace(settings, forward_slip=forward, reverse_slip=reverse)
    bay.submit([forecast(settings, commands) for commands in bay.forecast_commands()])


if __name__ == "__main__":
    main()
