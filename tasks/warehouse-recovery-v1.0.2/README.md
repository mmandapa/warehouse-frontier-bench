# Warehouse cart recovery

After manual relocation, a cart sees nearly identical warehouse aisles.
It needs to find a usable route, establish its position from observations,
and dock precisely despite errors in wheel odometry. The policy drives
the cart and can request additional sensor readings as it moves.

This is one CPU-only Harbor task. The agent receives a survey map, three
practice missions, an offline Python simulator client, and a short issue.
The separate verifier owns the official scenes and advances the simulator
from the submitted policy's commands. Only sensor readings and the survey
map reach the policy process. Its scalar reward is the fraction of 16
missions that end settled in the dock pose without a collision.

## Qualification

From the benchmark repository root:

```bash
.venv/bin/harbor lint --json tasks/warehouse-recovery-v1.0.2
.venv/bin/harbor run --max-retries 0 --config \
  results/warehouse-recovery/harbor-oracle-nop-v1.0.2.json
```

For a practice run, use the task's `environment/workspace` directory:

```bash
python3 -B practice.py --case 0 --policy policy.py
```

The starter ends the mission without docking. The authoring reference
and local controls are documented in the
[qualification report](../../results/warehouse-recovery/QUALIFICATION-v1.0.2.md).

The task uses 2 CPUs, 4 GiB RAM, 4 GiB storage, a 20-minute agent limit,
and a 4-minute verifier limit. This is a geometric differential-drive
simulation with quantized observations. It tests how a policy uses
evidence in a controlled mission. It does not measure visual perception
or transfer to a physical robot.
