#!/usr/bin/env python3
"""Parse native Gerbers and check Calxus layer/outline/drill/paste handoff.

Requires gerbonara 1.6.3. This checks exported geometry; it is not a PCB DRC,
an electrical connectivity proof, or a substitute for first-article testing.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import warnings
import zipfile

from gerbonara import LayerStack
from gerbonara.excellon import ExcellonFile
from gerbonara.graphic_objects import Flash, Line
from gerbonara.utils import MM
from shapely.geometry import box
from gerber_mask_geometry import mask_opening_geometry, positive_image_geometry, validate_tented_vias
from gerber_nonpad_holes import extract_expected_outline_circles, validate_nonpad_holes


# The actual JLCEDA 4.1.105 export has a combined PTH drill file and a second
# VIA-only view of the same holes. Resolve roles explicitly; gerbonara's generic
# filename heuristic classifies all three files as unknown drills.
NATIVE_LAYER_ROLES = {
    'Gerber_TopLayer.GTL': 'top copper',
    'Gerber_BottomLayer.GBL': 'bottom copper',
    'Gerber_InnerLayer1.G1': 'inner_1 copper',
    'Gerber_InnerLayer2.G2': 'inner_2 copper',
    'Gerber_TopSilkscreenLayer.GTO': 'top silk',
    'Gerber_BottomSilkscreenLayer.GBO': 'bottom silk',
    'Gerber_TopSolderMaskLayer.GTS': 'top mask',
    'Gerber_BottomSolderMaskLayer.GBS': 'bottom mask',
    'Gerber_TopPasteMaskLayer.GTP': 'top paste',
    'Gerber_BottomPasteMaskLayer.GBP': 'bottom paste',
    'Gerber_BoardOutlineLayer.GKO': 'mechanical outline',
    'Gerber_DocumentLayer.GDL': 'ignore',
    'Gerber_DrillDrawingLayer.GDD': 'ignore',
    'Drill_PTH_Through.DRL': 'drill plated',
    'Drill_NPTH_Through.DRL': 'drill nonplated',
    'Drill_PTH_Through_Via.DRL': 'ignore',
}


def validate_auxiliary_via_file(via_records, canonical_records, expected_via_ids=None):
    """Require the VIA-only file to be an exact one-to-one PTH subset.

    This does not discard coincident holes generally: only this explicit native
    alternate view is accepted, after matching every record and, when supplied,
    exactly the independently source-identified VIA set. Duplicate machining
    records inside either view remain errors.
    """
    checks, errors, used = [], [], set()
    for v in via_records:
        matches = [r for r in canonical_records
                   if r['shape'] == v['shape'] == 'ROUND'
                   and r['plated'] is v['plated'] is True
                   and math.dist(r['center_mm'], v['center_mm']) < 1e-7
                   and abs(r['diameter_mm']-v['diameter_mm']) < 1e-7]
        ok = len(matches) == 1 and matches[0]['id'] not in used
        if len(matches) == 1:
            used.add(matches[0]['id'])
        checks.append({'auxiliary_id': v['id'], 'canonical_id': matches[0]['id'] if len(matches) == 1 else None,
                       'matches': len(matches), 'pass': ok})
        if not ok:
            errors.append(v['id']+': VIA-only drill is not a unique exact combined-PTH record')
    if expected_via_ids is not None and used != set(expected_via_ids):
        errors.append('VIA-only file does not cover exactly the independently matched source VIA population')
    return {'pass': not errors, 'auxiliary_count': len(via_records),
            'canonical_matched_count': len(used), 'checks': checks, 'errors': errors,
            'scope': 'Explicit native VIA-only alternate view; combined PTH+NPTH files are canonical machining input, not additive drilling passes'}


def bbox_info(obj):
    box = obj.bounding_box(unit=MM)
    if box is None:
        return None
    (x0, y0), (x1, y1) = box
    return {'bounds_mm': box, 'center_mm': [(x0+x1)/2, (y0+y1)/2],
            'size_mm': [x1-x0, y1-y0]}


def extract_drills(layer, role_plated=None, origin_offset=(0.0, 0.0)):
    """Read actual Excellon flashes and straight G85/routed slots in millimetres.

    Hole positions are never inferred from copper-pad centres. Unknown/curved
    machining records are returned as errors instead of silently disappearing.
    """
    records, errors = [], []
    for index, obj in enumerate(layer.objects):
        o = obj.converted(MM)
        tool = obj.tool
        diameter = tool.unit.convert_to(MM, tool.diameter)
        plated = tool.plated if tool.plated is not None else role_plated
        if tool.plated is not None and role_plated is not None and tool.plated != role_plated:
            errors.append(f'{layer.original_path}: drill {index} conflicts with its PTH/NPTH file role')
        item = {'id': f'{layer.original_path}:{index}', 'file': str(layer.original_path),
                'source_indices': [index], 'plated': plated,
                'plating_basis': 'tool metadata' if tool.plated is not None else 'explicit drill-layer role',
                'diameter_mm': diameter}
        if isinstance(o, Flash):
            raw = [o.x, o.y]
            item.update(shape='ROUND', raw_center_mm=raw,
                        center_mm=[raw[i]+origin_offset[i] for i in (0, 1)])
        elif isinstance(o, Line):
            raw = [[o.x1, o.y1], [o.x2, o.y2]]
            ends = [[p[i]+origin_offset[i] for i in (0, 1)] for p in raw]
            travel = math.dist(*ends)
            if travel <= 1e-8:
                errors.append(f'{item["id"]}: zero-length routed slot is ambiguous')
                continue
            item.update(shape='SLOT', raw_end_centers_mm=raw, end_centers_mm=ends,
                        center_mm=[sum(p[i] for p in ends)/2 for i in (0, 1)],
                        overall_length_mm=travel+diameter,
                        axis_degrees_ccw_from_x=math.degrees(math.atan2(o.y2-o.y1, o.x2-o.x1)) % 180)
        else:
            errors.append(f'{item["id"]}: unsupported drill object {type(o).__name__}; explicit machining review required')
            continue
        records.append(item)
    return records, errors


def axis_error(a, b):
    return abs((a-b+90) % 180-90)


def endpoint_error(actual, expected):
    return min(max(math.dist(actual[i], expected[i]) for i in (0, 1)),
               max(math.dist(actual[i], expected[1-i]) for i in (0, 1)))


def validate_tht_drills(records, expectation, position_tolerance=.025,
                        dimension_tolerance=.025, angle_tolerance=1.0, allowed_extra_drill_ids=()):
    """One-to-one check of all 56 source-derived r7 through-holes.

    These tolerances compare exported nominal geometry, not a factory's process
    tolerance. No scale, reflection, rotation or inferred registration is used.
    """
    holes = expectation.get('holes', [])
    expected_counts = {'holes': 56, 'plated': 52, 'unplated': 4}
    counts = {'holes': len(holes), 'plated': sum(h.get('plated') is True for h in holes),
              'unplated': sum(h.get('plated') is False for h in holes)}
    if expectation.get('units') != 'mm' or counts != expected_counts:
        raise ValueError(f'Expected complete r7 millimetre contract {expected_counts}, received {counts}')
    identities = [(h['ref'], str(h['pin'])) for h in holes]
    if len(set(identities)) != 56 or any(h.get('shape') not in ('ROUND', 'SLOT') for h in holes):
        raise ValueError('Duplicate hole identities or unsupported expected shape')
    checks, errors, used = [], [], set()
    for h in holes:
        refpin = f'{h["ref"]}.{h["pin"]}'
        candidates = [(i, r) for i, r in enumerate(records)
                      if math.dist(h['center_mm'], r['center_mm']) <= position_tolerance]
        result = {'ref': h['ref'], 'pin': str(h['pin']), 'expected': {
            k: h[k] for k in ('shape', 'plated', 'center_mm', 'diameter_mm',
                              'slot_tool_diameter_mm', 'slot_overall_length_mm',
                              'slot_axis_degrees_ccw_from_x', 'slot_end_centers_mm') if k in h},
                  'center_candidates': len(candidates), 'pass': False, 'failures': []}
        if len(candidates) != 1:
            result['failures'].append(f'Expected exactly one drill at the specified centre, found {len(candidates)}')
            if records:
                nearest = min(records, key=lambda r: math.dist(h['center_mm'], r['center_mm']))
                result['nearest_actual'] = nearest
                result['nearest_center_error_mm'] = math.dist(h['center_mm'], nearest['center_mm'])
        else:
            index, actual = candidates[0]
            result['actual'] = actual
            result['center_error_mm'] = math.dist(h['center_mm'], actual['center_mm'])
            if index in used:
                result['failures'].append('The same actual drill would satisfy two expected holes')
            used.add(index)
            if actual['plated'] is not h['plated']:
                result['failures'].append('Plated/nonplated classification differs or is unknown')
            if actual['shape'] != h['shape']:
                result['failures'].append('Round/slot shape differs')
            wanted_diameter = h['diameter_mm'] if h['shape'] == 'ROUND' else h['slot_tool_diameter_mm']
            result['diameter_error_mm'] = abs(actual['diameter_mm']-wanted_diameter)
            if result['diameter_error_mm'] > dimension_tolerance:
                result['failures'].append('Round/tool diameter differs')
            if h['shape'] == actual['shape'] == 'SLOT':
                result['overall_length_error_mm'] = abs(actual['overall_length_mm']-h['slot_overall_length_mm'])
                result['axis_error_deg'] = axis_error(actual['axis_degrees_ccw_from_x'], h['slot_axis_degrees_ccw_from_x'])
                result['end_center_error_mm'] = endpoint_error(actual['end_centers_mm'], h['slot_end_centers_mm'])
                if result['overall_length_error_mm'] > dimension_tolerance:
                    result['failures'].append('Slot overall length differs')
                if result['axis_error_deg'] > angle_tolerance:
                    result['failures'].append('Slot long-axis direction differs')
                if result['end_center_error_mm'] > position_tolerance:
                    result['failures'].append('Slot router/G85 endpoint centres differ')
        result['pass'] = not result['failures']
        if not result['pass']:
            errors.append(refpin+': '+'; '.join(result['failures']))
        checks.append(result)
    unmatched = [r for i, r in enumerate(records) if i not in used and r['id'] not in allowed_extra_drill_ids]
    # The final via population has its own routing/VIPPO review. Unlisted large
    # holes or slots cannot be dismissed as that small-via population.
    unexpected = [r for r in unmatched if r['shape'] != 'ROUND' or r['diameter_mm'] > .6
                  or r['plated'] is not True]
    if unexpected:
        errors.append(f'{len(unexpected)} additional large, slotted, nonplated or unknown-plating drill records are not in the 56-hole contract')
    return {'pass': not errors, 'scope': 'All source-derived connector/service and mounting holes; remaining small plated drills are reported for separate via/VIPPO review',
            'expected_counts': counts, 'checked_holes': len(checks),
            'passed_holes': sum(c['pass'] for c in checks),
            'tolerances': {'center_mm': position_tolerance, 'diameter_and_length_mm': dimension_tolerance,
                           'axis_degrees': angle_tolerance, 'meaning': 'Nominal export comparison, not fabrication process acceptance'},
            'checks': checks, 'unmatched_small_plated_drill_count': len(unmatched)-len(unexpected),
            'unmatched_drill_size_counts': dict(collections.Counter(str(round(r['diameter_mm'], 6)) for r in unmatched)),
            'unexpected_drills': unexpected, 'errors': errors}


def validate_all_via_drills(records, expectation, through_hole_checks,
                            position_tolerance=.025, diameter_tolerance=.01):
    """Match all source-derived vias, and reject any unexplained actual hole."""
    vias = expectation.get('vias', [])
    if expectation.get('units') != 'mm' or expectation.get('expected_count') != len(vias) or not vias:
        raise ValueError('Complete saved-source via drilling expectations are required')
    if len({v['primitiveId'] for v in vias}) != len(vias) or not expectation.get('source_archive_sha256'):
        raise ValueError('Via expectations need unique IDs and a native source archive hash')
    used = {c['actual']['id'] for c in through_hole_checks if c.get('pass') and c.get('actual')}
    checks, errors = [], []
    for v in vias:
        c = {'primitiveId': v['primitiveId'], 'expected': v, 'pass': False, 'failures': []}
        found = [r for r in records if math.dist(r['center_mm'], v['center_mm']) <= position_tolerance]
        c['drill_matches'] = len(found)
        if len(found) != 1:
            c['failures'].append(f'Expected exactly one via drill, found {len(found)}')
        else:
            r = found[0]; c['actual'] = r
            if r['id'] in used:
                c['failures'].append('Actual hole already matched another via or component hole')
            used.add(r['id'])
            c['center_error_mm'] = math.dist(r['center_mm'], v['center_mm'])
            c['diameter_error_mm'] = abs(r['diameter_mm']-v['hole_diameter_mm'])
            if r['plated'] is not True or r['shape'] != 'ROUND':
                c['failures'].append('Via must be a round plated drill')
            if c['diameter_error_mm'] > diameter_tolerance:
                c['failures'].append('Via drill diameter differs from saved native source')
        c['pass'] = not c['failures']
        if not c['pass']:
            errors.append(v['primitiveId']+': '+'; '.join(c['failures']))
        checks.append(c)
    unexplained = [r for r in records if r['id'] not in used]
    if unexplained:
        errors.append(f'{len(unexplained)} actual drills are not uniquely accounted for by component, mounting or via expectations')
    return {'pass': not errors, 'expected_count': len(vias), 'checked_vias': len(checks),
            'passed_vias': sum(c['pass'] for c in checks), 'actual_total_drills': len(records),
            'scope': 'Every saved native VIA, including four EP VIPPO drills; this does not verify the resin/copper filling process',
            'tolerances': {'center_mm': position_tolerance, 'diameter_mm': diameter_tolerance},
            'checks': checks, 'unexplained_actual_drills': unexplained, 'errors': errors}


def inspect(args):
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    with zipfile.ZipFile(args.archive) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
        for name in archive.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Unsafe archive member path')
        entries = [{'name': f.filename, 'bytes': f.file_size} for f in archive.infolist()]
        cam_names = [n for n in archive.namelist() if Path(n).suffix.upper().startswith('.G')
                     or Path(n).suffix.upper() == '.DRL']
        unknown_cam = [n for n in cam_names if Path(n).name not in NATIVE_LAYER_ROLES]
        if unknown_cam:
            raise ValueError('Unmapped native CAM files require explicit review: '+str(unknown_cam))
        names = [Path(n).name for n in cam_names]
        if len(names) != len(set(names)):
            raise ValueError('Ambiguous duplicate CAM filenames in archive')
        auxiliary_names = [n for n in archive.namelist() if Path(n).name == 'Drill_PTH_Through_Via.DRL']
        auxiliary_via_bytes = archive.read(auxiliary_names[0]) if auxiliary_names else None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        import re
        stack = LayerStack.open(args.archive, lazy=False, autoguess=False,
                                overrides={re.escape(name): role for name, role in NATIVE_LAYER_ROLES.items()})
        auxiliary_vias, auxiliary_errors = [], []
        if auxiliary_via_bytes is not None:
            layer = ExcellonFile.from_string(auxiliary_via_bytes.decode(), filename='Drill_PTH_Through_Via.DRL')
            auxiliary_vias, auxiliary_errors = extract_drills(layer, True, args.drill_origin_offset_mm)
            errors.extend(auxiliary_errors)
    parser_warnings = [str(w.message) for w in caught]
    layers = []
    for key, wrapper in stack.graphic_layers.items():
        layer = wrapper.instance
        layers.append({'role': ' '.join(key), 'file': str(layer.original_path),
                       'objects': len(layer.objects), 'bounds_mm': layer.bounding_box(unit=MM),
                       'object_types': dict(collections.Counter(type(o).__name__ for o in layer.objects))})
    if len(stack.copper_layers) != 4:
        errors.append(f'Expected four copper layers, found {len(stack.copper_layers)}')
    for role in [('top', 'copper'), ('bottom', 'copper'), ('top', 'mask'), ('bottom', 'mask'),
                 ('top', 'paste'), ('top', 'silk'), ('mechanical', 'outline')]:
        if role not in stack.graphic_layers or not stack.graphic_layers[role].instance.objects:
            errors.append('Missing/empty manufacturing layer: '+' '.join(role))
    outline = stack.outline.instance if stack.outline else None
    nonpad_expectation = json.loads(args.nonpad_hole_expectations.read_text())
    outline_circles, nonpad_outline_indices = extract_expected_outline_circles(outline, nonpad_expectation, args.gerber_origin_offset_mm)
    outline_check = {'present': outline is not None}
    if outline:
        points, degree = [], collections.Counter()
        edges = []
        for index, obj in enumerate(outline.objects):
            if index in nonpad_outline_indices:
                continue
            if not all(hasattr(obj, a) for a in ('x1', 'y1', 'x2', 'y2')):
                errors.append('Outline contains non-line/arc object; explicit review required')
                continue
            o = obj.converted(MM)
            a, b = (round(o.x1, 4), round(o.y1, 4)), (round(o.x2, 4), round(o.y2, 4))
            points.extend((a, b)); degree[a] += 1; degree[b] += 1; edges.append((a, b))
        if points:
            extent = [max(p[i] for p in points)-min(p[i] for p in points) for i in (0, 1)]
            outline_check.update({'centerline_endpoint_extent_mm': extent,
                                  'outer_stroke_bounds_mm': outline.bounding_box(unit=MM),
                                  'endpoint_degrees': dict(collections.Counter(degree.values()))})
            if abs(extent[0]-80) > .02 or abs(extent[1]-42) > .02:
                errors.append(f'Board outline endpoint extents are {extent}, expected 80×42 mm')
            if any(d != 2 for d in degree.values()):
                errors.append('Outline endpoints do not form closed degree-2 contours')
            adjacency = collections.defaultdict(set)
            for a, b in edges:
                adjacency[a].add(b); adjacency[b].add(a)
            remaining = set(adjacency); contours = 0
            while remaining:
                contours += 1; queue = [remaining.pop()]
                while queue:
                    for n in adjacency[queue.pop()] & remaining:
                        remaining.remove(n); queue.append(n)
            outline_check['outer_contours'] = contours
            outline_check['separate_expected_inner_circle_features'] = len(outline_circles)
            if contours != 1:
                errors.append(f'Expected one board-edge contour, found {contours}')
    drill_records, drill_summary = [], []
    for wrapper in stack.drill_layers:
        layer = wrapper.instance
        tools = []
        for tool, count in layer.hit_count().items():
            tools.append({'diameter_mm': tool.unit.convert_to(MM, tool.diameter),
                          'plated': tool.plated, 'count': count})
        drill_summary.append({'file': str(layer.original_path), 'plating': layer.plating_type, 'tools': tools})
        role_plated = True if wrapper is stack.drill_pth else False if wrapper is stack.drill_npth else None
        found, drill_errors = extract_drills(layer, role_plated, args.drill_origin_offset_mm)
        drill_records.extend(found); errors.extend(drill_errors)
    if not stack.drill_pth or not stack.drill_npth:
        errors.append('Explicit plated and nonplated drill layers are both required')
    expectation = json.loads(args.drill_expectations.read_text())
    nonpad_validation, nonpad_drill_ids = validate_nonpad_holes(drill_records, outline_circles, nonpad_expectation)
    nonpad_validation['expectations_sha256'] = hashlib.sha256(args.nonpad_hole_expectations.read_bytes()).hexdigest()
    nonpad_validation['source_archive_sha256'] = nonpad_expectation.get('source_archive_sha256')
    errors.extend(nonpad_validation['errors'])
    drill_validation = validate_tht_drills(drill_records, expectation, allowed_extra_drill_ids=nonpad_drill_ids)
    drill_validation['expectations_sha256'] = hashlib.sha256(args.drill_expectations.read_bytes()).hexdigest()
    drill_validation['expectations_source_archive_sha256'] = expectation.get('source_archive_sha256')
    drill_validation['explicit_added_origin_offset_mm'] = list(args.drill_origin_offset_mm)
    errors.extend(drill_validation['errors'])
    mount_checks = [c for c in drill_validation['checks'] if c['ref'] in ('H1', 'H2', 'H3', 'H4')]
    via_expectation = json.loads(args.via_expectations.read_text())
    for e in (expectation, nonpad_expectation):
        if e.get('source_archive_sha256') != via_expectation['source_archive_sha256']:
            errors.append('PAD, non-PAD and VIA expectations must all come from the same final native archive')
    via_validation = validate_all_via_drills(drill_records, via_expectation, drill_validation['checks']+nonpad_validation['checks'])
    via_validation['expectations_sha256'] = hashlib.sha256(args.via_expectations.read_bytes()).hexdigest()
    via_validation['source_archive_sha256'] = via_expectation['source_archive_sha256']
    errors.extend(via_validation['errors'])
    auxiliary_validation = {'status': 'not_present', 'pass': True}
    if auxiliary_via_bytes is not None:
        matched_ids = {c['actual']['id'] for c in via_validation['checks'] if c.get('pass') and c.get('actual')}
        auxiliary_validation = validate_auxiliary_via_file(auxiliary_vias, drill_records, matched_ids)
        auxiliary_validation['sha256'] = hashlib.sha256(auxiliary_via_bytes).hexdigest()
        errors.extend(auxiliary_validation['errors'])
    mask_checks = {'pass': False, 'errors': []}
    mask_metadata = {}
    try:
        mask_images = {}
        for side in ('top', 'bottom'):
            layer = stack.graphic_layers[(side, 'mask')].instance
            mask_images[side], mask_metadata[side] = mask_opening_geometry(layer, args.gerber_origin_offset_mm)
        tenting = json.loads(args.tenting_expectations.read_text())
        if tenting.get('source_archive_sha256') != via_expectation['source_archive_sha256']:
            raise ValueError('All-via and tenting expectations must come from the same final native archive')
        mask_checks = validate_tented_vias(drill_records, tenting, mask_images)
        mask_checks['expectations_sha256'] = hashlib.sha256(args.tenting_expectations.read_bytes()).hexdigest()
        mask_checks['source_archive_sha256'] = tenting['source_archive_sha256']
    except (KeyError, ValueError) as e:
        mask_checks['errors'].append(str(e))
    errors.extend(mask_checks['errors'])
    paste_checks = []
    if args.pcb and args.stencil:
        pcb = json.loads(args.pcb.read_text()); scale = {'mil': .0254, 'mm': 1}[pcb['units']]
        components = {p['ref']: p for p in pcb['components']}
        proposal = json.loads(args.stencil.read_text())
        paste = stack.graphic_layers.get(('top', 'paste'))
        if paste:
            paste_image, paste_metadata = positive_image_geometry(paste.instance, args.gerber_origin_offset_mm, 'top-paste')
            for spec in proposal['components']:
                ref = spec['reference']; component = components[ref]
                pads = [p for p in component['pads'] if str(p['number']) == spec['native_ep_pin']]
                if len(pads) != 1:
                    errors.append(ref+': cannot locate unique actual EP pad'); continue
                cx, cy = pads[0]['x']*scale, pads[0]['y']*scale
                sx, sy = spec['copper_size_mm']
                ep_image = paste_image.intersection(box(cx-sx/2, cy-sy/2, cx+sx/2, cy+sy/2))
                geometries = list(ep_image.geoms) if ep_image.geom_type == 'MultiPolygon' else [ep_image] if ep_image.geom_type == 'Polygon' and not ep_image.is_empty else []
                candidates = [{'bounds_mm': list(g.bounds), 'area_mm2': g.area,
                               'interior_hole_count': len(g.interiors)} for g in geometries]
                checks = []
                for w in spec['windows']:
                    # Square four-window pattern is invariant under the native
                    # 0/90/180/270-degree component rotations in this design.
                    dx, dy = w['center_relative_to_actual_EP_mm']; wanted = [cx+dx, cy+dy]
                    radius = w['corner_radius_mm']; wx, wy = w['width_mm'], w['height_mm']
                    desired = box(wanted[0]-wx/2+radius, wanted[1]-wy/2+radius,
                                  wanted[0]+wx/2-radius, wanted[1]+wy/2-radius).buffer(radius, quad_segs=64)
                    # 0.003 mm permits the observed 0.1 mil pad-coordinate
                    # getter quantisation, but rejects unrounded square corners.
                    distances = [g.hausdorff_distance(desired) for g in geometries]
                    matches = [i for i, d in enumerate(distances) if d <= .003 and not geometries[i].interiors]
                    checks.append({'id': w['id'], 'expected_center_mm': wanted,
                                   'expected_corner_radius_mm': radius, 'matches': len(matches),
                                   'minimum_shape_distance_mm': min(distances) if distances else None,
                                   'shape_comparison_tolerance_mm': .003})
                ok = len(candidates) == 4 and all(c['matches'] == 1 for c in checks)
                web = min((g.distance(h) for i, g in enumerate(geometries) for h in geometries[i+1:]), default=None)
                if web is None or abs(web-spec['web_mm']) > .006:
                    ok = False
                paste_checks.append({'ref': ref, 'actual_ep_center_mm': [cx, cy], 'candidates': candidates,
                                     'windows': checks, 'pass': ok, 'minimum_web_mm': web,
                                     'actual_coverage_percent': 100*ep_image.area/(sx*sy),
                                     'scope': 'Resolved actual top-paste image: exactly four rounded openings, complete shapes/centres, web and coverage; not stencil thickness or reflow qualification'})
                if not ok:
                    errors.append(ref+': exported top-paste geometry is not exactly the four reviewed EP windows')
    else:
        errors.append('Actual PCB pad export and stencil proposal are required for EP paste validation')
    for side in ('top', 'bottom'):
        svg = stack.to_pretty_svg(side=side, margin=2, arg_unit=MM, svg_unit=MM)
        (args.output/('gerber-'+side+'.svg')).write_text(str(svg))
    if ('top', 'paste') in stack.graphic_layers:
        svg = stack.graphic_layers[('top', 'paste')].instance.to_svg(margin=1, arg_unit=MM, svg_unit=MM)
        (args.output/'gerber-top-paste.svg').write_text(str(svg))
    report = {'pass': not errors, 'scope': 'Native fabrication-file parsing and explicit geometry checks; does not certify routed-net connectivity, electrical DRC, impedance or assembly process',
              'archive_sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
              'archive_bytes': args.archive.stat().st_size, 'entries': entries,
              'parser': 'gerbonara 1.6.3', 'parser_warnings': parser_warnings,
              'layers': layers, 'outline': outline_check, 'drills': drill_summary,
              'mounting_holes': mount_checks, 'through_holes': drill_validation,
              'nonpad_locating_holes': nonpad_validation,
              'all_via_drills': via_validation, 'tented_vias': mask_checks,
              'auxiliary_via_drill_view': auxiliary_validation,
              'mask_image_metadata': mask_metadata,
              'ep_paste': paste_checks, 'errors': errors}
    (args.output/'gerber-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'pass': report['pass'], 'layers': len(layers), 'copper_layers': len(stack.copper_layers),
                      'ep_paste_checks': len(paste_checks), 'errors': errors}, ensure_ascii=False))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pcb', type=Path)
    parser.add_argument('--stencil', type=Path)
    parser.add_argument('--drill-expectations', type=Path, required=True,
                        help='Complete native-r7-tht-drill-expectations.json, 52 PTH + 4 NPTH')
    parser.add_argument('--nonpad-hole-expectations', type=Path, required=True,
                        help='The two independently verified J1 locating holes encoded as native FILL, additional to PAD holes')
    parser.add_argument('--via-expectations', type=Path, required=True,
                        help='All VIA records independently extracted from the final native archive')
    parser.add_argument('--tenting-expectations', type=Path, required=True,
                        help='Source-derived 128 added/restored vias; separate from four EP VIPPO vias')
    parser.add_argument('--drill-origin-offset-mm', type=float, nargs=2, default=(0.0, 0.0),
                        metavar=('DX', 'DY'), help='Explicit translation added to actual Excellon coordinates; never inferred')
    parser.add_argument('--gerber-origin-offset-mm', type=float, nargs=2, default=(0.0, 0.0),
                        metavar=('DX', 'DY'), help='Explicit translation added to Gerber mask/paste coordinates; never inferred')
    raise SystemExit(inspect(parser.parse_args()))
