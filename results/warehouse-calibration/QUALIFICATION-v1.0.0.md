# Warehouse calibration v1.0.0 qualification

The [task](../../tasks/warehouse-calibration-v1.0.0/README.md) asks an
agent to identify a serviced cart's dynamics from up to 20 command
ticks and one camera pose. It then predicts the endpoints of five
command sequences on independent resets. Twelve carts produce 60
forecasts.

| Control | Correct forecasts | Reward |
| --- | ---: | ---: |
| [Harbor oracle](harbor-controls-v1.0.0/oracle-frozen/result.json) | 60/60 | 1.000 |
| [Harbor no-op](harbor-controls-v1.0.0/nop/result.json) | 0/60 | 0.000 |
| [No camera, estimated drive](local-v1.0.0/no-camera.json) | 4/60 | 0.067 |
| [One slip value for both directions](local-v1.0.0/shared-slip.json) | 24/60 | 0.400 |

The no-camera controller recovered actuator lag, gyro bias, and wheel
response before forecasting with zero slip. It missed all 12 forward
and all 12 reverse forecasts. The shared-slip controller used the
measured forward slip for both directions. It passed all 12 forward
forecasts and missed all 12 reverse forecasts. The qualification
script checked that matched carts produced identical encoder and
gyro traces and that their forward and reverse endpoint separations
exceeded twice the position tolerance. It also checked the camera
budget, calibration order, and numeric validation.
[Qualification script](../../scripts/qualify_warehouse_calibration_v1_0_0.py)

Both final Harbor controls used the same frozen package and separate
offline verifier. An initial oracle run used a package checksum
from before the author-facing README was added. The reference
controller passed all three forecasts in both public practice cases.
Harbor lint passed. [Freeze manifest](frozen-v1.0.0.json)

The simulator assumes stable parameters and noiseless measurements
apart from rounding. The [freeze manifest](frozen-v1.0.0.json) records
the public and private files. The four
[authorized Luna trials](RESULTS-v1.0.0.md) all scored 60/60.
