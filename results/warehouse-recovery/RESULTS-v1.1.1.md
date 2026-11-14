# Warehouse recovery v1.1.1 model results

Four fresh Codex CLI 0.163.0 trials used `openai/gpt-6-luna` with medium
reasoning effort, a 900-second agent budget, two CPUs, and 4 GiB per
trial. Harbor used Docker with a separate offline verifier. All four
trials matched the frozen task and the qualification controls. The
agent locks recorded four fresh sessions, disabled web search and MCP,
and only the inference host was allowlisted. All trials completed
within the agent budget and had zero Harbor exceptions.

| Attempt | Reward | Docks | Harbor wall time | Observation | Artifacts |
| --- | ---: | ---: | ---: | --- | --- |
| 1 | 1 | 16/16 | 6m 23s | Docks in every scene using live lidar updates and A*. | [Trace](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-01/warehouse-recovery-v1.1.1__xeq9mWL/agent/trajectory.json), [policy](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-01/warehouse-recovery-v1.1.1__xeq9mWL/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-01/warehouse-recovery-v1.1.1__xeq9mWL/verifier/diagnostics.json) |
| 2 | 0.5 | 8/16 | 5m 42s | All eight misses finish within position tolerance but face the wrong way at the motion limit. | [Trace](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-02/warehouse-recovery-v1.1.1__F6wnkJu/agent/trajectory.json), [policy](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-02/warehouse-recovery-v1.1.1__F6wnkJu/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-02/warehouse-recovery-v1.1.1__F6wnkJu/verifier/diagnostics.json) |
| 3 | 0.625 | 10/16 | 3m 38s | Four wall collisions in one layout and two motion-limit misses at the dock. | [Trace](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-03/warehouse-recovery-v1.1.1__gc8nMPQ/agent/trajectory.json), [policy](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-03/warehouse-recovery-v1.1.1__gc8nMPQ/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-03/warehouse-recovery-v1.1.1__gc8nMPQ/verifier/diagnostics.json) |
| 4 | 0 | 0/16 | 4m 42s | Fourteen wall collisions and two policy exits before calling finish. | [Trace](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-04/warehouse-recovery-v1.1.1__EGg8e3N/agent/trajectory.json), [policy](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-04/warehouse-recovery-v1.1.1__EGg8e3N/artifacts/app/policy.py), [verifier](harbor-luna4-v1.1.1-docker-2026-11-12/warehouse-recovery-v1.1.1-luna-docker-2026-11-12-04/warehouse-recovery-v1.1.1__EGg8e3N/verifier/diagnostics.json) |

**Full solves** 1/4. **Mean reward** 0.53125.
The batch elapsed time from the first trial start to the last trial
finish was 20m 35s. Estimated model spend was
`$0.09001`. The [ledger](harbor-luna4-v1.1.1-docker-2026-11-12/ledger.json)
records per-trial spend and paths to the raw Harbor results.

## What failed

- Attempt 2's eight motion-limit misses all ended 0.114–0.126 m from the
  dock, inside the 0.22 m tolerance. Their heading errors were
  0.546–2.272 rad against the 0.12 rad limit. Its controller only switched
  to stationary alignment inside an estimated 0.12 m radius. The end
  poses show a final alignment failure. They alone cannot establish
  every control transition that caused it.
- Attempt 3 used graph search with backtracking. Four missions in the
  same layout collided with aisle walls, including the clear route.
  Two other missions reached the dock position and ran out of motion
  ticks with excessive heading error.
- Attempt 4's final public practice sweep docked on all three practice
  missions. On scored layouts it hit aisle walls in 14 missions,
  including all four clear routes. The policy process ended before
  calling finish in the other two. The [runtime audit](QUALIFICATION-v1.1.2.md)
  traced those exits to the verifier's unpublished 10-second CPU limit.
  In the corrected full replay, those two episodes docked and the 14 wall
  collisions reproduced.

## Interpretation

The controls establish that the task exercises rerouting. The model
trials show inconsistent execution of safe driving and final pose
alignment on held-out layouts. Across the four trials, successful
docks were 9/16 on clear routes, 9/16
with one closure, 9/16 with two closures, and
7/16 with two closures and changed grip.
The same layout families appear in each group, so these episode counts
are descriptive. Four runs are limited evidence about this model and
setup. The observed failures do not isolate an inability to replan.
