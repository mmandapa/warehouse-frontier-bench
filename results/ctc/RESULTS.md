# CTC task results

Status: locally validated; additional paid model trials await authorization.

| Task / setting | Attempts | Rewards | Interpretation |
|---|---:|---|---|
| v1 audit, Codex/gpt-6-luna, medium, Docker | 4 | 1, 1, 1, 1 | Saturated at this setting; helper supplied most evidence |
| CTC, Harbor oracle, Docker | 2 | 1, 1 | Reference is feasible through the final artifact/verifier path |
| CTC, Harbor no-op, Docker | 1 | 0 | Untouched workspace fails |
| CTC, unchanged dense baseline, local Wasmtime | 1 suite | 0; 12/16 cases pass | Large cases exhaust permitted storage; small-case semantics work |
| CTC, Codex/model | 0 | Not run | No empirical difficulty claim yet |

The final memory ceiling is 1,572,864 bytes. The recursive oracle passes all 16 private cases. Its maximum observed fuel use is 5,430,092,367; the largest-case allowance is 9,800,528,000, about 1.80 times that use. Local largest-case execution was about 0.34 seconds; these timings exclude module compilation and are diagnostic, not hardware-performance claims. Independent Harbor diagnostics preserve the actual container measurements.

Raw Harbor records: `harbor/ctc-oracle-v2/` and `harbor/ctc-noop-v2/`. Local oracle and baseline records: `oracle-local/` and `baseline-local/`. Fixture hashes: `fixture-manifest.json`. Reference, packaging, and sandbox controls are in the repository's pytest suite: **41 tests pass**. An additional 100 seeded oracle cases spanning the documented logit range also pass, with maximum absolute gradient error about 1.31e-10 against the independent reference. See `controls.json`.

A first 2 MiB feasibility prototype used block checkpointing and passed locally. Before any CTC model run, the final limit was reduced to 1.5 MiB and the oracle changed to recursive recomputation. The compiler's LLVM 14 linker did not support `--export-memory`; removing this unsupported flag fixed the initial build. These were setup/calibration changes, not model capability failures. No model runs were discarded.

The next authorized batch will use four independent attempts, medium effort, 20-minute agent budget, two-core/4-GiB containers, Codex 0.163.0, Harbor 0.25.0, no web search, and no automatic retries. The task is frozen before launch. Inspect failures against trajectories before interpreting reward. If all runs pass, report that result and propose a separately versioned harder variant. A genuine weaker-model failure is acceptable for the OA, but does not establish frontier difficulty.

The original measured implementation interval is in `../work-log.json`; this redesign adds further work outside it. Earlier research was not timed. We do not claim the full project took less than five hours. Daytona remains unvalidated because the assignment credential returned 401; Docker is the authorized fallback.
