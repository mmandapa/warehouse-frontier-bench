# Warehouse Cart Benchmark: Calibration and Recovery

This Harbor benchmark tests whether an agent can build a warehouse cart
controller that responds to new evidence. Recovery tests whether the
controller can revise a route after discovering a closure. Calibration
tests whether it can choose measurements that distinguish base traction
from the effect of recent motor effort and use them to predict motion.
Both tasks are CPU-only simulations. Each uses an offline deterministic
verifier and rewards the fraction of held-out cases solved.

| Task | GPT-6 Luna results through Codex | Full solves in original four | Main finding |
| --- | --- | ---: | --- |
| [Cart Recovery v1.1.2](tasks/warehouse-recovery-v1.1.2/README.md) | 0.3125, 0.8125, 0.3750, 0.5625 | 0/4 | Luna collided or exhausted its motion budget on some missions. GPT-6 Astra scored 1.0 in all four attempts on the same task. [Results](results/warehouse-recovery/RESULTS-v1.1.2.md) |
| [Cart Calibration v1.1.0](tasks/warehouse-calibration-v1.1.0/README.md) | Runnable policies scored 54/60, 52/60, 48/60, and 57/60 (retest) | 0/4 | All four runnable policies missed some position forecasts. [Results](results/warehouse-calibration/RESULTS-v1.1.0.md) |

The original four Calibration rewards were **0.9000, 0.8667, 0.0000, and
0.8000**. Attempt 3 exited before calibration because of a Python syntax
error. A fresh retest on the same freeze scored **0.9500 (57/60)**.
Across the four runnable submissions, **211/240 forecasts (87.9%)** passed.

The task READMEs link to setup and qualification commands. The results
link to each trajectory, submitted policy, and verifier diagnostic.
Both batches used 15-minute agent limits, two CPUs, and 4 GiB per trial.

The task paths above contain the two submitted versions. Their reports
include the controls and every model attempt on those versions.

## Reward design for reinforcement learning

Each case has a binary outcome. Recovery requires a collision-free dock
within the published tolerances. Calibration requires a forecast within both
the position and heading tolerances. Harbor returns a single terminal reward
per submission equal to the fraction of cases passed. A full solve earns 1.0.

An all-or-nothing reward would give all four Luna Recovery submissions a zero,
even though they docked in 5, 13, 6, and 9 of 16 missions. A group-relative
method such as GRPO uses differences in reward among attempts on the same
task. Equal rewards provide no relative advantage from task outcomes. The
fraction passed preserves those differences even when none of the attempts
solves every case. The four runnable Calibration submissions, including the
supplemental trial, passed 54, 52, 48, and 57 of 60 forecasts. Both examples
show reward variation in the observed rollouts. [GRPO and equal-reward groups](https://arxiv.org/html/2503.14476#S3.SS2)

The score weights cases equally, so improving on common scenarios can raise
the average while a policy still fails the hardest scenarios. The full-solve
count and verifier diagnostics show where that happens. These runs evaluate
fixed models. To test whether this reward helps training, sample layouts and
cart parameters for training and compare performance before and after training
on a separate set of scenarios.

The benchmark can expand by generating layouts with different detour lengths
and numbers of closures, or by sampling new drive parameters and varying
camera precision. Qualify each setting against a reference under the same
sensing and control limits before evaluating models.

## Run the Harbor controls

Install Harbor 0.25.0 and start Docker. Run these commands from the repository root.
Each task README also describes its practice cases and local verification.

```sh
harbor run -p tasks/warehouse-recovery-v1.1.2 -e docker -a oracle -r 0 -o jobs/warehouse/recovery --job-name oracle
harbor run -p tasks/warehouse-recovery-v1.1.2 -e docker -a nop -r 0 -o jobs/warehouse/recovery --job-name nop
harbor run -p tasks/warehouse-calibration-v1.1.0 -e docker -a oracle -r 0 -o jobs/warehouse/calibration --job-name oracle
harbor run -p tasks/warehouse-calibration-v1.1.0 -e docker -a nop -r 0 -o jobs/warehouse/calibration --job-name nop
```

The oracle scores 1.0 on both tasks. The no-op scores 0.0 on both.

## Scope and limits

Recovery measures navigation and docking in a 2D simulator. Calibration uses a
simplified traction model and rounded camera poses. The results cover the frozen
cases and model settings in the reports. The warehouse tasks are part of a
longer design iteration that exceeded the original five-hour take-home timebox.
