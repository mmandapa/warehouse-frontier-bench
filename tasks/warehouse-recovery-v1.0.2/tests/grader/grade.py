"""Grade a cart policy on protected warehouse scenes."""

import argparse
import json
from pathlib import Path
import time

from warehouse_sim.protocol import run_policy
from warehouse_sim.scenes import build_case
from warehouse_sim.world import Drive, make_layout


SEEDS = (317, 1217, 3001, 9923)
DRIVES = (Drive(1, 1, 0), Drive(.72, .72, 1), Drive(.64, .82, 2), Drive(.86, .66, 1))
FLOORS = (Drive(.57, .60, 0), Drive(.65, .56, 0))
EAST_GATES = (23.3, 25.6, 27.2)
WEST_GATES = (9.7, 10.85, 12.6)
FLOOR_SPANS = (None, (7.4, 9.65), (9.6, 12.65), (8.6, 10.25))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    public = Path(__file__).with_name("public")
    results = []
    for scene, seed in enumerate(SEEDS):
        layout = make_layout(seed)
        starts = [row for row, pose in enumerate(layout.starts) if pose.y != layout.dock.y]
        for index, row in enumerate(starts):
            for side, gates in (("east", EAST_GATES), ("west", WEST_GATES)):
                drive = DRIVES[(scene + index + 2 * (side == "west")) % len(DRIVES)]
                floor = FLOORS[(scene + index + (side == "east")) % len(FLOORS)]
                floor_span = FLOOR_SPANS[(scene + 2 * index + (side == "west")) % len(FLOOR_SPANS)]
                gate = gates[(scene + index) % len(gates)]
                surveyed, cart = build_case(seed, row, drive, side, floor, gate_x=gate, floor_span=floor_span)
                result = run_policy(args.policy, public, cart, surveyed)
                results.append({"case": f"{scene}-{index}-{side}", "floor_span_m": floor_span, **result})
    passed = sum(row["success"] for row in results)
    reward = passed / len(results)
    summary = {
        "reward": reward, "passed": passed, "total": len(results),
        "collisions": sum(row["collision"] for row in results),
        "seconds": round(time.monotonic() - started, 3),
    }
    args.logs.mkdir(parents=True, exist_ok=True)
    (args.logs / "diagnostics.json").write_text(json.dumps({**summary, "cases": results}, indent=2) + "\n")
    (args.logs / "reward.json").write_text(json.dumps({"reward": reward}) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
