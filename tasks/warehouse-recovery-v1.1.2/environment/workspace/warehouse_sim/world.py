"""Deterministic 2D warehouse and differential-drive cart for qualification."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import random


DT = 0.2
TRACK_M = 0.56
RADIUS_M = 0.28
MAX_WHEEL_MPS = 1.0
LIDAR_RANGE_M = 4.8
LIDAR_ANGLES = tuple(index * math.tau / 16 for index in range(16))
RAY_STEP_M = 0.08
FOOTPRINT = tuple((RADIUS_M * math.cos(a), RADIUS_M * math.sin(a)) for a in LIDAR_ANGLES)


def wrap(angle: float) -> float:
    return (angle + math.pi) % math.tau - math.pi


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    heading: float


@dataclass(frozen=True)
class Drive:
    left_gain: float
    right_gain: float
    lag_ticks: int


@dataclass(frozen=True)
class Rect:
    left: float
    bottom: float
    right: float
    top: float

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.bottom <= y <= self.top


@dataclass(frozen=True)
class Tag:
    name: str
    x: float
    y: float
    heading: float


@dataclass(frozen=True)
class TagReading:
    name: str
    range_m: float
    bearing_rad: float
    relative_heading_rad: float


@dataclass(frozen=True)
class Layout:
    aisles: tuple[Rect, ...]
    shelves: tuple[Rect, ...]
    tags: tuple[Tag, ...]
    starts: tuple[Pose, ...]
    dock: Pose
    left_junction_x: float
    right_junction_x: float

    def free(self, x: float, y: float) -> bool:
        return any(rect.contains(x, y) for rect in self.aisles) and not any(
            rect.contains(x, y) for rect in self.shelves
        )

    def footprint_clear(self, pose: Pose) -> bool:
        return self.free(pose.x, pose.y) and all(
            self.free(pose.x + dx, pose.y + dy) for dx, dy in FOOTPRINT
        )


@dataclass(frozen=True)
class Observation:
    tick: int
    odometry_m: float
    odometry_heading_rad: float
    gyro_heading_rad: float
    lidar_m: tuple[float, ...]
    tags: tuple[TagReading, ...]


def make_layout(seed: int) -> Layout:
    rng = random.Random(seed)
    rows = (4.0, 12.0, 20.0)
    left = float(rng.choice((5, 6, 7)))
    right = float(rng.choice((31, 32, 33)))
    central = float(rng.choice((25, 26, 27)))
    branch = rng.randrange(2)
    aisles = tuple(Rect(2, y - 1.35, 38, y + 1.35) for y in rows) + (
        Rect(left - 1.35, rows[0], left + 1.35, rows[-1]),
        Rect(right - 1.35, rows[0], right + 1.35, rows[-1]),
        Rect(central - 1.2, rows[branch], central + 1.2, rows[branch + 1]),
    )
    shelves = tuple(
        Rect(27.7 + row * .2, y + .65, 28.4 + row * .2, y + 1.35)
        for row, y in enumerate(rows)
    )
    tags = tuple(
        Tag(f"{side}-{row}", x, y + .62, math.pi if side == "east" else 0)
        for row, y in enumerate(rows)
        for side, x in (("east", right), ("west", left))
    )
    starts = tuple(Pose(18, y, 0) for y in rows)
    dock = Pose(9.0, rows[rng.randrange(len(rows))], -math.pi)
    return Layout(aisles, shelves, tags, starts, dock, left, right)


def wheel_step(pose: Pose, left_mps: float, right_mps: float, duration: float = DT) -> Pose:
    linear = (left_mps + right_mps) / 2
    angular = (right_mps - left_mps) / TRACK_M
    turn = angular * duration
    if abs(turn) < 1e-12:
        dx = linear * duration * math.cos(pose.heading)
        dy = linear * duration * math.sin(pose.heading)
    else:
        radius = linear / angular
        dx = radius * (math.sin(pose.heading + turn) - math.sin(pose.heading))
        dy = radius * (math.cos(pose.heading) - math.cos(pose.heading + turn))
    return Pose(pose.x + dx, pose.y + dy, wrap(pose.heading + turn))


def lidar(layout: Layout, pose: Pose) -> tuple[float, ...]:
    result = []
    for relative in LIDAR_ANGLES:
        heading = pose.heading + relative
        dx, dy = math.cos(heading) * RAY_STEP_M, math.sin(heading) * RAY_STEP_M
        for index in range(1, round(LIDAR_RANGE_M / RAY_STEP_M) + 1):
            if not layout.free(pose.x + dx * index, pose.y + dy * index):
                result.append(round(index * RAY_STEP_M, 2))
                break
        else:
            result.append(LIDAR_RANGE_M)
    return tuple(result)


def tag_readings(layout: Layout, pose: Pose) -> tuple[TagReading, ...]:
    readings = []
    for tag in layout.tags:
        dx, dy = tag.x - pose.x, tag.y - pose.y
        distance = math.hypot(dx, dy)
        bearing = wrap(math.atan2(dy, dx) - pose.heading)
        if distance > 5.8 or abs(bearing) > math.radians(55):
            continue
        if not all(layout.free(pose.x + dx * j / 24, pose.y + dy * j / 24) for j in range(1, 25)):
            continue
        readings.append(TagReading(
            tag.name, round(distance, 3), round(bearing, 4), round(wrap(tag.heading - pose.heading), 4)
        ))
    return tuple(readings)


class Cart:
    """Authoring API. A scored policy would receive only Observation values."""

    def __init__(
        self,
        layout: Layout,
        pose: Pose,
        drive: Drive,
        tick_limit: int = 1000,
        *,
        floor: tuple[tuple[Rect, Drive], ...] = (),
    ):
        if not layout.footprint_clear(pose):
            raise ValueError("initial footprint overlaps a wall or shelf")
        if not (0 < drive.left_gain <= 1 and 0 < drive.right_gain <= 1 and drive.lag_ticks >= 0):
            raise ValueError("invalid drive parameters")
        self.layout = layout
        self.pose = pose
        self.drive = drive
        self.floor = floor
        self.tick_limit = tick_limit
        self.tick = 0
        self.collided = False
        self.odometry_m = self.odometry_heading = self.gyro_heading = 0.0
        self._queue = deque([(0.0, 0.0)] * drive.lag_ticks)
        self._last_applied = (0.0, 0.0)

    def advance(self, left: float, right: float) -> None:
        if self.collided or self.tick >= self.tick_limit:
            raise RuntimeError("episode already ended")
        if not all(math.isfinite(v) and abs(v) <= MAX_WHEEL_MPS for v in (left, right)):
            raise ValueError("wheel command outside the published range")
        self._queue.append((left, right))
        left, right = self._queue.popleft()
        self._last_applied = (left, right)
        self.tick += 1
        self.odometry_m += (left + right) * DT / 2
        self.odometry_heading += (right - left) * DT / TRACK_M
        traction = next(
            (profile for rect, profile in self.floor if rect.contains(self.pose.x, self.pose.y)),
            self.drive,
        )
        actual_left, actual_right = left * traction.left_gain, right * traction.right_gain
        self.gyro_heading += (actual_right - actual_left) * DT / TRACK_M
        # Check substeps so a command cannot hop through a thin obstacle.
        for _ in range(4):
            self.pose = wheel_step(self.pose, actual_left, actual_right, DT / 4)
            if not self.layout.footprint_clear(self.pose):
                self.collided = True
                break

    def observe(self, *, expose: bool = False) -> Observation:
        return Observation(
            self.tick, round(self.odometry_m, 5), round(self.odometry_heading, 5),
            round(self.gyro_heading, 5), lidar(self.layout, self.pose),
            tag_readings(self.layout, self.pose) if expose else (),
        )

    def docked(self) -> bool:
        goal = self.layout.dock
        return (
            not self.collided
            and all(not any(command) for command in (*self._queue, self._last_applied))
            and math.hypot(goal.x - self.pose.x, goal.y - self.pose.y) <= .22
            and abs(wrap(goal.heading - self.pose.heading)) <= .12
        )
