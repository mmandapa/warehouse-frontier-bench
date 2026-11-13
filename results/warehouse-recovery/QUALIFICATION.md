# Warehouse cart recovery qualification

The task measures whether a policy can gather evidence about its location
and motion, select a usable warehouse route, and park at an assigned dock.
Two initial aisles can give the same observations. A temporary obstruction
may be outside lidar range until the cart approaches. The model includes
different floor grip near the dock. These are simulated cases rather than
replays of real incidents. BARN motivates constrained navigation, Nav2
motivates the dock pose and final approach, and RoboQuest motivates the
focus on choosing what to observe.
[BARN dataset](https://www.cs.utexas.edu/~xiao/BARN/BARN.html) ·
[Nav2 docking](https://docs.nav2.org/rolling/tutorials/general_tutorials/using_docking/) ·
[RoboQuest](https://arxiv.org/html/2610.10388v1)

## Authoring study

The first 2D version was rejected. A fixed motor pulse sequence and an east
marker visit docked on [72/72 held-out cases](2d-held-out.json). The expanded
mission adds blocked routes and a change in ground motion for the same
wheel command. The held-out study crosses six layouts, two plausible
start rows per layout, four drive profiles, both blocked directions, and
two loading surface profiles.

| Controller | Clean docks | Collisions |
| --- | ---: | ---: |
| Original fixed probe and east marker | 0/192 | 168 |
| Reroute using lidar, keep initial motion estimate | 0/192 | 24 |
| Recalibrate at dock, use a fixed marker route (each side) | 96/192 | 0 |
| Observation-only reference | 192/192 | 0 |
| Informed control | 192/192 | 0 |

The [held-out diagnostics](shift-held-out.json) contain each outcome. The
observation-only reference uses the same sensor data available through the
policy interface. The informed control gets actual pose and drive gains.
The strongest tested fixed route still passes only one half of the cases.

## Packaged verifier

The packaged task evaluates 16 scenes, including varied obstruction
positions. The private grader owns simulator state. The submitted
program runs as a separate process, and the Docker verifier assigns it an
unprivileged identity with access to the public client and simulator code.
The score is the fraction of scenes ending collision-free and settled
within the documented dock tolerances.

| Local package control | Score | Clean docks | Collisions |
| --- | ---: | ---: | ---: |
| Oracle | 1.0 | 16/16 | 0 |
| No-op | 0.0 | 0/16 | 0 |
| Fixed east route with recalibration | 0.5 | 8/16 | 0 |
| Adaptive route without final recalibration | 0.0 | 0/16 | 2 |

The [local grader diagnostics](local-v1.0.0) contain the per-scene results.
The oracle passed both public practice missions. Seven simulator and
mission checks passed, including an equal-observation pair with opposite
blocked routes. The authoring study and controls measure solvability and
discrimination.

The [first Harbor controls](harbor-controls-v1.0.0/warehouse-recovery-v1.0.0-oracle-nop/result.json)
failed before scoring because the verifier image omitted its test entry
point. Version 1.0.1 adds that file with the same policy API, cases, and
scoring. The [v1.0.1 Harbor controls](harbor-controls-v1.0.1/warehouse-recovery-v1.0.1-oracle-nop/result.json)
returned oracle 1.0 and no-op 0.0 without exceptions. Both used the same
Harbor task checksum. The [task manifest](frozen-v1.0.1.json) lists the
files included in the agent image separately from author-only material.
The controls took 61 seconds and made no model calls. Fresh agent
difficulty remains unmeasured.
