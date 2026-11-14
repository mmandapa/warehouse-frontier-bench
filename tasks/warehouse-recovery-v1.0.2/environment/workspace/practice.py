"""Run a public warehouse mission using the submitted policy interface."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from warehouse_sim.protocol import run_policy
from warehouse_sim.world import Cart, Drive, Pose, Rect, Tag, make_layout


def practice_scene(case: int):
    """Each practice mission makes a different part of the interface useful."""
    surveyed = make_layout((112, 405, 734)[case])
    start = next(pose for pose in surveyed.starts if pose.y != surveyed.dock.y)
    drive = (Drive(.90, .86, 0), Drive(.76, .69, 1), Drive(.84, .92, 2))[case]
    physical = surveyed
    floor = ()
    if case == 1:
        pallet = Rect(24.4, start.y - 1.35, 25.05, start.y + 1.35)
        physical = replace(surveyed, shelves=(*surveyed.shelves, pallet))
    elif case == 2:
        dock = Pose(13.5, surveyed.dock.y, surveyed.dock.heading)
        marker = Tag("practice-bay", 10.4, dock.y + .62, 0)
        surveyed = replace(surveyed, dock=dock, tags=(*surveyed.tags, marker))
        physical = surveyed
        pad = Rect(11.9, dock.y - 1.35, 15.6, dock.y + 1.35)
        floor = ((pad, Drive(.60, .68, 0)),)
    return surveyed, Cart(physical, start, drive, floor=floor)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    surveyed, cart = practice_scene(args.case)
    result = run_policy(args.policy, Path(__file__).with_name("warehouse_sim"), cart, surveyed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
