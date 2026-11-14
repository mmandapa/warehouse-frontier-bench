# Warehouse Cart Benchmark

Can a coding agent build a controller that makes reliable decisions from
limited sensor data? A warehouse cart's survey can be out of date, and
its motion can differ from what the motor commands imply. These tasks
test two ways to handle that uncertainty: adapt to evidence during a
mission and choose measurements before making a prediction.

| Task | What the agent receives and does | A case passes when |
| --- | --- | --- |
| [Cart Recovery](tasks/warehouse-recovery/README.md) | A surveyed map, simulator client, starter code, and three practice missions. Use lidar, odometry, gyro, and visible markers to localize a moved cart, route around uncharted obstructions, and dock. | The cart docks without collision, with no movement pending, within 0.22 m and 0.12 rad of the target pose. |
| [Cart Calibration](tasks/warehouse-calibration/README.md) | A simulator client, motion equations, starter code, and two practice cases. Use up to 30 command ticks and two camera readings to estimate traction, then predict endpoints for new command sequences. | The predicted endpoint is within 0.045 m and 0.025 rad of the simulated endpoint. |

Both tasks require a Python standard library policy at `/app/policy.py`.
Recovery calls the simulator to drive and stop the cart. Calibration
submits one position and heading per forecast sequence.

## Scoring and validity

The offline verifier returns one scalar, the fraction of cases passed.
Recovery grades 16 missions across four matched layouts. Calibration
grades 60 forecasts across 12 carts. Each case is pass/fail. The fraction
distinguishes a policy that docks on 13 of 16 missions from one that
docks on 5 of 16, even though neither is a full solve. This also gives
group-relative RL a reward difference when no rollout fully succeeds.
Per-case diagnostics show whether a policy repeatedly misses the same
scenario even when its average is high.

The agent image contains the practice workspace. The offline verifier
owns the scored initial states, obstacle placements, cart parameters,
and expected outcomes. The oracle and scored fixtures sit outside the
agent image. Each mission or cart starts a fresh policy process in the
verifier. Model web search was disabled and rollout egress was restricted
to the inference host. Both [Recovery](results/warehouse-recovery/QUALIFICATION.md)
and [Calibration](results/warehouse-calibration/QUALIFICATION.md)
passed Harbor lint and scored 1.0 with the oracle and 0.0 with no-op.

## Model results

All runs used Codex CLI 0.163.0 at medium reasoning effort through Harbor
0.25.0 and Docker. Entries are in attempt order and show cases passed
over cases evaluated. Run reports link to trajectories, submitted
policies, per-attempt rewards, and verifier diagnostics.

| Task | Model | Runs | Cases passed | Main finding |
| --- | --- | --- | --- | --- |
| [Recovery](results/warehouse-recovery/RESULTS.md) | GPT-6 Luna | 1–4 | 5/16, 13/16, 6/16, 9/16 | The best policy docked on every clear and single-closure route, then exhausted its motion budget on three two-closure routes. Other policies also collided on clear routes. |
| [Recovery](results/warehouse-recovery/RESULTS.md#astra-comparison) | GPT-6 Astra | 1–4 | 16/16, 16/16, 16/16, 16/16 | All four policies docked on every mission. |
| [Calibration](results/warehouse-calibration/RESULTS.md#original-four-attempts) | GPT-6 Luna | Original four | 54/60, 52/60, 0/60, 48/60 | Three policies missed position forecasts. One did not run. |
| [Calibration](results/warehouse-calibration/RESULTS.md#retest-after-attempt-3) | GPT-6 Luna | Follow-up | 57/60 | Three sustained reverse forecasts missed position tolerance. |

In Calibration attempt 2, a local analysis recovered all 60 forecasts
with exact camera positions and reproduced the eight misses with the
published millimeter rounding. The oracle got 60/60 at the same
resolution by choosing a different probe. For Recovery, offline replay
reproduced all 64 Luna episode diagnostics.

## Run the tasks

Install Harbor and start Docker. From the repository root:

```sh
uv tool install 'harbor==0.25.0'
for task in tasks/warehouse-recovery tasks/warehouse-calibration; do
  harbor lint "$task"
  harbor run -p "$task" -e docker -a oracle -r 0 -o "jobs/${task##*/}" --job-name oracle
  harbor run -p "$task" -e docker -a nop -r 0 -o "jobs/${task##*/}" --job-name nop
done
```

To evaluate Luna, configure your OpenAI credentials and run the saved
configs into a fresh output directory. These commands make model calls.

```sh
harbor run -c configs/recovery-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/recovery-luna
harbor run -c configs/calibration-luna.json -e docker -k 4 -n 1 -r 0 -o jobs/calibration-luna
```

Both tasks use two CPUs and 4 GiB per environment, with a 15-minute agent
limit and a four-minute verifier limit. Recorded model trials used about
57 minutes of combined Harbor trial time. Design and iteration exceeded
the five-hour authoring timebox.

## Coverage and next steps

Recovery can vary the number and placement of closures and the length
of a safe detour. Match layouts and start poses so a clear-route control
separates navigation errors from difficulty with replanning. Calibration
can vary traction parameters, camera precision, and forecast command
histories. Check that an oracle can still identify traction within the
same measurement budget. The challenge is that a plausible route or fit
can work on practice inputs and fail when new evidence changes what the
policy should do.

These small fixed simulation suites show how the tested agents behave in
this setting. A follow-up would compare agent-selected probes with a
known informative probe and evaluate a stronger model on Calibration.
