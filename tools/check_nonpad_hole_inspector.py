#!/usr/bin/env python3
"""Test the two actual-risk J1 non-PAD hole representations; synthetic CAM only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from gerbonara.excellon import ExcellonFile
from gerbonara.rs274x import GerberFile
from check_drill_inspector import fixture
from inspect_gerber import extract_drills
from gerber_nonpad_holes import extract_expected_outline_circles, validate_nonpad_holes


def outline_fixture(holes, half_circle=False):
    commands = ['G04 Synthetic locating-hole parser check*', '%FSLAX46Y46*%', '%MOMM*%',
                '%LPD*%', '%ADD10C,0.010*%', 'D10*', 'G75*']
    for h in holes:
        x, y = h['center_mm']; r = h['diameter_mm']/2
        def xy(x, y):
            return f'X{round(x*1e6):d}Y{round(y*1e6):d}'
        commands += [xy(x+r, y)+'D02*', 'G03'+xy(x-r, y)+f'I{round(-r*1e6):d}J0D01*']
        if not half_circle:
            commands += ['G03'+xy(x+r, y)+f'I{round(r*1e6):d}J0D01*']
    return '\n'.join(commands+['M02*', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expectations', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    expectation = json.loads(args.expectations.read_text())
    holes = [dict(h, shape='ROUND', plated=False) for h in expectation['holes']]
    drills, parse_errors = extract_drills(ExcellonFile.from_string(fixture(holes), filename='j1-npth.drl'))
    assert not parse_errors
    layer = GerberFile.from_string(outline_fixture(holes), filename='j1-cutouts.gko')
    circles, consumed = extract_expected_outline_circles(layer, expectation)
    assert len(circles) == 2 and len(consumed) == 4
    cases = []
    def check(name, d, c, wanted):
        report, permitted_drills = validate_nonpad_holes(d, c, expectation)
        assert report['pass'] == wanted, (name, report)
        cases.append({'name': name, 'expected_pass': wanted, 'observed_pass': report['pass'],
                      'passed_holes': report['passed_holes'], 'allowed_extra_NPTH_drills': len(permitted_drills)})
    check('two_NPTH_drills', drills, [], True)
    check('two_closed_inner_contours', [], circles, True)
    check('drill_and_contour_duplicate_machining', drills, circles, False)
    check('missing_one_locating_hole', drills[:1], [], False)
    small = copy.deepcopy(drills)
    for h in small: h['diameter_mm'] *= .1
    check('cached_diameter_ten_times_too_small', small, [], False)
    plated = copy.deepcopy(drills); plated[0]['plated'] = True
    check('wrong_plated_locating_hole', plated, [], False)
    partial = GerberFile.from_string(outline_fixture(holes, half_circle=True), filename='j1-incomplete.gko')
    partial_circles, _ = extract_expected_outline_circles(partial, expectation)
    check('open_180_degree_contours', [], partial_circles, False)
    # Backtracking the same half-circle has degree2 and total sweep360deg,
    # but does not describe a complete round locating hole.
    double_half = GerberFile.from_string(outline_fixture(holes), filename='j1-backtracked.gko')
    for i, arc in enumerate(double_half.objects):
        if i % 2: arc.clockwise = not arc.clockwise
    double_circles, _ = extract_expected_outline_circles(double_half, expectation)
    check('backtracked_half_circle_not_a_round_hole', [], double_circles, False)
    report = {'pass': True,
              'scope': 'Synthetic Excellon/Gerber parser checks only; no final Calxus CAM acceptance',
              'expectations_sha256': hashlib.sha256(args.expectations.read_bytes()).hexdigest(),
              'parser': 'gerbonara 1.6.3', 'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'pass': True, 'cases': len(cases)}))


if __name__ == '__main__': main()
