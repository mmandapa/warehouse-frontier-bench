/* Recursive recomputation keeps only O(S log T) forward state.
 * On entry beta belongs to end-1; on return it belongs to begin-1.
 * Each depth owns a checkpoint, so descending right cannot overwrite a
 * forward state still needed by the later left subtree. */
#include "ctc_math.h"
static double checkpoint[14][MAX_S];
static void reverse(int begin,int end,int depth,int C,int S,int blank,
                    const double*x,const double*before,double logZ,double*g){
    if(end-begin==1){
        forward_row(begin,C,S,blank,x,before,prev);
        gradient_row(begin,C,S,x,prev,logZ,g);
        if(begin)backward_row(begin,C,S,blank,x);
        return;
    }
    int middle=(begin+end)/2;
    for(int s=0;s<S;s++)prev[s]=before[s];
    for(int t=begin;t<middle;t++){
        forward_row(t,C,S,blank,x,prev,tmp);
        for(int s=0;s<S;s++)prev[s]=tmp[s];
    }
    for(int s=0;s<S;s++)checkpoint[depth][s]=prev[s];
    reverse(middle,end,depth+1,C,S,blank,x,checkpoint[depth],logZ,g);
    reverse(begin,middle,depth+1,C,S,blank,x,before,logZ,g);
}
int solve(int T,int C,int U,int blank,const double*x,const int32_t*y,double*loss,double*g){
    if(impossible(T,C,U,y,loss,g))return 1;
    int S=2*U+1;
    setup(T,C,U,blank,x,y);
    for(int s=0;s<S;s++)checkpoint[0][s]=prev[s]=-INFINITY;
    checkpoint[0][0]=prev[0]=0;
    for(int t=0;t<T;t++){
        forward_row(t,C,S,blank,x,prev,tmp);
        for(int s=0;s<S;s++)prev[s]=tmp[s];
    }
    double logZ=U?addlog(prev[S-1],prev[S-2]):prev[0];*loss=-logZ;
    for(int s=0;s<S;s++)beta[s]=-INFINITY;
    beta[S-1]=0;if(U)beta[S-2]=0;
    reverse(0,T,1,C,S,blank,x,checkpoint[0],logZ,g);
    return 0;
}
