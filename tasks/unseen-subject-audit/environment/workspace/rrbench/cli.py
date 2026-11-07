"""Agent-facing experiment helper; outputs are evidence, not authoritative grades."""
import argparse
import json
from pathlib import Path
from .contract import load_json
from .experiments import evaluate, load_data, original_folds


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/dev.npz"))
    p.add_argument("--folds", type=Path, help="JSON mapping dev-00000 row IDs to fold integers 0,1,2; omitted = original protocol")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--save-folds", type=Path)
    args = p.parse_args()
    data = load_data(args.data)
    folds = load_json(args.folds) if args.folds else original_folds(data[0], data[1])
    result = evaluate(data, folds)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if args.save_folds:
        args.save_folds.write_text(json.dumps(folds, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "per_subject"}, indent=2))


if __name__ == "__main__": main()
