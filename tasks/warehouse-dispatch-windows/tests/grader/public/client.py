"""Send one batch of dispatch commands per observed tick."""

import json


class Dispatch:
    def observe(self):
        return json.loads(input())

    def step(self, moves):
        print(json.dumps({'moves': moves}), flush=True)
