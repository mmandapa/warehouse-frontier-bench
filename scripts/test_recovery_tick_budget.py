"""Check the final-tick contract without starting a policy subprocess."""

from pathlib import Path
import sys
import unittest

GRADER = Path(__file__).resolve().parents[1] / "tasks/warehouse-recovery/tests/grader"
sys.path.insert(0, str(GRADER))

from warehouse_sim.facility import survey
from warehouse_sim.protocol import execute
from warehouse_sim.world import Cart, Drive


class Transcript:
    def __init__(self, requests):
        self.requests = iter(requests)
        self.responses = []

    def read(self):
        return next(self.requests)

    def write(self, response):
        self.responses.append(response)


DRIVE = {"op": "drive", "left": 0, "right": 0}
FINISH = {"op": "finish"}


class TickBudgetTests(unittest.TestCase):
    def run_mission(self, requests, lag=0):
        layout = survey(102)
        cart = Cart(layout, layout.dock, Drive(1, 1, lag), tick_limit=1)
        wire = Transcript(requests)
        result = execute(wire, cart, layout)
        self.assertEqual(cart.tick, 1)
        return result, wire.responses

    def test_can_observe_and_finish_after_exactly_using_budget(self):
        result, responses = self.run_mission([DRIVE, {"op": "sense"}, FINISH])
        self.assertTrue(result["success"])
        self.assertEqual(responses[1], {})
        self.assertEqual(responses[2]["tick"], 1)
        self.assertEqual(responses[3], {})

    def test_extra_movement_fails_without_exceeding_budget(self):
        for requests in ([DRIVE, DRIVE], [{**DRIVE, "ticks": 2}]):
            with self.subTest(requests=requests):
                result, _ = self.run_mission(requests)
                self.assertEqual(result["reason"], "motion limit")
                self.assertFalse(result["success"])

    def test_finish_requires_settled_cart(self):
        result, _ = self.run_mission([{**DRIVE, "left": -1, "right": 1}, FINISH], lag=1)
        self.assertEqual(result["reason"], "incorrect final pose or cart still moving")
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
