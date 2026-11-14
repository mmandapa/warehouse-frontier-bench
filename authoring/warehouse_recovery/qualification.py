"""Run solvability and shortcut controls for the 2D warehouse mission."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time

from .world import Cart, Drive, DT, Layout, Observation, Pose, TRACK_M, make_layout, wheel_step, wrap


DRIVES = (Drive(1, 1, 0), Drive(.72, .72, 1), Drive(.64, .82, 2), Drive(.86, .66, 1))
DEVELOPMENT = (42, 108)
HELD_OUT = (317, 981, 1217, 3001, 8501, 9923)


class MissionEnded(RuntimeError):
    pass


class RouteBlocked(RuntimeError):
    pass


class Controls:
    """The observation and action surface available to a reference controller."""

    def __init__(self, cart: Cart):
        self._cart = cart

    def observe(self, *, expose: bool = False) -> Observation:
        return self._cart.observe(expose=expose)

    def command(self, left: float, right: float) -> None:
        self._cart.advance(left, right)
        if self._cart.collided or self._cart.tick >= self._cart.tick_limit:
            raise MissionEnded


@dataclass
class Tracker:
    controls: Controls
    drive: Drive
    pose: Pose

    def __post_init__(self) -> None:
        self.pending = deque([(0.0, 0.0)] * self.drive.lag_ticks)

    def _apply(self, pose: Pose, command: tuple[float, float]) -> Pose:
        left, right = command
        return wheel_step(pose, self.drive.left_gain * left, self.drive.right_gain * right)

    def predicted_stop(self) -> Pose:
        pose = self.pose
        for command in self.pending:
            pose = self._apply(pose, command)
        return pose

    def wheels(self, left: float, right: float) -> None:
        self.controls.command(left, right)
        self.pending.append((left, right))
        self.pose = self._apply(self.pose, self.pending.popleft())

    def motion(self, linear: float, angular: float) -> None:
        left = (linear - angular * TRACK_M / 2) / self.drive.left_gain
        right = (linear + angular * TRACK_M / 2) / self.drive.right_gain
        scale = max(1.0, abs(left), abs(right))
        self.wheels(left / scale, right / scale)

    def settle(self) -> None:
        for _ in range(self.drive.lag_ticks + 1):
            self.wheels(0, 0)

    def turn(self, heading: float) -> None:
        for _ in range(100):
            error = wrap(heading - self.predicted_stop().heading)
            if abs(error) < .012:
                self.settle()
                return
            self.motion(0.0, max(-1.4, min(1.4, 3.0 * error)))
        raise MissionEnded

    def go(self, x: float, y: float, *, check_ahead: bool = False) -> None:
        origin = self.predicted_stop()
        if math.hypot(x - origin.x, y - origin.y) < .08:
            return
        self.turn(math.atan2(y - origin.y, x - origin.x))
        for _ in range(430):
            pose = self.predicted_stop()
            dx, dy = x - pose.x, y - pose.y
            distance = math.hypot(dx, dy)
            if distance < .075:
                self.settle()
                return
            error = wrap(math.atan2(dy, dx) - pose.heading)
            if check_ahead and abs(error) < .24 and self.controls.observe().lidar_m[0] < min(.90, distance + .30):
                self.settle()
                raise RouteBlocked
            self.motion(min(.78, 2.4 * distance) * max(0.0, math.cos(error)),
                        max(-1.3, min(1.3, 3.4 * error)))
        raise MissionEnded


def dock_route(layout: Layout, tracker: Tracker) -> None:
    dock = layout.dock
    if abs(tracker.pose.y - dock.y) > 1.0:
        nearest = min(
            (layout.left_junction_x, layout.right_junction_x),
            key=lambda x: abs(tracker.pose.x - x) + abs(dock.x - x),
        )
        row = min((p.y for p in layout.starts), key=lambda y: abs(tracker.pose.y - y))
        tracker.go(nearest, row)
        tracker.go(nearest, dock.y)
    tracker.go(dock.x, dock.y)
    tracker.turn(dock.heading)


def fixed_calibration(controls: Controls) -> tuple[Drive, tuple[tuple[float, float], ...]]:
    """Two gentle motor pulses, independent of any sensor result."""
    history = []
    measures = []
    for left, right in ((.32, 0.0), (0.0, .32)):
        before = controls.observe()
        first_tick = None
        for index in range(8):
            command = (left, right) if index < 5 else (0.0, 0.0)
            controls.command(*command)
            history.append(command)
            current = controls.observe()
            if first_tick is None and current.odometry_m > before.odometry_m:
                first_tick = index
        if first_tick is None:
            raise MissionEnded
        gain = abs(current.gyro_heading_rad - before.gyro_heading_rad) * TRACK_M / (.32 * 5 * DT)
        measures.append((min(1.0, gain), first_tick))
    if any(gain < .1 for gain, _ in measures):
        raise MissionEnded
    return Drive(measures[0][0], measures[1][0], measures[0][1]), tuple(history)


def pose_from_anchor(layout: Layout, observation: Observation) -> Pose:
    if not observation.tags:
        raise MissionEnded
    reading = min(observation.tags, key=lambda tag: tag.range_m)
    anchor = next(tag for tag in layout.tags if tag.name == reading.name)
    heading = wrap(anchor.heading - reading.relative_heading_rad)
    bearing = heading + reading.bearing_rad
    return Pose(
        anchor.x - reading.range_m * math.cos(bearing),
        anchor.y - reading.range_m * math.sin(bearing),
        heading,
    )


def fixed_probe_then_dock(layout: Layout, controls: Controls) -> None:
    drive, history = fixed_calibration(controls)
    estimate = layout.starts[0]
    for left, right in history:
        estimate = wheel_step(estimate, left * drive.left_gain, right * drive.right_gain)
    tracker = Tracker(controls, drive, estimate)
    tracker.go(layout.right_junction_x - 3.1, layout.starts[0].y)
    tracker.turn(0)
    tracker.pose = pose_from_anchor(layout, controls.observe(expose=True))
    dock_route(layout, tracker)


def measure(seed: int, start_index: int, drive: Drive, policy: str) -> dict:
    layout = make_layout(seed)
    initial = layout.starts[start_index]
    cart = Cart(layout, initial, drive)
    controls = Controls(cart)
    try:
        if policy == "fixed-probe":
            fixed_probe_then_dock(layout, controls)
        else:
            assumed_pose = layout.starts[0] if policy == "wrong-aisle" else initial
            assumed_drive = Drive(1, 1, 0) if policy == "nominal-drive" else drive
            dock_route(layout, Tracker(controls, assumed_drive, assumed_pose))
    except MissionEnded:
        pass
    return {
        "seed": seed, "start": start_index, "drive": [drive.left_gain, drive.right_gain, drive.lag_ticks],
        "docked": cart.docked(), "collision": cart.collided, "ticks": cart.tick,
        "position_error_m": round(math.hypot(cart.pose.x - layout.dock.x, cart.pose.y - layout.dock.y), 4),
    }


def qualify(seeds: tuple[int, ...]) -> dict:
    return {
        policy: [measure(seed, start, drive, policy) for seed in seeds for start in range(3) for drive in DRIVES]
        for policy in ("informed", "wrong-aisle", "nominal-drive", "fixed-probe")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    rows = qualify(DEVELOPMENT if args.development else HELD_OUT)
    summary = {
        name: {"total": len(cases), "docked": sum(case["docked"] for case in cases),
               "collisions": sum(case["collision"] for case in cases)}
        for name, cases in rows.items()
    }
    result = {"seconds": round(time.monotonic() - started, 3), "summary": summary, "trials": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
