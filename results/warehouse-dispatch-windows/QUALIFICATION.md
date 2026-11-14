# Warehouse Dispatch During Maintenance qualification

The dispatcher sees the lane graph, delivery deadlines, and two possible
maintenance calendars. It submits one batch of moves per tick. The selected
calendar becomes visible on a known tick. A move in progress is committed.
The ten held-out shifts cover both outcomes on five layouts. Each pair shares
its visible prefix. The reference dispatcher plans from the same public
observations available to submissions.

| Control | Score | Observed behavior |
| --- | ---: | --- |
| [Harbor oracle](harbor/oracle/warehouse-dispatch-windows__hf9n3cC/verifier/diagnostics.json) | 10/10 | Safely completed all deliveries on both outcomes of every layout. |
| [Harbor no-op](harbor/nop/warehouse-dispatch-windows__ESc55N2/verifier/diagnostics.json) | 0/10 | Failed to complete any shift. |
| [Assume first order, replan on announcement](docker-guess-a/diagnostics.json) | 8/10 | Missed deadlines in the fork and crossing layouts. |
| [Assume second order, replan on announcement](docker-guess-b/diagnostics.json) | 7/10 | Missed deadlines in the fork, pullout, and bypass layouts. |

On the fork, the reference clears a departing cart while keeping the
loaded cart at the fork until the announcement. Either one of two links
beyond the long approach can close. The single-order planners commit to
opposite approaches at tick 0, so each misses one of the matched outcomes.
In the crossing layout, sending the wrong cart to the intersection first
leaves the urgent cart unable to enter after announcement. Replaying the
controls with a 60-second watchdog in offline Docker reproduced all case
diagnostics from the local runner. Timeouts did not cause the misses.

We checked that the public and verifier copies of the client and simulator
match, the public context excludes the grader and scored layouts, and the
four practice shifts pass with the oracle. The oracle and no-op were run
against the [frozen task manifest](task-manifest.json). The known-calendar
variant can be solved by ordinary replanning. The new controls isolate the
change in the task: a policy must keep options open before the calendar is
selected. Four fresh model trials are needed to measure Luna difficulty.
