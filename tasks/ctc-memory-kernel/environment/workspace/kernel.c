/* Correct dense baseline. Replace its storage strategy to meet the memory limit. */
#include "ctc_math.h"
int solve(int T,int C,int U,int blank,const double*x,const int32_t*y,double*loss,double*g){
    if(impossible(T,C,U,y,loss,g))return 1;
    int S=2*U+1;
    uintptr_t start=((uintptr_t)(g+T*C)+64+7)&~(uintptr_t)7;
    uintptr_t end=start+(uintptr_t)T*S*sizeof(double);
    if(end>(uintptr_t)__builtin_wasm_memory_size(0)*65536)return 2;
    double *alpha=(double*)start;
    setup(T,C,U,blank,x,y);
    for(int s=0;s<S;s++)prev[s]=-INFINITY;prev[0]=0;
    for(int t=0;t<T;t++){
        forward_row(t,C,S,blank,x,prev,alpha+t*S);
        for(int s=0;s<S;s++)prev[s]=alpha[t*S+s];
    }
    double logZ=U?addlog(prev[S-1],prev[S-2]):prev[0];*loss=-logZ;
    for(int s=0;s<S;s++)beta[s]=-INFINITY;
    beta[S-1]=0;if(U)beta[S-2]=0;
    for(int t=T-1;t>=0;t--){
        gradient_row(t,C,S,x,alpha+t*S,logZ,g);
        if(t)backward_row(t,C,S,blank,x);
    }
    return 0;
}
