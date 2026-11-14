# Warehouse Cart Calibration model results

The simulator, agent instructions, and grader are the same across the
recorded model trials. The published package uses different distribution
metadata from the original batch. The ledgers link to the checksums and
original trial records.

## Fresh four attempts

Four fresh GPT-6 Luna attempts used the published Cart Calibration package.
All four policies submitted forecasts for every cart. The batch passed
**226/240 (94.2%)** forecasts and solved all 60 in one attempt.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| Calibration | GPT-6 Luna / Codex | 1 | 93.33% (56/60) | Four position misses. Three in sustained reverse and one in mixed direction. |
| Calibration | GPT-6 Luna / Codex | 2 | 86.67% (52/60) | Eight position misses. Four in sustained reverse, three in mixed direction, and one in sustained forward. |
| Calibration | GPT-6 Luna / Codex | 3 | 96.67% (58/60) | Two position misses, both in sustained reverse. |
| Calibration | GPT-6 Luna / Codex | 4 | 100% (60/60) | All forecasts met tolerance. |

<details>
<summary>Trial artifacts and timing</summary>

| Attempt | Harbor wall time | Artifacts |
| --- | ---: | --- |
| 1 | 3m 46s | [Trace](harbor-luna-fresh/calibration-luna-fresh-01/warehouse-calibration__8NHu45B/agent/trajectory.json), [Policy](harbor-luna-fresh/calibration-luna-fresh-01/warehouse-calibration__8NHu45B/artifacts/app/policy.py), [Verifier](harbor-luna-fresh/calibration-luna-fresh-01/warehouse-calibration__8NHu45B/verifier/diagnostics.json), [Harbor](harbor-luna-fresh/calibration-luna-fresh-01/warehouse-calibration__8NHu45B/result.json) |
| 2 | 4m 12s | [Trace](harbor-luna-fresh/calibration-luna-fresh-02/warehouse-calibration__me6kGCr/agent/trajectory.json), [Policy](harbor-luna-fresh/calibration-luna-fresh-02/warehouse-calibration__me6kGCr/artifacts/app/policy.py), [Verifier](harbor-luna-fresh/calibration-luna-fresh-02/warehouse-calibration__me6kGCr/verifier/diagnostics.json), [Harbor](harbor-luna-fresh/calibration-luna-fresh-02/warehouse-calibration__me6kGCr/result.json) |
| 3 | 5m 42s | [Trace](harbor-luna-fresh/calibration-luna-fresh-03/warehouse-calibration__XsAaVbd/agent/trajectory.json), [Policy](harbor-luna-fresh/calibration-luna-fresh-03/warehouse-calibration__XsAaVbd/artifacts/app/policy.py), [Verifier](harbor-luna-fresh/calibration-luna-fresh-03/warehouse-calibration__XsAaVbd/verifier/diagnostics.json), [Harbor](harbor-luna-fresh/calibration-luna-fresh-03/warehouse-calibration__XsAaVbd/result.json) |
| 4 | 2m 04s | [Trace](harbor-luna-fresh/calibration-luna-fresh-04/warehouse-calibration__kXV6zo9/agent/trajectory.json), [Policy](harbor-luna-fresh/calibration-luna-fresh-04/warehouse-calibration__kXV6zo9/artifacts/app/policy.py), [Verifier](harbor-luna-fresh/calibration-luna-fresh-04/warehouse-calibration__kXV6zo9/verifier/diagnostics.json), [Harbor](harbor-luna-fresh/calibration-luna-fresh-04/warehouse-calibration__kXV6zo9/result.json) |

</details>

The 60/60 policy fit the motion model jointly to gyro and camera readings
using bounded least squares from several starting points. The three
other policies passed every heading check but missed 14 positions.

[Offline replay](harbor-luna-fresh/offline-replay.json) reproduced all four
verifier diagnostics. [Batch ledger](harbor-luna-fresh/batch-ledger.json)
records the runs and $0.08200 in recorded
model spend. The [launch blocked by API quota](harbor-luna-fresh/quota-blocked-launch.json)
has no model score.

