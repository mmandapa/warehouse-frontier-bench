"""Run the four prespecified attempts with an all-inclusive two-hour job deadline."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['gpt-6-luna','gpt-6-astra','gpt-5.6-luna'], default='gpt-6-luna')
    p.add_argument('--job-name', default='primary-gpt-6-luna')
    p.add_argument('--environment', choices=['daytona','docker'], default='docker')
    p.add_argument('--task', choices=['unseen-subject-audit','ctc-memory-kernel'], default='unseen-subject-audit')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    root=Path(__file__).resolve().parents[1]
    command=[str(Path(sys.executable).with_name('harbor')), 'run',
             '-p',f'tasks/{args.task}','-e',args.environment,'-a','codex','-m',f'openai/{args.model}',
             '--ak','version=0.163.0','--ak','web_search=disabled','--effort','medium',
             '-k','4','-n','2','-r','0','--job-name',args.job_name,'-o','results/models']
    if args.dry_run:
        print(' '.join(command)); return
    if not os.environ.get('OPENAI_API_KEY'):
        raise SystemExit('Set OPENAI_API_KEY in your shell before running paid model trials.')
    if args.environment=='daytona' and not os.environ.get('DAYTONA_API_KEY'):
        raise SystemExit('Set DAYTONA_API_KEY in your shell for the Daytona sandbox backend.')
    env=os.environ.copy()
    # Keep native host login files out of this API-key-only experiment.
    env.pop('CODEX_AUTH_JSON_PATH',None); env.pop('CODEX_FORCE_AUTH_JSON',None)
    child=subprocess.Popen(command,cwd=root,env=env,start_new_session=True)
    try:
        raise SystemExit(child.wait(timeout=7200))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGINT)
        try: child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL); child.wait()
        raise SystemExit('Two-hour job deadline exceeded; inspect Docker for any surviving task containers.')


if __name__=='__main__': main()
