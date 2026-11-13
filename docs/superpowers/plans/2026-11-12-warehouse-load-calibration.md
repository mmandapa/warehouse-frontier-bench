# Warehouse load calibration

1. Copy the frozen task to v1.1.0 and update the public model, camera
   budget, and contract. Check that nominal behavior matches the old
   simulator with the load response set to zero.
2. Build an observation-only reference and private cases with sustained
   motion and pauses. Check identifiability and test the reference on
   independent seeded carts.
3. Replay the four saved submissions and a constant-slip control.
   Require valid submissions and inspect pose errors by scenario.
4. Freeze the task, verify the old manifests, and run Harbor oracle and
   no-op controls on the exact frozen package.
