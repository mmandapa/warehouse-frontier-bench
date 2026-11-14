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

All three public practice missions passed with the reference. The
official scenarios use different layouts and pallet positions. The
public image context contains the practice simulator, starter, and
instructions. Reference code, closure placement, and the grader are
outside that context. Default Harbor lint reported no findings. The
optional all-rules lint reports the inherited root agent user. The
separate verifier runs the submitted policy as UID 1001 with no network.

These controls were recorded during development. For runnable commands
and qualification of the submitted task, see the
[v1.1.2 report](QUALIFICATION.md).
