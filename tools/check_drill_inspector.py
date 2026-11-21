#!/usr/bin/env python3
"""Exercise the real Excellon parser against known r7 drill-export failure modes.

Synthetic software checks only. They are not Calxus fabrication-file validation.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from gerbonara.excellon import ExcellonFile
from inspect_gerber import extract_drills, validate_tht_drills


def fixture(holes, routed=False, translation=(0, 0)):
    lines = ['M48', 'METRIC,LZ', 'G90']
    for i, hole in enumerate(holes, 1):
        diameter = hole.get('diameter_mm', hole.get('slot_tool_diameter_mm'))
        lines += [';TYPE=PLATED' if hole['plated'] else ';TYPE=NON_PLATED', f'T{i:02d}C{diameter:.8f}']
    lines += ['%']
    for i, h in enumerate(holes, 1):
        lines += [f'T{i:02d}']
        if h['shape'] == 'ROUND':
            x, y = [h['center_mm'][k]+translation[k] for k in (0, 1)]
            lines += [f'X{x:.8f}Y{y:.8f}']
        else:
            (ax, ay), (bx, by) = [[p[k]+translation[k] for k in (0, 1)] for p in h['slot_end_centers_mm']]
            if routed:
                lines += [f'G00X{ax:.8f}Y{ay:.8f}', 'M15', f'G01X{bx:.8f}Y{by:.8f}', 'M16', 'G05']
            else:
                lines += [f'X{ax:.8f}Y{ay:.8f}G85X{bx:.8f}Y{by:.8f}']
    return '\n'.join(lines+['M30', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expectations', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.expectations.read_text())
    cases = []

    def check(name, holes, should_pass, routed=False, translation=(0, 0), offset=(0, 0)):
        actual_file = ExcellonFile.from_string(fixture(holes, routed, translation), filename=name+'.drl')
        records, parse_errors = extract_drills(actual_file, origin_offset=offset)
        result = validate_tht_drills(records, expected)
        actual_pass = result['pass'] and not parse_errors
        assert actual_pass == should_pass, (name, result['errors'], parse_errors)
        cases.append({'name': name, 'expected_pass': should_pass, 'observed_pass': actual_pass,
                      'parsed_drills': len(records), 'holes_passing': result['passed_holes'],
                      'errors_detected': len(result['errors'])+len(parse_errors)})

    base = expected['holes']
    check('complete_56_holes_G85', base, True)
    check('complete_56_holes_G00_G01_router', base, True, routed=True)
    shrink = copy.deepcopy(base)
    for h in shrink:
        if h['shape'] == 'ROUND':
            h['diameter_mm'] *= .1
        else:
            h['slot_tool_diameter_mm'] *= .1
            h['slot_end_centers_mm'] = [[h['center_mm'][i]+.1*(p[i]-h['center_mm'][i]) for i in (0, 1)]
                                         for p in h['slot_end_centers_mm']]
    check('cached_holes_ten_times_too_small', shrink, False)
    wrong_axis = copy.deepcopy(base)
    for h in wrong_axis:
        if h['ref'] == 'J2' and h['shape'] == 'SLOT':
            cx, cy = h['center_mm']
            h['slot_end_centers_mm'] = [[cx+(p[1]-cy), cy-(p[0]-cx)] for p in h['slot_end_centers_mm']]
    check('J2_slots_wrong_90_degree_rotation', wrong_axis, False)
    check('missing_J2_shield6', [h for h in base if (h['ref'], h['pin']) != ('J2', '6')], False)
    check('duplicate_actual_drill', base+[copy.deepcopy(base[4])], False)
    wrong_plating = copy.deepcopy(base)
    next(h for h in wrong_plating if h['ref'] == 'J2' and h['pin'] == '1')['plated'] = False
    check('J2_signal_wrong_plating', wrong_plating, False)
    check('unexplained_origin_translation', base, False, translation=(10, -5))
    check('explicit_origin_translation', base, True, translation=(10, -5), offset=(-10, 5))
    report = {'pass': True, 'scope': 'Synthetic Excellon software regression only; no final Gerber has been validated by this report',
              'expectations_sha256': hashlib.sha256(args.expectations.read_bytes()).hexdigest(),
              'parser': 'gerbonara 1.6.3', 'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
