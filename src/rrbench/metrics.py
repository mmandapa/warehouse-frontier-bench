import numpy as np

MARGIN = 0.01
BOOTSTRAP_SEED = 112
BOOTSTRAP_SAMPLES = 10000


def subject_scores(y, prediction, subjects):
    return {str(s): float(np.mean(prediction[subjects == s] == y[subjects == s]))
            for s in np.unique(subjects)}


def paired_summary(baseline, candidate):
    keys = sorted(baseline, key=int)
    if set(keys) != set(candidate) or not keys:
        raise ValueError("Both recipes need scores for the same nonempty subject set")
    a, b = np.array([baseline[k] for k in keys]), np.array([candidate[k] for k in keys])
    delta = b - a
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = delta[rng.integers(0, len(keys), size=(BOOTSTRAP_SAMPLES, len(keys)))].mean(axis=1)
    return {"baseline_accuracy": float(a.mean()), "candidate_accuracy": float(b.mean()),
            "delta": float(delta.mean()), "ci95": np.quantile(draws, [0.025, 0.975], method="linear").tolist(),
            "per_subject": {k: {"baseline": baseline[k], "candidate": candidate[k]} for k in keys}}


def decision(ci95):
    if ci95[0] > MARGIN:
        return "promote"
    if ci95[1] < MARGIN:
        return "reject"
    return "inconclusive"
