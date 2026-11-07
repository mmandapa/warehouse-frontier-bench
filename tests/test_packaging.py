import hashlib
import json
from pathlib import Path
import pytest

from rrbench.contract import SubmissionError
from rrbench.experiments import load_data
from rrbench.verifier import verify

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'tasks/unseen-subject-audit'


def test_only_development_data_enters_the_agent_image():
    public=TASK/'environment/workspace/data'
    trusted=TASK/'tests/data'
    assert {p.name for p in public.glob('*.npz')} == {'dev.npz'}
    assert (public/'dev.npz').read_bytes() == (trusted/'dev.npz').read_bytes()
    dev, private=load_data(trusted/'dev.npz'),load_data(trusted/'private.npz')
    assert len(dev[1]) == 7352 and len(private[1]) == 2947
    assert not set(dev[2]) & set(private[2])


def test_staged_code_and_dataset_match_the_recorded_sources():
    for source in (ROOT/'src/rrbench').glob('*.py'):
        assert (TASK/'tests/rrbench'/source.name).read_bytes() == source.read_bytes()
        if source.name!='verifier.py':
            assert (TASK/'environment/workspace/rrbench'/source.name).read_bytes() == source.read_bytes()
    manifest=json.loads((ROOT/'data-manifest.json').read_text())
    for name, meta in manifest['partitions'].items():
        assert hashlib.sha256((TASK/f'tests/data/{name}.npz').read_bytes()).hexdigest() == meta['sha256']


def test_invalid_report_encoding_is_a_submission_failure(tmp_path):
    (tmp_path/'folds.json').write_text('{}')
    (tmp_path/'audit.json').write_text(json.dumps(dict(schema_version=1,original={},corrected={},decision='reject',selected_recipe='baseline')))
    (tmp_path/'report.md').write_bytes(b'a'*40+b'\xff')
    with pytest.raises(SubmissionError, match='UTF-8'):
        verify(tmp_path,tmp_path/'unused-trusted-data')
