#!/usr/bin/env python3
"""Check the actual Gerber parser/geometry treatment of the tenting risk.

Synthetic fixtures only: this report is not a final Calxus Gerber inspection.
"""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from gerbonara.rs274x import GerberFile
from shapely.geometry import Point
from gerber_mask_geometry import mask_opening_geometry, validate_tented_vias
from inspect_gerber import validate_all_via_drills


def gerber(body):
    return '\n'.join(['G04 Synthetic mask validation fixture*', '%FSLAX46Y46*%', '%MOMM*%',
                       '%ADD10C,0.5*%', '%ADD11C,0.8X0.4*%', '%ADD12C,0.3*%',
                       '%LPD*%', 'D10*', *body, 'M02*', ''])


def flash(x, y):
    return f'X{round(x*1e6):d}Y{round(y*1e6):d}D03*'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    vias = [{'primitiveId': f'fixture-{i}', 'center_mm': [10+i*2, 10],
             'hole_diameter_mm': .2, 'outer_diameter_mm': .5} for i in range(128)]
    expected = {'units': 'mm', 'expected_count': 128, 'source_archive_sha256': 'synthetic', 'vias': vias}
    drills = [{'id': v['primitiveId'], 'center_mm': v['center_mm'], 'diameter_mm': .2,
               'plated': True, 'shape': 'ROUND'} for v in vias]
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        def resolve(name, body):
            path = Path(tmp)/(name+'.gts'); path.write_text(gerber(body))
            return mask_opening_geometry(GerberFile.open(path))[0]

        openings = resolve('bridge-100706um', [flash(v['center_mm'][0]+.450706, 10) for v in vias])
        base_masks = {'top': openings, 'bottom': openings}
        result = validate_tented_vias(drills, expected, base_masks)
        assert result['pass'], result['errors']
        cases.append({'name': 'all_128_tented_both_sides_at_0p100706mm_nominal_bridge',
                      'pass': True, 'conservative_min_mm': result['minimum_observed_conservative_gap_mm']})
        exposed = resolve('one-exposed', [flash(v['center_mm'][0]+.450706, 10) for v in vias]+[flash(10, 10)])
        result = validate_tented_vias(drills, expected, {'top': openings, 'bottom': exposed})
        assert not result['pass'] and result['passed_vias'] == 127
        cases.append({'name': 'one_bottom_mask_opening_rejected', 'pass': True, 'failed_vias': 1})
        too_near = resolve('bridge-too-small', [flash(v['center_mm'][0]+.450706, 10) for v in vias]+[flash(10.44999, 10)])
        result = validate_tented_vias(drills, expected, {'top': too_near, 'bottom': openings})
        assert not result['pass'] and result['passed_vias'] == 127
        cases.append({'name': '0p09999mm_bridge_rejected_without_threshold_relaxation', 'pass': True})
        # Local aperture holes must not erase a previously exposed island.
        aperture_hole = resolve('aperture-hole', ['D12*', flash(10, 10), 'D11*', flash(10, 10)])
        assert aperture_hole.covers(Point(10, 10))
        clear_layer = resolve('layer-clear', [flash(10, 10), '%LPC*%', 'D12*', flash(10, 10)])
        assert not clear_layer.covers(Point(10, 10))
        cases.append({'name': 'aperture_local_hole_and_layer_clear_have_distinct_boolean_semantics', 'pass': True})
        invalid = Path(tmp)/'negative.gts'; invalid.write_text(gerber(['%IPNEG*%', flash(10, 10)]))
        try:
            mask_opening_geometry(GerberFile.open(invalid))
        except ValueError:
            pass
        else:
            raise AssertionError('Negative-image mask must not be silently accepted')
        cases.append({'name': 'negative_image_mask_refused', 'pass': True})
    assert validate_all_via_drills(drills, expected, [])['pass']
    shrunk = copy.deepcopy(drills); shrunk[0]['diameter_mm'] *= .1
    result = validate_all_via_drills(shrunk, expected, [])
    assert not result['pass'] and result['passed_vias'] == 127
    extra = drills+[{'id': 'unexplained-extra-via', 'center_mm': [5, 5], 'diameter_mm': .2,
                     'plated': True, 'shape': 'ROUND'}]
    result = validate_all_via_drills(extra, expected, [])
    assert not result['pass'] and len(result['unexplained_actual_drills']) == 1
    cases.append({'name': 'complete_via_population_checked_with_shrunken_and_extra_drill_rejected', 'pass': True})
    report = {'pass': True, 'scope': 'Synthetic parser/geometry software regressions only; no final fabrication files inspected',
              'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
