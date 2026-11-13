# Warehouse recovery v1.1.2 runtime audit

An offline Docker replay ran the four saved Luna policies through the
frozen v1.1.1 verifier. It reproduced all four scores and all 64 outcome
categories. In 62 episodes, the full diagnostics matched. The two
early exits in attempt 4 repeated with different final ticks.

A targeted probe measured about 10 seconds of child CPU time and
observed SIGKILL before verifier cleanup on both episodes. The policy
had not reached the published 12-second wall-time deadline. Removing
only the CPU limit let one episode dock in the targeted probe. The
second reached the wall-time deadline in that probe.

v1.1.2 removes the 10-second CPU limit from practice and grading. The
same 12-second wall-time deadline, 16 episodes, motion limits, and
scoring rules apply. The public instructions also specify the existing
memory, file-size, and request-size limits.

| Saved Luna policy | Official v1.1.1 | v1.1.2 replay | Observation |
| --- | ---: | ---: | --- |
| 1 | 1.000 | 1.000 | 16 docks |
| 2 | 0.500 | 0.500 | 8 misses at the motion limit with incorrect heading |
| 3 | 0.625 | 0.625 | 4 wall collisions and 2 heading misses at the motion limit |
| 4 | 0.000 | 0.125 | Both formerly CPU-limited episodes docked in this replay. The 14 wall collisions reproduced. |

The first three policies reproduced every episode diagnostic under the
corrected verifier. The fourth policy's two near-deadline episodes are
sensitive to runtime load, as the difference between the targeted
probe and full replay shows. These are saved-policy replays, with the
original model trials archived in the [v1.1.1 results](RESULTS-v1.1.1.md).

- [Original-version replay](runtime-audit-v1.1.2/v1.1.1-replay.json)
- [CPU and wall-time probe](runtime-audit-v1.1.2/cpu-probe.json)
- [Corrected replay](runtime-audit-v1.1.2/v1.1.2-replay.json)
- [Corrected attempt 4 diagnostics](runtime-audit-v1.1.2/v1.1.2-attempt-4-diagnostics.json)

Harbor lint passed. The [oracle](harbor-controls-v1.1.2/oracle/result.json)
scored 16/16 and the [no-op](harbor-controls-v1.1.2/nop/result.json) scored
0/16. Both used the separate Docker verifier, completed without
exceptions, and recorded the same task checksum. The
[freeze manifest](frozen-v1.1.2.json) records the qualified package.

The [fresh v1.1.2 Luna batch](RESULTS-v1.1.2.md) ran after qualification.
