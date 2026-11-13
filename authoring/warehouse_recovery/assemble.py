"""Assemble the task's simulator and separate reference policies from authoring sources."""

import ast
from pathlib import Path
import shutil


SOURCE = Path(__file__).resolve().parent
TASK = SOURCE.parents[1] / "tasks/warehouse-recovery-v1.0.0"


def read_definitions(file: str, names: tuple[str, ...]) -> str:
    text = (SOURCE / file).read_text()
    lines = text.splitlines(keepends=True)
    definitions = {getattr(node, "name", None): node for node in ast.parse(text).body}
    parts = []
    for name in names:
        node = definitions[name]
        first = min([node.lineno, *(item.lineno for item in node.decorator_list)])
        parts.append("".join(lines[first - 1:node.end_lineno]).rstrip())
    return "\n\n\n".join(parts) + "\n"


def main() -> None:
    for directory, files in (
        (TASK / "environment/workspace/warehouse_sim", ("world.py", "client.py", "protocol.py")),
        (TASK / "tests/grader/warehouse_sim", ("world.py", "scenes.py", "protocol.py")),
        (TASK / "tests/grader/public", ("world.py", "client.py")),
    ):
        directory.mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copy2(SOURCE / name, directory / name)

    imports = """from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
import math

from warehouse_sim.client import CartClient as Controls
from warehouse_sim.world import Drive, DT, Layout, Observation, Pose, TRACK_M, wheel_step, wrap
"""
    functions = read_definitions("qualification.py", (
        "MissionEnded", "RouteBlocked", "Tracker", "fixed_calibration", "pose_from_anchor",
    )) + "\n\n" + read_definitions("warehouse_shift.py", ("initial_tracker", "acquire_anchor", "go_to_dock"))
    controls = TASK / "tests/controls"
    controls.mkdir(exist_ok=True)
    for path, retries, recalibrate in (
        (TASK / "solution/policy.py", True, True),
        (controls / "fixed-east.py", False, True),
        (controls / "route-only.py", True, False),
    ):
        footer = f"""

if __name__ == "__main__":
    client = Controls()
    try:
        tracker = initial_tracker(client.layout, client)
        side = acquire_anchor(client.layout, tracker, "east", {retries})
        go_to_dock(client.layout, tracker, side, recalibrate={recalibrate})
    except (MissionEnded, RouteBlocked):
        pass
    client.finish()
"""
        path.write_text(imports + "\n\n" + functions + footer)


if __name__ == "__main__":
    main()
