from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math

from warehouse_sim.client import CartClient as Controls
from warehouse_sim.world import Drive, DT, Layout, Observation, Pose, TRACK_M, wheel_step, wrap


class MissionEnded(RuntimeError):
    pass


class RouteBlocked(RuntimeError):
    pass


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


def pulse(controls: Controls, drive: Drive, speed: float, turn: float, ticks: int = 3) -> None:
    left = (speed - turn * TRACK_M / 2) / drive.left_gain
    right = (speed + turn * TRACK_M / 2) / drive.right_gain
    scale = max(1.0, abs(left), abs(right))
    controls.command(left / scale, right / scale, ticks=ticks)
    controls.command(0, 0, ticks=drive.lag_ticks + 1)


def clamp(value: float, maximum: float) -> float:
    return max(-maximum, min(maximum, value))


def align(controls: Controls, drive: Drive, initial_heading: float, target: float) -> None:
    for _ in range(28):
        heading = initial_heading + controls.observe().gyro_heading_rad
        error = wrap(target - heading)
        if abs(error) < .024:
            return
        pulse(controls, drive, 0, clamp(1.9 * error, .78))
    raise MissionEnded


def visual_approach(layout: Layout, controls: Controls, drive: Drive) -> None:
    dock = layout.dock
    start_heading = layout.starts[0].heading
    align(controls, drive, start_heading, dock.heading)
    for _ in range(64):
        reading = controls.observe(expose=True)
        if not reading.tags:
            heading = start_heading + reading.gyro_heading_rad
            pulse(controls, drive, .32, clamp(2.6 * wrap(dock.heading - heading), .48), ticks=4)
            continue
        pose = pose_from_anchor(layout, reading)
        dx, dy = dock.x - pose.x, dock.y - pose.y
        distance = math.hypot(dx, dy)
        if distance <= .135:
            align(controls, drive, start_heading, dock.heading)
            return
        # Use the observed pose on every correction. Wheel gains can change
        # between pulses without accumulating an open-loop position error.
        longitudinal = dx * math.cos(dock.heading) + dy * math.sin(dock.heading)
        speed = clamp(1.1 * longitudinal, .44)
        cross_track = -dx * math.sin(dock.heading) + dy * math.cos(dock.heading)
        direction = 1 if speed >= 0 else -1
        desired = dock.heading + direction * clamp(2.0 * cross_track, .34)
        pulse(controls, drive, speed, clamp(2.9 * wrap(desired - pose.heading), .60), ticks=4)
    raise MissionEnded


def go_to_dock(layout: Layout, tracker: Tracker, side: str) -> None:
    connector = layout.right_junction_x if side == "east" else layout.left_junction_x
    source_y = min((start.y for start in layout.starts), key=lambda y: abs(tracker.pose.y - y))
    tracker.go(connector, source_y)
    tracker.go(connector, layout.dock.y)
    staging_x = layout.dock.x + 4.3 if side == "east" else connector + .85
    tracker.go(staging_x, layout.dock.y)
    visual_approach(layout, tracker.controls, tracker.drive)


if __name__ == "__main__":
    client = Controls()
    try:
        tracker = initial_tracker(client.layout, client)
        side = acquire_anchor(client.layout, tracker, "east", True)
        go_to_dock(client.layout, tracker, side)
    except (MissionEnded, RouteBlocked):
        pass
    client.finish()
