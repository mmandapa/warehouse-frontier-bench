# Warehouse Cart Benchmark

Can a coding agent write a controller that stays reliable when its model
of the world is incomplete? A physically plausible controller can
still take a blocked route or predict the wrong stopping point. These
two CPU-only Harbor simulations test whether agents can revise a plan
during a drive and choose measurements that improve a prediction.

| Task | What the agent gets and does | A case passes when |
| --- | --- | --- |
| [Cart Recovery](tasks/warehouse-recovery/README.md) | A survey map, candidate start poses, a simulator client, and three practice missions. Use lidar, odometry, a gyro, and visible markers to find the cart, drive around uncharted closures, and dock. | The cart docks without collision, within 0.22 m and 0.12 rad of the target pose, with no motion pending. |
| [Cart Calibration](tasks/warehouse-calibration/README.md) | Motion equations, a simulator client, and two practice cases. Use up to 30 command ticks and two camera measurements to learn how a serviced cart moves, then forecast its endpoint for new command sequences. | A forecast is within 0.045 m and 0.025 rad of the simulated endpoint. |

Both tasks take a Python standard library policy at `/app/policy.py`.
Recovery grades the policy's actions. Calibration grades its position
and heading forecasts.

## Scoring and validity

The offline verifier writes the **fraction of held-out cases passed**
to `/logs/verifier/reward.json`. Each case is binary. An incomplete
dock or a forecast outside either tolerance earns zero for that case. Full credit
requires every case to pass. We chose fractional reward because an
all-or-nothing score would treat a 13/16 recovery policy the same as a
5/16 policy. That difference gives a group-relative RL method a reward
signal even if neither submission solves the full suite. The average
can hide repeated failures, so the verifier also records per-case
diagnostics. The reported experiments evaluate fixed models.

- Recovery grades 16 missions. Each of four layouts keeps the start,
  dock, and initial observations fixed across clear routes, one closure,
  two closures, and two closures with a change in grip. A controller
  must use what it learns during the drive to stay on a viable route.
- Calibration grades five forecasts per cart across 12 carts. Paired carts can
  produce identical encoder and gyro readings under the same commands
  while traveling different distances. Limited camera measurements can
  resolve that difference if the probe commands reveal how traction
  varies with direction and recent effort.

The agent image contains the practice workspace. Held-out cases and
reference policies stay outside it. A separate offline verifier starts
a fresh policy process for each mission or cart. Model trials disabled
web search, allowed network access only to the inference host, and
started with fresh agent sessions. Both Docker oracles earned 1.0 and
both no-op controls earned 0.0. A Calibration control that fit constant
traction using both camera readings passed only 16/60 forecasts.
[Recovery qualification](results/warehouse-recovery/QUALIFICATION.md) ·
[Calibration qualification](results/warehouse-calibration/QUALIFICATION.md)

## Model results

All attempts used Codex CLI 0.163.0 at medium reasoning effort through
Harbor 0.25.0 on Docker. Each score shows the verifier reward and the
number of cases passed. The task reports link to the trial artifacts.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 1 | 0.3125 (5/16) | Eight collisions and three motion-limit misses. |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 2 | 0.8125 (13/16) | Three missions with two closures hit the motion limit. |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 3 | 0.3750 (6/16) | Ten collisions, including repeated collisions on two layouts. |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 4 | 0.5625 (9/16) | Six collisions and one incorrect final heading. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 1 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 2 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 3 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 4 | 1.0000 (16/16) | Docked on all 16 missions without collision. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 1 | 0.9333 (56/60) | Four position misses, three in sustained reverse. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 2 | 0.8667 (52/60) | Eight position misses, four in sustained reverse. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 3 | 0.9667 (58/60) | Two position misses, both in sustained reverse. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 4 | 1.0000 (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 1 | 1.0000 (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 2 | 1.0000 (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 3 | 1.0000 (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 4 | 1.0000 (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 1 | 0.9000 (54/60) | Six position misses. Divided the fitted load coefficient by the traction multiplier. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 2 | 0.8667 (52/60) | Eight position misses. The fit was sensitive to camera rounding. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 3 | 0.0000 (0/60) | The submitted policy had a Python syntax error. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 4 | 0.8000 (48/60) | Twelve position misses. All heading checks passed. |
| [Calibration](results/warehouse-calibration/RESULTS.md#retest-after-attempt-3) | GPT-6 Luna / Codex | Follow-up to original 3 | 0.9500 (57/60) | Three position misses, all in sustained reverse. |

One Calibration launch stopped at the API quota and has no score.
[Launch record](results/warehouse-calibration/harbor-luna-fresh/quota-blocked-launch.json)

**Recovery.** Luna's best policy docked on every clear and single-closure
route, then reached the motion limit in three two-closure missions.
Other Luna policies also collided on clear routes, so the gap includes
basic navigation and control. Astra completed every mission under the
same limits. Replaying the eight saved policies against the corrected
final-tick rule reproduced every mission pass/fail outcome.
[Recovery replay](results/warehouse-recovery/QUALIFICATION.md#final-tick-correction)

**Calibration.** In the fresh batch, Luna passed every heading check.
Three policies missed 14 positions in total, nine on sustained reverse
drives. The 60/60 policy used varied drive commands and fit gyro and
camera data jointly. For one original policy, replaying its probe with
unrounded camera positions eliminated eight forecast misses in a
controlled calculation. The oracle passed with the published camera
resolution using a different probe.

Each attempt on a task faced the same fixed cases. Scores describe
coverage of those cases, and the small batches limit conclusions
about other simulators or agent settings. For Recovery, a useful harder comparison would vary closure
placement on matched, reachable layouts. Calibration can vary traction
and camera precision while keeping the same probe budget. Comparing a
fixed informative probe with agent-chosen probes would help isolate
measurement choice from model fitting.

## Run the tasks

With Docker running, install Harbor and run the qualification controls
from the repository root. Expect reward 1.0 for oracle and 0.0 for no-op.

```sh
uv tool install 'harbor==0.25.0'
for task in tasks/warehouse-recovery tasks/warehouse-calibration; do
  harbor lint "$task"
  harbor run -p "$task" -e docker -a oracle -r 0 -o "jobs/${task##*/}" --job-name oracle
  harbor run -p "$task" -e docker -a nop -r 0 -o "jobs/${task##*/}" --job-name nop
done
```

Set your OpenAI credentials on the host to reproduce the four-attempt
Luna batches. These commands make paid model calls.

```sh
harbor run -c configs/recovery-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/recovery-luna
harbor run -c configs/calibration-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/calibration-luna
```

Each environment uses two CPUs and 4 GiB of RAM, with a 15-minute agent
limit and a four-minute verifier limit. The recorded model trials
used about 91 minutes of combined Harbor trial time.
