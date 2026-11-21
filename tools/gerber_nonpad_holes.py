"""Recognize the two native non-PAD J1 holes in drill or inner-outline CAM."""
import collections
import math
from gerbonara.graphic_objects import Arc, Flash
from gerbonara.graphic_primitives import Circle
from gerbonara.utils import MM


def extract_expected_outline_circles(layer, expectation, origin_offset=(0, 0)):
    """Read filled-circle flashes or complete circular arc contours only.

    Groups must close once through 360 degrees. Unknown outline types are left
    to the strict outer-outline checker; no circle is inferred from a bbox.
    """
    result, consumed = [], set()
    if layer is None:
        return result, consumed
    for h in expectation['holes']:
        arcs, flashes = [], []
        for i, raw in enumerate(layer.objects):
            o = raw.converted(MM)
            if not o.polarity_dark:
                continue
            if isinstance(o, Arc):
                center = [o.center[k]+origin_offset[k] for k in (0, 1)]
                if math.dist(center, h['center_mm']) <= .025:
                    arcs.append((i, o, center))
            elif isinstance(o, Flash):
                primitives = list(o.to_primitives(unit=MM))
                if len(primitives) == 1 and isinstance(primitives[0], Circle):
                    p = primitives[0]; center = [p.x+origin_offset[0], p.y+origin_offset[1]]
                    if math.dist(center, h['center_mm']) <= .025:
                        flashes.append({'id': f'outline:{i}', 'representation': 'filled-circle outline feature',
                                        'center_mm': center, 'diameter_mm': 2*p.r,
                                        'shape': 'ROUND', 'plated': False, 'source_indices': [i]})
                        consumed.add(i)
        result.extend(flashes)
        if arcs:
            centers = [c for _, _, c in arcs]
            radii = [math.dist(o.p1, o.center) for _, o, _ in arcs]
            degrees = collections.Counter()
            for _, o, _ in arcs:
                degrees[tuple(round(x, 5) for x in o.p1)] += 1
                degrees[tuple(round(x, 5) for x in o.p2)] += 1
            sweep = sum(o.sweep_angle() for _, o, _ in arcs)
            # Endpoint degree and summed absolute sweep alone also accept an
            # upper semicircle traced out and back. Require full angular union.
            intervals = []
            tau = 2*math.pi
            for _, o, _ in arcs:
                start = math.atan2(o.p1[1]-o.center[1], o.p1[0]-o.center[0])
                size = o.sweep_angle()
                lower = (start-size if o.clockwise else start) % tau
                if lower+size <= tau:
                    intervals.append((lower, lower+size))
                else:
                    intervals.extend(((lower, tau), (0, lower+size-tau)))
            covered, cursor = 0.0, 0.0
            for low, high in sorted(intervals):
                if high > cursor:
                    covered += high-max(low, cursor)
                    cursor = high
            closed_once = (all(v == 2 for v in degrees.values())
                           and abs(sweep-2*math.pi) < 1e-4
                           and abs(covered-2*math.pi) < 1e-4
                           and max(math.dist(centers[0], c) for c in centers) <= .0001
                           and max(radii)-min(radii) <= .0001)
            item = {'id': 'outline:'+','.join(str(i) for i, _, _ in arcs),
                    'representation': 'circular outline arc contour', 'center_mm': centers[0],
                    'diameter_mm': 2*sum(radii)/len(radii), 'shape': 'ROUND', 'plated': False,
                    'source_indices': [i for i, _, _ in arcs], 'closed_once': closed_once,
                    'sweep_degrees': math.degrees(sweep),
                    'angular_union_degrees': math.degrees(covered)}
            result.append(item); consumed.update(item['source_indices'])
    return result, consumed


def validate_nonpad_holes(drills, circles, expectation, position_tolerance=.025, dimension_tolerance=.025):
    if expectation.get('units') != 'mm' or expectation.get('expected_count') != 2 or len(expectation.get('holes', [])) != 2:
        raise ValueError('Exactly two source-derived J1 non-PAD holes are required')
    results, errors, allowed_drill_ids = [], [], set()
    for h in expectation['holes']:
        actual = [r for r in drills+circles if math.dist(r['center_mm'], h['center_mm']) <= position_tolerance]
        row = {'ref': h['ref'], 'source_id': h['source_id'], 'expected': h,
               'machining_representation_count': len(actual), 'failures': [], 'pass': False}
        if len(actual) != 1:
            row['failures'].append(f'Expected one machining representation, found {len(actual)} (missing or duplicate drill/outline)')
        else:
            r = actual[0]; row['actual'] = r
            row['center_error_mm'] = math.dist(r['center_mm'], h['center_mm'])
            row['diameter_error_mm'] = abs(r['diameter_mm']-h['diameter_mm'])
            if r['plated'] is not False or r['shape'] != 'ROUND':
                row['failures'].append('Locating hole must be round and nonplated')
            if row['diameter_error_mm'] > dimension_tolerance:
                row['failures'].append('Diameter differs from saved source')
            if r.get('closed_once') is False:
                row['failures'].append('Circular outline is not exactly one closed 360-degree contour')
        row['pass'] = not row['failures']
        if row['pass'] and 'representation' not in row['actual']:
            allowed_drill_ids.add(row['actual']['id'])
        if not row['pass']:
            errors.append(h['ref']+':'+h['source_id']+': '+'; '.join(row['failures']))
        results.append(row)
    return {'pass': not errors, 'expected_count': 2, 'passed_holes': sum(r['pass'] for r in results),
            'scope': 'Two independently confirmed J1 locating holes encoded as non-PAD native FILL; separate from the 56 PAD-defined holes',
            'checks': results, 'errors': errors}, allowed_drill_ids
