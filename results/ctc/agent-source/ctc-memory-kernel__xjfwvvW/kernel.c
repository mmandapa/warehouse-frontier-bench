#include "ctc_math.h"

/*
 * Checkpointed CTC forward/backward.  The caller's input and output buffers
 * occupy most of the module's 1.5 MiB.  Keep only a set of segment-end
 * forward rows and a small working block, recomputing rows inside each
 * segment while walking backwards.
 */
int solve(int T,int C,int U,int blank,const double*x,const int32_t*y,
          double*loss,double*g) {
    if (impossible(T,C,U,y,loss,g)) return 1;

    const int S=2*U+1;
    uintptr_t scratch=(uintptr_t)(g+T*C);
    scratch=(scratch+64+7)&~(uintptr_t)7;
    uintptr_t memend=(uintptr_t)__builtin_wasm_memory_size(0)*65536;
    if (scratch>memend) return 2;

    const uintptr_t rowbytes=(uintptr_t)S*sizeof(double);
    int rows=(int)((memend-scratch)/rowbytes);
    if (rows<1) return 2;

    /* Balance working rows and checkpoint rows to limit recomputation. */
    int K=rows/2;
    if (K<1) K=1;
    if (K>T) K=T;
    int checkpoint_capacity=rows-K;
    int B=T;
    if (K<T && checkpoint_capacity>0) {
        int segments_capacity=checkpoint_capacity+1;
        B=(T+segments_capacity-1)/segments_capacity;
        if (B<1) B=1;
    }
    int nsegments=(T+B-1)/B;
    int ncheck=nsegments-1;
    if ((uintptr_t)(ncheck+K)*rowbytes>memend-scratch) return 2;

    double *checkpoints=(double*)scratch;
    double *block=checkpoints+(uintptr_t)ncheck*S;

    setup(T,C,U,blank,x,y);
    for (int s=0;s<S;s++) prev[s]=-INFINITY;
    prev[0]=0.0;

    /* Initial forward pass: save the state immediately before each segment. */
    int ci=0;
    for (int t=0;t<T;t++) {
        forward_row(t,C,S,blank,x,prev,tmp);
        for (int s=0;s<S;s++) prev[s]=tmp[s];
        if (t+1<T && (t+1)%B==0) {
            for (int s=0;s<S;s++) checkpoints[(uintptr_t)ci*S+s]=prev[s];
            ci++;
        }
    }
    double logZ=U ? addlog(prev[S-1],prev[S-2]) : prev[0];
    *loss=-logZ;

    for (int s=0;s<S;s++) beta[s]=-INFINITY;
    beta[S-1]=0.0;
    if (U) beta[S-2]=0.0;

    /* Walk segments and then blocks in reverse, preserving the beta frontier. */
    for (int q=nsegments-1;q>=0;q--) {
        int segstart=q*B;
        int segend=segstart+B;
        if (segend>T) segend=T;

        for (int chunkend=segend-1;chunkend>=segstart;) {
            int chunkstart=chunkend-K+1;
            if (chunkstart<segstart) chunkstart=segstart;

            if (q==0) {
                for (int s=0;s<S;s++) prev[s]=-INFINITY;
                prev[0]=0.0;
            } else {
                const double *cp=checkpoints+(uintptr_t)(q-1)*S;
                for (int s=0;s<S;s++) prev[s]=cp[s];
            }

            /* Recreate this segment's prefix, then retain the current block. */
            for (int t=segstart;t<=chunkend;t++) {
                double *out=(t>=chunkstart)
                    ? block+(uintptr_t)(t-chunkstart)*S : tmp;
                forward_row(t,C,S,blank,x,prev,out);
                for (int s=0;s<S;s++) prev[s]=out[s];
            }

            for (int t=chunkend;t>=chunkstart;t--) {
                gradient_row(t,C,S,x,block+(uintptr_t)(t-chunkstart)*S,
                             logZ,g);
                if (t) backward_row(t,C,S,blank,x);
            }
            chunkend=chunkstart-1;
        }
    }
    return 0;
}
