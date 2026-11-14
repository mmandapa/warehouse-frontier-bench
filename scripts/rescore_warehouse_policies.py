"""Rescore archived policies in offline Docker using the isolated verifiers."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASKS = {"warehouse-recovery": 16, "warehouse-calibration": 60}


def read_json(path):
    return json.loads(path.read_text())


def save_report(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


def outcomes(task, rows):
    if task == "warehouse-recovery":
        return {row["case"]: (row["success"],) for row in rows}
    cases = {}
    for row in rows:
        scores = tuple(forecast["success"] for forecast in row["forecasts"])
        if not scores:
            if row["passed"]:
                raise ValueError("missing forecasts for a cart with credit")
            scores = (False,) * 5
        if len(scores) != 5 or sum(scores) != row["passed"]:
            raise ValueError("invalid forecast diagnostics")
        cases[f'{row["family"]}-{row["variant"]}'] = scores
    return cases


def evaluate(image, policy, output):
    output.mkdir()
    subprocess.run(
        [
            "docker", "run", "--rm", "--pull=never", "--network=none", "--cpus=2", "--memory=4g",
            "--mount", f"type=bind,source={policy},target=/app/policy.py,readonly",
            "--mount", f"type=bind,source={output},target=/logs/verifier",
            "--entrypoint", "/bin/bash", image, "/tests/test.sh",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        timeout=270,
    )
    diagnostics = read_json(output / "diagnostics.json")
    if diagnostics["reward"] != read_json(output / "reward.json")["reward"]:
        raise ValueError(f"reward and diagnostics disagree for {policy}")
    return diagnostics


def rescore(task, image, output):
    archive = ROOT / "results" / task
    package = ROOT / "tasks" / task
    controls = {
        "oracle": (package / "solution/policy.py", 1.0),
        "no-op": (package / "environment/workspace/policy.py", 0.0),
    }
    identity = {
        "task": task,
        "harbor_task_checksum": read_json(archive / "package-manifest.json")["harbor_task_checksum"],
        "verifier_image": subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True,
        ).strip(),
    }
    if output.exists():
        result = read_json(output)
        if any(result[key] != value for key, value in identity.items()):
            raise ValueError("existing report was produced with a different package or image")
    else:
        result = {**identity, "controls": [], "saved_submissions": []}
    remaining_controls = controls.keys() - {row["name"] for row in result["controls"]}
    previous_submissions = {row["trial"]: row for row in result["saved_submissions"]}
    with tempfile.TemporaryDirectory(prefix="warehouse-rescore-") as directory:
        scratch = Path(directory)
        for name, (policy, expected) in controls.items():
            if name not in remaining_controls:
                continue
            new = evaluate(image, policy, scratch / name)
            if new["reward"] != expected or new["total"] != TASKS[task]:
                raise ValueError(f"{task}: unexpected {name} control")
            result["controls"].append({"name": name, "reward": new["reward"], "passed": new["passed"]})
            save_report(output, result)
            print(task, name, f'{new["passed"]}/{new["total"]}', flush=True)
        for trajectory in sorted(archive.glob("**/agent/trajectory.json")):
            trial = trajectory.parents[1]
            policy = trial / "artifacts/app/policy.py"
            trial_name = str(trial.relative_to(ROOT))
            digest = sha256(policy.read_bytes()).hexdigest()
            if trial_name in previous_submissions:
                if previous_submissions[trial_name]["policy_sha256"] != digest:
                    raise ValueError(f"saved policy changed for {trial}")
                continue
            old = read_json(trial / "verifier/diagnostics.json")
            recorded = read_json(trial / "verifier/reward.json")["reward"]
            if old["reward"] != recorded:
                raise ValueError(f"original reward mismatch for {trial}")
            new = evaluate(image, policy, scratch / trial.name)
            before = outcomes(task, old["cases"])
            after = outcomes(task, new["cases"])
            if before.keys() != after.keys() or sum(map(len, after.values())) != TASKS[task]:
                raise ValueError(f"case coverage mismatch for {trial}")
            if sum(map(sum, after.values())) != new["passed"] or new["reward"] != new["passed"] / TASKS[task]:
                raise ValueError(f"incorrect reward aggregation for {trial}")
            changed = [
                {"case": name, "original": before[name], "isolated": after[name]}
                for name in before if before[name] != after[name]
            ]
            diagnostics_changed = sum(a != b for a, b in zip(old["cases"], new["cases"], strict=True))
            result["saved_submissions"].append({
                "trial": trial_name,
                "policy_sha256": digest,
                "original_reward": recorded,
                "isolated_reward": new["reward"],
                "passed": new["passed"],
                "total": new["total"],
                "changed_outcomes": changed,
                "cases_with_changed_diagnostics": diagnostics_changed,
            })
            save_report(output, result)
            print(task, trial.parent.name, f'{new["passed"]}/{new["total"]}',
                  f"{len(changed)} changed outcomes", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=TASKS)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rescore(args.task, args.image, args.output)


if __name__ == "__main__":
    main()
