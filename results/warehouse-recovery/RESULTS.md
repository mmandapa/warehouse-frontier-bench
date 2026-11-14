# Warehouse recovery model results

The tables report the original Harbor trials. The distributed task
includes a correction that lets a controller call `finish()` after
using its final simulation tick. See the
[qualification report](QUALIFICATION.md#final-tick-correction) for the
replay of the saved policies against the corrected grader.

Four fresh Codex CLI 0.163.0 trials used `openai/gpt-6-luna` at medium
reasoning effort. Harbor ran them sequentially in Docker with a
15-minute agent budget, two CPUs, and 4 GiB per trial. Agent web search
was disabled and network access was limited to the inference host.
All four trials used the task checksum from the qualification controls
and completed with zero Harbor exceptions.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| Recovery | GPT-6 Luna / Codex | 1 | 0.3125 (5/16) | Eight collisions and three misses at the motion limit with incorrect heading. |
| Recovery | GPT-6 Luna / Codex | 2 | 0.8125 (13/16) | Three misses at the motion limit, all on routes with two closures. |
| Recovery | GPT-6 Luna / Codex | 3 | 0.3750 (6/16) | Ten collisions. In two layouts the same collision occurred across all four matched scenarios. |
| Recovery | GPT-6 Luna / Codex | 4 | 0.5625 (9/16) | Six collisions and one finish with incorrect heading near the dock. |

<details>
<summary>Trial artifacts and timing</summary>

| Attempt | Harbor wall time | Artifacts |
| --- | ---: | --- |
| 1 | 7m 28s | [Trace](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-01/warehouse-recovery-v1.1.2__B7XZKxp/agent/trajectory.json), [policy](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-01/warehouse-recovery-v1.1.2__B7XZKxp/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-01/warehouse-recovery-v1.1.2__B7XZKxp/verifier/diagnostics.json) |
| 2 | 7m 22s | [Trace](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-02/warehouse-recovery-v1.1.2__UTLAitt/agent/trajectory.json), [policy](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-02/warehouse-recovery-v1.1.2__UTLAitt/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-02/warehouse-recovery-v1.1.2__UTLAitt/verifier/diagnostics.json) |
| 3 | 5m 54s | [Trace](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-03/warehouse-recovery-v1.1.2__FQiSncA/agent/trajectory.json), [policy](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-03/warehouse-recovery-v1.1.2__FQiSncA/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-03/warehouse-recovery-v1.1.2__FQiSncA/verifier/diagnostics.json) |
| 4 | 3m 50s | [Trace](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-04/warehouse-recovery-v1.1.2__mBRyrmC/agent/trajectory.json), [policy](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-04/warehouse-recovery-v1.1.2__mBRyrmC/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-luna-docker-2026-11-12-04/warehouse-recovery-v1.1.2__mBRyrmC/verifier/diagnostics.json) |

</details>

Luna fully solved 0/4 attempts. The mean reward was **0.515625**.
The batch took 24m 45s from the first trial start
to the last trial finish and cost an estimated
`$0.10525`. The [batch ledger](harbor-luna4-v1.1.2-docker-2026-11-12/ledger.json)
records per-trial cost and raw result paths.

An [offline replay](harbor-luna4-v1.1.2-docker-2026-11-12/offline-replay.json) of the four saved
policies with the frozen v1.1.2 verifier reproduced all 64 episode
diagnostics exactly. The 31 misses comprised 24 collisions, six
episodes reaching the 2,100-tick motion limit, and one finish with
excessive heading error. No scored episode reached the verifier
wall-clock deadline or ended with an early policy exit.

The strongest attempt passed every clear and single-closure case.
It reached the motion limit in three double-closure cases. In two of
those, the cart remained 16.13 m from the dock. In the third, its final
position and heading were inside tolerance when the motion budget
expired, before a successful finish. The other three attempts all
had collisions on clear routes. Across the batch, the four scenario
groups recorded 8/16, 8/16, 10/16, and 7/16 docks respectively.
The same layout families appear in each group. The observed misses
show difficulty delivering a reliable controller across layouts.
The episode totals alone give limited evidence about the effect of
route closures.

See the [v1.1.2 qualification audit](QUALIFICATION.md) for the
runtime correction and oracle/no-op results.

## Astra comparison

Four fresh `openai/gpt-6-astra` attempts used the same frozen task,
Codex version, medium reasoning effort, and 15-minute agent budget as
Luna. Astra docked in all 16 episodes on every attempt, with zero
collisions or Harbor exceptions.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| Recovery | GPT-6 Astra / Codex | 1 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| Recovery | GPT-6 Astra / Codex | 2 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| Recovery | GPT-6 Astra / Codex | 3 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| Recovery | GPT-6 Astra / Codex | 4 | 1.0000 (16/16) | Docked on all 16 missions without collision. |

<details>
<summary>Trial artifacts and timing</summary>

| Attempt | Harbor wall time | Recorded cost | Artifacts |
| --- | ---: | ---: | --- |
| 1 | 5m 10s | $1.62804 | [Trace](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-01/warehouse-recovery-v1.1.2__9xYGkxq/agent/trajectory.json), [policy](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-01/warehouse-recovery-v1.1.2__9xYGkxq/artifacts/app/policy.py), [verifier](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-01/warehouse-recovery-v1.1.2__9xYGkxq/verifier/diagnostics.json), [Harbor result](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-01/warehouse-recovery-v1.1.2__9xYGkxq/result.json) |
| 2 | 4m 14s | $1.04708 | [Trace](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-02/warehouse-recovery-v1.1.2__JdfbzHS/agent/trajectory.json), [policy](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-02/warehouse-recovery-v1.1.2__JdfbzHS/artifacts/app/policy.py), [verifier](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-02/warehouse-recovery-v1.1.2__JdfbzHS/verifier/diagnostics.json), [Harbor result](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-02/warehouse-recovery-v1.1.2__JdfbzHS/result.json) |
| 3 | 3m 36s | $0.88065 | [Trace](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-03/warehouse-recovery-v1.1.2__RpJZznW/agent/trajectory.json), [policy](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-03/warehouse-recovery-v1.1.2__RpJZznW/artifacts/app/policy.py), [verifier](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-03/warehouse-recovery-v1.1.2__RpJZznW/verifier/diagnostics.json), [Harbor result](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-03/warehouse-recovery-v1.1.2__RpJZznW/result.json) |
| 4 | 3m 40s | $0.85776 | [Trace](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-04/warehouse-recovery-v1.1.2__jzoaGxX/agent/trajectory.json), [policy](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-04/warehouse-recovery-v1.1.2__jzoaGxX/artifacts/app/policy.py), [verifier](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-04/warehouse-recovery-v1.1.2__jzoaGxX/verifier/diagnostics.json), [Harbor result](harbor-astra1-v1.1.2-docker-2026-11-12/warehouse-recovery-v1.1.2-astra-docker-2026-11-12-04/warehouse-recovery-v1.1.2__jzoaGxX/result.json) |

</details>

Recorded Astra spend was `$4.41353` across four attempts.
The three follow-up attempts accounted for `$2.78548`.

Astra fully solved 4/4 attempts and averaged 1.0000. Luna fully solved
0/4 and averaged 0.515625. Each attempt used the same 16 episodes, so
the comparison uses the same scenarios and Codex settings.

In the first Astra attempt, the controller estimated wheel traction
from encoder and gyro readings, checked its path against obstacles detected during the drive, and verified the settled dock pose before
finishing.
