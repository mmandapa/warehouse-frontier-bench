# Warehouse Dispatch During Maintenance

Dispatch carts that share lanes and loading bays. Each cart has a pickup,
a delivery, and a deadline in simulation ticks. The dispatcher observes
where carts are, how long their moves have left, and two possible work
orders. The active order is announced after the first dispatch decisions.

The task evaluates whether an agent can write a policy that coordinates
carts whose individually attractive moves can conflict or leave no room
to finish a job. Cart Recovery evaluates control of one vehicle under
partial information. This task uses discrete dispatch decisions and known
cart positions so the verifier can attribute failures to coordination,
route changes, or missed delivery deadlines.

A shift earns one point when all deliveries are on time and all moves
are valid. Harbor reports the fraction of ten shifts passed. Five held-out
layouts each run with both work orders under an identical visible prefix.
The verifier records decisions, completed deliveries, and the first
failure with its simulation tick. The 30-second wall limit per shift
bounds the policy process. Delivery deadlines are measured in simulated
time. The agent receives four public practice shifts. Harbor runs the
policy in a separate offline verifier with private writable storage per
shift. The task uses two CPUs, 4 GiB of RAM, and a 15-minute agent limit.

From the repository root with Docker running:

```sh
task=tasks/warehouse-dispatch-windows
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor lint "$task"
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run -p "$task" -a oracle -e docker -r 0
uvx --isolated --python 3.12 --from 'harbor==0.25.0' harbor run -p "$task" -a nop -e docker -r 0
```
