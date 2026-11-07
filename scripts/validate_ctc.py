"""Validate compiled controls and probe the oracle on 100 additional unseen inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ctcbench.grade import grade
from ctcbench.reference import reference
from ctcbench.runner import compile_module, execute, compare, fuel_budget, MEMORY_BYTES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--oracle', required=True, type=Path)
    p.add_argument('--baseline', required=True, type=Path)
    p.add_argument('--output', type=Path, default=ROOT / 'results/ctc/controls.json')
    args = p.parse_args()
    fixtures = ROOT / 'tasks/ctc-memory-kernel/tests/private.npz'
    oracle = grade(args.oracle, fixtures)
    baseline = grade(args.baseline, fixtures)
    noop = grade(args.output.parent / 'intentionally-absent-kernel.wasm', fixtures)
    assert oracle['reward'] == 1.0
    assert baseline['reward'] == noop['reward'] == 0.0
    engine, module = compile_module(args.oracle)
    rng = np.random.default_rng(20261107)
    max_error = 0.0
    for i in range(100):
        T, C, U = int(rng.integers(1, 90)), int(rng.integers(2, 25)), int(rng.integers(0, 30))
        blank = int(rng.integers(C))
        target = rng.choice([v for v in range(C) if v != blank], U).astype(np.int32)
        x = rng.uniform(-2000, 2000, (T, C)) if i % 3 == 0 else rng.normal(0, 3, (T, C))
        status, loss, gradient = reference(x, target, blank)
        result = execute(engine, module, x, target, blank)
        compare(result, status, loss, gradient)
        max_error = max(max_error, float(np.max(np.abs(result['gradient'] - gradient))))
    with np.load(fixtures) as data:
        fuel_ratios = [r['fuel_used'] / fuel_budget(*data[f'x{i}'].shape, len(data[f'y{i}']))
                       for i, r in enumerate(oracle['cases'])]
    report = {
        'memory_limit_bytes': MEMORY_BYTES,
        'oracle': {'reward': oracle['reward'], 'cases': len(oracle['cases']),
                   'module_sha256': hashlib.sha256(args.oracle.read_bytes()).hexdigest(),
                   'max_fraction_of_fuel_allowance': max(fuel_ratios)},
        'unchanged_baseline': {'reward': baseline['reward'], 'case_pass_fraction': baseline['case_pass_fraction'],
                               'module_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest()},
        'missing_artifact_noop': {'reward': noop['reward']},
        'additional_oracle_cases': {'seed': 20261107, 'count': 100, 'passed': 100,
                                    'max_absolute_gradient_error': max_error},
        'execution_note': 'Local Wasmtime controls; separate end-to-end Harbor controls are recorded alongside.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
