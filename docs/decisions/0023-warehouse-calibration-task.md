---
status: accepted
date: 2026-11-12
---

# Measure calibration before warehouse deployment

The recovery task measures the quality of a submitted controller. The
calibration task measures whether an agent can design an experiment to
resolve ambiguity in onboard measurements and predict future motion.

The maintenance bay has no obstacles. A submitted controller can run up
to 20 command ticks and request one measured camera pose. Applied
wheel commands and gyro changes reveal actuator lag, deadbands, and
differential response. They do not reveal common longitudinal slip.
One camera reading can constrain forward and reverse slip when the
experiment makes their contributions geometrically distinguishable.
Forecast commands begin from rest in independent simulated resets.

An offline verifier holds the cart configuration and the forecast
sequences. The candidate uses a bounded JSON protocol in an
unprivileged subprocess. The same simulator and protocol power local
practice. Forecast success requires both position and heading accuracy.
Reward is the fraction of forecasts that pass. The CPU-only task has
a 15-minute agent budget and no runtime dependencies beyond Python.

Passive log analysis would remove experiment selection. Free navigation
would repeat the recovery task and make calibration failures harder to
diagnose. The bay uses a simplified kinematic model with stable
parameters and exact sensors up to published rounding. It excludes
collision handling, sensor noise, and transfer to a physical cart.

Qualification requires a full-score oracle using the public API, a
zero-score no-op, and a measurable penalty for omitting the camera or
ignoring the reverse response. Paired carts must have identical encoder
and gyro traces under the same commands and different physical forecasts.
