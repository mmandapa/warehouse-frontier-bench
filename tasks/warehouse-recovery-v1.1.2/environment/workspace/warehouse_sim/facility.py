"""Construct surveyed warehouse layouts for local simulation."""

from __future__ import annotations

import math
import random

from .world import Layout, Pose, Rect, Tag


def survey(seed: int) -> Layout:
    rng = random.Random(seed)
    xs = tuple(float(5 + 11 * i + rng.randrange(3)) for i in range(4))
    ys = tuple(float(5 + 9 * i + rng.randrange(3)) for i in range(3))
    missing_row_edges = {(0, rng.randrange(3)), (2, rng.randrange(3))}
    missing_crossovers = {(0, rng.choice((1, 2))), (1, rng.choice((1, 2)))}
    corridors = []
    tags = []

    def aisle(x0: float, y0: float, x1: float, y1: float) -> None:
        half = rng.choice((1.05, 1.15, 1.25))
        corridors.append(Rect(x0 - half, y0 - half, x1 + half, y1 + half))
        for index, fraction in enumerate((-.06, .21, .50, .79, 1.06)):
            x, y = x0 + fraction * (x1 - x0), y0 + fraction * (y1 - y0)
            offset = .22 if index % 2 else -.22
            tags.append(Tag(f"M{len(tags) + 1:03d}", x + (offset if x0 == x1 else 0),
                            y + (offset if y0 == y1 else 0), 0.0))

    for row, y in enumerate(ys):
        for col, (left, right) in enumerate(zip(xs, xs[1:])):
            if (row, col) not in missing_row_edges:
                aisle(left, y, right, y)
    for row, (bottom, top) in enumerate(zip(ys, ys[1:])):
        for col, x in enumerate(xs):
            if (row, col) not in missing_crossovers:
                aisle(x, bottom, x, top)

    start_col, dock_col = rng.choice(((0, -1), (-1, 0)))
    starts = tuple(Pose(xs[start_col], y, 0.0) for y in ys)
    dock_row = rng.randrange(len(ys))
    dock_heading = rng.choice((0.0, math.pi / 2, -math.pi / 2, -math.pi))
    return Layout(tuple(corridors), (), tuple(tags), starts,
                  Pose(xs[dock_col], ys[dock_row], dock_heading), xs[0], xs[-1])
