"""Run a calibration policy on a public example."""

import argparse
import json
from pathlib import Path

from motion import CartParameters
from protocol import run_policy


EXAMPLES = (
    CartParameters(1, (.10, .20), (.84, .95), (.78, .91), -.06, -.05, .031, -.42, -.25),
    CartParameters(3, (.18, .11), (.97, .74), (.68, .88), .08, -.10, -.027, -.20, -.51),
)
COMMANDS = (
    [(0.83, .68)] * 19,
    [(-.71, -.87)] * 23,
    [(0.92, -.33)] * 4 + [(-.83, -.54)] * 7 + [(0., 0.)] * 8 + [(0.78, .86)] * 8,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("policy.py"))
    parser.add_argument("--case", type=int, choices=range(len(EXAMPLES)), default=0)
    args = parser.parse_args()
    result = run_policy(args.policy, Path(__file__).parent, EXAMPLES[args.case], COMMANDS)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