## Astra comparison

GPT-6 Astra used the same Cart Calibration package as the fresh Luna
batch, with Codex CLI 0.163.0 at medium reasoning effort, Harbor 0.25.0
on Docker, two CPUs, 4 GiB of RAM, and a 15-minute agent limit.
All four Astra submissions scored **100% (60/60)**, for **240/240** forecasts.
The fresh Luna batch passed **94.17% (226/240)** and scored 60/60 in one
of four attempts.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| Calibration | GPT-6 Astra / Codex | 1 | 100% (60/60) | All forecasts met tolerance. Maximum position error was 3.35 mm. |
| Calibration | GPT-6 Astra / Codex | 2 | 100% (60/60) | All forecasts met tolerance. Maximum position error was 4.76 mm. |
| Calibration | GPT-6 Astra / Codex | 3 | 100% (60/60) | All forecasts met tolerance. Maximum position error was 4.82 mm. |
| Calibration | GPT-6 Astra / Codex | 4 | 100% (60/60) | All forecasts met tolerance. Maximum position error was 4.83 mm. |

<details>
<summary>Trial artifacts and timing</summary>

| Attempt | Harbor wall time | Artifacts |
| --- | ---: | --- |
| 1 | 2m 53s | [Trace](harbor-astra/calibration-astra-01/warehouse-calibration__iYxrMov/agent/trajectory.json), [Policy](harbor-astra/calibration-astra-01/warehouse-calibration__iYxrMov/artifacts/app/policy.py), [Verifier](harbor-astra/calibration-astra-01/warehouse-calibration__iYxrMov/verifier/diagnostics.json), [Harbor](harbor-astra/calibration-astra-01/warehouse-calibration__iYxrMov/result.json) |
| 2 | 4m 05s | [Trace](harbor-astra/calibration-astra-02/warehouse-calibration__t2Ajwpg/agent/trajectory.json), [Policy](harbor-astra/calibration-astra-02/warehouse-calibration__t2Ajwpg/artifacts/app/policy.py), [Verifier](harbor-astra/calibration-astra-02/warehouse-calibration__t2Ajwpg/verifier/diagnostics.json), [Harbor](harbor-astra/calibration-astra-02/warehouse-calibration__t2Ajwpg/result.json) |
| 3 | 5m 20s | [Trace](harbor-astra/calibration-astra-03/warehouse-calibration__oE6Y8L2/agent/trajectory.json), [Policy](harbor-astra/calibration-astra-03/warehouse-calibration__oE6Y8L2/artifacts/app/policy.py), [Verifier](harbor-astra/calibration-astra-03/warehouse-calibration__oE6Y8L2/verifier/diagnostics.json), [Harbor](harbor-astra/calibration-astra-03/warehouse-calibration__oE6Y8L2/result.json) |
| 4 | 5m 15s | [Trace](harbor-astra/calibration-astra-04/warehouse-calibration__biRb848/agent/trajectory.json), [Policy](harbor-astra/calibration-astra-04/warehouse-calibration__biRb848/artifacts/app/policy.py), [Verifier](harbor-astra/calibration-astra-04/warehouse-calibration__biRb848/verifier/diagnostics.json), [Harbor](harbor-astra/calibration-astra-04/warehouse-calibration__biRb848/result.json) |

</details>

Offline replay reproduced all four policies' verifier diagnostics. Recorded
model spend was $4.47. [Offline replay](harbor-astra/offline-replay.json) · [Batch ledger](harbor-astra/batch-ledger.json)

Astra's largest position error on the scored suite was 4.83 mm against a
45 mm tolerance. The fixed suite reached its scoring ceiling for Astra.
A follow-up could vary how traction responds to sustained motor commands and
change camera resolution on new carts with the same measurement budget.

## Original four attempts

