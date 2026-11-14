---
status: accepted
date: 2026-11-12
---

# Test recovery when a surveyed route is blocked

## Context

On v1.0.2, a Luna controller chose an aisle end using lidar during localization and then followed surveyed junctions. It scored 16/16 in the completed trial. The new task asks whether an agent can build a controller that safely changes a plan after a later obstruction invalidates it.

## Decision

Use connected orthogonal warehouse layouts with different corridor connections. A survey provides corridor geometry and marker positions. Static unmarked pallets can invalidate a route and then its first alternative. Paired episodes hold the surveyed layout, start, and dock fixed while changing route closures and floor grip. Each closure has a reachable detour and fits within the existing sensing model. The cart must still meet the original physical docking tolerances.

Reuse the standard-library simulator, policy interface, and separate CPU-only verifier. Grade the fraction of missions with a safe settled dock. Diagnostics include the last physical pose and distances reached from each closure. Increase the published simulation tick budget to accommodate backtracking. Use a 900-second Harbor agent limit, two CPUs, and 4 GiB per environment.

## Alternatives and limits

Adding more pallets to the old geometry would still permit a fixed end-of-aisle strategy. Moving pallets or injecting sensor noise would make a miss harder to attribute. This variant keeps readings deterministic and varies route connectivity and traction. It assumes a usable survey and fixed obstacles during each episode.

Local acceptance requires an observation-only oracle that docks on every episode, a zero-score no-op, and a controller that passes clear cases but fails on closures without replanning. Check that initial observations match in paired episodes. Keep the old Luna score and replay its submitted policy for comparison. Harbor qualification and fresh model trials require separate evidence.
