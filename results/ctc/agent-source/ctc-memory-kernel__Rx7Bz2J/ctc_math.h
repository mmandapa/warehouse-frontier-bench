#include <math.h>
#include <stdint.h>
#define MAX_T 3072
#define MAX_U 256
#define MAX_S (2*MAX_U+1)
static int seq[MAX_S];
static double norm[MAX_T], prev[MAX_S], beta[MAX_S], tmp[MAX_S];
static double addlog(double a,double b) {
    if(a==-INFINITY)return b;
    if(b==-INFINITY)return a;
    double m=a>b?a:b;
    return m+log1p(exp(-fabs(a-b)));
}
static void setup(int T,int C,int U,int blank,const double*x,const int32_t*y) {
    for(int s=0;s<2*U+1;s++)seq[s]=(s%2)?y[s/2]:blank;
    for(int t=0;t<T;t++){
        double m=x[t*C];for(int c=1;c<C;c++)if(x[t*C+c]>m)m=x[t*C+c];
        double sum=0;for(int c=0;c<C;c++)sum+=exp(x[t*C+c]-m);
        norm[t]=m+log(sum);
    }
}
static void forward_row(int t,int C,int S,int blank,const double*x,const double*in,double*out) {
    for(int s=0;s<S;s++){
        double v=in[s];if(s)v=addlog(v,in[s-1]);
        if(s>=2&&seq[s]!=blank&&seq[s]!=seq[s-2])v=addlog(v,in[s-2]);
        out[s]=v+x[t*C+seq[s]]-norm[t];
    }
}
static void backward_row(int t,int C,int S,int blank,const double*x) {
    for(int s=0;s<S;s++){
        double v=beta[s]+x[t*C+seq[s]]-norm[t];
        if(s+1<S)v=addlog(v,beta[s+1]+x[t*C+seq[s+1]]-norm[t]);
        if(s+2<S&&seq[s+2]!=blank&&seq[s+2]!=seq[s])v=addlog(v,beta[s+2]+x[t*C+seq[s+2]]-norm[t]);
        tmp[s]=v;
    }
    for(int s=0;s<S;s++)beta[s]=tmp[s];
}
static void gradient_row(int t,int C,int S,const double*x,const double*a,double logZ,double*g) {
    for(int c=0;c<C;c++)g[t*C+c]=exp(x[t*C+c]-norm[t]);
    for(int s=0;s<S;s++)g[t*C+seq[s]]-=exp(a[s]+beta[s]-logZ);
}
static int impossible(int T,int C,int U,const int32_t*y,double*loss,double*g){
    int needed=U;for(int i=1;i<U;i++)if(y[i]==y[i-1])needed++;
    if(T>=needed)return 0;
    *loss=INFINITY;for(int i=0;i<T*C;i++)g[i]=0;return 1;
}
