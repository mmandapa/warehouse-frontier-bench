import json
import math
from pathlib import Path
import numpy as np


class SubmissionError(ValueError):
    """The submitted artifact violates the public task contract."""


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise SubmissionError(f"Duplicate JSON key: {key}")
        out[key] = value
    return out


def _finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise SubmissionError("Nonfinite JSON number")
    if isinstance(value, dict):
        for v in value.values(): _finite(v)
    if isinstance(value, list):
        for v in value: _finite(v)


def load_json(path, limit=1_000_000):
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise SubmissionError(f"Missing, linked, or oversized artifact: {path.name}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=lambda s: (_ for _ in ()).throw(SubmissionError(f"Invalid number: {s}")))
        _finite(value)
        return value
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise SubmissionError(f"Unreadable JSON artifact: {path.name}") from exc


def validate_folds(manifest, row_ids, labels, subjects, require_groups=True):
    if not isinstance(manifest, dict) or set(manifest) != set(row_ids):
        raise SubmissionError("Fold keys must exactly cover all development row IDs")
    if any(type(v) is not int or v not in (0, 1, 2) for v in manifest.values()):
        raise SubmissionError("Every fold ID must be an integer 0, 1, or 2")
    folds = np.array([manifest[r] for r in row_ids])
    classes = set(labels.tolist())
    result = []
    subject_counts = []
    for fold in range(3):
        train, valid = np.flatnonzero(folds != fold), np.flatnonzero(folds == fold)
        if not len(train) or not len(valid):
            raise SubmissionError("All three folds must be nonempty")
        if set(labels[train].tolist()) != classes or set(labels[valid].tolist()) != classes:
            raise SubmissionError("Every training and validation fold needs all activity classes")
        if require_groups and set(subjects[train]) & set(subjects[valid]):
            raise SubmissionError("Evaluation includes people present in its training partition")
        subject_counts.append(len(set(subjects[valid])))
        result.append((train, valid))
    if require_groups and max(subject_counts) - min(subject_counts) > 1:
        raise SubmissionError("Validation folds must have balanced subject counts (difference <= 1)")
    return result
