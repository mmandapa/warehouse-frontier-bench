import numpy as np
import pytest
from ctcbench.reference import reference,enumerate_reference


@pytest.mark.parametrize('blank,target',[(0,[]),(0,[1]),(0,[1,1]),(2,[0,1]),(1,[2,2])])
def test_dynamic_program_agrees_with_exhaustive_paths(blank,target):
    x=np.random.default_rng(2).normal(size=(5,3))
    a=reference(x,target,blank);b=enumerate_reference(x,target,blank)
    assert a[0]==b[0]
    np.testing.assert_allclose(a[1],b[1],rtol=1e-10)
    np.testing.assert_allclose(a[2],b[2],atol=1e-11)


def test_gradient_matches_finite_differences():
    x=np.random.default_rng(3).normal(size=(5,3));target=[1,1]
    grad=reference(x,target,0)[2]
    for t in range(5):
        for c in range(3):
            a=x.copy();b=x.copy();a[t,c]+=1e-5;b[t,c]-=1e-5
            numerical=(reference(a,target,0)[1]-reference(b,target,0)[1])/2e-5
            assert abs(numerical-grad[t,c])<1e-8


def test_impossible_alignment_and_empty_target():
    status,loss,grad=reference(np.zeros((2,3)),[1,1],0)
    assert status==1 and np.isinf(loss) and np.count_nonzero(grad)==0
    status,loss,grad=reference(np.zeros((2,3)),[],0)
    assert status==0 and loss==pytest.approx(2*np.log(3))
    np.testing.assert_allclose(grad.sum(axis=1),0,atol=1e-15)
