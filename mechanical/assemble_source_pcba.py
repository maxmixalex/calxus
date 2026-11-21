#!/usr/bin/env python3
"""Build an explicitly source-derived populated Calxus assembly.

This is not a fresh JLCEDA STEP or CAM acceptance. The r7 native model geometry
is retained for 93 fitted components; only the approved J2 model Z+0.1 is applied.
The native board outer wire/thickness is re-extruded without any inherited holes,
then cut from all candidate source PAD, VIA and confirmed J1 locating records.
No printed part, EDA footprint, document or native STEP is modified.
"""
from pathlib import Path
import argparse, collections, gzip, hashlib, json, math, subprocess, sys, tempfile, zipfile
import cadquery as cq

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'validation'))
sys.path.insert(0, str(ROOT.parent/'tools'))
from inspect_step import read_named_shapes
from validate_pcba import group_shapes, bounds, overlaps, cylinders
from check_native_project_archive import parse_source, records, attributes
from assemble_actual_pcba import render


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def common_volume(a, b):
    s = a.intersect(b)
    return max(0.0, s.Volume()) if s.Solids() else 0.0


def shape_record(s):
    return {'bbox_mm': bounds(s), 'volume_mm3': s.Volume(),
            'solid_count': len(s.Solids()), 'valid': s.isValid()}


def bounding_intersection_volume(a, b):
    """Conservative upper bound, including near-tangent imported coordinates."""
    return math.prod(max(0.0, min(a[i+3], b[i+3])-max(a[i], b[i])) for i in range(3))


def candidate_bindings(archive, reference):
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('Candidate archive CRC failure')
        entries = [n for n in z.namelist() if n.endswith('.epru')]
        if len(entries) != 1:
            raise ValueError('Expected one candidate project source')
        raw = z.read(entries[0]); docs = parse_source(raw.decode('utf-8'))
    byid = {d['head']['uuid']: d for d in docs}
    pcb = next(d for d in docs if d['head']['docType'] == 'PCB')
    attrs = attributes(pcb); checks = []; changes = []; seen = set()
    for h, c in records(pcb, 'COMPONENT'):
        a = attrs[h['id']]; ref = a['Designator']; old = reference['components'][ref]
        if ref in seen: raise ValueError('Duplicate component reference '+ref)
        seen.add(ref)
        dev = records(byid[a['Device']], 'META')[0][1]['attributes']
        now = {'component_id': h['id'], 'xy_mil': [c['x'], c['y']],
               'angle_deg': c.get('angle', 0), 'layer_id': c['layerId'],
               'footprint_uuid': a['Footprint'], 'device_uuid': a['Device'],
               'model_uuid': dev.get('3D Model'),
               'library_model_transform': dev.get('3D Model Transform'),
               'instance_model_transform': c.get('attrs', {}).get('3D Model Transform'),
               'supplier_part': dev.get('Supplier Part'),
               'manufacturer_part': dev.get('Manufacturer Part')}
        delta = {k: {'old': old.get(k), 'new': v} for k, v in now.items() if old.get(k) != v}
        if delta:
            if ref != 'J2' or set(delta) != {'instance_model_transform'}:
                raise ValueError(f'Unapproved pose/model change: {ref}: {delta}')
            values = delta['instance_model_transform']
            old_t = old['instance_model_transform'] or old['library_model_transform']
            a0 = [float(v) for v in old_t.split(',')]
            a1 = [float(v) for v in values['new'].split(',')]
            if a0[:-1] != a1[:-1] or abs((a1[-1]-a0[-1])*.0254-.1) > 1e-9:
                raise ValueError('J2 model change is not the approved Z+0.1 mm')
            changes.append({'ref': ref, 'old_transform': old_t,
                            'new_transform': values['new'],
                            'explicit_model_translation_mm': [0, 0, .1]})
        checks.append({'ref': ref, 'pose_footprint_device_model_preserved': True,
                       'approved_override_only': bool(delta)})
    if seen != set(reference['components']) or len(checks) != 97 or len(changes) != 1:
        raise ValueError('Unexpected candidate model population or changes')
    return {'archive_sha256': digest(archive), 'epru_sha256': hashlib.sha256(raw).hexdigest(),
            'pcb_uuid': pcb['head']['uuid'], 'component_checks': checks,
            'explicit_component_model_changes': changes,
            'outline_source': [{'header': h, 'data': d} for h, d in records(pcb, 'POLY') if d.get('layerId') == 11],
            'source_via_count': len(records(pcb, 'VIA')),
            'source_line_count': len(records(pcb, 'LINE'))}


