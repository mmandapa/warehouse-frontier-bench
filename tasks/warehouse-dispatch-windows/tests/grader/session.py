"""Tick simulation for a shift. Private events are applied at their start tick."""


class PolicyError(RuntimeError):
    pass


def lane(a, b):
    return tuple(sorted((a, b)))


def snapshot(spec, tick, states):
    notice = spec.get('notice')
    selected = spec['selected'] if notice and tick >= notice['announce_tick'] else None
    events = spec.get('incidents', [])
    if selected is not None:
        events = [*events, *notice['orders'][selected]]
    active = [event for event in events if event['start'] <= tick < event['end']]
    closed = sorted({lane(*e['lane']) for e in active if 'lane' in e})
    paused = sorted({e['bay'] for e in active if 'bay' in e})
    return {
        'tick': tick, 'lanes': spec['lanes'], 'closed': closed, 'paused': paused,
        'notice': notice, 'selected': selected,
        'carts': [{**cart, 'at': at, 'to': dest, 'remaining': left, 'stage': stage}
                  for cart, (at, dest, left, stage) in zip(spec['carts'], states, strict=True)],
    }


def service(spec, states, paused):
    updated = []
    for cart, (at, dest, left, stage) in zip(spec['carts'], states, strict=True):
        if dest is None and at not in paused:
            if stage == 0 and at == cart['pickup']:
                stage = 1
            elif stage == 1 and at == cart['delivery']:
                stage = 2
        updated.append((at, dest, left, stage))
    return tuple(updated)


def advance(states, moves, durations, closed):
    occupied = {at for at, dest, _, _ in states if dest is None}
    reserved = {dest for _, dest, _, _ in states if dest is not None}
    busy = {lane(at, dest) for at, dest, _, _ in states if dest is not None}
    started = list(states)
    for index, target in moves.items():
        at, dest, _, stage = states[index]
        edge = lane(at, target)
        if dest is not None:
            raise PolicyError('move issued to a cart in transit')
        if edge not in durations:
            raise PolicyError('move is not an adjacent lane')
        if edge in closed:
            raise PolicyError('move starts on a closed lane')
        if target in occupied:
            raise PolicyError('target is occupied at the start of the tick')
        if target in reserved:
            raise PolicyError('destination already reserved')
        if edge in busy:
            raise PolicyError('lane already reserved')
        reserved.add(target)
        busy.add(edge)
        started[index] = at, target, durations[edge], stage
    next_states = []
    for at, dest, left, stage in started:
        if dest is None:
            next_states.append((at, None, 0, stage))
        elif left == 1:
            next_states.append((dest, None, 0, stage))
        else:
            next_states.append((at, dest, left - 1, stage))
    return tuple(next_states)


def notify(wire, reason, **details):
    try:
        wire.write({'result': reason, **details})
    except (BrokenPipeError, PolicyError):
        # The last command has already determined the outcome.
        pass


def execute(wire, spec):
    carts = spec['carts']
    indices = {cart['id']: i for i, cart in enumerate(carts)}
    durations = {lane(a, b): ticks for a, b, ticks in spec['lanes']}
    states = tuple((cart['start'], None, 0, 0) for cart in carts)
    deliveries = {}
    decisions = []
    tick = 0
    reason = 'dispatcher stopped'
    success = False
    missed = []
    try:
        for tick in range(max(cart['deadline'] for cart in carts) + 1):
            view = snapshot(spec, tick, states)
            states = service(spec, states, set(view['paused']))
            view = snapshot(spec, tick, states)
            for cart in view['carts']:
                if cart['stage'] == 2:
                    deliveries.setdefault(cart['id'], tick)
            if len(deliveries) == len(carts):
                success, reason = True, 'all deliveries on time'
                notify(wire, reason)
                break
            missed = [cart['id'] for cart in view['carts'] if cart['stage'] != 2 and cart['deadline'] <= tick]
            if missed:
                reason = 'delivery deadline missed'
                notify(wire, reason, missed=missed)
                break
            wire.write(view)
            request = wire.read()
            moves = request.get('moves')
            if not isinstance(moves, dict) or not all(k in indices and isinstance(v, str) for k, v in moves.items()):
                raise PolicyError('moves must map cart IDs to adjacent node names')
            decisions.append({'view': view, 'moves': moves})
            states = advance(states, {indices[k]: v for k, v in moves.items()}, durations,
                             {lane(*edge) for edge in view['closed']})
    except (PolicyError, BrokenPipeError) as exc:
        reason = str(exc)
    return {'success': success, 'reason': reason, 'tick': tick, 'deliveries': deliveries,
            'missed': missed, 'decisions': decisions}
