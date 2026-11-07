# ADR-001: Grade reproducible audit evidence using an isolated verifier

Status: Accepted for the prototype

Date: 2026-11-06

The task measures whether a tool-using agent can audit a classifier improvement for deployment to unseen people. The OA requires one complete Harbor task, a scalar reward, four model attempts, CPU or one GPU, and less than two hours per task including setup and grading. We assume a small CPU dataset is a useful proxy; frontier difficulty is unproven.

Use the official UCI HAR training partition for development and reserve the original test partition for diagnostics. Freeze two classifier recipes after a bounded development-only calibration. Require a matched original/corrected comparison, person-macro accuracy, a deterministic paired-person bootstrap interval, and a policy-consistent decision. Agent outputs are bounded JSON and a short Markdown report. A separate verifier container reconstructs experiments from its own code and data; it never imports agent code or loads pickle. Only this verifier writes the scalar reward. Agent and verifier have separate filesystems and transfer only declared artifacts.

The primary reward checks protocol and evidence correctness. Hidden-test accuracy is diagnostic: the small held-out population must not turn a defensible development decision into a scientific-judgment failure. This revises the research memo's proposed quality floor. The interval describes the observed cross-validation comparison and is not a population-wide confidence guarantee.

Alternatives considered: arbitrary submitted Python gives more research freedom but requires a larger untrusted-code boundary; a GPU post-training task gives closer LLM research fidelity but threatens the five-hour OA; an LLM judge adds avoidable uncertainty for numerical criteria. Fixed recipes and a small verifier are sufficient here. One process grades one attempt; concurrency is at the Harbor trial level. Training threads and timeouts are bounded. Infrastructure exceptions are recorded separately from graded task failures. No database, web service, authentication layer, queue, or RL training loop is needed for this local batch workflow. Provider authentication belongs to Harbor's agent launcher and must not enter task artifacts.

The main bottleneck is replaying six model fits for each protocol. Measure runtime before agent trials. If task diversity, arbitrary model search, or sustained RL training is added, revisit sparse rewards, adaptive fold selection, verifier throughput, contamination, and the executable-code boundary. No claim of learning improvement follows from this prototype.
