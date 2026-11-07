/*
 * Memory bounded CTC forward/backward.  The full alpha table is too large for
 * the module's linear memory, so save one alpha vector at each block boundary.
 * During the reverse pass, reconstruct the rows within a block from its
 * checkpoint.  Checkpoints live after the output guard, so the gradient can be
 * written as soon as each row is complete.
 */
#include "ctc_math.h"
int solve(int T,int C,int U,int blank,const double*x,const int32_t*y,double*loss,double*g){
    if(impossible(T,C,U,y,loss,g))return 1;
    int S=2*U+1;
    uintptr_t start=((uintptr_t)(g+T*C)+64+7)&~(uintptr_t)7;
    uintptr_t memend=(uintptr_t)__builtin_wasm_memory_size(0)*65536;
    uintptr_t avail=memend>start?memend-start:0;
    /* Find the smallest block fitting either post-output scratch or g itself. */
    uintptr_t gbytes=(uintptr_t)T*C*sizeof(double);
    int Bs=0, Bg=0, nblocks;
    for(int b=1;b<=T;b++){
        nblocks=(T+b-1)/b;
        uintptr_t bytes=(uintptr_t)nblocks*(uintptr_t)S*sizeof(double);
        if(!Bs&&bytes<=avail)Bs=b;
        /* In g, frame-ordered checkpoints are safe when B*C >= S: while
           processing block k, its output starts past every checkpoint < k. */
        if(!Bg&&(uintptr_t)b*C>=(uintptr_t)S&&bytes<=gbytes)Bg=b;
    }
    int use_g=Bg&&( !Bs || Bg<Bs );
    int B=use_g?Bg:Bs;
    if(!B){B=T;use_g=0;}
    nblocks=(T+B-1)/B;
    double *check=use_g?g:(double*)start;
    setup(T,C,U,blank,x,y);
    for(int s=0;s<S;s++)prev[s]=-INFINITY;prev[0]=0;
    for(int t=0;t<T;t++){
        if(t%B==0){
            double *cp=check+(uintptr_t)(t/B)*S;
            for(int s=0;s<S;s++)cp[s]=prev[s];
        }
        forward_row(t,C,S,blank,x,prev,tmp);
        for(int s=0;s<S;s++)prev[s]=tmp[s];
    }
    double logZ=U?addlog(prev[S-1],prev[S-2]):prev[0];*loss=-logZ;
    for(int s=0;s<S;s++)beta[s]=-INFINITY;
    beta[S-1]=0;if(U)beta[S-2]=0;
    for(int block=nblocks-1;block>=0;block--){
        int begin=block*B, end=begin+B;
        if(end>T)end=T;
        double *cp=check+(uintptr_t)block*S;
        for(int s=0;s<S;s++)base[s]=cp[s];
        for(int t=end-1;t>=begin;t--){
            for(int s=0;s<S;s++)prev[s]=base[s];
            for(int r=begin;r<=t;r++){
                forward_row(r,C,S,blank,x,prev,tmp);
                for(int s=0;s<S;s++)prev[s]=tmp[s];
            }
            gradient_row(t,C,S,x,prev,logZ,g+t*C);
            if(t)backward_row(t,C,S,blank,x);
        }
    }
    return 0;
}
