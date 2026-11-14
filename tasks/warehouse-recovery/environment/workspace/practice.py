"""Run a public practice mission with the standard policy interface."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from warehouse_sim.facility import survey
from warehouse_sim.protocol import run_policy
from warehouse_sim.world import Cart, Drive, Rect


def practice_scene(case: int):
    layout = survey((102, 211, 337)[case])
    initial = layout.starts[(2, 0, 1)[case]]
    drive = (Drive(.89, .94, 0), Drive(.78, .88, 1), Drive(.89, .76, 2))[case]
    physical = layout
    floor = ()
    if case == 1:
        physical = replace(layout, shelves=(Rect(11.98, 13.7, 12.42, 16.3),))
    elif case == 2:
        dock = layout.dock
        floor = ((Rect(dock.x - 2.9, dock.y - 3.2, dock.x + 2.9, dock.y + 3.2),
                  Drive(.67, .55, 0)),)
    return layout, Cart(physical, initial, drive, 2100, floor=floor)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    survey_map, cart = practice_scene(args.case)
    result = run_policy(args.policy, Path(__file__).with_name("warehouse_sim"), cart, survey_map)
    print(json.dumps({key: value for key, value in result.items() if key != "exposures"}, indent=2))


if __name__ == "__main__":
    main()
