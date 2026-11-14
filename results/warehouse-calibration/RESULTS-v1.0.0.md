# Warehouse Cart Calibration v1.0.0 model results

Four fresh GPT-6 Luna trials used Codex CLI 0.163.0 at medium reasoning
effort through Harbor 0.25.0 and Docker. Each trial had a 15-minute
agent budget, two CPUs, and 4 GiB. Web search and MCP were disabled.
The agent's network allowed the inference host, and verification ran
in a separate offline container.

| Attempt | Reward | Correct forecasts | Calibration ticks | Max position error (mm) | Max heading error (rad) | Harbor wall time | Artifacts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 1.0000 | 60/60 | 14 | 0.01651 | 0.00002054 | 2m 38s | [Trace](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.0.0__47SghuM/agent/trajectory.json), [controller](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.0.0__47SghuM/artifacts/app/policy.py), [verifier](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.0.0__47SghuM/verifier/diagnostics.json), [Harbor result](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-01/warehouse-calibration-v1.0.0__47SghuM/result.json) |
| 2 | 1.0000 | 60/60 | 20 | 0.01121 | 0.00001785 | 3m 13s | [Trace](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.0.0__TZ6hnVP/agent/trajectory.json), [controller](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.0.0__TZ6hnVP/artifacts/app/policy.py), [verifier](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.0.0__TZ6hnVP/verifier/diagnostics.json), [Harbor result](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-02/warehouse-calibration-v1.0.0__TZ6hnVP/result.json) |
| 3 | 1.0000 | 60/60 | 20 | 0.01075 | 0.00001226 | 2m 26s | [Trace](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.0.0__v7n3aqx/agent/trajectory.json), [controller](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.0.0__v7n3aqx/artifacts/app/policy.py), [verifier](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.0.0__v7n3aqx/verifier/diagnostics.json), [Harbor result](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-03/warehouse-calibration-v1.0.0__v7n3aqx/result.json) |
| 4 | 1.0000 | 60/60 | 20 | 0.01784 | 0.00003030 | 2m 25s | [Trace](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.0.0__tyQ2cgR/agent/trajectory.json), [controller](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.0.0__tyQ2cgR/artifacts/app/policy.py), [verifier](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.0.0__tyQ2cgR/verifier/diagnostics.json), [Harbor result](harbor-luna4-v1.0.0-docker-2026-11-12/warehouse-calibration-v1.0.0-luna-docker-2026-11-12-04/warehouse-calibration-v1.0.0__tyQ2cgR/result.json) |

Luna solved all four attempts on the same frozen task. Every
submission used a camera reading for all 12 carts. All trials
completed without Harbor exceptions and used distinct sessions
and submitted controllers. Recorded model spend was
`$0.04373`. The
[ledger](harbor-luna4-v1.0.0-docker-2026-11-12/ledger.json) records the task checksum and
raw result paths.

The first two controllers fitted the wheel responses from isolated
commands, then used the camera position to estimate separate forward
and reverse slip. The first used 14 of 20 calibration ticks. These
results show that Luna can recover the parameters of this exact
kinematic model within the measurement budget.

A follow-up could introduce a repeatable load-dependent change in
traction. The agent would choose experiments at different speeds
and forecast a command sequence that crosses the traction change.
The test would require a new version and a fresh observability
check. The [qualification controls](QUALIFICATION-v1.0.0.md) show
what the current version measures.
