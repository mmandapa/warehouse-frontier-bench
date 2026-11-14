"""Run a public dispatch shift using the local policy."""

import argparse
import json
from pathlib import Path
import select
import subprocess
import sys
from time import monotonic

from session import PolicyError, execute


class Wire:
    def __init__(self, child):
        self.child = child
        self.deadline = monotonic() + 30

    def read(self):
        remaining = self.deadline - monotonic()
        if remaining <= 0 or not select.select([self.child.stdout], [], [], remaining)[0]:
            raise PolicyError('policy time limit')
        line = self.child.stdout.readline()
        if not line:
            raise PolicyError('policy exited before finish')
        try:
            result = json.loads(line)
        except ValueError as exc:
            raise PolicyError('invalid JSON') from exc
        if not isinstance(result, dict):
            raise PolicyError('request must be an object')
        return result

    def write(self, message):
        print(json.dumps(message), file=self.child.stdin, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', type=int)
    parser.add_argument('--policy', default='policy.py')
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name('practice-cases.json').read_text())
    if not 0 <= args.case < len(cases):
        parser.error(f'case must be between 0 and {len(cases)-1}')
    with subprocess.Popen([sys.executable, '-B', args.policy], text=True,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
        try:
            result = execute(Wire(child), cases[args.case])
        finally:
            child.kill()
    print(json.dumps(result, indent=2))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
