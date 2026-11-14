---
status: accepted
date: 2026-11-13
---

# Isolate writable policy storage per scored case

The verifier evaluates one submitted program across several missions or
carts. A fresh process and working directory reset in-memory state,
but the shared verifier filesystem let files written during one case
survive into the next. A score intended to measure independent cases
could then depend on case order.

Each scored case runs under its own unprivileged Linux user in a fresh
filesystem. It contains the Python runtime, the submitted policy, the
public client, and a private writable `/tmp`. The root-owned runtime
files are linked from the verifier image. The grader, hidden fixtures,
and logs stay outside the policy's filesystem. Harbor still runs one
offline verifier container per submission.

A fresh working directory alone leaves shared paths such as `/tmp`
accessible. Starting a new container per case would require Harbor
or its verifier to manage additional containers. Separate filesystem
roots inside the existing verifier keep the current task layout and
preserve the simulation protocol. This change isolates files. The
enclosing Docker container still provides the network and resource
boundaries.

Local practice keeps its existing process runner. Published scores
retain their original trial artifacts. The isolated replay compares
each saved policy's case outcomes against those artifacts. See the
[Recovery qualification](../../results/warehouse-recovery/QUALIFICATION.md)
and [Calibration qualification](../../results/warehouse-calibration/QUALIFICATION.md).

To reproduce the isolation check and rescore from the repository root:

```sh
for task in warehouse-recovery warehouse-calibration; do
  image="$task-isolation-audit:local"
  docker build --network=none -t "$image" "tasks/$task/tests"
  docker run --rm --pull=never --network=none -e WAREHOUSE_ISOLATE_CASES=1 \
    --mount "type=bind,source=$PWD/scripts/test_warehouse_policy_isolation.py,target=/test-isolation.py,readonly" \
    "$image" python3 -B /test-isolation.py
  python3 -B scripts/rescore_warehouse_policies.py "$task" \
    --image "$image" --output "/tmp/$task-isolation-replay.json"
done
```
