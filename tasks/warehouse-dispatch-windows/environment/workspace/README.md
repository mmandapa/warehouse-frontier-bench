# Dispatch console

The simulator starts at tick 0. You receive the lane map, jobs, current
cart positions, and current service interruptions. Use `Dispatch` from
`client.py`. Call `observe()` once, send the moves for that tick with
`step(moves)`, then call `observe()` again. A final observation contains
`result` instead of a tick. An empty move dictionary advances one tick.
Use stderr for policy logs.

| Observation | Contents |
| --- | --- |
| `tick` | Current simulation tick. |
| `lanes` | Lists `[a, b, duration]` for bidirectional lanes. Nodes are strings and duration is a positive integer in ticks. |
| `closed` | Endpoint pairs for lanes currently closed to new entries. Pair order has no meaning. |
| `notice` | Maintenance notice with `announce_tick` and an `orders` list. |
| `selected` | `null` until the announcement, then `0` or `1` for the selected order. |
| `paused` | Nodes where pickup and delivery service are currently paused. |
| `carts` | List of cart records with `id`, `start`, `pickup`, `delivery`, `deadline`, `at`, `to`, `remaining`, and `stage`. |

Each notice lists two possible orders. Before `announce_tick`, either
can be selected. On that tick, `selected` gives the chosen index before
the dispatcher acts. Only the selected order is carried out. Each order
is a list of events with an inclusive `start` and exclusive `end` in
simulation ticks, and either a `lane` endpoint pair or a `bay` node.
No event starts before the announcement. `closed` and `paused` show all
active events. Future events follow the chosen calendar with no other
interruptions. An order can have an empty event list.

A parked cart has `at` equal to its current node, `to` set to `null`,
and `remaining` set to zero. A cart in transit has `at` equal to the
origin of the move, `to` equal to its destination, and `remaining`
equal to the number of ticks until arrival. `stage` is `0` before pickup,
`1` after pickup, and `2` after delivery. Each cart has one job and may
keep moving after delivery. Pickup and delivery nodes are distinct.

Pass a dictionary from cart ID to the adjacent node it should enter.
Omitted carts stay put or continue an existing move. A move reserves
its destination and lane until arrival. The origin is vacated when the
move starts. A destination must be free at the **start** of the tick,
even if its occupant will move in the same batch. Two moves in the same
batch cannot claim the same destination or lane. A lane reservation
covers both directions. A moving cart cannot receive another command.
Starting on a closed lane is invalid. A cart already on a lane finishes
its move even if that lane closes. A move of duration 1 that starts at
tick 0 arrives at tick 1.

At each tick boundary the simulator updates closures and service state,
then processes pickups and deliveries for parked carts. Service happens
automatically if the cart is at the right node and the bay is open.
Carts can enter, leave, or pass through a paused bay. Pausing only affects
pickup and delivery. Lane and bay states can change at later ticks. The
policy receives the current state at each tick before it issues moves.
A delivery at its deadline counts. Any invalid batch or missed deadline
ends the shift. To pass, complete all jobs on time with valid dispatches.

The scored shifts use two to four carts. Each policy process has a
30-second wall-time limit per shift, 512 MiB of address space, a 4 MiB
per-file size limit, and an 8 KiB limit per response line. The submitted
policy file can be at most 1 MiB. The warehouse deadlines are in ticks.

Run `python3 -B practice.py 0`, `python3 -B practice.py 1`, `python3 -B practice.py 2`, or
`python3 -B practice.py 3` from `/app`. Each prints the move log and the
result. Use `--policy` to test a different file.
