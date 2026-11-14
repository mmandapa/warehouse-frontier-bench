"""Contract checks for the authoring simulator."""

import math
import unittest

from authoring.warehouse_recovery.world import Cart, Drive, Pose, make_layout, wheel_step
from authoring.warehouse_recovery.warehouse_shift import build_case, run_case


class WarehouseWorldTests(unittest.TestCase):
    def test_relocated_carts_have_identical_initial_observations(self):
        layout = make_layout(42)
        carts = [Cart(layout, p, Drive(1, 1, 0)) for p in layout.starts]
        self.assertGreater(len(carts), 1)
        self.assertTrue(all(c.observe(expose=True) == carts[0].observe(expose=True) for c in carts))

    def test_wheel_slip_changes_ground_travel_without_changing_odometry(self):
        layout = make_layout(42)
        nominal = Cart(layout, layout.starts[0], Drive(1, 1, 1))
        slipping = Cart(layout, layout.starts[0], Drive(.65, .65, 1))
        for _ in range(10):
            nominal.advance(.5, .5)
            slipping.advance(.5, .5)
        self.assertEqual(nominal.observe().odometry_m, slipping.observe().odometry_m)
        self.assertGreater(nominal.pose.x, slipping.pose.x)

    def test_differential_motion_supports_turns_without_translation(self):
        pose = wheel_step(Pose(4, 4, 0), -.5, .5)
        self.assertEqual((pose.x, pose.y), (4, 4))
        self.assertGreater(pose.heading, 0)

    def test_wall_contact_is_terminal(self):
        layout = make_layout(42)
        cart = Cart(layout, Pose(18, layout.starts[0].y, math.pi / 2), Drive(1, 1, 0))
        for _ in range(40):
            if cart.collided:
                break
            cart.advance(1, 1)
        self.assertTrue(cart.collided)
        with self.assertRaises(RuntimeError):
            cart.advance(0, 0)

    def test_anchor_requires_visibility_and_reveals_which_lane(self):
        layout = make_layout(42)
        visible = []
        for start in layout.starts:
            cart = Cart(layout, Pose(29, start.y, 0), Drive(1, 1, 0))
            visible.append(tuple(tag.name for tag in cart.observe(expose=True).tags))
        self.assertTrue(all(visible))
        self.assertEqual(len(set(visible)), len(visible))

    def test_initial_sensor_data_does_not_reveal_which_gate_is_closed(self):
        layout = make_layout(42)
        row = next(index for index, p in enumerate(layout.starts) if p.y != layout.dock.y)
        carts = [
            build_case(42, row, Drive(.72, .72, 1), side, Drive(.57, .60, 0))[1]
            for side in ("east", "west")
        ]
        self.assertEqual(carts[0].observe(expose=True), carts[1].observe(expose=True))

    def test_adaptive_controller_uses_both_routes_and_docks(self):
        for blocked, expected in (("east", "west"), ("west", "east")):
            with self.subTest(blocked=blocked):
                result = run_case(42, 1, Drive(.72, .72, 1), blocked, Drive(.57, .60, 0), "adaptive")
                self.assertEqual(result["chosen"], expected)
                self.assertTrue(result["docked"])
                self.assertFalse(result["collision"])


if __name__ == "__main__":
    unittest.main()
