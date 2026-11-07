# CTC results: Luna passes all four attempts

All four Codex/gpt-6-luna attempts earned 1.0 on the frozen CTC task. There were zero infrastructure exceptions. This version did not expose a genuine final capability failure. No Astra attempt was launched.

## Primary model results

Configuration: Harbor 0.25.0; Codex 0.163.0; openai/gpt-6-luna; medium effort; Docker; four attempts; concurrency two; no automatic retries. Agent budget: 20 minutes, two CPU cores, 4 GiB. Task linear memory: 1.5 MiB. Native web search is disabled.

| Attempt | Reward | Private cases | Total seconds | Main strategy | Evidence |
|---|---:|---:|---:|---|---|
| 1: Rx7Bz2J | 1.0 | 16/16 | 201.9 | Exact double checkpoints plus short replay blocks; replaced imprecise float compression | [Trial](../models/ctc-primary-gpt-6-luna/ctc-memory-kernel__Rx7Bz2J/result.json) |
| 2: Ky5pUP8 | 1.0 | 16/16 | 152.9 | Sparse checkpoints plus replay blocks; fixed excessive prefix recomputation | [Trial](../models/ctc-primary-gpt-6-luna/ctc-memory-kernel__Ky5pUP8/result.json) |
| 3: xjfwvvW | 1.0 | 16/16 | 116.5 | Coarse checkpoints plus short replay blocks | [Trial](../models/ctc-primary-gpt-6-luna/ctc-memory-kernel__xjfwvvW/result.json) |
| 4: iYoKavd | 1.0 | 16/16 | 226.8 | Reused the output gradient buffer for checkpoints with a lifetime constraint | [Trial](../models/ctc-primary-gpt-6-luna/ctc-memory-kernel__iYoKavd/result.json) |

Each run passed the same 16 private cases. These are four attempts on one task, not 64 independent tasks. All trial checksums equal `440f3e142539b2b27e1bda92a729ff2b356703ab40bc059f01e6e290ee0ccd51`, matching the pre-run freeze and oracle/no-op controls. The task, inputs, grader, tolerances, and resource limits were not changed during the batch.

Agent execution took 94.7 to 204.7 seconds; total trial time including setup and verification was 116.5 to 226.8 seconds. The complete two-concurrent batch took about 7 minutes 9 seconds. Harbor estimates USD 0.053421 for 1,088,429 input tokens (964,078 cached) and 56,479 output tokens. This is a pricing-based estimate, not verified provider billing. [Machine-readable summary](luna-summary.json) and [batch specification](luna-batch-spec.json) preserve the exact records.

## What the trajectories establish

The task engaged real memory and numerical reasoning. One attempt first used float-compressed rows and saw gradient errors around 2e-4 on difficult cases; it moved back to exact double storage and a two-level replay scheme. Two attempts initially exhausted fuel by replaying too much prefix work. They added sparse checkpoints or reused gradient-buffer storage with a safe reverse-pass lifetime. Those were intermediate debugging failures, not final benchmark failures.

Three final kernels use sparse outer checkpoints and smaller inner replay blocks. The fourth temporarily stores checkpoints in output memory and overwrites them only after their values are no longer needed. These valid alternatives were more efficient than the generic recursive oracle in three runs. Largest-case fuel was about 2.58 to 2.62 billion in those runs, and about 8.36 billion in the output-buffer variant. The largest-case allowance is 9.80 billion. Fuel measures pinned-engine work, not hardware throughput.

The [retained agent source](agent-source/) contains every final C implementation and build script. All four were recompiled after completion in a network-isolated compiler container; every resulting Wasm module was byte-identical to the submitted artifact. [Source provenance](agent-source/provenance.json) records hashes and capture/reconstruction method. Inspection found generic input-dependent recurrences and storage planning, with no fixture lookup in those implementations. This supports a valid-solution interpretation; it is not an exhaustive security audit.

## Why the harder variant still saturated

The original audit helper computed most of the evidence. CTC removed that shortcut, but the mathematical recurrences were still supplied and the remaining optimization was a familiar checkpoint/recompute pattern on one sequence structure. Public examples and numerical feedback let agents quickly repair their first implementation. That feedback is fair and should stay. The hypothesis that a tighter memory ceiling would create sufficient difficulty was not supported at the measured model and budget.

Do not spend on Astra to establish difficulty for this same setting. The smaller allowed model already solved it four times in under four minutes per trial. Do not shorten the budget below observed solve times, hide test families, or tighten tolerances after seeing these results to manufacture a failure. Four successes also do not prove universal reliability; broader instances and other models remain unmeasured.

The recommended next design is broader memory-planning structure: schedules for branched autodiff graphs with unequal tensor sizes and recomputation costs. The existing chain-specific recipe would need to become a general planner. Keep that as a separately versioned proposal and calibrate its oracle, baseline, no-op, and public-family coverage before paid trials. Its implementation and model difficulty are unverified. The [research note](../../docs/RESEARCH.md) specifies the proposed contract and evidence required.

## Controls and reproducibility

| Control | Result | Meaning |
|---|---|---|
| Harbor oracle, two attempts | 1.0, 1.0 | A feasible solution survives final artifact transfer and independent grading |
| Harbor no-op | 0.0 | Empty output fails |
| Unchanged dense baseline, local Wasmtime | 0.0; 12/16 cases pass | Large-case storage requires an algorithm change |
| Reference, boundary, and adversarial unit suite | 41 tests pass | Numerical semantics, staging, imports, memory, fuel, buffers, and wrong outputs are checked |
| Additional seeded oracle inputs | 100/100 pass | Reference feasibility extends beyond the frozen fixtures |

Raw controls: `harbor/ctc-oracle-v2/`, `harbor/ctc-noop-v2/`, `oracle-local/`, `baseline-local/`, and `controls.json`. Fixture hashes are in `fixture-manifest.json`; the complete task manifest is `freeze.json`.

An initial 2 MiB feasibility prototype admitted block checkpointing. The final 1.5 MiB limit and recursive oracle were established before CTC model rollouts. LLVM 14 rejected the initial unsupported `--export-memory` flag; this setup defect was fixed before model evaluation. No model attempts were discarded.

The original measured implementation interval is in `../work-log.json`; research and redesign add work outside it. Compliance of the complete effort with the OA five-hour timebox is not claimed. Daytona remains unvalidated after the supplied key returned HTTP 401; Docker is the explicitly authorized fallback.
