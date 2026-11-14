"""Run a public warehouse mission using the submitted policy interface."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from warehouse_sim.protocol import run_policy
from warehouse_sim.world import Cart, Drive, Rect, make_layout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=int, choices=(0, 1), required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    seed, gate = ((42, 25.1), (108, 11.3))[args.case]
    surveyed = make_layout(seed)
    row = next(i for i, p in enumerate(surveyed.starts) if p.y != surveyed.dock.y)
    start = surveyed.starts[row]
    obstruction = Rect(gate, start.y - 1.35, gate + .45, start.y + 1.35)
    floor = Rect(8.0, surveyed.dock.y - 1.35, 11.75, surveyed.dock.y + 1.35)
    physical = replace(surveyed, shelves=(*surveyed.shelves, obstruction))
    cart = Cart(physical, start, Drive(.76, .69, 1), floor=((floor, Drive(.60, .63, 0)),))
    result = run_policy(args.policy, Path(__file__).with_name("warehouse_sim"), cart, surveyed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
