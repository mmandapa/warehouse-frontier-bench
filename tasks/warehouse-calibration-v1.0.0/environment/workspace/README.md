# Maintenance bay

The cart starts at `(x, y, heading) = (0, 0, 0)`, with stationary wheels
and an empty history of nonzero commands. Coordinates are in meters.
Heading increases counterclockwise from the positive x axis. Each
tick lasts 0.2 seconds. The workspace provides the exact kinematic
equations in `motion.py`. The cart parameters for each evaluation
session are unknown and fixed throughout that session.

The command delay is 0–3 ticks. Each wheel's deadband is between 0.08
and 0.24 and is shared by its forward and reverse responses. Each of its
two gains is between 0.65 and 1.05. Separate slip coefficients for
positive and negative center motion range from −0.30 to +0.15. The gyro
has a constant bias between −0.06 and +0.06 rad/s. Sensors have no noise
beyond rounding to six decimal places.

| Client operation | Behavior |
| --- | --- |
| `BayClient()` | Reads the session budget from the simulator. |
| `drive(left, right)` | Advances one tick. Both commands must be between −1 and +1. Returns `tick`, the two cumulative applied-command integrals in `encoders_m`, and accumulated biased heading in `gyro_rad`. All readings start at zero. |
| `camera()` | Returns the current physical `[x, y, heading]`. It does not advance time. |
| `forecast_commands()` | Ends calibration and returns the ordered command sequences. Each starts from the same zero pose and command history. Score the endpoint immediately after the last listed tick, including any remaining actuator delay. |
| `submit(poses)` | Ends the session. Supply one `[x, y, heading]` per sequence in the same order. Values must be finite and within ±1,000. |

You may issue up to 20 drive commands and take one optional camera
reading before requesting the forecast sequences. Request the
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
