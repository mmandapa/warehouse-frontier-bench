"""Validate NumPy against PyTorch, freeze fixtures, and stage public/trusted code."""
from pathlib import Path
import hashlib,json,shutil,sys
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ctcbench.cases import cases
from ctcbench.reference import reference


def main():
    task=ROOT/'tasks/ctc-memory-kernel';manifest={'reference':'PyTorch 2.15.0 float64 CTCLoss after log_softmax','fixtures':{}}
    torch.set_num_threads(1)
    for private,path in [(False,task/'environment/workspace/public.npz'),(True,task/'tests/private.npz')]:
        path.parent.mkdir(parents=True,exist_ok=True)
        values={};suite=cases(private)
        for i,c in enumerate(suite):
            status,loss,grad=reference(c['logits'],c['target'],c['blank'])
            if status==0:
                x=torch.tensor(c['logits'],dtype=torch.float64,requires_grad=True)
                l=torch.nn.CTCLoss(blank=c['blank'],reduction='sum')(x.log_softmax(-1).unsqueeze(1),
                    torch.tensor(c['target'],dtype=torch.long),torch.tensor([len(x)]),torch.tensor([len(c['target'])]))
                l.backward()
                np.testing.assert_allclose(float(l.detach()),loss,atol=1e-6,rtol=1e-8)
                np.testing.assert_allclose(x.grad.numpy(),grad,atol=2e-6,rtol=2e-5)
            values.update({f'x{i}':c['logits'],f'y{i}':c['target'],f'b{i}':c['blank'],f's{i}':status,f'l{i}':loss,f'g{i}':grad})
        values.update(names=np.array([c['name'] for c in suite]),groups=np.array([c['group'] for c in suite]))
        np.savez_compressed(path,**values)
        manifest['fixtures']['private' if private else 'public']={'cases':len(suite),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    for destination in (task/'environment/workspace/ctcbench',task/'tests/ctcbench'):
        destination.mkdir(exist_ok=True,parents=True)
        for name in ('__init__.py','runner.py','grade.py'):
            shutil.copy2(ROOT/'src/ctcbench'/name,destination/name)
    (ROOT/'results/ctc').mkdir(parents=True,exist_ok=True)
    (ROOT/'results/ctc/fixture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    requirements='numpy==2.5.4\nwasmtime==50.0.1\n'
    for destination in (task/'environment/requirements.txt',task/'tests/requirements.txt'):destination.write_text(requirements)
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
