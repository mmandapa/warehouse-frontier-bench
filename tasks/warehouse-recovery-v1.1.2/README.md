# Warehouse cart recovery v1.1.2

The task tests whether an agent can build a controller that recovers from a
route failure discovered during execution. The agent receives a surveyed
map, a deterministic 2D simulator, and three practice missions. It submits
one Python controller that uses the survey and onboard observations to
navigate and stop at the dock.

Version 1.1.2 uses the documented 12-second wall-time budget for each
mission. See [ADR 0022](../../docs/decisions/0022-warehouse-policy-runtime.md)
for the versioned correction and its audit evidence.

Four private warehouse layouts each have four matched episodes. Each set
shares its map, true starting pose, dock, and initial sensor readings.
Episodes cover a clear route, one closure, two closures, and two closures
with a change in floor grip near the dock. The pallets are stationary.
The score is the fraction of 16 missions with collision-free, settled
docks within the published position and heading tolerances. Each
episode runs in a fresh policy process. The separate offline verifier
owns the physical state and sends only the survey and sensor readings.

The v1.1.0 reference docked in 16/16 local episodes and approached both
barriers in every two-closure episode. It used at most 1,400 of the 2,100
available simulation ticks. The no-op scored 0/16. A control limited to
its initial route scored 4/16. A controller that could replan once
scored 8/16, reaching the second closure before stopping. Luna's saved
v1.0.2 controller scored 1/16 when replayed unchanged on the new layouts.
That replay also changes the map geometry, so the matched controls give
the cleaner comparison of replanning behavior.

## Reproduce the local checks

From the repository root, using Python 3.12:

```bash
task=tasks/warehouse-recovery-v1.1.2
python3 -B "$task/tests/grader/grade.py" --policy "$task/solution/policy.py" \
  --logs /tmp/warehouse-recovery-v1.1.2-oracle
python3 -B "$task/tests/grader/grade.py" --policy "$task/environment/workspace/policy.py" \
  --logs /tmp/warehouse-recovery-v1.1.2-nop
harbor lint "$task"
```

The [v1.1.0 qualification report](../../results/warehouse-recovery/QUALIFICATION-v1.1.0.md)
links to the matched control diagnostics. See the [v1.1.2 audit](../../results/warehouse-recovery/QUALIFICATION-v1.1.2.md)
for the runtime correction, Harbor controls, and saved-policy replays.
The report distinguishes the original model runs from replays of the
saved policies under the corrected budget.
