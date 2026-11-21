"""Validate an EasyEDA STEP against the frozen enclosure, with no silent alignment.

Usage: python validate_pcba.py actual.step.gz report.json [--slider-offset -1 --fork-calibration -0.25]
The PCB datum must already be X0..80/Y0..42, bottom Z0. A nonmatching datum
is reported, never repaired by reflecting or relocating an imported model.
"""
from pathlib import Path
import argparse, gzip, hashlib, json, re, tempfile
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from inspect_step import read_named_shapes, describe


def bounds(shape):
    b = shape.BoundingBox()
    return [b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax]


def overlaps(a, b, tolerance=1e-7):
    return all(a[i] < b[i+3]-tolerance and b[i] < a[i+3]-tolerance for i in range(3))


def cylinders(shape):
    unique = {}
    for face in shape.Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cylinder = surface.Cylinder()
        p, d = cylinder.Location(), cylinder.Axis().Direction()
        if abs(d.Z()) < .99999:
            continue
        value = [p.X(), p.Y(), cylinder.Radius()*2]
        unique[tuple(round(v, 5) for v in value)] = value
    return sorted(unique.values())


def group_shapes(leaves, expected_refs):
    groups = {}
    unmapped = []
    for record in leaves:
        if not record['shape'].Solids():
            continue
        ref = None
        if record['name'].startswith('Board~'):
            ref = 'BOARD'
        else:
            for name in record['path']:
                candidate = re.split(r'~|->', name)[0]
                if candidate in expected_refs:
                    ref = candidate
                    break
        if ref is None:
            unmapped.append(describe(record))
            # Still test unknown solid geometry for collisions. An unmapped
            # model is reported and prevents a complete populated-PCBA pass.
            ref = 'UNMAPPED_SOLID_' + str(len(unmapped))
        groups.setdefault(ref, []).append(record['shape'])
    return {ref: cq.Compound.makeCompound(shapes) for ref, shapes in groups.items()}, unmapped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', type=Path)
    parser.add_argument('report', type=Path)
    parser.add_argument('--slider-offset', type=float, default=-3)
    parser.add_argument('--fork-calibration', type=float, default=0.0, help='Explicit clamped fork X relative to thumb, within contract range.')
    parser.add_argument('--j9-target', action='store_true', help='Also test old J9 anchor (32,25), rot90, at (32,26.25), rot0.')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent.parent
    design = json.loads((base.parent/'hardware/electrical/calxus_design_input.json').read_text())
    expected = {p['ref']: p for p in design['parts']}
    contract = json.loads((base/'mechanical_contract.json').read_text())
    calibration_range = contract['selector']['fork_calibration_x_range_mm']
    if not calibration_range[0] <= args.fork_calibration <= calibration_range[1]:
        raise ValueError('Fork calibration exceeds declared mechanical range')
    dnp_refs = set(contract['assembly_population']['pad_only_dnp_model_refs'])
    raw = args.step.read_bytes()
    plain = gzip.decompress(raw) if args.step.suffix == '.gz' else raw
    if not plain.startswith(b'ISO-10303-21;') or b'END-ISO-10303-21;' not in plain[-128:]:
        raise ValueError('Incomplete or invalid STEP text')
    with tempfile.TemporaryDirectory(prefix='calxus-pcba-') as tmp:
        step = Path(tmp)/'pcba.step'
        step.write_bytes(plain)
        leaves = read_named_shapes(step)
    groups, unmapped = group_shapes(leaves, set(expected))
    if 'BOARD' not in groups:
        raise ValueError('Named Board BREP was not found; inspect the STEP hierarchy first')
    board = groups['BOARD']
    bb = bounds(board)
    mount = [c for c in cylinders(board) if abs(c[2]-2.2) < .02]
    expected_holes = contract['board']['mounting_holes']
    hole_errors = [min(((x-a)**2+(y-b)**2)**.5 for a,b,_ in mount) if mount else None for x,y in expected_holes]
    board_check = {
        'bbox_mm': bb,
        'thickness_mm': bb[5]-bb[2],
        'datum_matches_without_transform': all(abs(a-b)<.03 for a,b in zip([bb[0],bb[1],bb[2],bb[3],bb[4]],[0,0,0,80,42])),
        'thickness_within_1p6_plus_minus_0p05': abs(bb[5]-bb[2]-1.6)<.05,
        'mount_holes_xy_diameter_mm': mount,
        'mount_hole_position_errors_mm': hole_errors,
        'mount_holes_match': len(mount)==4 and all(e is not None and e<.01 for e in hole_errors),
    }
    critical_mount={}
    for ref in ['J1','J2','SW1']:
        if ref not in groups:continue
        common=groups[ref].intersect(board)
        critical_mount[ref]={'bbox_mm':bounds(groups[ref]),'board_intersection_mm3':max(0,common.Volume()) if common.Solids() else 0.}
    print(json.dumps({'board':board_check,'mapped_components':len(groups)-1,'critical_mount':critical_mount}), flush=True)
    case_names = ['base','lid','comb_lower_tpu','comb_upper_tpu','slider_fork','slider_thumb']
    case = {name: cq.importers.importStep(str(base/'output'/('calxus_'+name+'.step'))).val() for name in case_names}
    for name in ['slider_fork','slider_thumb']:
        offset = args.slider_offset + (args.fork_calibration if name=='slider_fork' else 0)
        case[name] = case[name].translate((offset,0,0))
    hardware = {}
    assembly_path = base/'output'/'calxus_assembly.step'
    for record in read_named_shapes(assembly_path):
        name = record['name']
        if not name.startswith(('M2','Heat_shrink_collar_')):
            continue
        shape = record['shape']
        if 'slider' in name:
            shift = args.slider_offset+args.fork_calibration-contract['selector']['assembly_display_position_offset']-contract['selector'].get('assembly_display_fork_calibration_x',0)
            shape = shape.translate((shift,0,0))
        hardware[name] = shape
    if len([name for name in hardware if name.startswith('M2')]) != 10:
        raise ValueError('Expected five screw and five insert reference solids')
    if len([name for name in hardware if name.startswith('Heat_shrink_collar_')]) != 4:
        raise ValueError('Expected four heat-shrink collar reference solids')
    case.update(hardware)
    collisions, calculations, errors = [], 0, []
    component_details = {}
    for ref, shape in groups.items():
        b = bounds(shape)
        component_details[ref] = {'bbox_mm':b,'valid':shape.isValid(),'solid_count':len(shape.Solids()),'volume_mm3':shape.Volume(),'population':'DNP_PAD_ONLY_REFERENCE_MODEL' if ref in dnp_refs else 'FITTED' if ref!='BOARD' else 'BOARD'}
        if ref != 'BOARD':
            component_details[ref]['height_above_actual_pcb_top_mm'] = b[5]-bb[5]
            component_details[ref]['penetration_below_board_bottom_mm'] = max(0,bb[2]-b[2])
        for name, shell in case.items():
            if not overlaps(b,bounds(shell)):
                continue
            calculations += 1
            try:
                common = shape.intersect(shell)
                volume = common.Volume() if common.Solids() else 0.
                if volume > 1e-5:
                    collisions.append({'component':ref,'enclosure_part':name,'volume_mm3':volume,'bbox_mm':bounds(common)})
            except Exception as exc:
                errors.append({'component':ref,'enclosure_part':name,'error':str(exc)})
    moved_j9 = None
    if args.j9_target and 'J9' in groups:
        moved = groups['J9'].rotate((32,25,0),(32,25,1),-90).translate((0,1.25,0))
        moved_j9 = {'explicit_counterfactual':True,'from_anchor_mm':[32,25],'from_rotation_deg':90,'to_anchor_mm':[32,26.25],'to_rotation_deg':0,'bbox_mm':bounds(moved),'collisions':[]}
        for name,shell in case.items():
            if overlaps(bounds(moved),bounds(shell)):
                common = moved.intersect(shell)
                volume = common.Volume() if common.Solids() else 0.
                if volume > 1e-5:
                    moved_j9['collisions'].append({'enclosure_part':name,'volume_mm3':volume})
    physical_refs = {ref for ref,p in expected.items() if not p.get('pcb_only')}-dnp_refs
    dnp_collisions = [c for c in collisions if c['component'] in dnp_refs]
    collisions = [c for c in collisions if c['component'] not in dnp_refs]
    dnp_errors = [e for e in errors if e['component'] in dnp_refs]
    errors = [e for e in errors if e['component'] not in dnp_refs]
    missing = sorted(physical_refs-set(groups))
    critical_missing = sorted({'J1','J2','SW1'}-set(groups))
    invalid_models = sorted(ref for ref,d in component_details.items() if not d['valid'] and ref not in dnp_refs)
    board_mating_pass = all([
        board_check['datum_matches_without_transform'],
        board_check['thickness_within_1p6_plus_minus_0p05'],
        board_check['mount_holes_match'],board.isValid(),
        not any(c['component']=='BOARD' for c in collisions),
        not any(e['component']=='BOARD' for e in errors),
    ])
    report = {
        'schema':'calxus.actual-pcba-fit.v1',
        'source':args.step.name,'source_bytes':len(raw),'source_sha256':hashlib.sha256(raw).hexdigest(),
        'step_bytes':len(plain),'step_sha256':hashlib.sha256(plain).hexdigest(),
        'gzip_crc_verified':args.step.suffix=='.gz','applied_transform':'identity; no silent relocation or reflection',
        'board':board_check,'slider_offset_mm':args.slider_offset,'fork_calibration_x_mm':args.fork_calibration,
        'components':component_details,'unmapped_solid_models':unmapped,'critical_component_board_mating':critical_mount,
        'expected_physical_components':len(physical_refs),'dnp_pad_only_reference_models':sorted(dnp_refs),'dnp_reference_collisions':dnp_collisions,'dnp_reference_boolean_errors':dnp_errors,'missing_physical_models':missing,'critical_missing_models':critical_missing,
        'invalid_models':invalid_models,
        'enclosure_and_hardware_tested':list(case),
        'hardware_reference_assembly_sha256':hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
        'board_to_enclosure_and_fasteners_static_mating_pass':board_mating_pass,
        'exact_boolean_tests':calculations,'collision_threshold_mm3':1e-5,'collisions':collisions,'boolean_errors':errors,
        'j9_target_position_test':moved_j9,
        'limitations':['Imported vendor models are not independently measured samples.','Only the modeled switch detent is evaluated; slider offset must match that detent.','Missing, invalid or unmapped models prevent a complete populated-PCBA collision pass.','Screw and insert reference solids omit threads; nominal dimensions follow the mechanical BOM.','J3/J4/J5/J8 library connector models are DNP pad-only references; actual assembly has 93 fitted components.','Flexible cable routes and attached external plug overmolds are not represented by this PCBA source.','This is a static CAD check, not physical pull/flex/thermal or electrical validation.'],
    }
    report['sw1_model_mount_fit_pass']=critical_mount.get('SW1',{}).get('board_intersection_mm3',float('inf'))<1e-5
    fitted=[d for ref,d in component_details.items() if ref in physical_refs]
    report['actual_fitted_height_envelope_mm']={'max_above_board_top':max(d['height_above_actual_pcb_top_mm'] for d in fitted),'max_below_board_bottom':max(d['penetration_below_board_bottom_mm'] for d in fitted)}
    report['static_enclosure_fit_pass'] = all([board_mating_pass,not collisions,not errors,not missing,not critical_missing,not invalid_models,not unmapped,len(physical_refs)==contract['assembly_population']['actual_fitted_components']])
    report['critical_model_to_board_mount_pass']=all(d['board_intersection_mm3']<1e-4 for d in critical_mount.values()) and set(critical_mount)=={'J1','J2','SW1'}
    report['static_fit_pass'] = report['static_enclosure_fit_pass'] and report['critical_model_to_board_mount_pass']
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(args.report),'static_fit_pass':report['static_fit_pass'],'collisions':len(collisions),'missing_models':missing}),flush=True)


if __name__ == '__main__':
    main()
