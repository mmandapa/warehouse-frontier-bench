# Warehouse cart simulator

`warehouse_sim.client.CartClient` talks to the simulator through stdin
and stdout. The map has global coordinates in meters and headings in
radians, counterclockwise from positive x. It gives traversable aisle
rectangles, fixed shelves, surveyed marker poses, possible start poses,
and the assigned dock pose. The actual initial pose is unknown. A
temporary obstruction may be absent from the survey map.

```python
from warehouse_sim.client import CartClient

cart = CartClient()
survey = cart.layout
reading = cart.observe()
# Write your controller here.
cart.finish()
```

Use `print(..., file=sys.stderr)` for policy logging. Stdout is reserved
for the client.

| Operation or field | Meaning |
| --- | --- |
| `cart.command(left, right, ticks=1)` | Set wheel speed in m/s, between -1 and 1 inclusive. Each tick advances 0.2 seconds. A call can advance 1 to 10 ticks. Wheel actuation can lag the command. |
| `cart.observe()` | Read sensors without advancing simulation time. |
| `reading.odometry_m`, `reading.odometry_heading_rad` | Signed distance and unwrapped turn since the start, derived from wheel motion. Slip can make both differ from ground motion. |
| `reading.gyro_heading_rad` | Unwrapped change in ground heading since the start. |
| `reading.lidar_m` | 16 ranges in meters. Index 0 faces forward and indices increase counterclockwise in 22.5-degree increments. Range is capped at 4.8 m. |
| `cart.observe(expose=True).tags` | Visible surveyed markers. Each reading includes its name, range, bearing relative to the cart heading, and marker heading relative to the cart. No reading is returned for a marker outside the camera view or behind an obstruction. |
| `cart.finish()` | End the mission and grade the current cart state. |

The wheel separation is 0.56 m. The footprint has a radius of 0.28 m.
Floor grip can vary within a mission. A collision ends the mission.
To succeed, stop within 0.22 m and 0.12 rad of the dock with no pending
movement. The mission allows 1,000 simulation ticks. The controller has
12 seconds of wall time and up to 5,000 protocol requests per mission.
The verifier runs the submitted program from a fresh process for each
scenario and scores the fraction of missions successfully docked.

Run a practice mission from `/app`:

```bash
python -B practice.py --case 0 --policy policy.py
python -B practice.py --case 1 --policy policy.py
```

Both practice missions use the same policy interface as grading.