GPT-6 Luna fully solved 0 of 4 attempts in the original batch. The
original batch includes the syntax-error submission and its zero reward.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| Calibration | GPT-6 Luna / Codex | 1 | 90% (54/60) | Divided the fitted load coefficient by the baseline traction multiplier, although the simulator adds the base and load terms. |
| Calibration | GPT-6 Luna / Codex | 2 | 86.67% (52/60) | Used separate forward and reverse probes that did not vary direction and load enough to distinguish both slip terms at camera resolution. |
| Calibration | GPT-6 Luna / Codex | 3 | 0% (0/60) | Submitted a Python file with an unclosed parenthesis on line 136. It exited before issuing any command. |
| Calibration | GPT-6 Luna / Codex | 4 | 80% (48/60) | Fit slip from two camera poses with a prior toward the middle of the coefficient ranges. Heading stayed accurate, but 12 position forecasts missed. |

<details>
<summary>Trial artifacts and timing</summary>

| Attempt | Harbor wall time | Artifacts |
| --- | ---: | --- |
| 1 | 3m 05s | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/result.json) |
| 2 | 3m 04s | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/result.json) |
| 3 | 2m 38s | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/result.json) |
| 4 | 3m 25s | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/result.json) |

</details>

The mean score was **64.17% (154/240)** across all four trials. The three
runnable policies passed 85.56% (154/180) of forecasts. All 26 misses were
position errors beyond 0.045 m; their maximum heading error was below
0.00004 rad against a 0.025 rad tolerance. They used all 30 command ticks
and both camera readings on every cart. All three passed every pause
and intermittent-command forecast. The misses were on sustained
forward, sustained reverse, or mixed-direction commands.

For attempts 1 and 2, a local calculation held the wheel parameters at
their true values and reconstructed the camera equations from the saved
probe commands. Applying attempt 1's extra division with millimeter
rounding reproduced the same six misses. Removing that division and using
unrounded coordinates yielded 60/60; either change alone left six misses.
For attempt 2, its fit yielded 60/60 with unrounded camera positions and
reproduced the same eight misses with the published millimeter rounding.
This shows why a model can estimate steering well and still predict the
wrong travel distance. The reference used the same camera resolution and
scored 60/60 with a different probe.

Both Luna batches used Codex CLI 0.163.0 at medium reasoning effort
and Harbor 0.25.0 on Docker. Each had a 15-minute agent limit, two CPUs,
and 4 GiB. Web search was disabled. The agent network allowed only the
inference host, and the verifier ran offline. Neither batch had a
Harbor exception. An [offline replay](harbor-luna4-v1.1.0-docker-2026-11-12/offline-replay.json)
of the original four policies reproduced every diagnostic exactly.
That batch took 12m 26s from first launch to last result and cost $0.05516 in recorded
model spend. See the [ledger](harbor-luna4-v1.1.0-docker-2026-11-12/batch-ledger.json)
and [qualification report](QUALIFICATION.md).

These trials show calibration failures on this simulator and setup.
A next study could
hold the estimator and cart fixed while comparing agent-chosen probes
against a known informative probe.

## Retest after attempt 3

A separate trial after the original attempt 3 syntax error used the
same frozen package and Codex settings. It completed in 3m 59s.
The three missed forecasts had position errors of 9.35–13.34 cm against
a 4.5 cm tolerance. Every heading forecast passed. The
[offline replay](harbor-luna-followup-v1.1.0-docker-2026-11-12/offline-replay.json) reproduced
every diagnostic. Recorded spend was $0.01630.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| Calibration | GPT-6 Luna / Codex | Follow-up to original 3 | 95% (57/60) | Three position misses, all in sustained reverse. |

[Trace](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/agent/trajectory.json), [policy](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/artifacts/app/policy.py), [verifier diagnostics](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/verifier/diagnostics.json), [Harbor result](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/result.json).

Across these five earlier launches, Luna fully solved zero.
