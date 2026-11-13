"""Qualify the warehouse variant using the packaged verifier and local Python."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/warehouse-recovery-v1.1.0"
GRADER = TASK / "tests/grader"
REFERENCE = TASK / "solution/policy.py"
sys.path.insert(0, str(GRADER))

from grade import FAMILIES, SCENARIOS
from warehouse_sim.scenes import corridors, episode, family, shortest
from warehouse_sim.world import Pose


def check_matched_scenes():
    for args in FAMILIES:
        spec = family(*args)
        initial = episode(spec, 0).observe(expose=True)
        start = spec.layout.starts[spec.start_index]
        dock = spec.layout.dock
        edges = corridors(spec.layout)
        for _, count, grip in SCENARIOS:
            cart = episode(spec, count, mixed_grip=grip)
            assert cart.observe(expose=True) == initial
            path = shortest(edges, (start.x, start.y), (dock.x, dock.y), spec.closed[:count])
            assert path
            for a, b in zip(path, path[1:]):
                for step in range(51):
                    x, y = (a[axis] + (b[axis] - a[axis]) * step / 50 for axis in range(2))
                    assert cart.layout.footprint_clear(Pose(x, y, 0))


def grade(policy: Path, output: Path) -> dict:
    subprocess.run(
        [sys.executable, "-B", str(GRADER / "grade.py"), "--policy", str(policy),
         "--logs", str(output)],
        check=True,
    )
    return json.loads((output / "diagnostics.json").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-policy", type=Path, help="Path to a trusted, reviewed prior policy.")
    args = parser.parse_args()
    check_matched_scenes()
    source = REFERENCE.read_text()
    assert source.count("MAX_REPLANS = None") == 1
    with tempfile.TemporaryDirectory(prefix="warehouse-controls-") as directory:
        controls = {
            "oracle": REFERENCE,
            "no-op": TASK / "environment/workspace/policy.py",
        }
        for limit, name in enumerate(("fixed-route", "one-replan")):
            path = Path(directory) / f"{name}.py"
            path.write_text(source.replace("MAX_REPLANS = None", f"MAX_REPLANS = {limit}"))
            controls[name] = path
        if args.previous_policy is not None:
            controls["luna-v1.0.2"] = args.previous_policy.resolve()
        reports = {name: grade(path, args.output / name) for name, path in controls.items()}

    assert reports["oracle"]["passed"] == 16 and reports["oracle"]["collisions"] == 0
    assert reports["no-op"]["passed"] == 0
    for case in reports["oracle"]["cases"]:
        assert all(distance < 1.30 for distance in case["closest_closure_m"])
    for name, expected in (("fixed-route", {"clear"}), ("one-replan", {"clear", "one-closure"})):
        cases = reports[name]["cases"]
        assert all(case["success"] == (case["case"].split("-", 1)[1] in expected) for case in cases)
        assert reports[name]["collisions"] == 0
    for name, report in reports.items():
        print(f"{name}: {report['passed']}/{report['total']} ({report['reward']:.4f})")


if __name__ == "__main__":
    main()
