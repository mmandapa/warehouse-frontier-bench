# CTC kernel contract

## Mathematical behavior

Inputs are a single sequence of unnormalized logits `x[T,C]` and target labels `y[U]`. Set `p[t,c] = softmax(x[t,:])[c]`. A path contains one class per frame. Collapse a path by first merging consecutive equal classes, then removing all blanks. Let A be all paths that collapse to exactly `y`.

Return the unnormalized sequence loss `loss = -log(sum(path in A) product(t) p[t,path[t]])`, with no averaging over frames, labels, or batches. Return the derivative with respect to **unnormalized logits**, not log probabilities: `g[t,c] = p[t,c] - P(path[t]=c | collapse(path)=y)`.

If no valid path exists, return status **1**, positive infinity loss, and an entirely zero gradient. Otherwise return status **0**, a finite loss, and the complete gradient. No other status is accepted. Adjacent equal target labels require an intervening blank. An empty target is valid and allows only all-blank paths.

## Input domain

- `1 <= T <= 3072`, `2 <= C <= 24`, `0 <= U <= 256`.
- `0 <= blank < C`; blank is not necessarily zero.
- Every target is an integer in `[0,C)` different from blank.
- Logits are finite float64 values in `[-2000,2000]`. Extreme values and large row offsets are possible.
- Each call uses a fresh instance; cross-call persistence is not required. Private fixtures cover empty targets, repeated labels, nonzero blanks, minimally feasible alignments, impossible alignments, extreme logits, long sequences, and maximum-memory cases. The public suite represents all eight families. Private inputs differ; no additional family or narrower tolerance is hidden.

## WebAssembly ABI

Export a linear `memory`, an i32 global `__heap_base >= 65536`, and this function with eight i32 arguments and one i32 result:

```c
int solve(int T, int C, int U, int blank,
          const double *logits, const int32_t *target,
          double *loss, double *grad_logits);
```

Pointers are byte offsets into exported memory. Arrays are contiguous, row-major, little-endian. Both output arrays must be fully written. The input buffers are read-only. The harness places aligned, non-overlapping inputs and outputs after `__heap_base`, which must mark the end of stack/static storage. Leave enough memory for these buffers, alignment, and guards. Scratch space may follow the final output guard; the baseline demonstrates locating that space. Do not write guard bytes or input bytes. `U=0` needs no target dereference.

The exact allocation sequence is in `/app/ctcbench/runner.py`; it is the same in the private verifier. In particular: logits; 64-byte guard; aligned target; 64-byte guard; aligned loss; gradient; 64-byte guard. There is also a guard immediately before logits. No other host state is accessible.

## Resource and numerical limits

- Module file: regular file, at most **1,048,576 bytes**. No imports of any kind, including WASI, are supplied.
- Total linear memory: at most **1,572,864 bytes (1.5 MiB / 24 Wasm pages)**, including stack, static data, all inputs/outputs, and scratch. There is one memory and one instance. The provided build script allocates this maximum and a 64 KiB stack. Increasing initial or maximum memory does not bypass the verifier's store limit.
- Deterministic Wasmtime fuel per case: `50_000_000 + 6000*T*(2*U+1) + 4000*T*C`. Wasmtime version is 50.0.1. Fuel is an engine-specific work bound, not elapsed milliseconds. An infinite loop or excessive recomputation traps. No clock, filesystem, network, random source, or host callback is available to the module.
- Finite loss: `abs(actual-expected) <= 1e-6 + 1e-8*abs(expected)`.
- Each gradient element: `abs(actual-expected) <= 2e-6 + 2e-5*abs(expected)`. All must be finite for feasible alignments.
- Impossible alignments require positive infinity and exactly zero gradient.

No wall-clock speedup is required or scored. The outer verifier timeout is five minutes. The loss and gradient must be computed for the supplied inputs; lookup tables keyed to fixtures are not valid solutions.

## Tools and scoring

`bash build.sh [source.c]` uses LLVM 14, WASI libc's math library, and no entry point. The resulting module has no WASI imports when only the provided numerical routines are used. `python -m ctcbench.grade --module submission/kernel.wasm --fixtures public.npz` checks the public suite and reports fuel usage. You can inspect `public.npz` with NumPy and create additional local numerical experiments.

Binary reward is **1 only if every private case passes**, otherwise **0**. Case-pass fraction and fuel usage are diagnostics and do not change reward. The independent verifier uses its own code and expected outputs and ignores your local logs, scorer changes, and reward files.
