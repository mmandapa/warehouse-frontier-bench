"""Score a controller in matched warehouse missions."""

import argparse
import json
from pathlib import Path
import time

from warehouse_sim.protocol import run_policy
from warehouse_sim.scenes import episode, family
from warehouse_sim.world import Drive


FAMILIES = (
    (3847, 0, Drive(.91, .84, 1)),
    (8401, 1, Drive(.69, .87, 2)),
    (5393, 2, Drive(.88, .67, 1)),
    (2441, 0, Drive(.73, .73, 2)),
)
SCENARIOS = (
    ("clear", 0, False),
    ("one-closure", 1, False),
    ("two-closures", 2, False),
    ("two-closures-and-grip", 2, True),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    public = Path(__file__).with_name("public")
    results = []
    for index, config in enumerate(FAMILIES):
        spec = family(*config)
        for name, closures, mixed_grip in SCENARIOS:
            cart = episode(spec, closures, mixed_grip=mixed_grip)
            result = run_policy(args.policy, public, cart, spec.layout)
            results.append({
                "case": f"{index}-{name}",
                **result,
                "finish_pose": [round(value, 4) for value in (cart.pose.x, cart.pose.y, cart.pose.heading)],
                "closest_closure_m": [round(r, 4) if r < float("inf") else None for r in cart.gate_ranges],
            })
    passed = sum(row["success"] for row in results)
    summary = {
        "reward": passed / len(results), "passed": passed, "total": len(results),
        "collisions": sum(row["collision"] for row in results),
        "seconds": round(time.monotonic() - started, 3),
    }
    args.logs.mkdir(parents=True, exist_ok=True)
    (args.logs / "diagnostics.json").write_text(json.dumps({**summary, "cases": results}, indent=2) + "\n")
    (args.logs / "reward.json").write_text(json.dumps({"reward": summary["reward"]}) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
