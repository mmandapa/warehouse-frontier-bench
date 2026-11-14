"""Check saved dispatch decisions independently of the scoring engine."""

from collections import Counter
from pathlib import Path
import json
import sys

from fixtures import cases


def check(spec, record):
    jobs = {job['id']: job for job in spec['carts']}
    roads = {frozenset((a, b)): duration for a, b, duration in spec['lanes']}
    positions = {name: job['start'] for name, job in jobs.items()}
    transit = {}
    picked = set()
    delivered = {}
    notice = spec['notice']
    decisions = record['decisions']
    for tick in range(len(decisions) + 1):
        for name, (_, target, arrival) in list(transit.items()):
            if arrival == tick:
                positions[name] = target
                del transit[name]
        choice = spec['selected'] if tick >= notice['announce_tick'] else None
        events = [] if choice is None else notice['orders'][choice]
        active = [event for event in events if event['start'] <= tick < event['end']]
        closed = {frozenset(event['lane']) for event in active if 'lane' in event}
        paused = {event['bay'] for event in active if 'bay' in event}
        for name, position in positions.items():
            if position in paused:
                continue
            job = jobs[name]
            if name not in picked and position == job['pickup']:
                picked.add(name)
            elif name in picked and position == job['delivery']:
                delivered.setdefault(name, tick)
        expired = [name for name in jobs if name not in delivered and jobs[name]['deadline'] <= tick]
        if len(delivered) == len(jobs) or expired:
            assert tick == len(decisions) == record['tick']
            assert record['success'] == (not expired)
            assert record['reason'] == ('delivery deadline missed' if expired else 'all deliveries on time')
            assert record['missed'] == expired and record['deliveries'] == delivered
            return
        step = decisions[tick]
        view = step['view']
        assert view['tick'] == tick and view['notice'] == notice and view['selected'] == choice
        assert {frozenset(edge) for edge in view['closed']} == closed and set(view['paused']) == paused
        assert {frozenset((a,b)): duration for a,b,duration in view['lanes']} == roads
        for cart in view['carts']:
            name = cart['id']
            stage = 2 if name in delivered else int(name in picked)
            if name in transit:
                origin, target, arrival = transit[name]
                expected = origin, target, arrival - tick, stage
            else:
                expected = positions[name], None, 0, stage
            assert tuple(cart[key] for key in ('at','to','remaining','stage')) == expected
        occupied = set(positions.values())
        reserved = {target for _, target, _ in transit.values()}
        lanes_in_use = {frozenset((origin, target)) for origin, target, _ in transit.values()}
        for name, target in step['moves'].items():
            origin = positions.pop(name)
            edge = frozenset((origin, target))
            assert edge in roads and edge not in closed and edge not in lanes_in_use
            assert target not in occupied and target not in reserved
            transit[name] = origin, target, tick + roads[edge]
            reserved.add(target)
            lanes_in_use.add(edge)
    raise AssertionError('Saved decisions ended before an independently verified outcome')


def main(root):
    specs = dict(cases())
    for job in sorted((root/'harbor').iterdir()):
        path, = job.glob('*/verifier/diagnostics.json')
        report = json.loads(path.read_text())
        assert set(specs) == {row['shift'] for row in report['cases']}
        for record in report['cases']:
            check(specs[record['shift']], record)
        assert sum(r['success'] for r in report['cases']) == report['passed']
        assert report['reward'] == report['passed'] / len(specs)
        for first in [r for r in report['cases'] if r['shift'].endswith('-1')]:
            other = next(r for r in report['cases'] if r['shift'] == first['shift'][:-1] + '2')
            reveal = specs[first['shift']]['notice']['announce_tick']
            assert first['decisions'][:reveal] == other['decisions'][:reveal]
        print(job.name, report['passed'], Counter(r['reason'] for r in report['cases']))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
