"""Summarize a completed, frozen four-attempt CTC model batch without modifying its records."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from report_results import records

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', default='ctc-primary-gpt-6-luna')
    args = parser.parse_args()
    job = ROOT / 'results/models' / args.job
    rows = records(job, 'research-reliability/ctc-memory-kernel')
    if len(rows) != 4 or any(r['seconds'] is None for r in rows):
        raise SystemExit('Require all four completed attempt records before writing a final summary.')
    frozen = json.loads((ROOT / 'results/ctc/freeze.json').read_text())
    if any(r['task_checksum'] != frozen['task_checksum'] for r in rows):
        raise SystemExit('Task checksum changed; separate the task versions before summarizing.')
    for row in rows:
        path = ROOT / 'results' / row['evidence']
        diagnostic = path / 'verifier/diagnostics.json'
        data = json.loads(diagnostic.read_text()) if diagnostic.exists() else {}
        row['case_pass_fraction'] = data.get('case_pass_fraction')
        row['failed_cases'] = [c for c in data.get('cases', []) if not c['passed']]
        row.pop('decision', None)
    valid = [r for r in rows if not r['invalid'] and r['score'] is not None]
    usage = {key: sum((r['agent_result'] or {}).get(key, 0) or 0 for r in rows)
             for key in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens', 'cost_usd')}
    summary = {'generated_at': datetime.now(timezone.utc).isoformat(),
               'job': args.job, 'task_checksum': frozen['task_checksum'],
               'attempts': rows, 'valid_attempts': len(valid),
               'infrastructure_exceptions': sum(r['invalid'] for r in rows),
               'mean_reward': sum(r['score'] for r in valid) / len(valid) if valid else None,
               'usage': usage, 'billing_note': 'Harbor price estimate, not independently verified provider billing.'}
    (ROOT / 'results/ctc/luna-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'attempts'}, indent=2))


if __name__ == '__main__':
    main()
