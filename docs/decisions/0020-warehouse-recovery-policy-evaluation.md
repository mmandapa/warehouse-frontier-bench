---
status: accepted
date: 2026-11-11
---

# Grade warehouse recovery with a separate simulator process

## Context

The initial 2D cart mission admitted a fixed motor test and east-side
inspection that docked on all 72 held-out cases. Adding temporary route
closures and a separate loading surface created two decisions in the same
mission. A policy needs to find its aisle and a usable route, then recover
accurate pose and motion estimates before docking. The observation-only
reference docked on 192 of 192 held-out study cases. The two fixed-side
controls with loading-surface calibration each docked on 96.

## Decision

Use one CPU-only Harbor task. The agent writes a Python policy and can
exercise it against public scenarios. The offline verifier owns the
official initial states, advances the simulator, and supplies sensor data
to the policy over a local stream. The policy runs as a separate
unprivileged process. The verifier scores the physical result and saves
diagnostic action and observation summaries.

Use collision-free docking fraction as the scalar reward. Each scenario
uses the same published motion bounds, observation meanings, final pose
tolerance, and simulated time limit. Keep simulator code visible for
testing and keep official scene assignments and reference code private.

## Alternatives and limits

Running a full robotics stack would add rendering assets and GPU setup
to a task about evidence and control. A symbolic map omits steering error
and docking geometry. A geometric differential-drive model supports both
within the CPU limit. It assumes a known surveyed map and a cart footprint,
and it does not model contact forces or transfer to a real robot.

Qualification requires a full-score reference using the same policy
interface, a zero-score no-op, and rejection of controls that skip
rerouting or motion recalibration. Report fresh model difficulty only
after an authorized evaluation.
