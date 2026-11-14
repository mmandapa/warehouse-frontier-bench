"""Construct matched private episodes for late route closures."""

from dataclasses import dataclass, replace
from heapq import heappop, heappush
import math

from .facility import survey
from .world import Cart, Drive, Layout, Rect


Point = tuple[float, float]
Edge = tuple[Point, Point]
TICK_LIMIT = 2100


def corridors(layout: Layout) -> tuple[Edge, ...]:
    edges = []
    for rect in layout.aisles:
        width, height = rect.right - rect.left, rect.top - rect.bottom
        if width > height:
            y = (rect.bottom + rect.top) / 2
            edge = ((rect.left + height / 2, y), (rect.right - height / 2, y))
        else:
            x = (rect.left + rect.right) / 2
            edge = ((x, rect.bottom + width / 2), (x, rect.top - width / 2))
        edges.append(tuple(tuple(round(axis, 5) for axis in point) for point in edge))
    return tuple(edges)


def shortest(edges: tuple[Edge, ...], start: Point, end: Point, blocked: tuple[Edge, ...] = ()) -> tuple[Point, ...]:
    pending = [(0.0, (start,))]
    seen = set()
    while pending:
        distance, path = heappop(pending)
        point = path[-1]
        if point in seen:
            continue
        if point == end:
            return path
        seen.add(point)
        for edge in edges:
            if edge not in blocked and point in edge:
                other = edge[1] if edge[0] == point else edge[0]
                if other not in seen:
                    heappush(pending, (distance + math.dist(point, other), (*path, other)))
    return ()


def barrier(edge: Edge, fraction: float) -> Rect:
    (x0, y0), (x1, y1) = edge
    x, y = x0 + fraction * (x1 - x0), y0 + fraction * (y1 - y0)
    if x0 == x1:
        return Rect(x - 1.30, y - .22, x + 1.30, y + .22)
    return Rect(x - .22, y - 1.30, x + .22, y + 1.30)


def closure_options(path: tuple[Point, ...]) -> list[Edge]:
    # A later closure is beyond the first segment, with corner cases preferred.
    pairs = list(zip(path, path[1:]))
    after_turn = [
        i for i in range(1, len(pairs))
        if (pairs[i][0][0] == pairs[i][1][0]) != (pairs[i-1][0][0] == pairs[i-1][1][0])
    ]
    indexes = after_turn + [i for i in range(1, len(pairs)) if i not in after_turn]
    return [tuple(sorted(pairs[i])) for i in indexes]


@dataclass(frozen=True)
class Family:
    layout: Layout
    start_index: int
    closed: tuple[Edge, Edge]
    drive: Drive


def family(seed: int, start_index: int, drive: Drive) -> Family:
    layout = survey(seed)
    start = layout.starts[start_index]
    origin, dock = (start.x, start.y), (layout.dock.x, layout.dock.y)
    edges = corridors(layout)
    nominal = shortest(edges, origin, dock)
    initial = Cart(layout, start, drive).observe(expose=True)
    for first in closure_options(nominal):
        detour = shortest(edges, origin, dock, (first,))
        for second in closure_options(detour):
            last_route = shortest(edges, origin, dock, (first, second))
            if not last_route or sum(math.dist(a, b) for a, b in zip(last_route, last_route[1:])) > 78:
                continue
            physical = replace(layout, shelves=(barrier(first, .48), barrier(second, .57)))
            if Cart(physical, start, drive).observe(expose=True) == initial:
                return Family(layout, start_index, (first, second), drive)
    raise ValueError(f"no usable paired closures for seed {seed}, start {start_index}")


class RecordedCart(Cart):
    def __init__(self, *args, gates: tuple[Rect, ...], **kwargs):
        super().__init__(*args, **kwargs)
        self.gates = gates
        self.gate_ranges = [math.inf] * len(gates)

    def advance(self, left: float, right: float) -> None:
        super().advance(left, right)
        x, y = self.pose.x, self.pose.y
        for index, gate in enumerate(self.gates):
            dx = max(gate.left - x, x - gate.right, 0.0)
            dy = max(gate.bottom - y, y - gate.top, 0.0)
            self.gate_ranges[index] = min(self.gate_ranges[index], math.hypot(dx, dy))


def episode(spec: Family, closures: int, *, mixed_grip: bool = False) -> RecordedCart:
    layout = spec.layout
    gates = tuple(barrier(edge, fraction) for edge, fraction in zip(spec.closed[:closures], (.48, .57)))
    floor = ()
    if mixed_grip:
        dock = layout.dock
        floor = ((Rect(dock.x - 3.25, dock.y - 2.45, dock.x + 3.25, dock.y + 2.45),
                  Drive(.56, .70, 0) if spec.start_index % 2 else Drive(.72, .53, 0)),)
    return RecordedCart(replace(layout, shelves=gates), layout.starts[spec.start_index],
                        spec.drive, TICK_LIMIT, floor=floor, gates=gates)
