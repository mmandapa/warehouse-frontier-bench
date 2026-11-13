"""Construct private physical state and a matching public survey map."""

from dataclasses import replace

from .world import Cart, Drive, Layout, Rect, make_layout


def build_case(
    seed: int, row: int, drive: Drive, blocked: str, floor: Drive, *, gate_x: float | None = None,
) -> tuple[Layout, Cart]:
    surveyed = make_layout(seed)
    initial = surveyed.starts[row]
    if gate_x is None:
        gate_x = 25.6 if blocked == "east" else 10.55
    gate = Rect(gate_x, initial.y - 1.35, gate_x + .45, initial.y + 1.35)
    physical = replace(surveyed, shelves=(*surveyed.shelves, gate))
    loading = Rect(8.2, surveyed.dock.y - 1.35, 11.8, surveyed.dock.y + 1.35)
    return surveyed, Cart(physical, initial, drive, floor=((loading, floor),))
