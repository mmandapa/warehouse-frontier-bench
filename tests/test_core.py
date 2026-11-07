import json
from pathlib import Path

import numpy as np
import pytest

from rrbench.contract import SubmissionError, load_json, validate_folds
from rrbench.metrics import decision, paired_summary, subject_scores


def test_people_have_equal_weight_despite_different_window_counts():
    scores = subject_scores(np.array([1, 1, 1, 1]), np.array([1, 1, 1, 0]), np.array([4, 4, 4, 9]))
    assert scores == {"4": 1.0, "9": 0.0}
    assert np.mean(list(scores.values())) == 0.5


def test_paired_bootstrap_known_constant_gain():
    result = paired_summary({"1": 0.5, "2": 0.5}, {"1": 0.75, "2": 0.75})
    assert result["delta"] == 0.25
    assert result["ci95"] == [0.25, 0.25]
    assert result == paired_summary({"2": 0.5, "1": 0.5}, {"2": 0.75, "1": 0.75})


@pytest.mark.parametrize("bounds,expected", [([0.02, 0.03], "promote"), ([-0.02, 0.0], "reject"), ([0.01, 0.03], "inconclusive"), ([0.0, 0.01], "inconclusive")])
def test_strict_decision_boundaries(bounds, expected):
    assert decision(bounds) == expected


def fixture():
    subjects = np.repeat(np.arange(6), 2)
    labels = np.tile([1, 2], 6)
    ids = [f"r{i}" for i in range(12)]
    good = {rid: int(person % 3) for rid, person in zip(ids, subjects)}
    return ids, labels, subjects, good


def test_complete_grouped_folds_and_valid_alternative_are_accepted():
    ids, labels, subjects, good = fixture()
    assert len(validate_folds(good, ids, labels, subjects)) == 3
    alternative = {k: (v + 1) % 3 for k, v in good.items()}
    assert len(validate_folds(alternative, ids, labels, subjects)) == 3


@pytest.mark.parametrize("mutation", ["overlap", "missing", "bool", "extra", "empty_fold"])
def test_invalid_fold_manifests_rejected(mutation):
    ids, labels, subjects, good = fixture()
    if mutation == "overlap": good[ids[0]] = 1
    if mutation == "missing": good.pop(ids[0])
    if mutation == "bool": good[ids[0]] = True
    if mutation == "extra": good["unknown"] = 0
    if mutation == "empty_fold": good = {k: 0 for k in good}
    with pytest.raises(SubmissionError): validate_folds(good, ids, labels, subjects)


@pytest.mark.parametrize("payload", ['{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}', '{"a": 1e999}', '{"a":' + '9' * 5000 + '}'])
def test_strict_json_rejects_ambiguous_or_nonfinite_values(tmp_path, payload):
    p = tmp_path / "submission.json"; p.write_text(payload)
    with pytest.raises(SubmissionError): load_json(p)


def test_missing_and_oversized_artifacts_are_task_failures(tmp_path):
    with pytest.raises(SubmissionError): load_json(tmp_path / "missing.json")
    p = tmp_path / "large.json"; p.write_text('"' + 'x' * 1024 + '"')
    with pytest.raises(SubmissionError): load_json(p, limit=100)


def test_huge_integer_evidence_is_a_task_failure():
    from rrbench.verifier import compare
    with pytest.raises(SubmissionError): compare(10 ** 1000, 0.5)
