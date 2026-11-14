"""Own the simulator state while an external policy chooses actions."""

from __future__ import annotations

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

from motion import Bay, forecast, wrap


MAX_MESSAGE = 8192
TICK_LIMIT = 30
CAMERA_LIMIT = 2
MAX_REQUESTS = TICK_LIMIT + CAMERA_LIMIT + 2
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
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024,) * 2)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    except (ValueError, OSError):
        pass


POSITION_TOLERANCE_M = 0.045
HEADING_TOLERANCE_RAD = 0.025


def number(value, bound):
    return type(value) in (int, float) and -bound <= value <= bound


def evaluate(poses, settings, sequences):
    if not isinstance(poses, list) or len(poses) != len(sequences):
        raise PolicyError("submit one pose per sequence")
    records = []
    for guess, commands in zip(poses, sequences):
        if not isinstance(guess, list) or len(guess) != 3 or not all(number(v, 1000) for v in guess):
            raise PolicyError("each pose must contain three finite numbers between -1000 and 1000")
        expected = forecast(settings, commands)
        position = math.hypot(guess[0] - expected[0], guess[1] - expected[1])
        heading = abs(wrap(guess[2] - expected[2]))
        records.append({
            "success": position <= POSITION_TOLERANCE_M and heading <= HEADING_TOLERANCE_RAD,
            "position_error_m": round(position, 8),
            "heading_error_rad": round(heading, 8),
        })
    return records


def execute(wire, settings, sequences):
    bay = Bay(settings)
    camera_readings = 0
    forecasts_sent = False
    records = []
    reason = "request limit"
    try:
        wire.write({"tick_limit": TICK_LIMIT})
        for _ in range(MAX_REQUESTS):
            request = wire.read()
            op = request.get("op")
            if op == "drive":
                left, right = request.get("left"), request.get("right")
                if forecasts_sent or bay.tick >= TICK_LIMIT or not all(number(v, 1) for v in (left, right)):
                    raise PolicyError("invalid calibration command or tick budget exceeded")
                wire.write(bay.advance(left, right))
            elif op == "camera":
                if camera_readings >= CAMERA_LIMIT or forecasts_sent:
                    raise PolicyError("camera budget exceeded or calibration already ended")
                camera_readings += 1
                x, y, heading = bay.pose
                wire.write({"pose": [round(x, 3), round(y, 3), round(heading, 6)]})
            elif op == "forecast":
                if forecasts_sent:
                    raise PolicyError("forecast commands can be requested once")
                forecasts_sent = True
                wire.write({"sequences": sequences})
            elif op == "submit":
                if not forecasts_sent:
                    raise PolicyError("request forecast commands before submitting")
                records = evaluate(request.get("poses"), settings, sequences)
                reason = "submitted"
                wire.write({})
                break
            else:
                raise PolicyError("unknown operation")
    except (PolicyError, BrokenPipeError, OverflowError) as exc:
        reason = str(exc)
    return {
        "passed": sum(r["success"] for r in records),
        "reason": reason,
        "ticks": bay.tick,
        "camera_used": camera_readings > 0,
        "camera_readings": camera_readings,
        "forecasts": records,
    }

def run_policy(policy: Path, public_library: Path, settings, sequences) -> dict:
    if policy.is_symlink() or not policy.is_file() or policy.stat().st_size > 1_048_576:
        return {"passed": 0, "reason": "missing or invalid policy", "ticks": 0, "camera_used": False, "camera_readings": 0, "forecasts": []}
    with tempfile.TemporaryDirectory(prefix="warehouse-policy-") as directory:
        work = Path(directory)
        work.chmod(0o755)
        shutil.copyfile(policy, work / "policy.py")
        for name in ("client.py", "motion.py"):
            shutil.copyfile(public_library / name, work / name)
        identity = {"user": 1001, "group": 1001, "extra_groups": []} if os.geteuid() == 0 else {}
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(work), "PYTHONNOUSERSITE": "1"}
        with subprocess.Popen(
            [sys.executable, "-B", str(work / "policy.py")], cwd=work, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, preexec_fn=limits, **identity,
        ) as child:
            os.set_blocking(child.stdin.fileno(), False)
            try:
                return execute(Wire(child, time.monotonic() + WALL_LIMIT), settings, sequences)
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
