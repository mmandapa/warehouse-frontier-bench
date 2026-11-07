"""Independent full-table NumPy reference; never linked into submitted WebAssembly."""
import itertools
import numpy as np


def reference(logits, target, blank):
    T,C=logits.shape; U=len(target)
    if T < U + sum(target[i]==target[i-1] for i in range(1,U)):
        return 1,float('inf'),np.zeros_like(logits)
    z=logits-logits.max(axis=1,keepdims=True)
    logp=z-np.log(np.exp(z).sum(axis=1,keepdims=True))
    ext=np.full(2*U+1,blank,dtype=int); ext[1::2]=target
    S=len(ext); a=np.full((T,S),-np.inf); prev=np.full(S,-np.inf);prev[0]=0
    skip=np.zeros(S,dtype=bool)
    skip[2:] = (ext[2:]!=blank)&(ext[2:]!=ext[:-2])
    for t in range(T):
        one=np.r_[-np.inf,prev[:-1]]
        two=np.full(S,-np.inf)
        if S>2: two[2:]=prev[:-2]
        a[t]=logp[t,ext]+np.logaddexp(np.logaddexp(prev,one),np.where(skip,two,-np.inf))
        prev=a[t]
    logZ=a[-1,-1] if U==0 else np.logaddexp(a[-1,-1],a[-1,-2])
    beta=np.full((T,S),-np.inf); beta[-1,-1]=0
    if U: beta[-1,-2]=0
    for t in range(T-2,-1,-1):
        v=logp[t+1,ext]+beta[t+1]
        one=np.r_[v[1:],-np.inf]
        two=np.full(S,-np.inf)
        if S>2: two[:-2]=np.where(skip[2:],v[2:],-np.inf)
        beta[t]=np.logaddexp(np.logaddexp(v,one),two)
    posterior=np.exp(a+beta-logZ)
    grad=np.exp(logp)
    for s,label in enumerate(ext): grad[:,label]-=posterior[:,s]
    return 0,float(-logZ),grad


def enumerate_reference(logits,target,blank):
    """Exact path enumeration for tiny independent semantic controls."""
    z=logits-logits.max(axis=1,keepdims=True)
    p=np.exp(z);p/=p.sum(axis=1,keepdims=True)
    mass=0.; occupancy=np.zeros_like(p)
    for path in itertools.product(range(p.shape[1]),repeat=p.shape[0]):
        collapsed=[v for i,v in enumerate(path) if (i==0 or v!=path[i-1]) and v!=blank]
        if collapsed!=list(target):continue
        probability=float(np.prod(p[np.arange(len(path)),path]));mass+=probability
        occupancy[np.arange(len(path)),path]+=probability
    if mass==0:return 1,float('inf'),np.zeros_like(p)
    return 0,float(-np.log(mass)),p-occupancy/mass
