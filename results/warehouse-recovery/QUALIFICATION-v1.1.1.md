# Warehouse recovery v1.1.1 prompt audit

The issue asks for a safe dock after the cart is moved. It no longer
identifies the obstructed lane or states how many closures there can be.
The public README specifies the sensor interface, motion limits, docking
tolerances, and the guarantee that each mission has a usable route.
The practice missions still exercise the same public interface on
different surveys.

The only differences from v1.1.0 are the version field, issue wording,
public README, and authoring README. The public image copies only its
workspace. Private closure placements, scored seeds, reference code,
verifier code, and previous model artifacts are outside that workspace.
The public source scan found no scored seeds, oracle control markers,
or credential patterns. Default Harbor lint returned no findings.

| Check | Result |
| --- | --- |
| [Local oracle](local-v1.1.1/oracle/diagnostics.json) | 16/16, no collisions |
| [Local no-op](local-v1.1.1/no-op/diagnostics.json) | 0/16 |
| [Matched v1.1.0 controls](QUALIFICATION-v1.1.0.md) | Fixed route 4/16 and one replan 8/16 on identical scenarios and physics |
| [Harbor oracle](harbor-controls-v1.1.1/oracle-retry-01/result.json) | 1.0, 16/16, no exceptions, 1m 13s |
| [Harbor no-op](harbor-controls-v1.1.1/nop/result.json) | 0.0, 0/16, no exceptions, 28s |
| [Fresh model attempts](RESULTS-v1.1.1.md) | 4 scored, 1 full solve |

These controls establish that the scored scenarios distinguish different
levels of replanning. They do not establish how often a fresh model can
solve the task. A relevant model failure would be a controller that
works on clear routes and stops or collides when it encounters a new
closure, with that explanation supported by the trajectory and physical
diagnostics.

Both controls used the same Harbor task checksum and separate verifier.
The [first oracle attempt](harbor-controls-v1.1.1/oracle/result.json)
failed during setup after Docker ran out of disk space and produced no
score. The successful retry followed a restart and build-cache cleanup.

To reproduce from the repository root with Docker running:

```bash
task=tasks/warehouse-recovery-v1.1.1
jobs=results/warehouse-recovery/harbor-controls-v1.1.1-reproduction
harbor run -p "$task" -e docker -a oracle -r 0 -o "$jobs" --job-name oracle
harbor run -p "$task" -e docker -a nop -r 0 -o "$jobs" --job-name nop
```

Expected rewards are 1.0 and 0.0 with no exceptions. These runs do not
require model credentials.
