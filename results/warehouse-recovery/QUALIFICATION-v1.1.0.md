# Warehouse recovery v1.1.0 qualification

Local controls ran through the packaged verifier on Python 3.12.14.
Every episode started a new policy process. Each matched set had
identical initial observations, and a footprint check confirmed an
open centerline route to the dock in every episode.

| Control | Docks | Reward | Outcome |
| --- | ---: | ---: | --- |
| [Oracle](local-v1.1.0/oracle/diagnostics.json) | 16/16 | 1.0 | Docks after approaching each closure, including both in every two-closure mission. |
| [No-op](local-v1.1.0/no-op/diagnostics.json) | 0/16 | 0.0 | Finishes at the starting pose. |
| [Fixed route](local-v1.1.0/fixed-route/diagnostics.json) | 4/16 | 0.25 | Docks on clear routes and stops at the first closure without collision. |
| [One replan](local-v1.1.0/one-replan/diagnostics.json) | 8/16 | 0.5 | Docks after the first detour and stops at the second closure without collision. |
| [Saved Luna v1.0.2 policy](local-v1.1.0/luna-v1.0.2/diagnostics.json) | 1/16 | 0.0625 | Docks in one clear episode and collides in the other 15 on the new geometry. |

All three public practice missions passed with the reference. The
official scenarios use different layouts and pallet positions. The
public image context contains the practice simulator, starter, and
instructions. Reference code, closure placement, and the grader are
outside that context. Default Harbor lint reported no findings. The
optional all-rules lint reports the inherited root agent user. The
separate verifier runs the submitted policy as UID 1001 with no network.

The old task and its valid 1.0 result remain intact. There are zero fresh
model attempts on v1.1.0. The task sets a 900-second agent limit and two
CPUs and 4 GiB of RAM for both the agent and verifier environments.

## Run the remaining Harbor controls

Docker Desktop was unavailable on the Mac after the disk-space failure.
Run from the repository root once the Docker daemon is available:

```bash
task=tasks/warehouse-recovery-v1.1.0
jobs=results/warehouse-recovery/harbor-controls-v1.1.0
harbor run -p "$task" -e docker -a oracle -r 0 -o "$jobs" --job-name oracle
harbor run -p "$task" -e docker -a nop -r 0 -o "$jobs" --job-name nop
```

Expected rewards are 1.0 and 0.0, with both trials completing without
exceptions. These commands use local controls and require no model
credentials.
