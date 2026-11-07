#include <math.h>
#include <stdint.h>

#define MAX_T 3072
#define MAX_U 256
#define MAX_S (2 * MAX_U + 1)

/* These arrays live before __heap_base.  Forward rows themselves are kept in
   the caller-provided scratch area, after the output guard. */
static int seq[MAX_S];
static double norm[MAX_T];
static double prev[MAX_S], beta[MAX_S], tmp[MAX_S];

static double addlog(double a, double b) {
    if (a == -INFINITY) return b;
    if (b == -INFINITY) return a;
    double m = a > b ? a : b;
    double d = -fabs(a - b);
    /* Terms this small cannot affect the requested tolerances, and avoiding
       libm calls for them matters in the recomputing schedule. */
    if (d < -40.0) return m;
    return m + log1p(exp(d));
}

static void setup(int T, int C, int U, int blank,
                  const double *x, const int32_t *y) {
    for (int s = 0; s < 2 * U + 1; ++s)
        seq[s] = (s & 1) ? y[s / 2] : blank;
    for (int t = 0; t < T; ++t) {
        const double *row = x + (uintptr_t)t * C;
        double m = row[0];
        for (int c = 1; c < C; ++c) if (row[c] > m) m = row[c];
        double sum = 0.0;
        for (int c = 0; c < C; ++c) sum += exp(row[c] - m);
        norm[t] = m + log(sum);
    }
}

static void forward_row(int t, int C, int S, const double *x,
                        const double *in, double *out) {
    const double *row = x + (uintptr_t)t * C;
    for (int s = 0; s < S; ++s) {
        double v = in[s];
        if (s) v = addlog(v, in[s - 1]);
        if (s >= 2 && (s & 1) && seq[s] != seq[s - 2])
            v = addlog(v, in[s - 2]);
        out[s] = v + row[seq[s]] - norm[t];
    }
}

/* Given beta at time t, produce beta at t-1. */
static void backward_row(int t, int C, int S, const double *x) {
    const double *row = x + (uintptr_t)t * C;
    for (int s = 0; s < S; ++s) {
        double v = beta[s] + row[seq[s]] - norm[t];
        if (s + 1 < S)
            v = addlog(v, beta[s + 1] + row[seq[s + 1]] - norm[t]);
        if (s + 2 < S && (s & 1) && seq[s + 2] != seq[s])
            v = addlog(v, beta[s + 2] + row[seq[s + 2]] - norm[t]);
        tmp[s] = v;
    }
    for (int s = 0; s < S; ++s) beta[s] = tmp[s];
}

static void gradient_row(int t, int C, int S, const double *x,
                         const double *a, double logZ, double *g) {
    const double *row = x + (uintptr_t)t * C;
    double *gr = g + (uintptr_t)t * C;
    for (int c = 0; c < C; ++c) gr[c] = exp(row[c] - norm[t]);
    for (int s = 0; s < S; ++s)
        gr[seq[s]] -= exp(a[s] + beta[s] - logZ);
}

static int impossible(int T, int U, const int32_t *y,
                      double *loss, double *g, int C) {
    int needed = U;
    for (int i = 1; i < U; ++i) if (y[i] == y[i - 1]) ++needed;
    if (T >= needed) return 0;
    *loss = INFINITY;
    for (int i = 0; i < T * C; ++i) g[i] = 0.0;
    return 1;
}
