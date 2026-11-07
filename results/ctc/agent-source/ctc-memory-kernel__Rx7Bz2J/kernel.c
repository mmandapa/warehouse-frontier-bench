#include "ctc_math.h"

static void forward_step(int t, int C, int S, int blank, const double *x,
                         const double *in, double *out) {
    for (int s = 0; s < S; ++s) {
        double v = in[s];
        if (s) v = addlog(v, in[s - 1]);
        if (s >= 2 && seq[s] != blank && seq[s] != seq[s - 2])
            v = addlog(v, in[s - 2]);
        out[s] = v + x[(uintptr_t)t * C + seq[s]] - norm[t];
    }
}

static void backward_step(int t, int C, int S, int blank, const double *x) {
    for (int s = 0; s < S; ++s) {
        double v = beta[s] + x[(uintptr_t)t * C + seq[s]] - norm[t];
        if (s + 1 < S)
            v = addlog(v, beta[s + 1] + x[(uintptr_t)t * C + seq[s + 1]] - norm[t]);
        if (s + 2 < S && seq[s + 2] != blank && seq[s + 2] != seq[s])
            v = addlog(v, beta[s + 2] + x[(uintptr_t)t * C + seq[s + 2]] - norm[t]);
        tmp[s] = v;
    }
    for (int s = 0; s < S; ++s) beta[s] = tmp[s];
}

static void write_gradient(int t, int C, int S, const double *x,
                           const double *a, double logZ, double *g) {
    uintptr_t base = (uintptr_t)t * C;
    for (int c = 0; c < C; ++c) g[base + c] = exp(x[base + c] - norm[t]);
    for (int s = 0; s < S; ++s)
        g[base + seq[s]] -= exp(a[s] + beta[s] - logZ);
}

int solve(int T, int C, int U, int blank, const double *x, const int32_t *y,
          double *loss, double *g) {
    if (impossible(T, C, U, y, loss, g)) return 1;

    const int S = 2 * U + 1;
    const uintptr_t after_outputs = (uintptr_t)(g + (uintptr_t)T * C) + 64;
    const uintptr_t scratch = (after_outputs + 7) & ~(uintptr_t)7;
    const uintptr_t mem_end = (uintptr_t)__builtin_wasm_memory_size(0) * 65536u;
    if (scratch >= mem_end) return 2;

    /* Keep exact double rows at outer checkpoints and in a short local block.
       The local block is rebuilt from its outer checkpoint when needed. */
    const uintptr_t row_bytes = (uintptr_t)S * sizeof(double);
    const uintptr_t available = mem_end - scratch;
    int capacity = (int)(available / row_bytes);
    int block = 0, outer = 0;
    if (capacity >= T) {
        block = outer = T;
    } else {
        int best_cost = 0x7fffffff;
        for (int k = 1; k <= capacity && k <= T; ++k) {
            int l = (T + (capacity - k + 1) - 1) / (capacity - k + 1);
            if (l < k) l = k;
            if (l > T) continue;
            int nb = (T + l - 1) / l;
            int nc = nb - 1;
            if (nc + k > capacity) continue;
            /* Approximate the repeated prefix work; this is monotone with the
               exact work and keeps selection constant-time per candidate. */
            int cost = T + (T * l) / (2 * k);
            if (cost < best_cost) { best_cost = cost; block = k; outer = l; }
        }
    }
    if (!block) return 2;

    int nblocks = (T + outer - 1) / outer;
    int ncheck = nblocks - 1;
    double *check_data = (double *)scratch;
    double *local_data = check_data + (uintptr_t)ncheck * S;

    setup(T, C, U, blank, x, y);
    for (int s = 0; s < S; ++s) prev[s] = -INFINITY;
    prev[0] = 0.0;
    for (int t = 0; t < T; ++t) {
        forward_step(t, C, S, blank, x, prev, tmp);
        for (int s = 0; s < S; ++s) prev[s] = tmp[s];
        if ((t + 1) % outer == 0 && t + 1 < T) {
            int ci = (t + 1) / outer - 1;
            for (int s = 0; s < S; ++s)
                check_data[(uintptr_t)ci * S + s] = prev[s];
        }
    }
    double logZ = U ? addlog(prev[S - 1], prev[S - 2]) : prev[0];
    *loss = -logZ;

    for (int s = 0; s < S; ++s) beta[s] = -INFINITY;
    beta[S - 1] = 0.0;
    if (U) beta[S - 2] = 0.0;

    for (int b = nblocks - 1; b >= 0; --b) {
        int begin = b * outer;
        int end = begin + outer;
        if (end > T) end = T;
        int outer_begin = begin;
        for (int inner_end = end; inner_end > outer_begin; ) {
            int inner_begin = inner_end - block;
            if (inner_begin < outer_begin) inner_begin = outer_begin;
            if (b == 0) {
                for (int s = 0; s < S; ++s) prev[s] = -INFINITY;
                prev[0] = 0.0;
            } else {
                int ci = b - 1;
                for (int s = 0; s < S; ++s)
                    prev[s] = check_data[(uintptr_t)ci * S + s];
            }
            for (int t = outer_begin; t < inner_begin; ++t) {
                forward_step(t, C, S, blank, x, prev, tmp);
                for (int s = 0; s < S; ++s) prev[s] = tmp[s];
            }
            int len = inner_end - inner_begin;
            for (int j = 0; j < len; ++j) {
                int t = inner_begin + j;
                forward_step(t, C, S, blank, x, prev, tmp);
                for (int s = 0; s < S; ++s) {
                    prev[s] = tmp[s];
                    local_data[(uintptr_t)j * S + s] = tmp[s];
                }
            }
            for (int j = len - 1; j >= 0; --j) {
                int t = inner_begin + j;
                write_gradient(t, C, S, x, local_data + (uintptr_t)j * S,
                               logZ, g);
                if (t) backward_step(t, C, S, blank, x);
            }
            inner_end = inner_begin;
        }
    }
    return 0;
}
