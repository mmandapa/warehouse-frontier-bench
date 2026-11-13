"""Qualify the calibration task with trusted policies and matched cases."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/warehouse-calibration-v1.0.0"
GRADER = TASK / "tests/grader"
PUBLIC = GRADER / "public"
ORACLE = TASK / "solution/policy.py"
sys.path.insert(0, str(GRADER))

from protocol import PolicyError, execute, run_policy
from public.motion import Bay, forecast
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
    assert execute(Transcript([zero] * 20 + [camera, reveal, valid]), settings, sequences)["passed"] == len(sequences)
    for requests in (
        [zero] * 21,
        [camera, camera, reveal, valid],
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
        outcomes.append({"family": family, "variant": variant, **result})
    passed = sum(row["passed"] for row in outcomes)
    total = sum(len(row["forecasts"]) for row in outcomes)
    return {"reward": passed / total, "passed": passed, "total": total, "cases": outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenarios = list(cases())
    check_observability(scenarios)
    check_protocol(scenarios[0])
    source = ORACLE.read_text()
    line = "    forward, reverse = estimate_slip(settings, bay.camera())"
    assert source.count(line) == 1
    with tempfile.TemporaryDirectory(prefix="calibration-controls-") as directory:
        controls = {"oracle": ORACLE, "no-op": TASK / "environment/workspace/policy.py"}
        for name, replacement in (
            ("no-camera", "    forward = reverse = 0"),
            ("shared-slip", line + "\n    reverse = forward"),
        ):
            path = Path(directory) / f"{name}.py"
            path.write_text(source.replace(line, replacement))
            controls[name] = path
        results = {name: grade(policy, scenarios) for name, policy in controls.items()}

    assert results["oracle"]["reward"] == 1.0
    assert results["no-op"]["reward"] == 0.0
    assert all(row["forecasts"][0]["success"] and not row["forecasts"][1]["success"]
               for row in results["shared-slip"]["cases"])
    assert all(not row["forecasts"][0]["success"] and not row["forecasts"][1]["success"]
               for row in results["no-camera"]["cases"])
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in results.items():
        (args.output / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
        print(f"{name}: {data['passed']}/{data['total']}")

if __name__ == "__main__":
    main()
