"""Score safe, on-time shifts and retain dispatch decisions for diagnosis."""

import argparse
import json
from pathlib import Path

from fixtures import cases
from runner import run_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--logs', type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).with_name('public')
    records = [{'shift': name, **run_policy(args.policy, public, spec)} for name, spec in cases()]
    passed = sum(record['success'] for record in records)
    reward = passed / len(records)
    args.logs.mkdir(parents=True, exist_ok=True)
    (args.logs / 'diagnostics.json').write_text(json.dumps({
        'reward': reward, 'passed': passed, 'total': len(records), 'cases': records,
    }, indent=2) + '\n')
    (args.logs / 'reward.json').write_text(json.dumps({'reward': reward}) + '\n')
    print(f'{passed}/{len(records)} shifts safely dispatched')


if __name__ == '__main__':
    main()
