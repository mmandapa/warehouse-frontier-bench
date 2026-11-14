"""Qualify the calibration task with trusted policies and matched cases."""

import argparse
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import math
from random import Random
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/warehouse-calibration-v1.1.0"
GRADER = TASK / "tests/grader"
PUBLIC = GRADER / "public"
ORACLE = TASK / "solution/policy.py"
sys.path.insert(0, str(GRADER))

from protocol import CAMERA_LIMIT, TICK_LIMIT, PolicyError, execute, run_policy
from public.motion import Bay, CartParameters, forecast, wrap
from scenes import cases


def check_observability(scenarios):
    # Forward, reverse and turn commands cover the wheel-response branches.
    commands = [(0, 0), (.67, .75), (-.81, -.72), (.94, -.60)] * 5
    for first, second in zip(scenarios[::2], scenarios[1::2], strict=True):
        family, _, settings, sequences = first
        other_family, _, other_settings, other_sequences = second
        assert family == other_family and sequences == other_sequences
        first_bay, second_bay = Bay(settings), Bay(other_settings)
        for command in commands:
            assert first_bay.advance(*command) == second_bay.advance(*command)
        assert first_bay.pose[:2] != second_bay.pose[:2]
        for command_sequence in sequences[:2]:
            a = forecast(settings, command_sequence)
            b = forecast(other_settings, command_sequence)
            position_separation = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5
            assert position_separation > 2 * .045


class Transcript:
    def __init__(self, requests):
        self.requests = iter(requests)

    def read(self):
        try:
            return next(self.requests)
        except StopIteration as error:
            raise PolicyError("policy exited before finish") from error

    def write(self, _):
        pass


def check_protocol(scenario):
    _, _, settings, sequences = scenario
    zero = {"op": "drive", "left": 0, "right": 0}
    reveal = {"op": "forecast"}
    camera = {"op": "camera"}
    valid = {"op": "submit", "poses": [list(forecast(settings, row)) for row in sequences]}
    legal = [zero] * TICK_LIMIT + [camera] * CAMERA_LIMIT + [reveal, valid]
    assert execute(Transcript(legal), settings, sequences)["passed"] == len(sequences)
    for requests in (
        [zero] * (TICK_LIMIT + 1),
        [camera] * (CAMERA_LIMIT + 1) + [reveal, valid],
        [reveal, zero, valid],
        [reveal, camera, valid],
        [reveal, reveal, valid],
        [valid],
        [reveal, {"op": "submit", "poses": [[float("nan"), 0, 0]] * len(sequences)}],
        [{"op": "drive", "left": True, "right": 0}],
    ):
        result = execute(Transcript(requests), settings, sequences)
        assert result["passed"] == 0 and result["reason"] != "submitted"


def grade(policy, scenarios):
    outcomes = []
    for family, variant, settings, sequences in scenarios:
        result = run_policy(policy, PUBLIC, settings, sequences)
        assert result["reason"] == "submitted", (policy.name, family, variant, result["reason"])
        assert len(result["forecasts"]) == len(sequences)
        outcomes.append({"family": family, "variant": variant, **result})
    passed = sum(row["passed"] for row in outcomes)
    total = sum(len(row["forecasts"]) for row in outcomes)
    return {"reward": passed / total, "passed": passed, "total": total, "cases": outcomes}


def test_seeded_reference():
    sys.path.insert(0, str(PUBLIC))
    spec = importlib.util.spec_from_file_location("calibration_oracle", ORACLE)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    rng = Random(97037)
    sequences = ([(.88, .83)] * 26, [(-.90, -.89)] * 27)
    worst_position, worst_heading = 0.0, 0.0
    for _ in range(120):
        settings = CartParameters(
            rng.randrange(4),
            tuple(rng.uniform(.08, .24) for _ in range(2)),
            tuple(rng.uniform(.65, 1.05) for _ in range(2)),
            tuple(rng.uniform(.65, 1.05) for _ in range(2)),
            rng.uniform(-.12, .14), rng.uniform(-.12, .14), rng.uniform(-.06, .06),
            rng.uniform(-.62, -.12), rng.uniform(-.62, -.12),
        )
        bay = Bay(settings)
        observations, cameras = [], []
        for tick, command in enumerate(oracle.PROBES, 1):
            observations.append(bay.advance(*command))
            if tick in oracle.CHECKPOINTS:
                x, y, heading = bay.pose
                cameras.append([round(x, 3), round(y, 3), round(heading, 6)])
        drive = oracle.estimate_drive(observations)
        slips = oracle.estimate_slip(drive, cameras)
        estimated = replace(drive, **dict(zip(oracle.SLIP_FIELDS, slips)))
        for commands in sequences:
            actual, predicted = forecast(settings, commands), forecast(estimated, commands)
            worst_position = max(worst_position, math.dist(actual[:2], predicted[:2]))
            worst_heading = max(worst_heading, abs(wrap(actual[2] - predicted[2])))
    assert worst_position < .045 and worst_heading < .025
    return {"carts": 120, "forecasts": 240, "max_position_error_m": worst_position,
            "max_heading_error_rad": worst_heading}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenarios = list(cases())
    check_observability(scenarios)
    check_protocol(scenarios[0])
    seeded = test_seeded_reference()
    source = ORACLE.read_text()
    line = "    slip = estimate_slip(settings, cameras)"
    assert source.count(line) == 1
    with tempfile.TemporaryDirectory(prefix="calibration-controls-") as directory:
        controls = {"oracle": ORACLE, "no-op": TASK / "environment/workspace/policy.py"}
        for name, replacement in (
            ("no-camera", "    slip = [0.0] * 4"),
            ("constant-slip", "    matrix, target = slip_system(settings, cameras)\n"
             "    a = sum(row[0] ** 2 for row in matrix)\n"
             "    b = sum(row[0] * row[1] for row in matrix)\n"
             "    c = sum(row[1] ** 2 for row in matrix)\n"
             "    d = sum(row[0] * val for row, val in zip(matrix, target))\n"
             "    e = sum(row[1] * val for row, val in zip(matrix, target))\n"
             "    slip = [*solve([[a, b], [b, c]], [d, e]), 0.0, 0.0]"),
        ):
            path = Path(directory) / f"{name}.py"
            policy_source = source.replace(line, replacement)
            if name == "no-camera":
                camera = "        if tick in CHECKPOINTS:\n            cameras.append(bay.camera())\n"
                assert policy_source.count(camera) == 1
                policy_source = policy_source.replace(camera, "")
            path.write_text(policy_source)
            controls[name] = path
        results = {name: grade(policy, scenarios) for name, policy in controls.items()}

    assert results["oracle"]["reward"] == 1.0
    assert results["no-op"]["reward"] == 0.0
    assert all(row["camera_readings"] == 0 for row in results["no-camera"]["cases"])
    assert all(row["camera_readings"] == 2 for row in results["constant-slip"]["cases"])
    for name in results.keys() - {"oracle", "no-op"}:
        assert 0 < results[name]["passed"] < 30, (name, results[name]["passed"])
        assert all(f["heading_error_rad"] < .001 for row in results[name]["cases"] for f in row["forecasts"])
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in results.items():
        (args.output / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
        print(f"{name} {data['passed']}/{data['total']}")
    (args.output / "seeded-reference.json").write_text(json.dumps(seeded, indent=2) + "\n")
    print("Seeded reference", seeded)


if __name__ == "__main__":
    main()
