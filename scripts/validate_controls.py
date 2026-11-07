"""Run reference, equivalent-solution, false-pass, and positive-gain controls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import numpy as np
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from rrbench.contract import SubmissionError
from rrbench.experiments import load_data, evaluate, original_folds, row_ids
from rrbench.metrics import decision
from rrbench.verifier import verify


def make_answer(data, seed=None):
    X, y, subjects = data
    split = GroupKFold(3) if seed is None else GroupKFold(3, shuffle=True, random_state=seed)
    ids, folds = row_ids(len(y)), {}
    for k, (_, valid) in enumerate(split.split(X, y, subjects)):
        folds.update({ids[i]: k for i in valid})
    original = evaluate(data, original_folds(X, y))
    corrected = evaluate(data, folds, require_groups=True)
    choice = decision(corrected['ci95'])
    return folds, dict(schema_version=1, original=original, corrected=corrected, decision=choice,
                      selected_recipe='candidate' if choice=='promote' else 'baseline')


def write_answer(root, folds, audit):
    root.mkdir(exist_ok=True, parents=True)
    (root/'folds.json').write_text(json.dumps(folds))
    (root/'audit.json').write_text(json.dumps(audit))
    (root/'report.md').write_text('Controlled fixture: matched comparisons and a policy-consistent model recommendation.\n')


def main():
    trusted = ROOT/'tasks/unseen-subject-audit/tests/data'
    scratch = Path(tempfile.mkdtemp(prefix='rrbench-controls-'))
    results = []
    def check(name, path, want, data=trusted):
        start = time.monotonic()
        try:
            diagnostic = verify(path, data); got, reason = True, diagnostic['decision']
        except SubmissionError as e:
            got, reason = False, str(e)
        if got != want: raise AssertionError(f'{name}: {got} != {want}: {reason}')
        results.append(dict(control=name, accepted=got, reason=reason, seconds=time.monotonic()-start))
        print(name, 'PASS', reason, flush=True)
    data = load_data(trusted/'dev.npz')
    folds, audit = make_answer(data)
    answer = scratch/'oracle'; write_answer(answer, folds, audit); check('reference', answer, True)
    empty = scratch/'empty'; empty.mkdir(); (empty/'reward.json').write_text('{"reward":1}')
    check('empty-and-forged-local-reward', empty, False)
    invalids = [
        ('row-split', original_folds(data[0], data[1]), audit),
        ('invented-number', folds, {**audit, 'corrected':{**audit['corrected'],'delta':0.99}}),
        ('wrong-decision', folds, {**audit,'decision':'promote' if audit['decision']!='promote' else 'reject'}),
        ('extra-field', folds, {**audit,'execute':'python /app/payload.py'}),
        ('missing-row', {k:v for i,(k,v) in enumerate(folds.items()) if i}, audit),
    ]
    for name, f, a in invalids:
        path=scratch/name; write_answer(path, f, a); check(name,path,False)
    alt=scratch/'alternate'; f,a=make_answer(data,83); write_answer(alt,f,a); check('different-valid-grouping',alt,True)
    # Positive-gain control: a categorical nonlinear boundary the tree can learn.
    # This is a verifier control, not an additional benchmark task or model result.
    positive=scratch/'positive-data'; positive.mkdir()
    rng=np.random.default_rng(7)
    for split, people in [('dev',range(1,7)),('private',range(7,10))]:
        y=np.tile(np.repeat(np.arange(1,7),20),len(people))
        subjects=np.repeat(list(people),120)
        X=(y.astype(float)+rng.normal(0,0.02,len(y))).reshape(-1,1)
        np.savez_compressed(positive/f'{split}.npz',X=X,y=y,subjects=subjects)
    f,a=make_answer(load_data(positive/'dev.npz'))
    assert a['decision']=='promote',a['corrected']
    path=scratch/'positive'; write_answer(path,f,a); check('genuine-positive-gain',path,True,positive)
    out=ROOT/'results/controls.json'; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__': main()
