# Warehouse cart recovery

The task tests whether an agent can build a controller that recovers from a
route failure discovered during execution. The agent receives a surveyed
map, a deterministic 2D simulator, and three practice missions. It submits
one Python controller that uses the survey and onboard observations to
navigate and stop at the dock.

Four private warehouse layouts each have four matched episodes. Each set
shares its map, true starting pose, dock, and initial sensor readings.
Episodes cover a clear route, one closure, two closures, and two closures
with a change in floor grip near the dock. The pallets are stationary.
The score is the fraction of 16 missions with collision-free, settled
docks within the published position and heading tolerances. Each
episode runs in a fresh policy process. The separate offline verifier
owns the physical state and sends only the survey and sensor readings.

## Reproduce the local checks

From the repository root, using Python 3.12 and `uv`:

```bash
task=tasks/warehouse-recovery
python3 -B "$task/tests/grader/grade.py" --policy "$task/solution/policy.py" \
  --logs /tmp/warehouse-recovery-oracle
python3 -B "$task/tests/grader/grade.py" --policy "$task/environment/workspace/policy.py" \
  --logs /tmp/warehouse-recovery-nop
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor lint "$task"
```

The [qualification report](../../results/warehouse-recovery/QUALIFICATION.md)
records the Harbor controls. See the [model results](../../results/warehouse-recovery/RESULTS.md)
for trajectories and verifier diagnostics.
