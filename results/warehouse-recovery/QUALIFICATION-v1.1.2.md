# Warehouse recovery v1.1.2 runtime audit

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

The [fresh v1.1.2 Luna batch](RESULTS-v1.1.2.md) ran after qualification.
