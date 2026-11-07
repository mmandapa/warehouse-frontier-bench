# Observed results

These records describe this task version only. A verifier control is not a frontier-agent result. Infrastructure errors have no capability score.

## Primary model attempts

| Task | Attempt | Model / harness | Score | Main finding | Evidence |
|---|---|---|---|---|---|
| unseen-subject-audit | 1 | openai/gpt-6-luna / codex | 1.0 | inconclusive; reproducible audit accepted | [Captured trial](models/primary-docker-gpt-6-luna/unseen-subject-audit__gjTqgcB/result.json) |
| unseen-subject-audit | 2 | openai/gpt-6-luna / codex | 1.0 | inconclusive; reproducible audit accepted | [Captured trial](models/primary-docker-gpt-6-luna/unseen-subject-audit__rw7JcVM/result.json) |
| unseen-subject-audit | 3 | openai/gpt-6-luna / codex | 1.0 | inconclusive; reproducible audit accepted | [Captured trial](models/primary-docker-gpt-6-luna/unseen-subject-audit__xUZ5v2c/result.json) |
| unseen-subject-audit | 4 | openai/gpt-6-luna / codex | 1.0 | inconclusive; reproducible audit accepted | [Captured trial](models/primary-docker-gpt-6-luna/unseen-subject-audit__zwMgipP/result.json) |

Valid completed primary attempts: 4 of 4. Mean single-attempt reward: 1.000.

All four attempts succeeded and selected inconclusive under their submitted participant-disjoint comparisons. This instance did not expose a genuine capability failure in the allowed smaller model. The observed 4/4 result is not a population-wide reliability estimate. The agent reports and ATIF trajectories are in each captured trial directory.

Harbor records 643,993 input tokens, including 558,082 cached tokens, and 15,705 output tokens. Its pricing-based cost estimate is USD 0.024169; provider billing was not independently checked. Total elapsed time per attempt was 103.7–109.8 seconds, including setup and verification.

Two task checksums appear in the raw records because a host syntax check generated two bytecode-cache files in the oracle-only `tasks/unseen-subject-audit/solution/` directory between trial launches. Moving only those caches restored the first checksum exactly; [provenance.json](provenance.json) records the proof and file hashes. Codex never receives the oracle solution files. Agent-visible files and trusted verifier code were unchanged, and the submission ZIP excludes caches.

## Validation and provisioning records

| Run | Score / status | Seconds | Evidence |
|---|---|---|---|
| oracle-integration / oracle | 0.0 | 104.5 | [Trial](oracle/oracle-integration/unseen-subject-audit__oRsucse/result.json) |
| oracle-validated / oracle | 1.0 | 68.3 | [Trial](oracle/oracle-validated/unseen-subject-audit__cG34agX/result.json) |
| oracle-validated / oracle | 1.0 | 62.0 | [Trial](oracle/oracle-validated/unseen-subject-audit__Z5pXQZZ/result.json) |
| empty-negative / nop | 0.0 | 28.4 | [Trial](negative/empty-negative/unseen-subject-audit__KmZQB5e/result.json) |
| final-boundary-check / oracle | 1.0 | 65.0 | [Trial](oracle/final-boundary-check/unseen-subject-audit__GGD5jXM/result.json) |
| release-oracle / oracle | 1.0 | 72.3 | [Trial](oracle/release-oracle/unseen-subject-audit__d2bT9j6/result.json) |
| primary-daytona-gpt-6-luna / codex | DaytonaAuthenticationError | 9.8 | [Trial](models/primary-daytona-gpt-6-luna/unseen-subject-audit__rY69X8j/result.json) |
| primary-daytona-gpt-6-luna / codex | DaytonaAuthenticationError | 9.5 | [Trial](models/primary-daytona-gpt-6-luna/unseen-subject-audit__6ov9fq3/result.json) |
| primary-daytona-gpt-6-luna / codex | DaytonaAuthenticationError | 9.4 | [Trial](models/primary-daytona-gpt-6-luna/unseen-subject-audit__899xZ7u/result.json) |
| primary-daytona-gpt-6-luna / codex | DaytonaAuthenticationError | 9.3 | [Trial](models/primary-daytona-gpt-6-luna/unseen-subject-audit__JtNHYcF/result.json) |

The initial local oracle returned zero because its Python path omitted `/app`; this was a packaging defect corrected before model execution. Four initial Daytona provisioning records failed before model execution because the PDF text extractor interleaved a label into a wrapped credential. They are retained as infrastructure failures. A geometric table-cell extraction recovered the full key, but a real authenticated list request still returned HTTP 401 Invalid credentials. The earlier SDK preflight was a lazy iterator that made no request; that preflight was corrected. No Daytona sandbox or model execution started. The user authorized Docker fallback for the four final model attempts. No provider secret is part of the task or this package.

## Numerical reference and limits

On the local Linux reference, original subject-macro accuracy was 97.1149% for the baseline and 98.3501% for the candidate. Under the oracle’s person-disjoint folds it was 90.9127% and 90.6786%. The paired mean difference was −0.2342 percentage points, with descriptive 95% bounds [−1.8615, +1.6480] percentage points. The fixed one-point promotion policy therefore returns inconclusive. Retained-baseline private accuracy was 95.4614%; it does not affect reward.

Host macOS and Linux tree predictions differed at some ties. The agent image now computes its original report at build time, and the reference solution checks exact reproduction. Treat each captured sandbox’s own helper and trusted replay as authoritative for that attempt. Do not copy host-generated metrics into a different runtime.

Development-only calibration considered standardized LinearSVC with C=0.01 and C=0.001, three-neighbor classification, and 64-tree ExtraTrees. The pair was frozen before model attempts. The practical margin came from the design policy and was not fitted to model failures. The baseline is intentionally modest; the task does not measure discovery of the best classifier.

The public contract explains metric and decision semantics, so this may be easy for frontier agents. If all four attempts pass, report saturation of this instance and next test budgeted experiment selection with conflicting preliminary evidence. Do not conceal success or change grading after inspecting agent answers. If an attempt fails, inspect its trajectory before calling the cause scientific judgment.

## Proposed harder variant (not implemented)

Give the agent three plausible improvement claims and a budget of three additional experiments. Include one genuine improvement, one invalid evaluation claim, and one noisy seed-selection claim. Provide a documented experiment interface with explicit costs and deployment requirements, while leaving the diagnostic choice to the agent. Require it to allocate its budget before results are revealed, then submit evidence and a decision for each claim. A trusted experiment service must record budget use; agent-authored logs cannot establish which experiments ran.

This adds experiment selection under limited information to the numerical audit. It needs independently reproducible positive and negative controls and four new attempts under a new task version. Its difficulty and learning value remain hypotheses; it is not part of this OA implementation.

Alternative valid participant partitions can produce a different policy decision; the corresponding numerical evidence must reproduce. Adaptive fold choice remains a limitation. The bootstrap is conditional on overlapping CV fits and a small participant population. One task and four attempts cannot support a general model ranking, a broad research-capability claim, or RL learning improvement.

## Time and costs

Implementation timing started at 2026-11-06 21:06:36 America/Chicago (2026-11-07 03:06:36 UTC). Job records provide measured setup, agent, and verifier times; work-log.json records the final packaging checkpoint. Earlier research preparation was not timed; combined compliance with the OA’s five-hour limit is not claimed. The token cost above is Harbor’s estimate, not an invoice. No Daytona sandbox was provisioned; Daytona billing was not inspected.

The raw result files, verifier diagnostics, and available trajectories are included. `controls.json` contains the nine semantic/adversarial controls and `unit-tests.txt` contains the captured unit-test output.
