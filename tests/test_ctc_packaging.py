"""Protect the boundary between source, public workspace, and trusted verifier."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'tasks/ctc-memory-kernel'


def test_ctc_staging_has_no_oracle_or_private_fixture():
    public = TASK / 'environment/workspace'
    trusted = TASK / 'tests'
    assert {p.name for p in public.glob('*.npz')} == {'public.npz'}
    assert not (public / 'oracle.c').exists()
    for destination in (public / 'ctcbench', trusted / 'ctcbench'):
        assert {p.name for p in destination.glob('*.py')} == {'__init__.py', 'runner.py', 'grade.py'}
        for staged in destination.glob('*.py'):
            assert staged.read_bytes() == (ROOT / 'src/ctcbench' / staged.name).read_bytes()


def test_ctc_fixture_hashes_and_public_family_coverage():
    manifest = json.loads((ROOT / 'results/ctc/fixture-manifest.json').read_text())
    for name, path in [('public', TASK / 'environment/workspace/public.npz'),
                       ('private', TASK / 'tests/private.npz')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['fixtures'][name]['sha256']
    with np.load(TASK / 'environment/workspace/public.npz') as public, np.load(TASK / 'tests/private.npz') as private:
        assert set(public['groups']) == set(private['groups'])
        for i in range(len(private['names'])):
            assert all(not np.array_equal(private[f'x{i}'], public[f'x{j}'])
                       for j in range(len(public['names'])))
