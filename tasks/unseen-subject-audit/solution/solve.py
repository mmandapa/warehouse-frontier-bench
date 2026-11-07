import json
import os
from pathlib import Path
from sklearn.model_selection import GroupKFold
from rrbench.experiments import load_data, row_ids, original_folds, evaluate
from rrbench.metrics import decision

data = load_data('data/dev.npz')
X, y, subjects = data
ids, folds = row_ids(len(y)), {}
for k, (_, valid) in enumerate(GroupKFold(3).split(X, y, subjects)):
    folds.update({ids[i]: k for i in valid})
original = evaluate(data, original_folds(X, y))
if json.loads(Path('original_report.json').read_text()) != original:
    raise RuntimeError('The packaged original report differs from the runtime reproduction')
corrected = evaluate(data, folds, require_groups=True)
choice = decision(corrected['ci95'])
output = Path(os.environ.get('RRBENCH_SUBMISSION_DIR', '/app/submission')); output.mkdir(parents=True, exist_ok=True)
(output/'folds.json').write_text(json.dumps(folds, sort_keys=True)+'\n')
(output/'audit.json').write_text(json.dumps({'schema_version':1, 'original':original, 'corrected':corrected,
    'decision':choice, 'selected_recipe':'candidate' if choice=='promote' else 'baseline'}, indent=2)+'\n')
(output/'report.md').write_text(f'''# Replacement audit

The original row split puts windows from the same people in training and validation. It does not estimate the stated unseen-person deployment target. I used three person-disjoint folds and refit both frozen recipes on each training partition, including training-only scaling.

Original subject-macro accuracies: baseline {original['baseline_accuracy']:.8f}, candidate {original['candidate_accuracy']:.8f}. Corrected: baseline {corrected['baseline_accuracy']:.8f}, candidate {corrected['candidate_accuracy']:.8f}. Paired mean change {corrected['delta']:.8f}; descriptive 95% interval {corrected['ci95']}.

Decision: {choice}; retain the baseline unless promotion is established. This does not prove that every tree model is worse or that the interval generalizes to a population. The folds share training observations, and the dataset has few people. A larger prospective study is needed before a real deployment decision.
''')
