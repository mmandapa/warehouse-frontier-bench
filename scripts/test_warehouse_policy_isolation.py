"""Run in a verifier image to check that writable storage resets between cases."""

import os
from pathlib import Path
import subprocess
import sys
from functools import partial

sys.path.insert(0, "/grader")
from policy_fs import enter_policy_filesystem, policy_filesystem


def run_case(check):
    with policy_filesystem() as (work, uid):
        if uid is None:
            raise RuntimeError("run with WAREHOUSE_ISOLATE_CASES=1 inside the verifier")
        subprocess.run(
            ["/usr/local/bin/python3.12", "-B", "-c", check],
            cwd=work,
            env={"LD_LIBRARY_PATH": "/usr/local/lib", "HOME": "/tmp"},
            preexec_fn=partial(enter_policy_filesystem, work, uid),
            check=True,
        )
        return uid


if __name__ == "__main__":
    assert os.geteuid() == 0
    prefix = (
        "from pathlib import Path\n"
        "marker = Path('/tmp/warehouse-preflight')\n"
        "assert not marker.exists()\n"
        "assert not Path('/grader').exists()\n"
        "assert not Path('/app').exists()\n"
        "assert not Path('/proc').exists()\n"
    )
    first = run_case(prefix + "marker.write_text('test data')\n")
    second = run_case(prefix)
    assert first != second
    print("Two cases used distinct identities and private writable storage")
