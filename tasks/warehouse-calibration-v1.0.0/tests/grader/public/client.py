"""Public interface to a single maintenance-bay session."""

import json
import sys


class BayClient:
    def __init__(self):
        hello = json.loads(sys.stdin.readline())
        self.tick_limit = hello["tick_limit"]

    @staticmethod
    def _request(op, **payload):
        print(json.dumps({"op": op, **payload}, allow_nan=False), flush=True)
        return json.loads(sys.stdin.readline())

    def drive(self, left, right):
        return self._request("drive", left=left, right=right)

    def camera(self):
        return self._request("camera")["pose"]

    def forecast_commands(self):
        return self._request("forecast")["sequences"]

    def submit(self, poses):
        self._request("submit", poses=poses)
