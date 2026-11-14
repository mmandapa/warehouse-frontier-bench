# Warehouse cart recovery qualification

The capability question is whether an agent can acquire enough evidence to
localize a cart after a manual relocation, account for uncertain motion, and
complete an assigned dock approach. Qualification uses a full 2D mission
through repeated aisles. A cart starting in either of two similar aisles can
initially produce the same short-range scan. Wheel odometry measures
nominal motion and can overestimate floor travel under slip.

## Model and interfaces

- A warehouse map defines traversable bays, aisle junctions, anchor tags,
  and a surveyed dock pose. A circular footprint and the cart's heading
  matter throughout the trajectory. Continuous wheel commands are bounded.
- The controller receives a timestamp, nominal odometry, relative yaw,
  lidar ranges, and relative tag observations when it requests an exposure.
  A tag has finite range and must be in view. Ground-truth pose and traction
  parameters are available to the authoring verifier.
- The target is the assigned dock pose after the cart settles. Score position,
  heading, collision, and operating limits from simulator state. No score
  component requires a particular estimator, waypoint list, or maneuver.
- The qualification is deterministic and local. It uses a geometric
  differential-drive model and no renderer, GPU, or provider endpoint.
  It does not model contact forces, deformable payloads, or real sensor noise.

## Alternatives and assumptions

One-lane system identification isolates a sensor effect but lacks route
ambiguity and recovery decisions. A full RoboQuest or ROS/Gazebo stack
introduces assets and deployment risk beyond the assignment's timebox.
BARN informs the geometric navigation and held-out map design, while the
Nav2 docking interface motivates combining rough navigation with a final
pose target. This fixture is a synthetic reduction of that workflow.

## Qualification gates

1. Verify that the aliased start pair has equal initial observations,
   that progress can reveal a stable identifying feature, and that the
   intended dock is physically reachable with each represented drive mode.
2. Compare a known-pose control, a blind controller that uses the same
   observation interface as an agent, and strong shortcuts such as choosing
   one start, using odometry alone, and a fixed diagnostic route.
3. Exercise mirrored layouts, changed tag visibility, and different
   traction on held-out seeds. Run the same controllers in a paired setting
   with the start disclosed to isolate acquisition from execution.
4. A candidate needs a blind reference that reaches at least 90% and a
   meaningful gap from the strongest fixed control across held-out maps.
   A routine approach that saturates rejects the candidate even if weaker
   controls fail. Model difficulty remains unknown until fresh trials.

References: [BARN dataset](https://www.cs.utexas.edu/~xiao/BARN/BARN.html),
[Nav2 docking](https://docs.nav2.org/rolling/tutorials/general_tutorials/using_docking/),
and [RoboQuest](https://arxiv.org/html/2610.10388v1).
