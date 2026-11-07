# Assignment requirements audit

This checks the supplied benchmark brief against the repository's observed state. It treats the brief as assignment requirements, not permission to expose its embedded credentials. The user separately authorized the private repository and bounded provider-key use.

| Requirement | Evidence | Status |
|---|---|---|
| Meaningful capability gap and motivation | Main README; research diagnosis distinguishes helper use from algorithmic memory planning | Design hypothesis; model evidence pending for CTC |
| Explain benchmark beyond implemented tasks | README and research note describe budget ladders, held-out generator families, and related differentiable dynamic programs | Present |
| 1–2 end-to-end Harbor tasks | `tasks/unseen-subject-audit` and `tasks/ctc-memory-kernel` | Two implemented |
| Clear instructions, inputs, tools, outputs, and success rule | Both tasks have instruction.md and public contracts | Present; CTC oracle verifies executability |
| Scalar reward in [0,1] | Separate verifiers write `reward.json`; primary rewards are binary | Verified |
| Optional oracle / solution | Both tasks have solution/solve.sh; new CTC oracle passes two Harbor runs | Provided and tested |
| No-op control requested by user | Untouched workspace receives zero through Harbor for both tasks | Verified |
| CPU-only or permitted single GPU | Both use two CPU cores and 4 GiB, no GPU | Within allowed option |
| Under two hours per task, including setup/evaluation | Explicit setup/agent/verifier limits; reference controls finish in seconds to minutes; model agent budget 20 minutes | Configured and measured for controls; CTC model path pending |
| Required resources available in environment | Prepared audit data; CTC compiler, baseline, public fixtures, NumPy and Wasmtime | Verified by controls and packaging tests |
| Run at least one specified model on each task through Harbor, k=4 | Audit: four Codex/gpt-6-luna runs preserved. CTC: no paid runs yet | **Incomplete for CTC; awaiting renewed API-use authorization** |
| Aim for genuine capability failure / low score | Audit saturated honestly. CTC model difficulty not yet measured | **Not established** |
| If all pass, report honestly and propose harder variant | Audit 4/4 reported; CTC redesign documented without changing old scores | Satisfied for original task |
| Compact results table and relevant trajectories | Original results plus CTC controls, frozen checksum, and raw Harbor records | Present; add CTC model trajectories after authorized runs |
| Short README and setup/run commands | Main README links detailed research and contracts | Present; commands exercised in local environment |
| Repository or ZIP submission | Private GitHub repository; current ZIP contains both tasks, code, data, controls, and evidence | Published privately and packaged |
| Time spent, limitations, next steps | Original measured interval, untimed earlier work, redesign caveat, results/research docs | Present; complete effort is **not** verified within five hours |
| Daytona pointer | Backend option documented; supplied key returned 401, user authorized Docker fallback | Optional; no claim of successful Daytona execution |
| Imagination, benchmark judgment, engineering, and analysis | Saturation diagnosis, resource-bounded primitive, independent numerical references, Wasm boundary, controls, alternatives, preserved provenance | Reviewer judgment; design evidence is concrete, empirical difficulty remains a gate |

No implementation control substitutes for model evaluation. No-op=0 proves that doing nothing fails; oracle=1 proves one solution is feasible; neither proves the problem is hard. A failing unchanged baseline adds evidence of a substantive optimization requirement. Model rollouts and trajectory diagnosis determine whether that requirement challenges the measured agent fairly.
