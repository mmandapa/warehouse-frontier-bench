"""Give each Linux verifier case its own policy filesystem."""

from contextlib import contextmanager
from itertools import count
import os
from pathlib import Path
import shutil
import sys
import tempfile


RUNTIME = Path("/opt/warehouse-python")
CASES = Path("/opt/warehouse-cases")
CASE_UIDS = count(10001)


@contextmanager
def policy_filesystem():
    isolated = os.environ.get("WAREHOUSE_ISOLATE_CASES") == "1"
    if isolated and (sys.platform != "linux" or os.geteuid() != 0 or not RUNTIME.is_dir()):
        raise RuntimeError("isolated policy cases require the Linux verifier image")
    with tempfile.TemporaryDirectory(prefix="warehouse-policy-", dir=CASES if isolated else None) as directory:
        work = Path(directory)
        # The runtime is immutable to the policy. Linking it avoids copying Python for each case.
        uid = next(CASE_UIDS) if isolated else None
        if uid is not None:
            shutil.copytree(RUNTIME, work, symlinks=True, copy_function=os.link, dirs_exist_ok=True)
            scratch = work / "tmp"
            scratch.mkdir(mode=0o700)
            os.chown(scratch, uid, uid)
        work.chmod(0o755)
        yield work, uid


def enter_policy_filesystem(work, uid):
    os.chroot(work)
    os.chdir("/")
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
