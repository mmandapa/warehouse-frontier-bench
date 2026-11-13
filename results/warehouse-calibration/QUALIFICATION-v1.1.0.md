# Warehouse Cart Calibration v1.1.0 qualification

The task tests whether an agent can design measurements that identify
how recent motor effort changes a cart's travel distance. The agent
gets 30 command ticks and up to two camera poses. The verifier grades
five forecasts per cart across 12 carts. Each forecast starts with a
fresh pose, command queue, and load state. A forecast earns credit when
both its position and heading are within tolerance.
[Task and run commands](../../tasks/warehouse-calibration-v1.1.0/README.md)

| Control or saved submission | Correct forecasts | Reward |
| --- | ---: | ---: |
| [Oracle](local-v1.1.0/oracle.json) | 60/60 | 1.000 |
| [No-op](local-v1.1.0/no-op.json) | 0/60 | 0.000 |
| [No camera](local-v1.1.0/no-camera.json) | 12/60 | 0.200 |
| [Constant slip fitted to both cameras](local-v1.1.0/constant-slip.json) | 16/60 | 0.267 |
| [Luna v1.0.0 policy 1](local-v1.1.0/luna-1.json) | 10/60 | 0.167 |
| [Luna v1.0.0 policy 2](local-v1.1.0/luna-2.json) | 15/60 | 0.250 |
| [Luna v1.0.0 policy 3](local-v1.1.0/luna-3.json) | 12/60 | 0.200 |
| [Luna v1.0.0 policy 4](local-v1.1.0/luna-4.json) | 11/60 | 0.183 |

The constant-slip control uses the reference's exact probe commands and
both camera observations. It fits one slip coefficient per direction
by least squares. Its 16/60 shows how much a constant model loses even
with the new task's measurement budget. The saved v1.0.0 controllers
all submitted 60 forecasts and kept heading errors below 0.001 rad.
Their misses were position errors. Their original four 60/60 scores
remain recorded under the earlier task version.
[Original results](RESULTS-v1.0.0.md)

The reference also met the same tolerances on 240 forecasts across
120 additional seeded carts. Its worst position error there was 0.033 m
against the 0.045 m tolerance. Both public practice cases passed.
The qualification script checks matched encoder and gyro traces,
physical separation, protocol limits, and replay outcomes.
[Seeded reference results](local-v1.1.0/seeded-reference.json)
[Qualification script](../../scripts/qualify_warehouse_calibration_v1_1_0.py)

The simulator equations are public. Cart parameters and forecast
sequences live in the offline verifier. The two new camera readings
have millimeter position resolution. The load model and finite
parameter ranges are assumptions about the simulated cart.

Harbor lint passed. The final oracle scored 60/60 and the no-op scored
0/60 on the same frozen checksum with zero exceptions. The verifier
ran in a separate Docker environment.
[Oracle run](harbor-controls-v1.1.0/oracle/result.json)
[No-op run](harbor-controls-v1.1.0/nop/result.json)
[Freeze manifest](frozen-v1.1.0.json)

Four fresh sequential GPT-6 Luna trials completed on this freeze. Their
scores were 0.9000, 0.8667, 0.0000, and 0.8000. The zero came from a
syntax error in the submission. The three other attempts missed position
tolerance on some forecasts. See the [results and artifacts](RESULTS-v1.1.0.md).
