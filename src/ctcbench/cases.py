import numpy as np

GROUPS=('empty','repeats','nonzero_blank','minimal','impossible','extreme','long','memory')


def cases(private=False):
    rng=np.random.default_rng(917 if private else 42)
    count=2 if private else 1
    out=[]
    for group in GROUPS:
        for repeat in range(count):
            T,C,U,blank=24,6,7,0
            if group=='empty':T,C,U=13+repeat,5,0
            if group=='repeats':T,C,U=29+repeat,5,9
            if group=='nonzero_blank':T,C,U,blank=37+repeat,9,12,5+repeat
            if group=='minimal':T,C,U=18,5,12
            if group=='impossible':T,C,U=4,5,8
            if group=='extreme':T,C,U,blank=64,8,19,3
            if group=='long':T,C,U=1536+repeat*256,16,128
            if group=='memory':T,C,U,blank=3072-repeat*128,24,256,repeat*7
            vocab=[x for x in range(C) if x!=blank]
            target=rng.choice(vocab,size=U).astype(np.int32)
            if group in ('repeats','minimal'):
                target=np.array([vocab[(i//2)%len(vocab)] for i in range(U)],dtype=np.int32)
            if group=='minimal':T=U+sum(target[i]==target[i-1] for i in range(1,U))
            logits=rng.normal(0,2.5,(T,C)).astype(np.float64)
            if group=='extreme':logits=logits*120+rng.normal(0,300,(T,1))
            out.append(dict(name=f'{group}-{repeat}',group=group,logits=logits,target=target,blank=blank))
    return out
