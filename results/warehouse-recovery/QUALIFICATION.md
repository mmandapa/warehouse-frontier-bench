# Warehouse recovery qualification

An offline Docker replay ran the four saved Luna policies through the
frozen v1.1.1 verifier. It reproduced all four scores and all 64 outcome
categories. In 62 episodes, the full diagnostics matched. The two
early exits in attempt 4 repeated with different final ticks.

A targeted probe measured about 10 seconds of child CPU time and
observed SIGKILL before verifier cleanup on both episodes. The policy
had not reached the published 12-second wall-time deadline. Removing
only the CPU limit let one episode dock in the targeted probe. The
second reached the wall-time deadline in that probe.

v1.1.2 removes the 10-second CPU limit from practice and grading. The
same 12-second wall-time deadline, 16 episodes, motion limits, and
scoring rules apply. The public instructions also specify the existing
memory, file-size, and request-size limits.

Harbor lint passed. The [oracle](harbor-controls-v1.1.2/oracle/result.json)
scored 16/16 and the [no-op](harbor-controls-v1.1.2/nop/result.json) scored
0/16. Both used the separate Docker verifier, completed without
exceptions, and recorded the same task checksum. The
[freeze manifest](frozen-v1.1.2.json) records the qualified package.

The [manifest from the original distribution](evaluated-package-manifest.json)
records the package before the final-tick correction. The original control
and model records retain their evaluated package identifiers. See the
[model results](RESULTS.md).

Harbor controls on that package matched its manifest.
The [oracle](package-controls/oracle/result.json) scored 16/16;
the [no-op](package-controls/nop/result.json) scored 0/16.

## Final-tick correction

The grader previously ended the mission on the last permitted movement
tick. The practice runner and grader now acknowledge a command that
uses exactly the remaining ticks, then allow observation and docking.
An over-budget drive still fails. Docking still requires the cart to
have stopped within both pose tolerances.

The Harbor [oracle](final-tick-controls/oracle/result.json) scored
16/16 and the [no-op](final-tick-controls/nop/result.json) scored 0/16
on the corrected package, both without exceptions. Run the regression
checks from the repository root:

```sh
python3 -B scripts/test_recovery_tick_budget.py
```

An [offline Docker replay](final-tick-replay.json) rescored all eight
saved model submissions with the corrected verifier. All 128 mission
pass/fail outcomes matched the original trials. One mission's diagnostic
details changed while its outcome stayed a fail.

## Isolated verifier replay

The verifier gives each mission its own unprivileged user and private
writable storage. The [offline replay](isolation-replay.json) rescored
all eight saved policies through the isolated verifier. All 128 mission
outcomes and all eight rewards matched the original model trials.

The [oracle](isolation-controls/oracle.json) and
[no-op](isolation-controls/nop.json) ran through Harbor on the package
identified by the [current manifest](package-manifest.json). They
scored 16/16 and 0/16, respectively.
