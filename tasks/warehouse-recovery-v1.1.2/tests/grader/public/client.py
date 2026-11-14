"""Public JSON stream client for a warehouse cart policy."""

from dataclasses import fields
import json
import sys

from .world import Layout, Observation, Pose, Rect, Tag, TagReading


class CartClient:
    def __init__(self):
        initial = json.loads(sys.stdin.readline())
        layout = initial["layout"]
        self.layout = Layout(
            tuple(Rect(**entry) for entry in layout["aisles"]),
            tuple(Rect(**entry) for entry in layout["shelves"]),
            tuple(Tag(**entry) for entry in layout["tags"]),
            tuple(Pose(**entry) for entry in layout["starts"]),
            Pose(**layout["dock"]),
            layout["left_junction_x"], layout["right_junction_x"],
        )
        self.tick_limit = initial["tick_limit"]

    def _call(self, request):
        print(json.dumps(request, allow_nan=False), flush=True)
        response = json.loads(sys.stdin.readline())
        if "error" in response:
            raise RuntimeError(response["error"])
        return response

    def command(self, left: float, right: float, ticks: int = 1) -> None:
        self._call({"op": "drive", "left": left, "right": right, "ticks": ticks})

    def observe(self, *, expose: bool = False) -> Observation:
        response = self._call({"op": "sense", "expose": expose})
        response["lidar_m"] = tuple(response["lidar_m"])
        response["tags"] = tuple(TagReading(**entry) for entry in response["tags"])
        return Observation(**{field.name: response[field.name] for field in fields(Observation)})

    def finish(self) -> None:
        self._call({"op": "finish"})
