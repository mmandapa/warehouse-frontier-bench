# Warehouse replanning implementation plan

Goal is a separate v1.1.0 Harbor variant that measures recovery after late route invalidation. The design is recorded in ADR 0021.

- [x] Add public facility geometry and independent practice episodes. Keep the policy API unchanged and publish the motion and sensing limits.
- [x] Build paired private scenes and prove that the closures are initially indistinguishable and that detours exist. Run an observation-only oracle using the same protocol.
- [x] Compare no-op, fixed-route and one-replan controls, and the saved Luna policy. Check physics diagnostics for intended failures.
- [x] Audit the agent image context, verify frozen v1.0.2, record the local results, and freeze the new variant.
- [ ] Run Harbor oracle and no-op when Docker is available. See the qualification report for commands.
