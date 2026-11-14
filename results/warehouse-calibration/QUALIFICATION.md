# Warehouse Cart Calibration qualification

The task tests whether an agent can design measurements that identify
how recent motor effort changes a cart's travel distance. The agent
gets 30 command ticks and up to two camera poses. The verifier grades
five forecasts per cart across 12 carts. Each forecast starts with a
fresh pose, command queue, and load state. A forecast earns credit when
both its position and heading are within tolerance.
[Task and run commands](../../tasks/warehouse-calibration/README.md)

| Control or saved submission | Correct forecasts | Reward |
| --- | ---: | ---: |
| [Oracle](local-v1.1.0/oracle.json) | 60/60 | 1.000 |
| [No-op](local-v1.1.0/no-op.json) | 0/60 | 0.000 |
| [No camera](local-v1.1.0/no-camera.json) | 12/60 | 0.200 |
| [Constant slip fitted to both cameras](local-v1.1.0/constant-slip.json) | 16/60 | 0.267 |

The constant-slip control uses the reference's exact probe commands and
both camera observations. It fits one slip coefficient per direction
by least squares. Its 16/60 shows how much a constant model loses even
with the new task's measurement budget. 
The reference also met the same tolerances on 240 forecasts across
120 additional seeded carts. Its worst position error there was 0.033 m
against the 0.045 m tolerance. Both public practice cases passed.
The qualification script checks matched encoder and gyro traces,
physical separation, protocol limits, and control outcomes.
[Seeded reference results](local-v1.1.0/seeded-reference.json)
[Qualification script](../../scripts/qualify_warehouse_calibration.py)

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

The [original package oracle](package-controls/oracle/result.json)
scored 60/60 and the [no-op](package-controls/nop/result.json) scored
0/60. See the [model results](RESULTS.md) for the original trials.

## Isolated verifier replay

The verifier gives each cart its own unprivileged user and private
writable storage. The [offline replay](isolation-replay.json) rescored
all 13 saved policies. All 780 forecast outcomes and all 13 rewards
matched the original model trials. The quota-blocked launch produced
no submission to rescore.

The [oracle](isolation-controls/oracle.json) and
[no-op](isolation-controls/nop.json) ran through Harbor on the package
identified by the [current manifest](package-manifest.json). They
scored 60/60 and 0/60, respectively.
