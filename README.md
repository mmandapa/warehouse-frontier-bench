# Warehouse Cart Benchmark

The Warehouse Cart Benchmark is a science and engineering benchmark
focused on robotics simulation and decision-making under uncertainty.
It tests whether coding agents can write policies that turn incomplete
observations into reliable control, prediction, and coordination.

Each task starts with a different unknown. Recovery hides the cart's
initial pose and some route obstructions. Calibration hides how wheel
slip changes under load. Dispatch announces the active maintenance order
after some move decisions. The policy must use the observations and
commands available in its simulator to finish within the task's budget.

Across these tasks, a plausible local decision can break the overall
objective. A route on the survey map can be blocked, a motion model
that fits the probe can miss a reverse forecast, and routes that look
feasible for individual carts can leave the fleet stuck. The benchmark
records those consequences through missed docks, forecast errors, and
missed deliveries.

- **Cart Recovery** tests whether a policy can locate the cart from
  sensor data and revise its route when it discovers a blockage absent
  from the map. It must still reach the dock safely within the motion
  budget.
- **Cart Calibration** tests whether a policy can choose measurements
  that reveal how the cart moves and use them to predict its final
  position and heading for command sequences it hasn't tried.
- **Warehouse Dispatch During Maintenance** tests whether a dispatcher
  can coordinate carts through shared lanes while either of two announced
  maintenance calendars may still take effect.

| Task | What the agent gets and does | A case passes when |
| --- | --- | --- |
| [Cart Recovery](tasks/warehouse-recovery/README.md) | A survey map, candidate start poses, a simulator client, and three practice missions. Use lidar, odometry, a gyro, and visible markers to find the cart, drive around uncharted closures, and dock. | The cart docks without collision, within 0.22 m and 0.12 rad of the target pose, with no motion pending. |
| [Cart Calibration](tasks/warehouse-calibration/README.md) | Motion equations, a simulator client, and two practice cases. Use up to 30 command ticks and two camera measurements to learn how a serviced cart moves, then forecast its endpoint for new command sequences. | A forecast is within 0.045 m and 0.025 rad of the simulated endpoint. |
| [Warehouse Dispatch During Maintenance](tasks/warehouse-dispatch-windows/README.md) | A lane graph, up to four carts, pickup and delivery deadlines, two possible maintenance calendars, and four practice shifts. Dispatch move batches before and after the calendar is selected. | Every delivery meets its simulated deadline and every move respects reservations and closures. |

All three tasks take a Python standard library policy at `/app/policy.py`.

## Scoring and validity

The offline verifier writes the **fraction of held-out cases passed**
to `/logs/verifier/reward.json`. Each case is binary. An incomplete
dock, a forecast outside either tolerance, or a late dispatch earns zero
for that case. Full credit requires every case to pass. We chose fractional reward because an
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
- Dispatch grades ten shifts across five paired layouts. The two shifts
  per layout share the same observations up to the announcement. After
  that point the selected calendar determines closures and bay service.

Each Harbor attempt starts a fresh agent session in its own Docker
container with only the practice workspace. Web search is disabled and
network access is restricted to the inference host. Harbor passes the
submitted policy to a separate offline verifier that holds the hidden
cases. The reference policies stay outside the agent image.

Each scored case starts a fresh process with private writable storage.
The Harbor oracles earned 1.0 and the no-op controls earned 0.0 on all
three tasks. Offline replays reproduced all four Dispatch Luna move logs
at both the original and doubled policy watchdog. A Calibration control
that fit constant traction using both camera readings passed 16/60.
[Recovery qualification](results/warehouse-recovery/QUALIFICATION.md) ·
[Calibration qualification](results/warehouse-calibration/QUALIFICATION.md) ·
[Dispatch qualification](results/warehouse-dispatch-windows/QUALIFICATION.md)

## Model results

All attempts used Codex CLI 0.163.0 at medium reasoning effort through
Harbor 0.25.0 on Docker. Each score shows the percentage of cases passed
and the exact count over total. The task reports link to the trial artifacts.

