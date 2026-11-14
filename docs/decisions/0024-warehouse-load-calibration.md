---
status: accepted
date: 2026-11-12
---

# Forecast cart motion after different motor loads

All four Luna submissions solved Calibration v1.0.0. The first used
14 of 20 ticks and one camera pose to identify fixed traction in both
directions. A follow-up should require measuring a property of the cart
that changes during operation.

Calibration v1.1.0 adds a load state that rises with applied motor
commands and decays when the motors are idle. Each direction has an
unknown base slip and an unknown load response. The cart's physical
position is still the only measurement that reflects slip. The agent
gets 30 ticks and two camera poses with position rounded to millimeters.
It needs to collect observations that distinguish four slip parameters
and forecast endpoints from a fresh pose, actuator queue, and load.
The simulator and its equations remain public. The split between the
agent image and offline verifier follows the first calibration task.

The verifier uses 12 carts and five forecasts per cart. The forecasts
cover sustained movement in both directions, a change of direction,
a pause between runs, and intermittent load. The reward is the fraction
of forecasts within the published pose tolerances. Local qualification
requires a full-score oracle, a zero-score no-op, and controlled replays
of the four previous Luna submissions. A control that fits one constant
per direction isolates the cost of ignoring load history. The reference
must also work on seeded carts outside the scored fixture.

Adding noise to the old constant model would make the same experiment
less precise. Changing traction with recent commands makes the
identification problem different and allows reproducible tests of
recovery after a pause. This is a simplified motor-load model. The
benchmark measures identification and prediction in simulation.
