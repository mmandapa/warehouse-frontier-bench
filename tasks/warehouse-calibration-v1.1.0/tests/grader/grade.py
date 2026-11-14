"""Score forecasts of independent, hidden cart resets."""

import argparse
import json
from pathlib import Path

from protocol import run_policy
from scenes import cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    public = Path(__file__).with_name("public")
    rows = []
    total = 0
    for family, variant, settings, sequences in cases():
        outcome = run_policy(args.policy, public, settings, sequences)
        rows.append({"family": family, "variant": variant, **outcome})
        total += len(sequences)
    passed = sum(row["passed"] for row in rows)
    reward = passed / total
    args.logs.mkdir(parents=True, exist_ok=True)
    (args.logs / "reward.json").write_text(json.dumps({"reward": reward}) + "\n")
    (args.logs / "diagnostics.json").write_text(
        json.dumps({"reward": reward, "passed": passed, "total": total, "cases": rows}, indent=2) + "\n"
    )
    print(f"{passed}/{total} forecasts within tolerance")


if __name__ == "__main__":
    main()
