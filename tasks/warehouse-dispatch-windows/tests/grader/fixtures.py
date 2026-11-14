"""Pair each layout with both maintenance orders under a shared visible prefix."""


def cart(name, start, pickup, delivery, deadline):
    return {'id': name, 'start': start, 'pickup': pickup, 'delivery': delivery, 'deadline': deadline}


def lane_event(a, b, start, end):
    return {'lane': [a, b], 'start': start, 'end': end}


def bay_event(bay, start, end):
    return {'bay': bay, 'start': start, 'end': end}


def paired(name, lanes, carts, announce, first_order, second_order):
    notice = {'announce_tick': announce, 'orders': [first_order, second_order]}
    for selected in (0, 1):
        yield f'{name}-{selected + 1}', {'lanes': lanes, 'carts': carts,
                                        'notice': notice, 'selected': selected}


def cases():
    fork = [('S', 'A', 3), ('S', 'B', 3), ('A', 'D', 1), ('B', 'D', 1),
            ('D', 'L', 1), ('D', 'R', 1), ('S', 'P', 1)]
    yield from paired('fork', fork, [cart('line', 'S', 'S', 'L', 6),
                                     cart('exit', 'D', 'D', 'R', 3),
                                     cart('empty', 'P', 'P', 'S', 5)], 1,
                      [lane_event('B', 'D', 1, 8)], [lane_event('A', 'D', 1, 8)])

    pullout = [('W', 'J', 1), ('J', 'E', 2), ('J', 'P', 1), ('E', 'O', 1), ('W', 'S', 1)]
    yield from paired('pullout', pullout, [cart('load', 'W', 'W', 'O', 9),
                                           cart('return', 'E', 'E', 'S', 9)], 3,
                      [lane_event('J', 'E', 3, 6)], [lane_event('J', 'P', 3, 5)])

    crossing = [('N', 'X', 2), ('S', 'X', 2), ('X', 'W', 2), ('X', 'E', 2), ('W', 'P', 1), ('E', 'Q', 1)]
    yield from paired('crossing', crossing, [cart('a', 'N', 'N', 'Q', 10),
                                             cart('b', 'S', 'S', 'P', 10)], 2,
                      [lane_event('S', 'X', 4, 8), bay_event('P', 2, 6)],
                      [lane_event('N', 'X', 2, 6)])

    bypass = [('A', 'B', 1), ('B', 'C', 2), ('C', 'D', 1), ('D', 'E', 1),
              ('A', 'F', 2), ('F', 'G', 1), ('G', 'E', 2), ('B', 'H', 1), ('D', 'I', 1)]
    yield from paired('bypass', bypass, [cart('x', 'A', 'A', 'I', 8), cart('y', 'E', 'E', 'H', 9),
                                         cart('z', 'F', 'G', 'D', 8)], 3,
                      [lane_event('B', 'C', 3, 8), bay_event('E', 3, 7)],
                      [lane_event('D', 'I', 3, 6)])

    grid = [('A', 'B', 1), ('B', 'C', 2), ('C', 'D', 1), ('D', 'E', 2),
            ('A', 'F', 2), ('B', 'G', 1), ('C', 'H', 1), ('D', 'I', 1), ('E', 'J', 2),
            ('F', 'G', 1), ('G', 'H', 2), ('H', 'I', 1), ('I', 'J', 1), ('H', 'K', 1)]
    yield from paired('grid', grid, [cart('north', 'A', 'F', 'J', 11), cart('south', 'J', 'E', 'C', 10),
                                     cart('east', 'D', 'I', 'F', 11), cart('west', 'G', 'G', 'K', 9)], 1,
                      [lane_event('G', 'H', 1, 4), bay_event('I', 1, 4)],
                      [lane_event('H', 'I', 1, 4), bay_event('E', 1, 3)])
