"""Construct private physical state and a matching public survey map."""

from dataclasses import replace

from .world import Cart, Drive, Layout, Rect, make_layout


def build_case(
    seed: int, row: int, drive: Drive, blocked: str, floor: Drive, *, gate_x: float | None = None,
    floor_span: tuple[float, float] | None = (8.2, 11.8),
) -> tuple[Layout, Cart]:
    surveyed = make_layout(seed)
    initial = surveyed.starts[row]
    if gate_x is None:
        gate_x = 25.6 if blocked == "east" else 10.55
    gate = Rect(gate_x, initial.y - 1.35, gate_x + .45, initial.y + 1.35)
    physical = replace(surveyed, shelves=(*surveyed.shelves, gate))
    surface = ()
    if floor_span is not None:
        left, right = floor_span
        loading = Rect(left, surveyed.dock.y - 1.35, right, surveyed.dock.y + 1.35)
        surface = ((loading, floor),)
    return surveyed, Cart(physical, initial, drive, floor=surface)