def load_drills(paths, sha):
    result = []; provenance = []
    expected = {'PAD': 56, 'J1_NONPAD': 2, 'VIA': 189}
    for kind, path in paths.items():
        d = json.loads(path.read_text())
        if d['source_archive_sha256'] != sha:
            raise ValueError('Drill contract belongs to a different candidate: '+str(path))
        rows = d.get('holes', d.get('vias'))
        if len(rows) != expected[kind]:
            raise ValueError(f'Unexpected {kind} count: {len(rows)}')
        for row in rows:
            r = dict(row); r['source_kind'] = kind
            if kind == 'VIA':
                r['diameter_mm'] = r['hole_diameter_mm']; r['ref'] = 'VIA'
            r['key'] = kind + ':' + str(r.get('primitiveId') or r.get('ref', '')+'.'+str(r.get('pin') or r.get('source_id')))
            result.append(r)
        provenance.append({'kind': kind, 'path': str(path.relative_to(ROOT.parent)),
                           'sha256': digest(path), 'count': len(rows)})
    if len({r['key'] for r in result}) != 247:
        raise ValueError('Duplicate drilling feature IDs')
    return result, provenance


def drill_cutter(row, z0, thickness):
    x, y = row['center_mm']; w = cq.Workplane('XY').center(x, y)
    if row['shape'] == 'ROUND':
        w = w.circle(row['diameter_mm']/2)
    elif row['shape'] == 'SLOT':
        w = w.slot2D(row['slot_overall_length_mm'], row['slot_tool_diameter_mm'],
                     angle=row['slot_axis_degrees_ccw_from_x'])
    else:
        raise ValueError('Unsupported drill shape '+row['shape'])
    return w.extrude(thickness+1).translate((0, 0, z0-.5)).val()


def source_board(native, rows):
    bb = bounds(native); thickness = bb[5]-bb[2]
    faces = [f for f in native.Faces() if f.geomType() == 'PLANE' and
             abs(f.Center().z-bb[2]) < 1e-7 and abs(f.normalAt().z) > .99999]
    face = max(faces, key=lambda f: f.Area())
    # Outer wire only: explicitly discard every pre-existing hole, including
    # the erroneous J2 export holes. No residual baseline vias can survive.
    blank = cq.Solid.extrudeLinear(face.outerWire(), [], cq.Vector(0, 0, thickness))
    tools = [drill_cutter(row, bb[2], thickness) for row in rows]
    print(json.dumps({'phase': 'board_cut', 'feature_count': len(tools)}), flush=True)
    board = blank.cut(cq.Compound.makeCompound(tools)).clean()
    if not board.isValid() or len(board.Solids()) != 1:
        raise ValueError('Source-derived board is not one valid solid')
    checks = []
    measured = cylinders(board)
    expected_volume = 0.0
    for row in rows:
        x, y = row['center_mm']
        if row['shape'] == 'ROUND':
            d = row['diameter_mm']; probes = [[x, y, d]]
            area = math.pi*(d/2)**2
        else:
            d = row['slot_tool_diameter_mm']; length = row['slot_overall_length_mm']
            probes = [[px, py, d] for px, py in row['slot_end_centers_mm']]
            area = math.pi*(d/2)**2+d*(length-d)
        errors = [min(math.sqrt(sum((a-b)**2 for a, b in zip(p, q))) for q in measured) for p in probes]
        checks.append({'key': row['key'], 'shape': row['shape'], 'cylinder_probe_errors_mm': errors,
                       'pass': all(e < 2e-6 for e in errors)})
        expected_volume += area*thickness
    removed = blank.Volume()-board.Volume()
    delta = abs(removed-expected_volume)
    if not all(c['pass'] for c in checks) or delta > 1e-4:
        raise ValueError('Source-hole geometry mismatch or overlapping drill cuts')
    proof = {'method': 'Native bottom-face OUTER wire only, extruded through unchanged native thickness; all inner wires discarded before all247 cuts.',
             'native_board': shape_record(native), 'undrilled_outer_blank': shape_record(blank),
             'source_derived_board': shape_record(board),
             'native_outer_bbox_preserved': max(abs(a-b) for a, b in zip(bounds(native), bounds(board))) < 1e-7,
             'drilling_feature_count': len(rows), 'drilling_counts': dict(collections.Counter(r['source_kind'] for r in rows)),
             'nominal_removed_volume_mm3': expected_volume, 'measured_removed_volume_mm3': removed,
             'removed_volume_error_mm3': delta, 'per_feature_boundary_checks': checks,
             'nominal_drill_geometry_note': 'All189 nominal via drills are modeled. Four EP VIPPO vias require fabrication fill/cap; resin/copper fill and mask/copper surface films are not separately represented.',
             'pass': True}
    return board, proof