| Task | Model and harness | Attempt | Score | Main failure or finding |
| --- | --- | --- | --- | --- |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 1 | 31.25% (5/16) | Eight collisions and three motion-limit misses. |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 2 | 81.25% (13/16) | Three missions with two closures hit the motion limit. |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 3 | 37.5% (6/16) | Ten collisions, including repeated collisions on two layouts. |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna / Codex | 4 | 56.25% (9/16) | Six collisions and one incorrect final heading. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 1 | 100% (16/16) | Docked on all 16 missions without collision. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 2 | 100% (16/16) | Docked on all 16 missions without collision. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 3 | 100% (16/16) | Docked on all 16 missions without collision. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 4 | 100% (16/16) | Docked on all 16 missions without collision. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 1 | 93.33% (56/60) | Four position misses, three in sustained reverse. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 2 | 86.67% (52/60) | Eight position misses, four in sustained reverse. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 3 | 96.67% (58/60) | Two position misses, both in sustained reverse. |
| [Calibration](results/warehouse-calibration/RESULTS.md#fresh-four-attempts) | GPT-6 Luna / Codex | Fresh 4 | 100% (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 1 | 100% (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 2 | 100% (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 3 | 100% (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 4 | 100% (60/60) | All forecasts met both tolerances. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 1 | 90% (54/60) | Six position misses. Divided the fitted load coefficient by the traction multiplier. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 2 | 86.67% (52/60) | Eight position misses. The fit was sensitive to camera rounding. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 3 | 0% (0/60) | The submitted policy had a Python syntax error. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna / Codex | Original 4 | 80% (48/60) | Twelve position misses. All heading checks passed. |
| [Calibration](results/warehouse-calibration/RESULTS.md#retest-after-attempt-3) | GPT-6 Luna / Codex | Follow-up to original 3 | 95% (57/60) | Three position misses, all in sustained reverse. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md) | GPT-6 Luna / Codex | 1 | 100% (10/10) | Found fleet schedules compatible with both maintenance orders. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md) | GPT-6 Luna / Codex | 2 | 40% (4/10) | Committed a cart before the announcement and missed delivery deadlines. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md) | GPT-6 Luna / Codex | 3 | 100% (10/10) | Checked joint move feasibility under both orders. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md) | GPT-6 Luna / Codex | 4 | 40% (4/10) | Evaluated both orders per cart, then missed deadlines when carts needed to clear space for each other. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 1 | 100% (10/10) | Searched joint moves and branched on the selected calendar. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 2 | 100% (10/10) | Checked feasible continuations for both maintenance orders. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 3 | 100% (10/10) | Built a shared dispatch plan and branched at the announcement. |
| [Dispatch](results/warehouse-dispatch-windows/RESULTS.md#astra-comparison) | GPT-6 Astra / Codex | 4 | 100% (10/10) | Searched joint schedules for both calendar outcomes. |

One Calibration launch stopped at the API quota and has no score.
[Launch record](results/warehouse-calibration/harbor-luna-fresh/quota-blocked-launch.json)

**Recovery.** Luna's best policy docked on every clear and single-closure
route, then reached the motion limit in three two-closure missions.
Other Luna policies also collided on clear routes. The score reflects
the reliability of localization, route planning, and motion control
together. [Recovery analysis](results/warehouse-recovery/RESULTS.md)

**Calibration.** In the fresh batch, Luna passed every heading check.
Three policies missed 14 positions in total, nine on sustained reverse
drives. The 60/60 policy used varied drive commands and fit gyro and
camera data jointly. For one original policy, replaying its probe with
unrounded camera positions eliminated eight forecast misses in a
controlled calculation. The oracle passed with the published camera
resolution using a different probe.

**Dispatch.** Luna passed two of four attempts. Both incomplete policies
made valid moves but missed simulated delivery deadlines. One committed
to an approach before the maintenance announcement. The other evaluated
both calendars for each cart and still had carts block one another. Astra
passed all four attempts by planning joint moves before the announcement.
[Dispatch analysis and traces](results/warehouse-dispatch-windows/RESULTS.md)

Each attempt on a task faced the same fixed cases. Scores describe
coverage of those cases, and the small batches limit conclusions
about other simulators or agent settings. For Recovery, a useful harder comparison would vary closure
placement on matched, reachable layouts. Calibration can vary traction
and camera precision while keeping the same probe budget. Comparing a
fixed informative probe with agent-chosen probes would help isolate
measurement choice from model fitting. Dispatch can vary the announcement
tick and available pullouts across matched layouts to test when keeping
both schedules feasible requires a different early move.

## Run the tasks

With Docker running and `uv` installed, run the qualification controls
from the repository root. `uvx` runs Harbor 0.25.0 in an isolated Python
3.12 environment, even when another `harbor` command is installed.
Expect reward 1.0 for oracle and 0.0 for no-op.

```sh
for task in tasks/warehouse-recovery tasks/warehouse-calibration tasks/warehouse-dispatch-windows; do
  uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor lint "$task"
  uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run \
    -p "$task" -e docker -a oracle -r 0 -o "jobs/${task##*/}" --job-name oracle
  uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run \
    -p "$task" -e docker -a nop -r 0 -o "jobs/${task##*/}" --job-name nop
done
```

Set your OpenAI credentials on the host to reproduce the model batches. These commands make paid model calls.

```sh
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run \
  -c configs/recovery-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/recovery-luna
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run \
  -c configs/calibration-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/calibration-luna
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run \
  -c configs/dispatch-windows-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/dispatch-luna
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run \
  -c configs/dispatch-windows-astra.json -e docker -k 4 -n 1 -r 0 -o jobs/dispatch-astra
```

All tasks run on local Docker with two CPUs and 4 GiB of RAM for each
agent and verifier container. The agent gets 15 minutes per attempt.
The verifier gets up to four minutes for Recovery and Calibration and
six minutes for Dispatch. Dispatch grades delivery deadlines in
simulation ticks. Its separate wall-time watchdog is 30 seconds per
shift. Task reports give measured attempt times.
