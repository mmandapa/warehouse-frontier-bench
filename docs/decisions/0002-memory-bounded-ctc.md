# ADR-002: Replace the saturated audit with a memory-bounded numerical kernel task

Status: Accepted and validated through Harbor oracle/no-op controls; empirical model difficulty is not yet established.

Date: 2026-11-06

## Evidence and requirements

All four v1 Codex/gpt-6-luna trajectories passed. They read a contract containing the evaluation rule and called a supplied helper that computed the entire evidence object. The remaining work was a participant-to-fold mapping and JSON assembly. Keep these results as a saturation baseline; changing its grader after observing answers would invalidate the comparison.

The replacement must require substantive research engineering, have a feasible reference solution and a failing no-op, stay CPU-only and below the OA's two-hour per-task limit, and preserve a reliable verifier boundary. Difficulty must be measured on a frozen version. Do not create failure by withholding interface requirements, breaking dependencies, or tightening tolerances after agent runs.

## Alternatives and decision

A less guided statistical audit would still mostly test a familiar grouped-split recipe. A GPU kernel optimization task is directly relevant but currently requires working GPU sandbox access. Choose a CPU CTC loss-and-logit-gradient kernel under a 1.5-MiB WebAssembly linear-memory limit. The supplied dense baseline is correct for small inputs but cannot store its full dynamic-programming table for large shapes. The agent must change its storage/compute strategy while preserving numerical semantics.

The reference uses recursive recomputation; alternatives are accepted if they meet the same behavior, memory, and fuel bounds. An initial two-MiB feasibility prototype admitted simple block checkpointing, so the limit was tightened before any replacement-task model trial. The 1.5-MiB ceiling includes module stack, static data, and I/O buffers. A generous deterministic fuel budget bounds excessive recomputation; it measures instrumented work, not GPU speed or real hardware throughput. Wall time remains a diagnostic and outer timeout.

## Component and trust boundaries

The agent owns C source, local experiments, and the submitted WebAssembly bytes. A fresh verifier owns private inputs and expected outputs. It compiles the module with a pinned Wasmtime engine, supplies no imports or WASI, limits linear memory and fuel, and exchanges only numeric values through bounded memory. It never imports agent Python or gives the kernel filesystem, clock, network, or grader references. Input-buffer and guard checks catch accidental corruption. Container limits also bound host/JIT resources; a Wasmtime store's linear-memory limit does not bound all host allocation.

The trusted full-table NumPy reference is checked against exhaustive path enumeration, finite differences, and PyTorch CTCLoss after log_softmax. Fixed fixture hashes are recorded before model trials. The agent sees representative cases from every test family and the complete ABI and resource contract. Binary reward requires every private case to pass; diagnostics expose each failure. Missing output and the unchanged dense baseline must receive zero, and the checkpointed reference must receive one through Harbor.

## Sources and limits

- [Graves et al., CTC (2006)](https://www.cs.toronto.edu/~graves/icml_2006.pdf): sequence-label marginalization and forward/backward semantics.
- [PyTorch CTCLoss](https://docs.pytorch.org/docs/2.15/generated/torch.nn.CTCLoss.html): independent implementation, target and blank semantics.
- [Chen et al., sublinear-memory training](https://arxiv.org/abs/1604.06174): recomputation/checkpointing as a real memory/compute tradeoff.
- [Wasmtime Python API](https://bytecodealliance.github.io/wasmtime-py/): fuel and store resource limits.
- [METR on reward hacking](https://metr.org/blog/2025-06-05-recent-reward-hacking/): do not run submitted code with access to reference outputs or grading machinery.

This measures numerical implementation and memory planning for a standard ML primitive. It is not novel algorithm discovery, a broad autoresearch score, or proof of learning improvement. Public algorithms can be familiar to models; only held-version agent trials establish whether this particular composition is difficult.
