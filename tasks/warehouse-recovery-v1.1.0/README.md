# Warehouse cart recovery v1.1.0

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

The reference docked in 16/16 local episodes and approached both
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
task=tasks/warehouse-recovery-v1.1.0
python3 -B scripts/qualify_warehouse_recovery_v1_1_0.py \
  --output /tmp/warehouse-recovery-v1.1.0-controls
harbor lint "$task"
```

The [qualification report](../../results/warehouse-recovery/QUALIFICATION-v1.1.0.md)
links to saved diagnostics and lists the Harbor controls and remaining
verification. A meaningful model failure would be a controller that
docks in clear missions but repeatedly stops or collides at a newly
encountered closure or fails to settle after a traction change. Model
difficulty is unmeasured for this version.
