import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from threadpoolctl import threadpool_limits
from .contract import validate_folds
from .metrics import paired_summary, subject_scores


def load_data(path):
    with np.load(path, allow_pickle=False) as d:
        return d["X"], d["y"], d["subjects"]


def row_ids(n):
    return [f"dev-{i:05d}" for i in range(n)]


def recipe(name):
    if name == "baseline":
        return make_pipeline(StandardScaler(), LinearSVC(C=0.001, dual=False, max_iter=10000, random_state=17))
    if name == "candidate":
        return ExtraTreesClassifier(n_estimators=64, max_features="sqrt", random_state=17, n_jobs=1)
    raise ValueError("Unknown frozen recipe")


def original_folds(X, y):
    ids, out = row_ids(len(y)), {}
    for k, (_, v) in enumerate(StratifiedKFold(3, shuffle=True, random_state=17).split(X, y)):
        out.update({ids[i]: k for i in v})
    return out


def evaluate(data, manifest, require_groups=False):
    X, y, subjects = data
    splits = validate_folds(manifest, row_ids(len(y)), y, subjects, require_groups)
    scores = {}
    with threadpool_limits(limits=1):
        for name in ("baseline", "candidate"):
            prediction = np.empty(len(y), dtype=y.dtype)
            for train, valid in splits:
                prediction[valid] = recipe(name).fit(X[train], y[train]).predict(X[valid])
            scores[name] = subject_scores(y, prediction, subjects)
    return paired_summary(scores["baseline"], scores["candidate"])
