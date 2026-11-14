"""Public kinematic model for the maintenance bay."""

from dataclasses import dataclass
import math

DT = 0.2
TRACK_M = 0.56
LOAD_RETENTION = 0.82


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


@dataclass(frozen=True)
class CartParameters:
    lag: int
    deadbands: tuple[float, float]
    forward_gains: tuple[float, float]
    reverse_gains: tuple[float, float]
    forward_slip: float
    reverse_slip: float
    gyro_bias: float
    forward_load_slip: float = 0.0
    reverse_load_slip: float = 0.0


def wheel_response(command, deadband, forward, reverse):
    gain = forward if command >= 0 else reverse
    return gain * math.copysign(max(abs(command) - deadband, 0.0), command)


def step(pose, left, right, settings, load):
    left_speed, right_speed = (
        wheel_response(command, deadband, forward, reverse)
        for command, deadband, forward, reverse in zip(
            (left, right), settings.deadbands, settings.forward_gains, settings.reverse_gains
        )
    )
    center_speed = (left_speed + right_speed) / 2
    slip = settings.forward_slip if center_speed >= 0 else settings.reverse_slip
    load_slip = settings.forward_load_slip if center_speed >= 0 else settings.reverse_load_slip
    distance = DT * center_speed * (1 + slip + load_slip * load)
    turn = DT * (right_speed - left_speed) / TRACK_M
    x, y, heading = pose
    half_turn = turn / 2
    arc_scale = math.sin(half_turn) / half_turn if turn else 1.0
    return (
        x + distance * arc_scale * math.cos(heading + half_turn),
        y + distance * arc_scale * math.sin(heading + half_turn),
        wrap(heading + turn),
    ), turn


class Bay:
    def __init__(self, settings):
        self.settings = settings
        self.pending = [(0.0, 0.0)] * settings.lag
        self.pose = (0.0, 0.0, 0.0)
        self.tick = 0
        self.encoder = [0.0, 0.0]
        self.gyro = 0.0
        self.load = 0.0

    def advance(self, left, right):
        self.pending.append((left, right))
        applied = self.pending.pop(0)
        self.tick += 1
        for i, value in enumerate(applied):
            self.encoder[i] += DT * value
        effort = (abs(applied[0]) + abs(applied[1])) / 2
        self.load = LOAD_RETENTION * self.load + (1 - LOAD_RETENTION) * effort
        self.pose, turn = step(self.pose, *applied, self.settings, self.load)
        self.gyro += turn + DT * self.settings.gyro_bias
        return {
            "tick": self.tick,
            "encoders_m": [round(value, 6) for value in self.encoder],
            "gyro_rad": round(self.gyro, 6),
        }


def forecast(settings, commands):
    bay = Bay(settings)
    for left, right in commands:
        bay.advance(left, right)
    return bay.pose
