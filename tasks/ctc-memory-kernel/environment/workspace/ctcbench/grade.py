import argparse
import json
from pathlib import Path
import numpy as np
from .runner import compile_module,execute,compare,KernelFailure


def grade(module_path,fixture_path):
    with np.load(fixture_path,allow_pickle=False) as d:
        names=d['names'].tolist();groups=d['groups'].tolist();cases=[]
        try: engine,module=compile_module(module_path)
        except KernelFailure as exc:return {'reward':0.,'cases':[],'reason':str(exc)}
        for i,name in enumerate(names):
            row={'name':name,'group':groups[i]}
            try:
                result=execute(engine,module,d[f'x{i}'],d[f'y{i}'],int(d[f'b{i}']))
                compare(result,int(d[f's{i}']),float(d[f'l{i}']),d[f'g{i}'])
                row.update(passed=True,fuel_used=result['fuel_used'],seconds=result['seconds'])
            except KernelFailure as exc:row.update(passed=False,reason=str(exc))
            cases.append(row)
    return {'reward':float(all(c['passed'] for c in cases)),
            'case_pass_fraction':sum(c['passed'] for c in cases)/len(cases),'cases':cases}


def main():
    p=argparse.ArgumentParser(description='Capability-limited CTC kernel verification')
    p.add_argument('--module',type=Path,default=Path('/app/submission/kernel.wasm'))
    p.add_argument('--fixtures',type=Path,default=Path('/grader/private.npz'))
    p.add_argument('--logs',type=Path)
    args=p.parse_args()
    result=grade(args.module,args.fixtures)
    if args.logs:
        args.logs.mkdir(parents=True,exist_ok=True)
        for name,value in [('reward.json',{'reward':result['reward']}),('diagnostics.json',result)]:
            temp=args.logs/(name+'.tmp');temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temp.replace(args.logs/name)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
