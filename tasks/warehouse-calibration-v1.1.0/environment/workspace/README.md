# Maintenance bay

The cart starts at `(x, y, heading) = (0, 0, 0)`, with stationary wheels
an empty history of nonzero commands, and zero motor load. Coordinates are in meters.
Heading increases counterclockwise from the positive x axis. Each
tick lasts 0.2 seconds. The workspace provides the exact kinematic
equations in `motion.py`. The cart parameters for each evaluation
session are unknown and fixed throughout that session.

The command delay is 0–3 ticks. Each wheel's deadband is between 0.08
and 0.24 and is shared by its forward and reverse responses. Each of its
two gains is between 0.65 and 1.05. Base slip for each direction is
between −0.12 and +0.14. Each direction's load coefficient is between
−0.62 and −0.12. The gyro has a constant bias between −0.06 and
+0.06 rad/s. Encoder and gyro readings are rounded to six decimal places.

Every tick updates motor load using the delayed commands actually applied
to the wheels. The new load is 0.82 times the previous load plus 0.18
times the mean absolute applied command. Longitudinal speed is the
nominal center speed multiplied by `1 + base_slip + load_coefficient * load`.
The direction comes from the sign of the nominal center speed. The
load term affects displacement. The gyro still measures the angular
response of the two wheels plus bias.

| Client operation | Behavior |
| --- | --- |
| `BayClient()` | Reads the session budget from the simulator. |
| `drive(left, right)` | Advances one tick. Both commands must be between −1 and +1. Returns `tick`, the two cumulative applied-command integrals in `encoders_m`, and accumulated biased heading in `gyro_rad`. All readings start at zero. |
| `camera()` | Returns the current physical `[x, y, heading]`, with position rounded to 0.001 m and heading to 0.000001 rad. It does not advance time. |
| `forecast_commands()` | Ends calibration and returns the ordered command sequences. Each starts with zero pose, an empty command history, and zero motor load. Predict the endpoint immediately after the last listed tick. Commands still queued after that tick have no effect on the endpoint. |
| `submit(poses)` | Ends the session. Supply one `[x, y, heading]` per sequence in the same order. Values must be finite and within ±1,000. |

You may issue up to 30 drive commands and take up to two camera
readings before requesting the forecast sequences. Request the
sequences once, then submit once. A valid forecast is within
0.045 m Euclidean position error and 0.025 rad wrapped heading error.
The verifier starts a fresh policy process for each cart and grades
the fraction of forecasts within both tolerances. An invalid protocol
request ends the current session with zero credit.

Each policy process has a 12-second wall-clock budget. On Linux, it
has 512 MiB of address space and a 4 MiB file size limit. Each JSON
request, including the newline, fits in 8 KiB. Use stdout for the
provided client only.

Run either public practice case from `/app`:

```sh
python3 -B practice.py --case 0 --policy policy.py
python3 -B practice.py --case 1 --policy policy.py
```
