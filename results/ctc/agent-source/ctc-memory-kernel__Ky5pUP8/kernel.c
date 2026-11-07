#include "ctc_math.h"

int solve(int T, int C, int U, int blank,
          const double *x, const int32_t *y, double *loss, double *g) {
    if (impossible(T, U, y, loss, g, C)) return 1;

    const int S = 2 * U + 1;
    setup(T, C, U, blank, x, y);

    /* The ABI leaves a guard after grad. Scratch begins after that guard. */
    uintptr_t scratch = ((uintptr_t)(g + (uintptr_t)T * C) + 64 + 7) & ~(uintptr_t)7;
    uintptr_t limit = (uintptr_t)__builtin_wasm_memory_size(0) * 65536u;
    int rows = (int)((limit - scratch) / ((uintptr_t)S * sizeof(double)));
    if (rows < 1) return 2;

    /* Store sparse checkpoints between reverse segments, then regenerate
       each segment's local forward rows. This avoids replaying every prefix
       from frame zero while keeping the same bounded scratch requirement. */
    int interval = (2 * T + rows - 1) / rows;
    if (interval < 1) interval = 1;
    int checkpoint_rows = (T - 1) / interval;
    int block_rows = rows - checkpoint_rows;
    if (block_rows > interval) block_rows = interval;
    if (block_rows < 1) return 2;
    double *checkpoints = (double *)scratch;
    double *block = checkpoints + (uintptr_t)checkpoint_rows * S;

    /* Compute log likelihood with two rolling rows and save segment starts. */
    for (int s = 0; s < S; ++s) prev[s] = -INFINITY;
    prev[0] = 0.0;
    for (int t = 0; t < T; ++t) {
        forward_row(t, C, S, x, prev, tmp);
        if (t + 1 < T && (t + 1) % interval == 0) {
            double *dst = checkpoints + (uintptr_t)((t + 1) / interval - 1) * S;
            for (int s = 0; s < S; ++s) dst[s] = tmp[s];
        }
        for (int s = 0; s < S; ++s) prev[s] = tmp[s];
    }
    const double logZ = U ? addlog(prev[S - 1], prev[S - 2]) : prev[0];
    *loss = -logZ;

    for (int s = 0; s < S; ++s) beta[s] = -INFINITY;
    beta[S - 1] = 0.0;
    if (U) beta[S - 2] = 0.0;

    /* Walk backward by blocks. Each block's alpha rows are regenerated from
       time zero, trading bounded recomputation for O(block_rows * S) memory. */
    for (int seg_end = T; seg_end > 0; ) {
        int seg_begin = ((seg_end - 1) / interval) * interval;
        int end = seg_end;
        while (end > seg_begin) {
            int begin = end - block_rows;
            if (begin < seg_begin) begin = seg_begin;
            if (seg_begin == 0) {
                for (int s = 0; s < S; ++s) prev[s] = -INFINITY;
                prev[0] = 0.0;
            } else {
                const double *cp = checkpoints + (uintptr_t)(seg_begin / interval - 1) * S;
                for (int s = 0; s < S; ++s) prev[s] = cp[s];
            }
            for (int t = seg_begin; t < end; ++t) {
                forward_row(t, C, S, x, prev, tmp);
                if (t >= begin) {
                    double *dst = block + (uintptr_t)(t - begin) * S;
                    for (int s = 0; s < S; ++s) dst[s] = tmp[s];
                }
                for (int s = 0; s < S; ++s) prev[s] = tmp[s];
            }

            for (int t = end - 1; t >= begin; --t) {
                const double *a = block + (uintptr_t)(t - begin) * S;
                gradient_row(t, C, S, x, a, logZ, g);
                if (t > 0) backward_row(t, C, S, x);
            }
            end = begin;
        }
        seg_end = seg_begin;
    }
    return 0;
}
