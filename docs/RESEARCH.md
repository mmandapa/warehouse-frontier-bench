# Research: from a saturated audit to memory-bounded ML implementation

## Decision and evidence

Keep the original `unseen-subject-audit` as an observed saturation baseline. Add one replacement task, `ctc-memory-kernel`, measuring whether an agent can preserve a numerically sensitive ML primitive while changing its algorithm to satisfy a tight working-memory budget. There are two implemented tasks, within the assignment's 1–2-task limit. Four frozen-version Codex/gpt-6-luna trials subsequently all passed. The replacement did not establish the intended capability gap; the measured result and next proposal appear below.

The initial task was too guided for the measured model. All four Codex/gpt-6-luna attempts received 1.0. Inspection of their trajectories showed essentially the same route: read the public contract, construct a participant-to-fold assignment, call the supplied experiment helper, and copy its audit evidence into the required files. The helper already owned model fitting, group-macro scoring, the bootstrap, and policy decisions. A correct verifier did not make the task a difficult research problem. The failure was in task construction, not evidence that its scores should be changed.

The original oracle and no-op controls were already present and passed their intended checks. They establish that an answer exists and an empty workspace fails. They do **not** establish difficulty, validity against plausible wrong implementations, or resistance to shortcuts. The replacement therefore adds an unchanged compiled baseline control, independent numerical references, targeted negative controls, and explicit calibration rules.

## Research that changed the design

