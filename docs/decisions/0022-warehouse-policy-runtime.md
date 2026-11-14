---
status: accepted
date: 2026-11-12
---

# Enforce the published warehouse policy runtime budget

The warehouse task promised 12 seconds of wall time per episode. The
simulator also set a 10-second CPU limit on the policy process. A replay
of the fourth Luna submission confirmed that the CPU limit killed two
episodes. With that limit removed, one of those episodes docked within
12 seconds and the other reached the wall-time limit.

Version 1.1.2 removes the shorter CPU limit from the practice and scored
runners. The published 12-second wall-time limit covers the mission
protocol and remains the termination condition for a slow controller.
The public README specifies the existing memory, file-size, and request
size limits. The course, sensors, docking tolerances, and agent budget
use the same values as v1.1.1.

Version 1.1.1 and its original trial artifacts are archived as scored.
The [audit](../../results/warehouse-recovery/QUALIFICATION.md)
reports the replay results with version labels. The wall-time limit
makes near-budget outcomes sensitive to runtime load, so comparisons
should use equivalent local resources and retain per-episode reasons.
