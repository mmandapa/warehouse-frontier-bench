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
SLIPS = ((-.25, .10), (.14, -.28))


def cases():
    for family, (lag, deadbands, forward, reverse, bias) in enumerate(DRIVES):
        sequences = commands(54819 + 7919 * family)
        for variant, slip in enumerate(SLIPS):
            yield family, variant, CartParameters(lag, deadbands, forward, reverse, *slip, bias), sequences


def commands(seed):
    rng = Random(seed)
    def magnitude():
        return round(rng.uniform(.63, .99), 3)
    forward = [(magnitude(), magnitude()) for _ in range(17)]
    reverse = [(-magnitude(), -magnitude()) for _ in range(19)]
    mixed = [(magnitude(), -magnitude())] * 5 + [(magnitude(), magnitude())] * 8
    mixed += [(-magnitude(), -magnitude())] * 9 + [(magnitude(), -magnitude())] * 6
    switchback = [(magnitude(), magnitude() * .30)] * 8 + [(-magnitude() * .30, -magnitude())] * 8
    switchback += [(magnitude(), -magnitude())] * 5 + [(0.0, 0.0)] * 3
    short = [(0.37, 0.42), (0.43, 0.36), (0.0, 0.0)] * 4
    return forward, reverse, mixed, switchback, short
