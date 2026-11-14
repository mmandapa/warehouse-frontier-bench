# Warehouse Dispatch During Maintenance results

Four fresh GPT-6 Luna attempts used Codex CLI 0.163.0 at medium reasoning
effort, Harbor 0.25.0, and local Docker. The agent had 15 minutes, two CPUs,
and 4 GiB. A verifier case passed when every cart met its delivery deadline
without issuing an invalid move. The [frozen task](task-manifest.json)
was the same for all four attempts and the oracle and no-op controls.

| Attempt | Score | Agent time | Main finding | Artifacts |
| --- | ---: | ---: | --- | --- |
| 1 | 100% (10/10) | 106.1 s | Searched joint moves and kept a viable schedule under both orders. | [Trajectory](harbor/dispatch-windows-luna-01/warehouse-dispatch-windows__cLepegM/agent/trajectory.json) · [Policy](harbor/dispatch-windows-luna-01/warehouse-dispatch-windows__cLepegM/artifacts/app/policy.py) · [Verifier](harbor/dispatch-windows-luna-01/warehouse-dispatch-windows__cLepegM/verifier/diagnostics.json) |
| 2 | 40% (4/10) | 200.9 s | Routed carts individually. Committed to a blocked approach before announcement and missed simulated deadlines in six shifts across four layouts. | [Trajectory](harbor/dispatch-windows-luna-02/warehouse-dispatch-windows__bQhJkfw/agent/trajectory.json) · [Policy](harbor/dispatch-windows-luna-02/warehouse-dispatch-windows__bQhJkfw/artifacts/app/policy.py) · [Verifier](harbor/dispatch-windows-luna-02/warehouse-dispatch-windows__bQhJkfw/verifier/diagnostics.json) |
| 3 | 100% (10/10) | 128.2 s | Checked that joint moves left an on-time continuation under both orders. | [Trajectory](harbor/dispatch-windows-luna-03/warehouse-dispatch-windows__Y38eCnJ/agent/trajectory.json) · [Policy](harbor/dispatch-windows-luna-03/warehouse-dispatch-windows__Y38eCnJ/artifacts/app/policy.py) · [Verifier](harbor/dispatch-windows-luna-03/warehouse-dispatch-windows__Y38eCnJ/verifier/diagnostics.json) |
| 4 | 40% (4/10) | 143.0 s | Checked both orders for each cart individually. Other carts' future needs were absent from those estimates. Six shifts missed deadlines across three layouts. | [Trajectory](harbor/dispatch-windows-luna-04/warehouse-dispatch-windows__7krbyKP/agent/trajectory.json) · [Policy](harbor/dispatch-windows-luna-04/warehouse-dispatch-windows__7krbyKP/artifacts/app/policy.py) · [Verifier](harbor/dispatch-windows-luna-04/warehouse-dispatch-windows__7krbyKP/verifier/diagnostics.json) |

Two submissions earned full credit. The mean score was 70% (28/40).
The trajectories reported a combined cost of $0.05155. All four attempts
returned verifier scores with no Harbor exception. The traces showed local
workspace commands and no evidence of web search or hidden grader access.
The verifier used a separate offline environment for each submission.

On the fork with order 2 selected, attempt 2 released the loaded cart
onto approach A at tick 0. The announced order closed the link at the far
end of that approach, and the cart could not reach its delivery by tick 6.
Attempt 4 waited for the announcement and passed both fork cases. On
the first pullout case, it sent the loaded cart into the junction at
tick 0 and then repeatedly moved it between the junction and pullout
while the other cart moved between two nodes. The oracle also sends
the loaded cart into the junction at tick 0. At tick 1 it moves the cart
into the pullout, then sends the returning cart through the junction at
tick 2. The returning cart delivers at tick 6 and the loaded cart at
tick 9. Switching to the reference after the saved first move preserved
on-time deliveries in both pullout cases. These outcomes distinguish
planning for either maintenance order from coordinating the fleet.

Both failed submissions finished well inside the agent time budget.
All 12 failed shifts ended at simulated delivery deadlines. A separate
[decision-log checker](check-saved-decisions.py) reconstructed arrivals,
reservations, observations, service and deadlines for all 40 scored
shifts and the 20 oracle and no-op shifts. The saved pre-announcement
observations and moves matched across both orders on every layout.
Offline Docker replays at the published 30-second policy watchdog and
at 60 seconds reproduced all four verifier diagnostics byte for byte.
See the [attempt 2 replay](trace-audit-02-60s/diagnostics.json),
[attempt 4 replay](trace-audit-04-60s/diagnostics.json), and
[first-move counterfactuals](first-move-counterfactuals.json).

Both failed policies also missed a public practice shift when replayed.
Attempt 2 missed the second order on the public fork and attempt 4 missed
a delivery in the public four-cart case. Neither ran the practice commands
in its saved agent session. These four trials show a split between the
observed strategies on five layouts. Both orders on a layout can expose
the same coordination mistake, so the 10 shifts are paired observations.
Attempts 2 and 4 both failed five of the same shifts. Their moves differed on each
of those shifts, and their completed deliveries differed on three. If a
layout counts as solved only when both orders pass, attempt 2 solved
one of five layouts and attempt 4 solved two of five.