def static_fit(groups, case, physical, source_sha):
    report = {'schema': 'calxus.source-derived-pcba-fit.v1',
              'geometry_origin': 'SOURCE_DERIVED_NOT_FRESH_NATIVE_STEP',
              'candidate_archive_sha256': source_sha,
              'native_cam_or_drc_acceptance': False,
              'components': {}, 'enclosure_collisions': [], 'component_board_collisions': [],
              'component_pair_collisions': [], 'boolean_errors': [],
              'slider_offset_mm': -1, 'fork_calibration_x_mm': -.25,
              'enclosure_collision_threshold_mm3': 1e-5,
              'component_mount_collision_threshold_mm3': 1e-4,
              'component_pair_collision_threshold_mm3': 1e-4,
              'conservative_bbox_volume_exclusions': []}
    counts = collections.Counter()
    case_boxes = {name: bounds(part) for name, part in case.items()}
    board_box = bounds(groups['BOARD'])
    for index, ref in enumerate(['BOARD', *sorted(physical)]):
        if index % 20 == 0: print(json.dumps({'phase':'static_fit','completed_components':index}),flush=True)
        s = groups[ref]; info = shape_record(s); info['population'] = 'BOARD' if ref == 'BOARD' else 'FITTED'
        report['components'][ref] = info
        for name, wall in case.items():
            upper = bounding_intersection_volume(info['bbox_mm'], case_boxes[name])
            if upper <= 1e-5:
                if upper > 0: report['conservative_bbox_volume_exclusions'].append({'pair':[ref,name],'upper_bound_mm3':upper,'threshold_mm3':1e-5})
                continue
            counts['enclosure'] += 1
            try:
                v = common_volume(s, wall)
                if v > 1e-5: report['enclosure_collisions'].append({'component': ref, 'part': name, 'volume_mm3': v})
            except Exception as e: report['boolean_errors'].append({'pair': [ref, name], 'error': str(e)})
        if ref != 'BOARD':
            upper = bounding_intersection_volume(info['bbox_mm'], board_box)
            if upper <= 1e-4:
                info['board_intersection_volume_upper_bound_mm3'] = upper
                if upper > 0: report['conservative_bbox_volume_exclusions'].append({'pair':[ref,'BOARD'],'upper_bound_mm3':upper,'threshold_mm3':1e-4})
            else:
                counts['board_mount'] += 1
                v = common_volume(s, groups['BOARD']); info['board_intersection_mm3'] = v
                if v > 1e-4: report['component_board_collisions'].append({'component': ref, 'volume_mm3': v})
    refs = sorted(physical)
    print(json.dumps({'phase':'component_pair_fit'}),flush=True)
    for i, ra in enumerate(refs):
        for rb in refs[i+1:]:
            upper = bounding_intersection_volume(report['components'][ra]['bbox_mm'], report['components'][rb]['bbox_mm'])
            if upper <= 1e-4:
                if upper > 0: report['conservative_bbox_volume_exclusions'].append({'pair':[ra,rb],'upper_bound_mm3':upper,'threshold_mm3':1e-4})
                continue
            counts['component_pair'] += 1
            v = common_volume(groups[ra], groups[rb])
            if v > 1e-4: report['component_pair_collisions'].append({'components': [ra, rb], 'volume_mm3': v})
    report['exact_boolean_tests'] = dict(counts)
    report['broad_phase_pair_counts'] = {'enclosure_and_hardware':(len(physical)+1)*len(case),
                                       'component_to_board':len(physical),
                                       'between_fitted_components':len(physical)*(len(physical)-1)//2}
    report['bbox_proof'] = 'A solid intersection is contained in the intersection of its two axis-aligned bounding boxes. Pairs with zero or sub-threshold box-intersection volume cannot exceed the stated collision threshold. Bounds are computed once per immutable rigid shape.'
    report['fitted_component_count'] = len(physical)
    report['all_models_valid'] = all(d['valid'] for d in report['components'].values())
    report['source_geometry_fit_pass'] = all([len(physical) == 93, report['all_models_valid'],
        not report['enclosure_collisions'], not report['component_board_collisions'],
        not report['component_pair_collisions'], not report['boolean_errors']])
    report['limitations'] = ['Source-derived geometry validation is not a native editor DRC, fresh native export or CAM acceptance.',
        'Vendor/native automatic models are not independently measured samples.',
        'No physical print, insertion, load, thermal, electrical or USB compliance test is implied.',
        'Rigid models omit free flexible cable routes, solder fillets, threads, plating/fill and surface artwork.']
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', type=Path, default=ROOT.parent/'hardware/native/Calxus_RevA_candidate.epro2')
    ap.add_argument('--native-step', type=Path, default=ROOT/'validation/Calxus_RevA_r7_PCBA.step.gz')
    ap.add_argument('--skip-render', action='store_true')
    ap.add_argument('--skip-selector', action='store_true')
    args = ap.parse_args(); out = ROOT/'output'; temp = ROOT/'tmp'; temp.mkdir(exist_ok=True)
    c = json.loads((ROOT/'mechanical_contract.json').read_text())
    freeze_path = ROOT/'validation/printed-parts-frozen-r1_2.json'
    freeze = json.loads(freeze_path.read_text())
    if len(freeze['files']) != 14 or any(digest(ROOT/r['path']) != r['sha256'] for r in freeze['files']):
        raise ValueError('Frozen seven-part STEP/STL geometry has changed')
    bindings_path = ROOT/'validation/native-r7-model-source-bindings.json'
    bindings = json.loads(bindings_path.read_text())
    if digest(args.native_step) != bindings['native_step_sha256']:
        raise ValueError('Native model source does not match r7 binding evidence')
    provenance = candidate_bindings(args.candidate, bindings)
    paths = {'PAD': ROOT.parent/'validation/native-candidate-tht-drill-expectations.json',
             'J1_NONPAD': ROOT.parent/'validation/native-candidate-nonpad-hole-expectations.json',
             'VIA': ROOT.parent/'validation/native-candidate-via-drill-expectations.json'}
    rows, drill_sources = load_drills(paths, provenance['archive_sha256'])
    expected = set(bindings['components']); dnp = set(c['assembly_population']['pad_only_dnp_model_refs']); physical = expected-dnp
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)/'r7.step'; p.write_bytes(gzip.decompress(args.native_step.read_bytes()))
        groups, unmapped = group_shapes(read_named_shapes(p), expected)
    if unmapped or set(groups) != expected|{'BOARD'} or len(physical) != 93:
        raise ValueError('Native source models are incomplete or unmapped')
    board, board_proof = source_board(groups['BOARD'], rows)
    groups['BOARD'] = board; groups['J2'] = groups['J2'].translate((0, 0, .1))
    board_path = out/'calxus_source_board.step.gz'
    board_step = temp/'calxus_source_board.step'; cq.exporters.export(board, str(board_step))
    board_path.write_bytes(gzip.compress(board_step.read_bytes(), compresslevel=9, mtime=0))
    board_proof.update({'geometry_origin': 'SOURCE_DERIVED_NOT_FRESH_NATIVE_STEP',
                        'candidate_archive_sha256': provenance['archive_sha256'],
                        'native_model_source_sha256': digest(args.native_step),
                        'drill_sources': drill_sources, 'output_sha256': digest(board_path)})
    (ROOT/'validation/source-derived-board-geometry.json').write_text(json.dumps(board_proof, indent=2)+'\n')
    palette = {'base': (.12,.17,.22), 'lid': (.23,.31,.38), 'comb_lower_tpu': (.10,.10,.10),
               'comb_upper_tpu': (.10,.10,.10), 'slider_fork': (.10,.43,.45), 'slider_thumb': (.10,.48,.50)}
    assembly = cq.Assembly(name='Calxus_SOURCE_DERIVED_93_component_assembly'); case = {}; items = []; case_sources = []
    off, cal = -1, -.25
    for name, color in palette.items():
        path = out/f'calxus_{name}.step'; shape = cq.importers.importStep(str(path)).val()
        if name.startswith('slider_'): shape = shape.translate((off+(cal if name=='slider_fork' else 0), 0, 0))
        case[name] = shape; assembly.add(shape, name='PRINTED_'+name, color=cq.Color(*color))
        shift = {'lid': (0,0,28), 'slider_fork': (0,0,12), 'slider_thumb': (0,0,39),
                 'comb_lower_tpu': (10,0,0), 'comb_upper_tpu': (10,0,13)}.get(name, (0,0,0))
        items.append((shape.translate(shift), color)); case_sources.append({'path': path.name, 'sha256': digest(path)})
    hardware = []
    for rec in read_named_shapes(out/'calxus_assembly.step'):
        name = rec['name']
        if not name.startswith(('M2','Heat_shrink_collar_')): continue
        s = rec['shape']
        if 'slider' in name: s = s.translate((off+cal-c['selector']['assembly_display_position_offset']-c['selector'].get('assembly_display_fork_calibration_x',0),0,0))
        color = (.72,.52,.22) if 'insert' in name else (.15,.15,.15) if name.startswith('Heat') else (.58,.60,.62)
        assembly.add(s,name=name,color=cq.Color(*color)); case[name] = s; hardware.append(name)
        if 'screw' in name: items.append((s.translate((0,0,43 if 'slider' in name else 35)),color))
    if len(hardware)!=14: raise ValueError('Expected14 hardware/collar references')
    print(json.dumps({'phase':'static_fit','fitted':len(physical)}),flush=True)
    fit = static_fit(groups,case,physical,provenance['archive_sha256'])
    fit_path=ROOT/'validation/source-derived-pcba-fit.json';fit_path.write_text(json.dumps(fit,indent=2)+'\n')
    if not fit['source_geometry_fit_pass']:
        raise ValueError('Source-derived PCBA fit failed; inspect '+str(fit_path))
    pcba = cq.Assembly(name='Calxus_SOURCE_DERIVED_PCBA_FOR_VALIDATION');pcba_items=[(board,(.06,.36,.26))]
    pcba.add(board,name='Board~SOURCE_DERIVED',color=cq.Color(.06,.36,.26))
    assembly.add(board,name='SOURCE_DERIVED_BOARD',color=cq.Color(.06,.36,.26));items.append((board.translate((0,0,5)),(.06,.36,.26)))
    for ref in sorted(physical):
        color = (.65,.67,.69) if ref.startswith(('J','SW')) else (.13,.14,.15) if ref.startswith(('U','D')) else (.38,.32,.23) if ref.startswith('C') else (.23,.25,.28)
        assembly.add(groups[ref],name='ACTUAL_'+ref,color=cq.Color(*color));pcba.add(groups[ref],name=ref+'~R7_NATIVE_MODEL',color=cq.Color(*color))
        items.append((groups[ref].translate((0,0,5)),color))
        pcba_items.append((groups[ref],color))
    step = temp/'calxus_source_assembly.step'; assembly.save(str(step));target=out/'calxus_source_assembly.step.gz'
    target.write_bytes(gzip.compress(step.read_bytes(),compresslevel=9,mtime=0))
    pcba_path=temp/'calxus_source_pcba.step';pcba.save(str(pcba_path))
    motion_path=ROOT/'validation/source-derived-selector-motion.json'
    if not args.skip_selector:
        subprocess.run([sys.executable,str(ROOT/'validation/validate_selector.py'),str(pcba_path),str(motion_path)],check=True)
        motion=json.loads(motion_path.read_text());motion.update({'geometry_origin':'SOURCE_DERIVED_NOT_FRESH_NATIVE_STEP','candidate_archive_sha256':provenance['archive_sha256'],'native_cam_or_drc_acceptance':False,'explicit_j2_translation_mm':[0,0,.1]})
        motion_path.write_text(json.dumps(motion,indent=2)+'\n')
    image_path=out/'calxus_source_assembly_exploded.png'
    pcba_image=out/'calxus_source_pcba.png'
    if not args.skip_render:
        render(items,image_path,'CALXUS R1.2 | SOURCE-DERIVED assembly','93 actual component models + frozen enclosure | final source drills | not a fresh native STEP')
        render(pcba_items,pcba_image,'CALXUS R1.2 | SOURCE-DERIVED populated board','93 fitted native models | J2 model Z +0.10 mm | 247 source drill features | 4 DNP bodies omitted')
    if digest(args.candidate) != provenance['archive_sha256']:
        raise ValueError('Candidate changed during generation; regenerate against the frozen source')
    latest_rows, latest_sources = load_drills(paths, provenance['archive_sha256'])
    if latest_rows != rows:
        raise ValueError('Drilling rows changed during generation; regenerate against frozen contracts')
    # Ancillary contract metadata may be clarified while shape rows stay fixed.
    # Preserve the actual final input-file hashes without changing any geometry.
    drill_sources = latest_sources; board_proof['drill_sources'] = latest_sources
    (ROOT/'validation/source-derived-board-geometry.json').write_text(json.dumps(board_proof,indent=2)+'\n')
    if any(digest(ROOT/r['path']) != r['sha256'] for r in freeze['files']):
        raise ValueError('Printed geometry changed during source assembly generation')
    manifest={'schema':'calxus.source-derived-assembly.v1','revision':c['revision'],
        'status':'SOURCE_DERIVED_DESIGN_GEOMETRY_NOT_NATIVE_DRC_OR_CAM_ACCEPTANCE',
        'candidate_archive':str(args.candidate.relative_to(ROOT.parent)),'candidate_archive_sha256':provenance['archive_sha256'],
        'native_r7_model_source':'validation/'+args.native_step.name,'native_r7_model_source_sha256':digest(args.native_step),
        'source_binding_snapshot':str(bindings_path.relative_to(ROOT)),'source_binding_snapshot_sha256':digest(bindings_path),
        'source_preservation_audit':provenance,'drill_sources':drill_sources,
        'actual_fitted_components':93,'omitted_dnp_connector_models':sorted(dnp),
        'explicit_transforms':[{'ref':'J2','translation_mm':[0,0,.1],'reason':'Approved instance model seating correction; exact candidate source binding delta verified.'}],
        'other_component_transforms':'identity; no X/Y, rotation, footprint or component shape changes',
        'board_method':board_proof['method'],'thumb_position_offset_mm':off,'fork_calibration_relative_thumb_mm':cal,
        'case_part_sources':case_sources,'hardware_reference_names':hardware,
        'printed_design_freeze':str(freeze_path.relative_to(ROOT)),'printed_design_freeze_sha256':digest(freeze_path),
        'fit_report':fit_path.name,'fit_report_sha256':digest(fit_path),
        'board_validation':'source-derived-board-geometry.json',
        'selector_validation':None if args.skip_selector else motion_path.name,
        'output_step_gz':target.name,'output_step_gz_sha256':digest(target),
        'render':None if args.skip_render else image_path.name,
        'populated_board_render':None if args.skip_render else pcba_image.name,
        'materials':{'rigid_printed_parts':'PETG or ASA; see mechanical BOM','combs':'TPU95A','fasteners':'M2 steel screw reference solids, brass insert reference solids','collars':'polyolefin heat-shrink reference solids','board':'Homogeneous native laminate envelope; source drill voids. Individual FR4/copper/mask/fill layers are not modeled as separate solids.','components':'Imported r7 native vendor/automatic model geometry. Colors distinguish part classes and do not certify their material composition.'},
        'render_note':'Exploded view translates PCBA+5Z/lid+28Z and other parts for visibility. Exchange STEP stays assembled. No envelope blocks substitute for the93 component models.',
        'limits':fit['limitations']+['After connection recovery, compare native final export and CAM against this source-derived design; this file does not establish those checks.']}
    mp=ROOT/'validation/calxus_source_assembly-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'assembly':str(target),'bytes':target.stat().st_size,'fit_pass':fit['source_geometry_fit_pass'],'manifest':str(mp),'preview':str(image_path)},indent=2),flush=True)
    if not args.skip_selector:
        # Preserve exact source BREP and reuse repeated native definitions.
        # The compact exchange replaces the large intermediate only after an
        # independent import verifies all114 objects and247 holes.
        subprocess.run([sys.executable,str(ROOT/'validation/export_instanced_source_step.py')],check=True)
        subprocess.run([sys.executable,str(ROOT/'validation/validate_source_assembly.py'),
                        '--manifest','calxus_source_assembly_instanced-manifest.json',
                        '--report','source-derived-assembly-instanced-roundtrip.json'],check=True)
        subprocess.run([sys.executable,str(ROOT/'validation/promote_instanced_source_step.py')],check=True)


if __name__=='__main__':
    main()
