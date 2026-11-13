"""Own the simulator state while an external policy chooses actions."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import resource
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from .world import Cart, Layout, wrap


MAX_MESSAGE = 8192
MAX_REQUESTS = 5000
WALL_LIMIT = 12.0


class PolicyError(RuntimeError):
    pass


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
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024,) * 2)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    except (ValueError, OSError):
        pass


def execute(wire: Wire, cart: Cart, layout: Layout) -> dict:
    evidence = []
    reason = "request limit"
    try:
        wire.write({"layout": asdict(layout), "tick_limit": cart.tick_limit})
        for _ in range(MAX_REQUESTS):
            request = wire.read()
            op = request.get("op")
            if op == "sense":
                expose = request.get("expose", False)
                if type(expose) is not bool:
                    raise PolicyError("expose must be a boolean")
                observation = cart.observe(expose=expose)
                if expose and len(evidence) < 128:
                    evidence.append({"tick": cart.tick, "tags": [tag.name for tag in observation.tags]})
                wire.write(asdict(observation))
            elif op == "drive":
                left, right, ticks = request.get("left"), request.get("right"), request.get("ticks", 1)
                if (not all(type(x) in (float, int) and math.isfinite(x) and abs(x) <= 1 for x in (left, right))
                        or type(ticks) is not int or not 1 <= ticks <= 10):
                    raise PolicyError("invalid wheel speed or command duration")
                for _ in range(ticks):
                    cart.advance(left, right)
                    if cart.collided or cart.tick >= cart.tick_limit:
                        break
                if cart.collided:
                    reason = "collision"
                    break
                if cart.tick >= cart.tick_limit:
                    reason = "motion limit"
                    break
                wire.write({})
            elif op == "finish":
                wire.write({})
                reason = "docked" if cart.docked() else "incorrect final pose or cart still moving"
                break
            else:
                raise PolicyError("unknown operation")
    except (PolicyError, BrokenPipeError, OverflowError) as exc:
        reason = str(exc)
    return {
        "success": reason == "docked", "reason": reason, "ticks": cart.tick, "collision": cart.collided,
        "position_error_m": round(math.hypot(cart.pose.x - layout.dock.x, cart.pose.y - layout.dock.y), 5),
        "heading_error_rad": round(abs(wrap(cart.pose.heading - layout.dock.heading)), 5),
        "exposures": evidence,
    }


def run_policy(policy: Path, public_library: Path, cart: Cart, layout: Layout) -> dict:
    if policy.is_symlink() or not policy.is_file() or policy.stat().st_size > 1_048_576:
        return {"success": False, "reason": "missing or invalid policy", "ticks": 0, "collision": False}
    with tempfile.TemporaryDirectory(prefix="warehouse-policy-") as directory:
        work = Path(directory)
        work.chmod(0o755)
        shutil.copyfile(policy, work / "policy.py")
        shutil.copytree(public_library, work / "warehouse_sim")
        identity = {"user": 1001, "group": 1001, "extra_groups": []} if os.geteuid() == 0 else {}
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(work), "PYTHONNOUSERSITE": "1"}
        with subprocess.Popen(
            [sys.executable, "-B", str(work / "policy.py")], cwd=work, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, preexec_fn=limits, **identity,
        ) as child:
            os.set_blocking(child.stdin.fileno(), False)
            try:
                return execute(Wire(child, time.monotonic() + WALL_LIMIT), cart, layout)
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