| Primary source | Relevant lesson | Application here |
|---|---|---|
| [Prime Intellect: auditing public evaluations](https://www.primeintellect.ai/blog/auditing-public-evaluations), Nov 3, 2026 | Ambiguous interfaces and brittle graders can masquerade as model weakness; public solution retrieval can invalidate a score. | Publish the ABI, tolerances, resource limits, and case families. Accept any correct algorithm. Restrict network access and keep private expected outputs out of the agent image. |
| [Abundant: TheoremSmith](https://www.abundant.ai/blog/theoremsmith/), Oct 13, 2026 | Oracle and blank controls precede solve rollouts; trajectory inspection separates real difficulty from task defects. | Require Harbor oracle=1 and no-op=0, inspect failures, then consider adversarial rollouts. No failure quota or post-hoc tightening. |
| [METR: recent reward hacking](https://metr.org/blog/2025-06-05-recent-reward-hacking/) | Agents can modify shared reference code, timing machinery, and expected answers. | Transfer only a WebAssembly module into a separate verifier. Supply no host imports, WASI, filesystem, network, or clock to the module. |
| [Graves et al.: CTC](https://www.cs.toronto.edu/~graves/icml_2006.pdf) | Alignment marginalization is a real sequence-learning primitive with a forward/backward dynamic program. | Test loss and the full derivative with respect to logits, including repeated labels and blank semantics. |
| [Chen et al.: sublinear-memory training](https://arxiv.org/abs/1604.06174) | Recomputing intermediate states trades additional work for reduced memory. | Require a substantive compute/storage tradeoff, with both memory and deterministic work bounded. |
| [PyTorch CTCLoss](https://docs.pytorch.org/docs/2.15/generated/torch.nn.CTCLoss.html) | A separate maintained implementation provides a useful numerical cross-check. | Validate generated feasible fixtures against float64 PyTorch loss and autograd, in addition to enumeration and finite differences. |
| [Wasmtime Python API](https://bytecodealliance.github.io/wasmtime-py/) | Fuel and store limits are enforceable runtime controls, with limits distinct from total host memory. | Pin the engine; cap linear memory and fuel. Retain outer container resources and timeout for host/JIT work. |

These sources support design methods, not a claim that this task is novel or frontier-hard. The task's particular difficulty must be established experimentally. The earlier landscape research remains historical context; this redesign uses direct evidence from the implemented task and primary evaluation research, rather than the author's GitHub projects as a quality reference.

## Alternatives considered

1. **Remove the statistical-audit helper.** Cheap to implement but likely still a familiar grouped-cross-validation exercise. Less scaffolding could mostly add boilerplate rather than research reasoning.
2. **Introduce messier scientific evidence and adaptive experiment search.** Promising longer-term family, but a fair scalar score needs careful handling of multiple defensible conclusions, stochastic fits, and search-budget accounting. Too much new verifier uncertainty for this revision.
3. **GPU kernel or distributed-training optimization.** Strong fit to ML systems work, but the assignment's Daytona key returned HTTP 401 and no GPU backend was validated. Provisioning uncertainty would confound results.
4. **CPU numerical kernel with a memory constraint.** Chosen: inexpensive reproducible execution, independent mathematical references, a feasible oracle, and an actual algorithmic change rather than answer formatting. CTC supplies enough semantic edge cases to catch plausible shortcuts without obscure toolchains.

The agent receives correct C recurrences and a dense baseline. This deliberately reduces ambiguity about mathematics and tool setup. It does not receive the oracle's storage strategy. The intended challenge is planning and implementing the memory/work tradeoff without breaking gradients or extreme-input stability. This is a narrower, more defensible claim than general autonomous research ability.

## Difficulty calibration before model evaluation

A first 2 MiB design admitted a simple block-checkpointed oracle and passed all private fixtures locally. Before any replacement-task model rollout, the limit was revised to 1.5 MiB and a recursive oracle was implemented. On the largest shape, the full double alpha table alone is 12,607,488 bytes; input logits plus output gradients consume 1,179,648 bytes. Ordinary dense storage is impossible under the final cap. A uniform float64 block-checkpoint table plus replay block also exceeds the remaining space with the supplied baseline's storage layout. Other valid strategies, including mixed precision that meets the same numerical tolerances, remain allowed.

This feasibility calibration used reference programs only; no model result motivated the tighter limit. The published work allowance is deliberately generous to the recursive oracle, not a tight oracle-speed race. Exact fuel measurements and artifact hashes are saved under `results/ctc/`. Wasmtime fuel is an engine-specific instruction accounting mechanism; it must never be described as a measured hardware speedup.

## Validation protocol

1. Check the independent NumPy reference with exhaustive tiny path enumeration, finite-difference logit gradients, and PyTorch float64 on every feasible fixture.
2. Freeze public/private fixture hashes and runtime code before model trials. Every private family has a public representative. Hidden values are not hidden requirements.
3. Require two end-to-end Harbor oracle rewards of 1.0 and a no-op reward of 0.0. Also compile the unchanged baseline and require primary reward 0.0 with large-case resource failures.
4. Test plausible and hostile failures: loss without gradients, unwritten outputs, incorrect impossible-alignment behavior, input mutation, excessive memory, forbidden host imports, and infinite computation.
5. Launch four prespecified attempts on the frozen task with no automatic retries. Record model, harness, effort, budget, task checksum, trajectories, failures, and infrastructure exceptions. Do not select only favorable runs.
6. Diagnose each low score against the trajectory and actual module. If instructions or infrastructure are defective, version the fix and rerun an entire clearly labeled batch. Do not silently regrade failures under a changed task.
7. If all four pass, report saturation at that setting. Propose a harder version separately. If weaker-model failures are genuine, the OA permits that evidence; a stronger-model comparison is still needed before claiming frontier difficulty.

The user separately authorized four CTC Luna attempts. That batch finished with four rewards of 1.0 and no infrastructure exceptions. No Astra batch was authorized or launched. The final task checksum matches its pre-run freeze and all controls. See `results/ctc/RESULTS.md` for timings, cost estimate, source provenance, and trajectory findings.


## Update after four Luna attempts

The hypothesis that memory pressure on this CTC implementation would be sufficiently challenging was not supported. All four agents solved the private suite in 94.7 to 204.7 seconds of agent execution. They fixed actual fuel or numerical errors, but these remained intermediate errors. Their final generic algorithms use sparse checkpoints with local replay or safe temporary reuse of gradient output memory. All four retained source programs recompile to byte-identical submitted modules.

The task provides a validated numerical environment and useful debugging trajectories. It is not evidence of a remaining frontier capability gap. The next change should broaden the problem structure instead of repeatedly reducing the same memory or time allowance. A stronger-model run on this setting is not the next cost-effective experiment.

## Proposed successor: memory planning across branched autodiff graphs

Status: proposal only; not implemented or empirically calibrated. It would replace a task under a new version, preserving the measured CTC version in Git history and its result manifest, rather than adding a third submitted environment.

[Checkmate](https://arxiv.org/abs/1910.02653) studies rematerialization schedules for general neural-network dependency graphs, including unequal compute costs and activation sizes. [Dynamic Tensor Rematerialization](https://ztatlock.net/pubs/2021-iclr-dtr/) studies online eviction and recomputation. These motivate a more general memory-planning task; their published results do not predict current agent difficulty.

Give the agent a typed graph format: nodes, dependencies, output sizes in bytes, recomputation work units, required reverse operations, and a memory budget. Start with public chains, residual diamonds, fork/join graphs, and asymmetric branches, each with explicit small examples and a legal baseline. The agent implements a planner that emits compute, release, and reverse operations for unseen graphs. A trusted simulator validates dependencies, tensor lifetimes, completion, peak live bytes, and total work. It reads no agent-reported memory or timing numbers. The input and transition semantics, including transient allocation and reuse, must be fully public.

A chain checkpoint heuristic must remain an explicit negative baseline. General branching and unequal costs make placement depend on interactions between subgraphs, rather than one checkpoint interval. This is the intended additional capability, not a claim that it is already hard for Luna. Include alternate valid schedules; never compare schedule text with one canonical answer.

Before implementation, establish exact-search oracle costs on small graphs and feasible reference schedules plus lower bounds on larger graphs. Distinguish proven optimal costs from heuristic reference costs. A scalar reward can gate on legality and then normalize extra recomputation work against declared baseline/reference anchors; choose those anchors before model trials and show the full work-cost diagnostics. Oracle=1 and no-op=0 remain mandatory controls, alongside periodic-chain, greedy-eviction, and invalid-lifetime controls.

Calibrate graph size, topology variety, and memory/work ratios against oracle feasibility and meaningful baselines. A CPU simulator keeps evaluation inexpensive. Do not claim GPU speedups from simulated work. First run a small development pilot under a separate explicit allowance, then freeze one task version and launch four prespecified attempts. If this version also saturates, report that rather than tightening its grader after the fact.

[MLRC-Bench](https://arxiv.org/abs/2504.09702) and [FML-bench](https://arxiv.org/abs/2510.10472) also motivate separating research-method discovery from engineering execution and examining exploration behavior. A budgeted experiment-design task remains an alternative if the objective is scientific judgment rather than compiler-style planning. Those older benchmark results are contextual evidence, not current-model capability claims. METR's [RE-Bench repository](https://github.com/METR/RE-Bench) is archived and marked deprecated; it is a historical design reference, not an up-to-date difficulty guarantee.

## Founder evaluation lens

The useful asset is a repeatable task-and-verifier construction method: select a real bottleneck, make the interface fair, prove a solution exists, test negative controls, measure model behavior, and preserve provenance. A hard-looking prompt or a low score alone has little value. The current task can yield trajectories about memory reasoning, recurrence preservation, numerical debugging, and experiment selection, each grounded in an executable final artifact.

For a larger benchmark, vary sequence length, target length, class count, numerical range, and memory/work ratios; hold out generator families as well as random seeds. Extend to other differentiable dynamic programs only after independent references exist. Maintain a ladder of oracle-feasible budgets rather than increasing constraints until a particular model fails. Rank instance difficulty using repeated trials and report uncertainty. Randomizing data alone does not create broad algorithmic coverage.

The proof of concept provides an episodic RL environment: a task reset creates a workspace, the agent uses tools, and the final verifier returns one scalar reward. It does not train a policy or demonstrate learning gains. Sparse binary reward fits exact artifact correctness; per-case diagnostics aid analysis without rewarding a loss-only or small-case-only implementation as complete success.

## Submission limits

The original timed implementation interval is in `results/work-log.json`; earlier research was untimed. The additional redesign is beyond that original interval, so the complete project must not be presented as a verified five-hour exercise. CPU/Docker is the measured backend; Daytona remains unvalidated because the supplied key was rejected. The private GitHub repository contains solutions and private fixtures for reviewers; agents under evaluation must receive only their task environment, never a repository checkout or its credentials.
