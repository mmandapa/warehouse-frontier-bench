"""Summarize captured Harbor records without treating infrastructure errors as scores."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
PRIMARY=RESULTS/'models/primary-docker-gpt-6-luna'


def records(root):
    rows=[]
    for path in root.rglob('result.json'):
        d=json.loads(path.read_text())
        if 'trial_name' not in d: continue
        e=d.get('exception_info') or {}
        score=(d.get('verifier_result') or {}).get('rewards',{}).get('reward')
        start=datetime.fromisoformat(d['started_at'].replace('Z','+00:00'))
        end=datetime.fromisoformat(d['finished_at'].replace('Z','+00:00')) if d.get('finished_at') else None
        agent=d['config']['agent']
        diag=path.parent/'verifier/diagnostics.json'
        diagnostics=json.loads(diag.read_text()) if diag.exists() else {}
        audit_path=path.parent/'artifacts/app/submission/audit.json'
        audit=json.loads(audit_path.read_text()) if audit_path.exists() else {}
        rows.append(dict(trial=d['trial_name'],model=agent.get('model_name'),harness=agent['name'],
                         score=score,invalid=bool(e) or diagnostics.get('invalid_trial',False),
                         exception=e.get('exception_type'),reason=diagnostics.get('reason'),
                         seconds=(end-start).total_seconds() if end else None,
                         evidence=str(path.parent.relative_to(RESULTS)),started_at=d['started_at'],
                         task_checksum=d.get('task_checksum'),agent_result=d.get('agent_result')))
        rows[-1]['decision']=audit.get('decision')
    return sorted(rows,key=lambda x:x['started_at'])


def main():
    primary=records(PRIMARY) if PRIMARY.exists() else []
    all_records=records(RESULTS)
    summary={'generated_at':datetime.now(timezone.utc).isoformat(),'primary':primary,
             'local_and_infrastructure_checks':[r for r in all_records if r['evidence'] not in {x['evidence'] for x in primary}]}
    (RESULTS/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# Observed results','',
           'These records describe this task version only. A verifier control is not a frontier-agent result. Infrastructure errors have no capability score.','',
           '## Primary model attempts','',
           '| Task | Attempt | Model / harness | Score | Main finding | Evidence |',
           '|---|---|---|---|---|---|']
    for i,r in enumerate(primary,1):
        status=r['exception'] if r['invalid'] else r['reason'] or f"{r['decision']}; reproducible audit accepted"
        score='Invalid trial' if r['invalid'] else str(r['score'])
        lines.append(f"| unseen-subject-audit | {i} | {r['model']} / {r['harness']} | {score} | {status} | [Captured trial]({r['evidence']}/result.json) |")
    if not primary: lines.append('| unseen-subject-audit | 1–4 | gpt-6-luna / Codex | Running | Docker fallback authorized after Daytona HTTP 401 | — |')
    valid=[r for r in primary if not r['invalid'] and r['score'] is not None]
    lines+=['',f'Valid completed primary attempts: {len(valid)} of 4.']
    if valid: lines[-1]+=f" Mean single-attempt reward: {sum(r['score'] for r in valid)/len(valid):.3f}."
    if len(valid)==4 and all(r['score']==1 for r in valid):
        lines+=['','All four attempts succeeded and selected inconclusive under their submitted participant-disjoint comparisons. This instance did not expose a genuine capability failure in the allowed smaller model. The observed 4/4 result is not a population-wide reliability estimate. The agent reports and ATIF trajectories are in each captured trial directory.']
    if valid:
        usage={k:sum((r['agent_result'] or {}).get(k,0) or 0 for r in valid)
               for k in ('n_input_tokens','n_cache_tokens','n_output_tokens','cost_usd')}
        lines+=['',f"Harbor records {usage['n_input_tokens']:,} input tokens, including {usage['n_cache_tokens']:,} cached tokens, and {usage['n_output_tokens']:,} output tokens. Its pricing-based cost estimate is USD {usage['cost_usd']:.6f}; provider billing was not independently checked. Total elapsed time per attempt was {min(r['seconds'] for r in valid):.1f}–{max(r['seconds'] for r in valid):.1f} seconds, including setup and verification."]
    lines+=['','Two task checksums appear in the raw records because a host syntax check generated two bytecode-cache files in the oracle-only `tasks/unseen-subject-audit/solution/` directory between trial launches. Moving only those caches restored the first checksum exactly; [provenance.json](provenance.json) records the proof and file hashes. Codex never receives the oracle solution files. Agent-visible files and trusted verifier code were unchanged, and the submission ZIP excludes caches.']
    lines+=['','## Validation and provisioning records','',
            '| Run | Score / status | Seconds | Evidence |','|---|---|---|---|']
    for r in summary['local_and_infrastructure_checks']:
        status=r['exception'] if r['invalid'] else str(r['score'])
        lines.append(f"| {r['evidence'].split('/')[-2]} / {r['harness']} | {status} | {r['seconds']:.1f} | [Trial]({r['evidence']}/result.json) |")
    lines+=['',
      'The initial local oracle returned zero because its Python path omitted `/app`; this was a packaging defect corrected before model execution. Four initial Daytona provisioning records failed before model execution because the PDF text extractor interleaved a label into a wrapped credential. They are retained as infrastructure failures. A geometric table-cell extraction recovered the full key, but a real authenticated list request still returned HTTP 401 Invalid credentials. The earlier SDK preflight was a lazy iterator that made no request; that preflight was corrected. No Daytona sandbox or model execution started. The user authorized Docker fallback for the four final model attempts. No provider secret is part of the task or this package.',
      '', '## Numerical reference and limits','',
      'On the local Linux reference, original subject-macro accuracy was 97.1149% for the baseline and 98.3501% for the candidate. Under the oracle’s person-disjoint folds it was 90.9127% and 90.6786%. The paired mean difference was −0.2342 percentage points, with descriptive 95% bounds [−1.8615, +1.6480] percentage points. The fixed one-point promotion policy therefore returns inconclusive. Retained-baseline private accuracy was 95.4614%; it does not affect reward.',
      '',
      'Host macOS and Linux tree predictions differed at some ties. The agent image now computes its original report at build time, and the reference solution checks exact reproduction. Treat each captured sandbox’s own helper and trusted replay as authoritative for that attempt. Do not copy host-generated metrics into a different runtime.',
      '',
      'Development-only calibration considered standardized LinearSVC with C=0.01 and C=0.001, three-neighbor classification, and 64-tree ExtraTrees. The pair was frozen before model attempts. The practical margin came from the design policy and was not fitted to model failures. The baseline is intentionally modest; the task does not measure discovery of the best classifier.',
      '',
      'The public contract explains metric and decision semantics, so this may be easy for frontier agents. If all four attempts pass, report saturation of this instance and next test budgeted experiment selection with conflicting preliminary evidence. Do not conceal success or change grading after inspecting agent answers. If an attempt fails, inspect its trajectory before calling the cause scientific judgment.',
      '', '## Proposed harder variant (not implemented)','',
      'Give the agent three plausible improvement claims and a budget of three additional experiments. Include one genuine improvement, one invalid evaluation claim, and one noisy seed-selection claim. Provide a documented experiment interface with explicit costs and deployment requirements, while leaving the diagnostic choice to the agent. Require it to allocate its budget before results are revealed, then submit evidence and a decision for each claim. A trusted experiment service must record budget use; agent-authored logs cannot establish which experiments ran.',
      '',
      'This adds experiment selection under limited information to the numerical audit. It needs independently reproducible positive and negative controls and four new attempts under a new task version. Its difficulty and learning value remain hypotheses; it is not part of this OA implementation.',
      '',
      'Alternative valid participant partitions can produce a different policy decision; the corresponding numerical evidence must reproduce. Adaptive fold choice remains a limitation. The bootstrap is conditional on overlapping CV fits and a small participant population. One task and four attempts cannot support a general model ranking, a broad research-capability claim, or RL learning improvement.',
      '', '## Time and costs','',
      'Implementation timing started at 2026-11-06 21:06:36 America/Chicago (2026-11-07 03:06:36 UTC). Job records provide measured setup, agent, and verifier times; work-log.json records the final packaging checkpoint. Earlier research preparation was not timed; combined compliance with the OA’s five-hour limit is not claimed. The token cost above is Harbor’s estimate, not an invoice. No Daytona sandbox was provisioned; Daytona billing was not inspected.',
      '', 'The raw result files, verifier diagnostics, and available trajectories are included. `controls.json` contains the nine semantic/adversarial controls and `unit-tests.txt` contains the captured unit-test output.','']
    (RESULTS/'RESULTS.md').write_text('\n'.join(lines))


if __name__=='__main__': main()
