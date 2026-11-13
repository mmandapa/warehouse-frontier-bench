# Warehouse Cart Calibration v1.0.0

This is the second task in the warehouse benchmark. The agent writes a
calibration program for a cart whose drive parameters changed during
maintenance. The program can issue up to 20 motor commands and request
one camera pose. It then predicts endpoints for five new sequences on
independent resets of that cart. The full contract and two practice
cases are in the [workspace README](environment/workspace/README.md).

The task measures whether an agent can select measurements that resolve
ambiguity and use them to predict behavior outside its calibration
sequence. The verifier uses six pairs of carts. Within each pair,
encoders and gyro readings agree for identical commands, but the carts
travel different distances. The pairs share the same forecast sequences.
The verifier owns the cart parameters and scores submitted endpoints
against the simulator's physical state.

Each forecast earns one point when its Euclidean position error is at
most 0.045 m and its wrapped heading error is at most 0.025 rad. The
reward is the fraction of the 60 forecasts that pass. The agent can use
any probing or estimation strategy that satisfies the public protocol.

Run these commands from the repository root with Harbor 0.25.0 and Docker.

```sh
task=tasks/warehouse-calibration-v1.0.0
harbor lint "$task"
harbor run -p "$task" -e docker -a oracle -r 0 -o jobs/calibration --job-name oracle
harbor run -p "$task" -e docker -a nop -r 0 -o jobs/calibration --job-name nop
```

The task uses two CPUs, 4 GiB of memory, and a 15-minute agent limit.
The verifier runs in a separate offline container and starts a fresh
policy process per cart. The local qualification script checks the
paired cases, protocol limits, and reference policies.

```sh
python3 -B scripts/qualify_warehouse_calibration_v1_0_0.py \
  --output /tmp/warehouse-calibration-qualification
```

The [design decision](../../docs/decisions/0023-warehouse-calibration-task.md)
records why the task uses active calibration. The
[qualification report](../../results/warehouse-calibration/QUALIFICATION-v1.0.0.md)
contains control scores and model status.
