"""Own the simulator state while an external policy chooses actions."""

from __future__ import annotations

from functools import partial
import json
import os
from pathlib import Path
import resource
import select
import shutil
import signal
import subprocess
import sys
import time

from policy_fs import enter_policy_filesystem, policy_filesystem
from session import PolicyError, execute


MAX_MESSAGE = 8192
WALL_LIMIT = 30.0


class Wire:
    def __init__(self, child: subprocess.Popen, deadline: float):
        self.child = child
        self.deadline = deadline
        self.buffer = bytearray()

    def _time_left(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise PolicyError("policy time limit")
        return remaining

    def read(self) -> dict:
        self._time_left()
        fd = self.child.stdout.fileno()
        while b"\n" not in self.buffer:
            if len(self.buffer) >= MAX_MESSAGE:
                raise PolicyError("message too large")
            if not select.select([fd], [], [], self._time_left())[0]:
                raise PolicyError("policy time limit")
            data = os.read(fd, min(4096, MAX_MESSAGE - len(self.buffer)))
            if not data:
                raise PolicyError("policy exited before finish")
            self.buffer.extend(data)
        index = self.buffer.index(b"\n")
        line = bytes(self.buffer[:index])
        del self.buffer[:index + 1]
        try:
            request = json.loads(line)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise PolicyError("invalid JSON") from exc
        if not isinstance(request, dict):
            raise PolicyError("request must be an object")
        return request

    def write(self, message: dict) -> None:
        data = memoryview(json.dumps(message, allow_nan=False).encode() + b"\n")
        fd = self.child.stdin.fileno()
        while data:
            if not select.select([], [fd], [], self._time_left())[1]:
                raise PolicyError("policy time limit")
            try:
                data = data[os.write(fd, data[:4096]):]
            except BlockingIOError:
                continue


def limits() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024,) * 2)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    except (ValueError, OSError):
        pass


def isolated_limits(work: Path, uid: int) -> None:
    enter_policy_filesystem(work, uid)
    limits()




def run_policy(policy: Path, public_library: Path, session) -> dict:
    if policy.is_symlink() or not policy.is_file() or policy.stat().st_size > 1_048_576:
        return {"success": False, "reason": "missing or invalid policy", "tests": [], "spent": 0}
    with policy_filesystem() as (work, uid):
        isolated = uid is not None
        shutil.copyfile(policy, work / "policy.py")
        shutil.copyfile(public_library / "client.py", work / "client.py")
        identity = {}
        if not isolated and os.geteuid() == 0:
            identity = {"user": 1001, "group": 1001, "extra_groups": []}
        executable = "/usr/local/bin/python3.12" if isolated else sys.executable
        policy_path = "/policy.py" if isolated else str(work / "policy.py")
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp" if isolated else str(work),
            "PYTHONNOUSERSITE": "1",
        }
        if isolated:
            env["LD_LIBRARY_PATH"] = "/usr/local/lib"
        setup = partial(isolated_limits, work, uid) if uid is not None else limits
        with subprocess.Popen(
            [executable, "-B", policy_path], cwd=work, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, preexec_fn=setup, **identity,
        ) as child:
            os.set_blocking(child.stdin.fileno(), False)
            try:
                return execute(Wire(child, time.monotonic() + WALL_LIMIT), session)
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    if child.poll() is None:
                        raise
