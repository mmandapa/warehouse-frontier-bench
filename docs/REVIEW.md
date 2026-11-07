# Pre-publication engineering review

Scope: the CTC replacement, preserved v1 evidence, and private repository publication. Paid CTC model trials are pending separate authorization.

## Findings addressed

- LLVM 14 lacks `--export-memory`; the provided toolchain exports its default memory without that flag. Oracle compilation is verified through Harbor.
- A malformed module exporting a function in place of `__heap_base` could have produced a Python attribute exception. The runtime now validates export kinds and i32 global type before access; a regression test confirms a graded task failure.
- Git line-ending normalization could change v1 task checksums after cloning. `.gitattributes` preserves bytes verbatim, including original UCI documentation. Raw trajectories and dataset text retain their original whitespace.
- Rebuilt build-context source matches canonical source; public and private fixture hashes and public-family coverage are tested. Neither reference implementation nor private fixtures enter the agent context.
- Package and staged-file scans reject credential-like values. The OA PDF, provider keys, host auth files, virtual environment, and Python caches are excluded.

## Verified behavior

- Independent loss/gradient checks: exhaustive tiny paths, finite differences, and float64 PyTorch CTCLoss/autograd for generated feasible fixtures.
- 41 unit tests pass, including numerical semantics, build-context boundaries, artifact validation, forbidden imports, memory cap, fuel exhaustion, input mutation, output guards, and plausible wrong answers.
- Recursive oracle passes every private fixture and 100 additional seeded inputs, including extreme logits.
- Two Harbor oracle attempts earn 1.0; the no-op earns 0.0 with no infrastructure exception. The unchanged compiled dense baseline earns 0.0 and passes 12/16 small cases.
- All Harbor control checksums match the frozen task. Dependency consistency and locked resolution pass. uv has no native advisory-audit command in this installed version; no comprehensive supply-chain audit is claimed.

## Operational boundaries and limits

Each trial owns its workspace and output directory. Two concurrent model trials do not share mutable research state. A fresh Wasmtime store/instance owns each case's linear memory and fuel. Expected arrays remain in trusted Python memory and are never written into module memory. Only `kernel.wasm` crosses the agent/verifier boundary.

No database or persistent service is required. Model authentication belongs to the launcher, not the numerical module. There is no application authentication flow. Diagnostics and rewards are written via temporary-file replacement. Model retries are disabled to preserve attempt accounting; provisioning errors must be reported separately. The wrapper bounds the overall job, while Harbor bounds setup, agent execution, and verification. After an outer timeout, inspect for surviving Docker containers; the wrapper does not claim perfect orphan cleanup.

The numerical verifier is fast in measured cases; Docker builds and agent interaction dominate end-to-end work. Wasmtime's fuel is version-specific, and its linear-memory limit excludes compilation/host allocations; container limits and the verifier timeout provide outer bounds. A multi-tenant untrusted submission service would need stronger compilation resource isolation, worker supervision, artifact retention policy, and load/backpressure controls. Those are outside this local batch benchmark.

The mathematical problem is standard, private fixtures are finite, and WebAssembly is not a proof of malicious-code safety. No adversarial model rollout has been run for the new task. No model difficulty, hardware speedup, frontier ranking, or RL learning gain follows from the controls alone. A four-attempt frozen model batch and trajectory diagnosis remain the next empirical gate.
