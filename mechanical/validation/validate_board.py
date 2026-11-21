"""Measure the named Board BREP in an actual native STEP; never relocate it.

python validate_board.py input.step.gz report.json --context 'recovery baseline'
No inference is made from get3DFile element arguments: actual nonempty shapes
are counted before classifying the export as board-only geometry.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import cadquery as cq
from inspect_step import read_named_shapes, describe
from validate_pcba import bounds, cylinders


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('step',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--expected-thickness',type=float,default=1.6062)
    p.add_argument('--context',default='Native board geometry verification')
    args=p.parse_args()
    raw=args.step.read_bytes();plain=gzip.decompress(raw) if args.step.suffix=='.gz' else raw
    assert plain.startswith(b'ISO-10303-21;') and b'END-ISO-10303-21;' in plain[-128:]
    with tempfile.TemporaryDirectory(prefix='calxus-board-')as tmp:
        f=Path(tmp)/'board.step';f.write_bytes(plain);leaves=read_named_shapes(f)
    descriptions=[describe(r)for r in leaves]
    boards=[r['shape']for r in leaves if r['name'].startswith('Board~') and r['shape'].Solids()]
    assert len(boards)==1, 'Expected exactly one named Board BREP'
    shape=boards[0];bb=bounds(shape)
    all_cylinders=cylinders(shape)
    holes=[c for c in all_cylinders if abs(c[2]-2.2)<.01]
    targets=[(3.5,3.5),(76.5,3.5),(3.5,38.5),(76.5,38.5)]
    errors=[min(((a-x)**2+(b-y)**2)**.5 for a,b,_ in holes)if holes else None for x,y in targets]
    datum_errors=[abs(a-b)for a,b in zip([bb[0],bb[1],bb[2],bb[3],bb[4]],[0,0,0,80,42])]
    thickness=bb[5]-bb[2]
    nonempty=[d for d in descriptions if not d['empty_geometry']]
    checks={
        'valid_single_board_solid':shape.isValid() and len(shape.Solids())==1,
        'positive_y_datum_within_0p03_mm':max(datum_errors)<.03,
        'thickness_matches_expected_within_0p01_mm':abs(thickness-args.expected_thickness)<.01,
        'four_mount_holes_match_within_0p01_mm':len(holes)==4 and all(e is not None and e<.01 for e in errors),
    }
    report={
        'schema':'calxus.actual-board-brep.v1','context':args.context,
        'source_file':args.step.name,'source_bytes':len(raw),'source_sha256':hashlib.sha256(raw).hexdigest(),
        'step_bytes':len(plain),'step_sha256':hashlib.sha256(plain).hexdigest(),
        'gzip_crc_verified':args.step.suffix=='.gz','units':'mm','cadquery_version':cq.__version__,
        'applied_transform':'identity; no relocation or reflection',
        'shape_hierarchy':descriptions,'nonempty_leaf_count':len(nonempty),
        'board_only_geometry_independently_verified':len(nonempty)==1 and nonempty[0]['name'].startswith('Board~'),
        'board_bbox_mm':bb,'board_size_mm':[bb[3]-bb[0],bb[4]-bb[1],thickness],
        'board_volume_mm3':shape.Volume(),'thickness_mm':thickness,
        'expected_physical_stack_total_mm':args.expected_thickness,
        'thickness_error_mm':thickness-args.expected_thickness,
        'board_datum_absolute_errors_mm':datum_errors,
        'mount_holes_xy_diameter_mm':holes,'mount_hole_position_errors_mm':errors,
        'all_vertical_cylindrical_features_xy_diameter_mm':all_cylinders,
        'checks':checks,'board_geometry_pass':all(checks.values()),
        'limitations':[
            'This is the named Board BREP only; it is not a populated-PCBA enclosure collision check.',
            'Copper connectivity, stencil output and routing completeness are not assessed here.',
            'The approximately 0.0127-mm board-edge inset is recorded as exported, without compensating geometry.',
        ],
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['board_geometry_pass','board_only_geometry_independently_verified','board_bbox_mm','thickness_mm','thickness_error_mm','mount_holes_xy_diameter_mm','mount_hole_position_errors_mm']},indent=2))
    if not report['board_geometry_pass']:raise SystemExit(1)


if __name__=='__main__':
    main()
