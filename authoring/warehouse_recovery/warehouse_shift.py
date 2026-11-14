"""Qualification cases with a blocked aisle and changed grip near the dock."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import replace
import json
import math
from pathlib import Path
import time

from .qualification import (
    Controls, DRIVES, DEVELOPMENT, HELD_OUT, MissionEnded, RouteBlocked, Tracker,
    fixed_calibration, fixed_probe_then_dock, pose_from_anchor,
)
from .scenes import build_case
from .world import Drive, Layout, Pose, make_layout, wheel_step, wrap


FLOOR_PROFILES = (Drive(.57, .60, 0), Drive(.65, .56, 0))
POLICIES = (
    "original-fixed", "fixed-east", "fixed-west", "route-only",
    "calibrate-east", "calibrate-west", "adaptive", "informed",
)


def initial_tracker(layout: Layout, controls: Controls) -> Tracker:
    drive, history = fixed_calibration(controls)
    position = layout.starts[0]
    for left, right in history:
        position = wheel_step(position, left * drive.left_gain, right * drive.right_gain)
    return Tracker(controls, drive, position)


def acquire_anchor(layout: Layout, tracker: Tracker, preferred: str, retry_other_side: bool) -> str:
    sides = (preferred, "west" if preferred == "east" else "east") if retry_other_side else (preferred,)
    for side in sides:
        x = layout.right_junction_x - 3.1 if side == "east" else layout.left_junction_x + 3.1
        try:
            tracker.go(x, layout.starts[0].y, check_ahead=True)
        except RouteBlocked:
            continue
        tracker.turn(0 if side == "east" else -math.pi)
        observation = tracker.controls.observe(expose=True)
        if observation.tags:
            tracker.pose = pose_from_anchor(layout, observation)
            return side
    raise MissionEnded


def go_to_dock(
    layout: Layout, tracker: Tracker, side: str, *, recalibrate: bool, known_floor: Drive | None = None,
    floor_entry: Callable[[], Pose] | None = None,
) -> None:
    connector = layout.right_junction_x if side == "east" else layout.left_junction_x
    source_y = min((start.y for start in layout.starts), key=lambda y: abs(tracker.pose.y - y))
    tracker.go(connector, source_y)
    tracker.go(connector, layout.dock.y)
    if not recalibrate and known_floor is None:
        tracker.go(layout.dock.x, layout.dock.y)
        tracker.turn(layout.dock.heading)
        return

    tracker.go(10.45 if side == "east" else 8.95, layout.dock.y)
    if known_floor is None:
        drive, _ = fixed_calibration(tracker.controls)
    else:
        drive = replace(known_floor, lag_ticks=tracker.drive.lag_ticks)
    # A realignment here keeps drift accumulated at the floor boundary out of
    # the final approach. Only the informed control reads the simulator pose.
    if floor_entry is not None:
        final = Tracker(tracker.controls, drive, floor_entry())
    else:
        heading = wrap(tracker.controls.observe().gyro_heading_rad)
        final = Tracker(tracker.controls, drive, replace(tracker.pose, heading=heading))
        final.turn(-math.pi)
        for _ in range(3):
            observation = final.controls.observe(expose=True)
            if observation.tags:
                final.pose = pose_from_anchor(layout, observation)
                break
            final.go(final.pose.x - .23, final.pose.y)
        else:
            raise MissionEnded
    final.go(layout.dock.x, layout.dock.y)
    final.turn(layout.dock.heading)


def run_case(seed: int, row: int, drive: Drive, blocked: str, floor: Drive, policy: str) -> dict:
    surveyed, cart = build_case(seed, row, drive, blocked, floor)
    controls = Controls(cart)
    chosen = None
    try:
        if policy == "informed":
            tracker = Tracker(controls, drive, surveyed.starts[row])
            chosen = "west" if blocked == "east" else "east"
            go_to_dock(surveyed, tracker, chosen, recalibrate=False, known_floor=floor, floor_entry=lambda: cart.pose)
        elif policy == "original-fixed":
            fixed_probe_then_dock(surveyed, controls)
        else:
            tracker = initial_tracker(surveyed, controls)
            preferred = "west" if policy in ("fixed-west", "calibrate-west") else "east"
            chosen = acquire_anchor(surveyed, tracker, preferred, policy in ("route-only", "adaptive"))
            go_to_dock(surveyed, tracker, chosen, recalibrate=policy in ("calibrate-east", "calibrate-west", "adaptive"))
    except (MissionEnded, RouteBlocked):
        pass
    return {
        "seed": seed, "row": row, "blocked": blocked, "drive": [drive.left_gain, drive.right_gain, drive.lag_ticks],
        "floor": [floor.left_gain, floor.right_gain], "chosen": chosen, "docked": cart.docked(),
        "collision": cart.collided, "ticks": cart.tick,
        "position_error_m": round(math.hypot(cart.pose.x - surveyed.dock.x, cart.pose.y - surveyed.dock.y), 4),
    }


def evaluate(seeds: tuple[int, ...]) -> dict:
    cases = []
    for seed in seeds:
        layout = make_layout(seed)
        cases.extend(
            (seed, row, drive, side, floor)
            for row, start in enumerate(layout.starts) if start.y != layout.dock.y
            for drive in DRIVES
            for side in ("east", "west")
            for floor in FLOOR_PROFILES
        )
    return {policy: [run_case(*case, policy) for case in cases] for policy in POLICIES}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    trials = evaluate(DEVELOPMENT if args.development else HELD_OUT)
    summary = {
        policy: {"total": len(cases), "docked": sum(c["docked"] for c in cases),
                 "collisions": sum(c["collision"] for c in cases)}
        for policy, cases in trials.items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump({"seconds": round(time.monotonic() - started, 3), "summary": summary, "trials": trials},
                  stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
