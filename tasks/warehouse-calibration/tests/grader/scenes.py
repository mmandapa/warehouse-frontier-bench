"""Private cart parameters and forecast sequences."""

from random import Random
from public.motion import CartParameters


DRIVES = (
    (0, (.12, .19), (.91, .76), (.70, .88), .042),
    (1, (.16, .10), (.72, .93), (.94, .67), -.035),
    (2, (.21, .15), (1.02, .80), (.75, .98), .023),
    (3, (.08, .22), (.83, .99), (.95, .73), -.047),
    (3, (.23, .13), (.69, .84), (.87, .95), .056),
    (2, (.14, .24), (.95, .71), (.79, .89), -.015),
)
SLIPS = ((-.08, .10, -.56, -.14), (.12, -.12, -.18, -.62))


def cases():
    for family, (lag, deadbands, forward, reverse, bias) in enumerate(DRIVES):
        sequences = commands(54819 + 7919 * family)
        for variant, (base_f, base_r, load_f, load_r) in enumerate(SLIPS):
            yield family, variant, CartParameters(
                lag, deadbands, forward, reverse, base_f, base_r, bias, load_f, load_r,
            ), sequences


def commands(seed):
    rng = Random(seed)
    def magnitude():
        return round(rng.uniform(.63, .99), 3)
    forward = [(magnitude(), magnitude()) for _ in range(25)]
    reverse = [(-magnitude(), -magnitude()) for _ in range(27)]
    mixed = [(magnitude(), -magnitude())] * 5 + [(magnitude(), magnitude())] * 8
    mixed += [(-magnitude(), -magnitude())] * 9 + [(magnitude(), -magnitude())] * 6
    pause = [(magnitude(), magnitude() * .60)] * 8 + [(0.0, 0.0)] * 10
    pause += [(magnitude() * .60, magnitude())] * 8
    intermittent = [(0.37, 0.42), (0.91, 0.88), (0.0, 0.0)] * 7
    return forward, reverse, mixed, pause, intermittent
