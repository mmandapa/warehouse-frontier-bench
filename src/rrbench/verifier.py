"""Trusted replay. Never execute, import, or deserialize agent-authored programs."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from .contract import SubmissionError, load_json, validate_folds
from .experiments import evaluate, load_data, original_folds, recipe, row_ids
from .metrics import decision, subject_scores


def compare(actual, expected, path="evidence"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise SubmissionError(f"Incorrect keys at {path}")
        for key in expected: compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise SubmissionError(f"Incorrect sequence at {path}")
        for i, value in enumerate(expected): compare(actual[i], value, f"{path}[{i}]")
    elif type(actual) not in (int, float) or not -1 <= actual <= 1 or not math.isfinite(actual) or abs(actual - expected) > 1e-6:
        raise SubmissionError(f"Numerical disagreement at {path}")


def verify(submission, trusted_data):
    submission, trusted_data = Path(submission), Path(trusted_data)
    folds = load_json(submission / "folds.json")
    audit = load_json(submission / "audit.json", limit=100_000)
    required = {"schema_version", "original", "corrected", "decision", "selected_recipe"}
    if not isinstance(audit, dict) or set(audit) != required or type(audit["schema_version"]) is not int or audit["schema_version"] != 1:
        raise SubmissionError("audit.json must match schema version 1 exactly")
    report = submission / "report.md"
    if report.is_symlink() or not report.is_file() or not 40 <= report.stat().st_size <= 16000:
        raise SubmissionError("report.md must contain 40–16000 bytes of explanation")
    try:
        report.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise SubmissionError("report.md must be readable UTF-8") from exc
    # Check the representation before doing any expensive experiment replay.
    data = load_data(trusted_data / "dev.npz")
    validate_folds(folds, row_ids(len(data[1])), data[1], data[2])
    original = evaluate(data, original_folds(data[0], data[1]))
    corrected = evaluate(data, folds, require_groups=True)
    compare(audit["original"], original, "original")
    compare(audit["corrected"], corrected, "corrected")
    expected_decision = decision(corrected["ci95"])
    selected = "candidate" if expected_decision == "promote" else "baseline"
    if audit["decision"] != expected_decision or audit["selected_recipe"] != selected:
        raise SubmissionError("Recommendation does not follow the published decision policy")
    X, y, subjects = data
    test_X, test_y, test_subjects = load_data(trusted_data / "private.npz")
    if set(subjects) & set(test_subjects):
        raise RuntimeError("Trusted dataset split is not subject-disjoint")
    with threadpool_limits(limits=1):
        prediction = recipe(selected).fit(X, y).predict(test_X)
    hidden_scores = subject_scores(test_y, prediction, test_subjects)
    return {"decision": expected_decision, "corrected": corrected,
            "selected_recipe": selected, "heldout_subject_macro_accuracy": float(np.mean(list(hidden_scores.values()))),
            "heldout_is_diagnostic_only": True}


def atomic_json(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--submission", type=Path, default=Path("/app/submission"))
    p.add_argument("--data", type=Path, default=Path("/grader/data"))
    p.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = p.parse_args(); args.logs.mkdir(parents=True, exist_ok=True)
    import time
    start = time.monotonic()
    try:
        diagnostics = verify(args.submission, args.data)
        reward = 1.0
    except SubmissionError as exc:
        reward, diagnostics = 0.0, {"reason": str(exc)}
    except Exception as exc:
        atomic_json(args.logs / "diagnostics.json", {"invalid_trial": True, "error_type": type(exc).__name__, "error": str(exc)})
        raise
    diagnostics.update(invalid_trial=False, verification_seconds=time.monotonic() - start)
    atomic_json(args.logs / "diagnostics.json", diagnostics)
    atomic_json(args.logs / "reward.json", {"reward": reward})
    print(json.dumps({"reward": reward, "reason": diagnostics.get("reason", "contract satisfied")}))


if __name__ == "__main__": main()
