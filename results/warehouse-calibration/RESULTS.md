# Warehouse Cart Calibration model results

The recorded model trials use the same agent workspace, instructions,
simulator, and grader as the task linked from the repository README.
The task package label and its top-level README were updated for
distribution. Original trial IDs and hashes are retained below.

Four runnable GPT-6 Luna submissions passed **211/240 forecasts (87.9%)**
on the frozen task. The results were **54/60, 52/60, 48/60, and 57/60**.
The last score came from a fresh retest after attempt 3 exited with a
Python syntax error. Offline replay reproduced the retest's three
position misses on sustained reverse drives.

| Attempt with a runnable submission | Correct forecasts | Reward |
| --- | ---: | ---: |
| 1 | 54/60 | 0.9000 |
| 2 | 52/60 | 0.8667 |
| 4 | 48/60 | 0.8000 |
| Retest | 57/60 | 0.9500 |

## Original four attempts

GPT-6 Luna fully solved 0 of 4 attempts in the original batch. The
original batch includes the syntax-error submission and its zero reward.

| Attempt | Reward | Correct forecasts | Harbor wall time | Main finding | Artifacts |
| --- | ---: | ---: | ---: | --- | --- |
| 1 | 0.9000 | 54/60 | 3m 05s | Divided the fitted load coefficient by the baseline traction multiplier, although the simulator adds the base and load terms. | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.1.0__w6JJ6vx/result.json) |
| 2 | 0.8667 | 52/60 | 3m 04s | Used separate forward and reverse probes that did not vary direction and load enough to distinguish both slip terms at camera resolution. | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.1.0__2i3B9DT/result.json) |
| 3 | 0.0000 | 0/60 | 2m 38s | Submitted a Python file with an unclosed parenthesis on line 136. It exited before issuing any command. | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.1.0__3AmDaW3/result.json) |
| 4 | 0.8000 | 48/60 | 3m 25s | Fit slip from two camera poses with a prior toward the middle of the coefficient ranges. Heading stayed accurate, but 12 position forecasts missed. | [Trace](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/agent/trajectory.json), [Policy](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/artifacts/app/policy.py), [Verifier](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/verifier/diagnostics.json), [Harbor](harbor-luna4-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.1.0__WRnAKRg/result.json) |

Mean reward was **0.6417** across all trials. The three runnable policies
scored 154/180 forecasts (0.8556). All 26 misses in those policies were
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

The four fresh trials used Codex CLI 0.163.0 at medium reasoning effort
and Harbor 0.25.0 on Docker. Each had a 15-minute agent limit, two CPUs,
and 4 GiB. Web search was disabled; the agent network allowed the
inference host, and the verifier ran offline. All four had distinct
session IDs, resume disabled, the qualified task checksum, and no
Harbor exceptions. An [offline replay](harbor-luna4-v1.1.0-docker-2026-11-12/offline-replay.json)
of all four policies reproduced every diagnostic exactly. The batch took
12m 26s from first launch to last result and cost $0.05516 in recorded
model spend. See the [ledger](harbor-luna4-v1.1.0-docker-2026-11-12/batch-ledger.json)
and [qualification report](QUALIFICATION.md).

These trials show calibration failures on this simulator and setup.
A next study could
hold the estimator and cart fixed while comparing agent-chosen probes
against a known informative probe. No stronger-model run was performed
on this task version.

## Retest after attempt 3

One fresh trial used the same frozen package and harness settings to
get another observation of a runnable calibration policy after the
syntax error in attempt 3. It scored **0.9500 (57/60)** in
3m 59s, with no Harbor exceptions. All three misses were sustained
reverse forecasts. Position errors were 9.35–13.34 cm against the
4.5 cm tolerance; heading passed for every forecast. The
[offline replay](harbor-luna-followup-v1.1.0-docker-2026-11-12/offline-replay.json) reproduced
every diagnostic. Recorded spend was $0.01630.
Artifacts: [trace](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/agent/trajectory.json), [policy](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/artifacts/app/policy.py), [verifier diagnostics](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/verifier/diagnostics.json), [Harbor result](harbor-luna-followup-v1.1.0-docker-2026-11-12/warehouse-calibration-v1.1.0-luna-followup-01/warehouse-calibration-v1.1.0__6tqXHM6/result.json).

Across the five launches, Luna fully solved zero.
