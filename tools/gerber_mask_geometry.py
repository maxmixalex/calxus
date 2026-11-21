#!/usr/bin/env python3
"""Measure real Gerber mask openings around explicitly listed tented vias.

Uses the parsed Gerber image, including clear polarity and macro aperture holes.
All coordinates are millimetres. Via-in-pad resin/copper filling is a separate
fabrication requirement and is deliberately outside this tenting check.
"""
import math
import re

from gerbonara.utils import MM
from gerbonara import graphic_primitives as gp
from shapely.geometry import GeometryCollection, Point, Polygon


ARC_ERROR_MM = 0.00001


def positive_image_geometry(layer, origin_offset=(0.0, 0.0), role='solder-mask'):
    """Resolve the positive mask image in file order, not just bounding boxes.

    A positive solder-mask Gerber's dark features are openings. Negative image
    backgrounds require separate review and are refused. Primitive arcs are
    polygonised to at most ARC_ERROR_MM; acceptance later subtracts that bound.
    """
    path = layer.original_path
    if path is not None:
        text = path.read_text(errors='strict')
        if re.search(r'%\s*IPNEG\s*\*|TF\.FilePolarity\s*,\s*Negative', text, re.I):
            raise ValueError(f'{path}: negative {role} image polarity is not supported; explicit review required')
    image = GeometryCollection()
    object_count = 0
    clear_objects = 0
    primitive_count = 0
    zero_area_primitives = 0
    for obj in layer.objects:
        # A hole in an aperture leaves the previous image unchanged. Resolve
        # aperture-local positive/negative features before compositing the flash.
        local = GeometryCollection()
        for primitive in obj.to_primitives(unit=MM):
            # A fully suppressed circular/rectangular mask aperture may be
            # exported as a literal zero-area primitive. It opens no material.
            zero = ((isinstance(primitive, gp.Circle) and primitive.r == 0)
                    or (isinstance(primitive, (gp.Line, gp.Arc)) and primitive.width == 0)
                    or (isinstance(primitive, gp.Rectangle) and (primitive.w == 0 or primitive.h == 0)))
            if zero:
                zero_area_primitives += 1
                continue
            if not hasattr(primitive, 'to_arc_poly'):
                raise ValueError(f'Unsupported Gerber {role} primitive {type(primitive).__name__}')
            poly = primitive.to_arc_poly().approximate_arcs(max_error=ARC_ERROR_MM)
            points = [(x+origin_offset[0], y+origin_offset[1]) for x, y in poly.outline]
            if len(points) < 3:
                raise ValueError(f'Degenerate Gerber {role} primitive')
            geometry = Polygon(points)
            if not geometry.is_valid:
                raise ValueError(f'Invalid Gerber {role} polygon; no automatic topology repair applied')
            if primitive.polarity_dark == obj.polarity_dark:
                local = local.union(geometry)
            else:
                local = local.difference(geometry)
            primitive_count += 1
        if obj.polarity_dark:
            image = image.union(local)
        else:
            image = image.difference(local)
            clear_objects += 1
        object_count += 1
    if image.is_empty:
        raise ValueError(f'{path}: empty resolved {role} image')
    return image, {'file': str(path), 'objects': object_count,
                   'clear_objects': clear_objects, 'primitives': primitive_count,
                   'declared_zero_area_primitives': zero_area_primitives,
                   'opening_area_mm2': image.area,
                   'arc_polygonisation_max_error_mm': ARC_ERROR_MM,
                   'explicit_added_origin_offset_mm': list(origin_offset)}


def mask_opening_geometry(layer, origin_offset=(0.0, 0.0)):
    return positive_image_geometry(layer, origin_offset, 'solder-mask')


def validate_tented_vias(records, expectation, mask_images, position_tolerance=.025,
                         diameter_tolerance=.01, minimum_bridge_mm=.1):
    """Check listed actual holes against both final mask images.

    Expected input: units='mm', expected_count=128 and vias with primitiveId,
    center_mm, hole_diameter_mm and outer_diameter_mm. Coordinates are explicit;
    they are never registered by fitting, mirroring, scaling or rotation.
    """
    vias = expectation.get('vias', [])
    expected_count = expectation.get('expected_count')
    if expectation.get('units') != 'mm' or expected_count != 128 or len(vias) != 128:
        raise ValueError('Expected the complete 128-via millimetre tenting contract')
    ids = [v['primitiveId'] for v in vias]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate native primitiveId in tenting contract')
    if set(mask_images) != {'top', 'bottom'}:
        raise ValueError('Both actual top and bottom mask images are required')
    checks, errors, used = [], [], set()
    for v in vias:
        result = {'primitiveId': v['primitiveId'], 'expected': v,
                  'pass': False, 'failures': [], 'mask': {}}
        candidates = [(i, r) for i, r in enumerate(records)
                      if math.dist(r['center_mm'], v['center_mm']) <= position_tolerance]
        result['drill_matches'] = len(candidates)
        if len(candidates) != 1:
            result['failures'].append(f'Expected exactly one actual drill; found {len(candidates)}')
        else:
            index, actual = candidates[0]
            result['actual_drill'] = actual
            if index in used:
                result['failures'].append('Actual drill reused for another expected via')
            used.add(index)
            if actual['shape'] != 'ROUND' or actual['plated'] is not True:
                result['failures'].append('Actual via must be a round plated hole')
            if abs(actual['diameter_mm']-v['hole_diameter_mm']) > diameter_tolerance:
                result['failures'].append('Actual drill diameter differs from the native via contract')
            point = Point(actual['center_mm'])
            for side, openings in mask_images.items():
                distance = openings.distance(point)
                gap = distance-actual['diameter_mm']/2
                # Conservative lower bound prevents arc approximation from
                # turning a nominal 0.09999 mm bridge into a false pass.
                lower_bound = gap-ARC_ERROR_MM
                side_pass = lower_bound >= minimum_bridge_mm
                result['mask'][side] = {
                    'center_to_nearest_opening_mm': distance,
                    'hole_edge_to_opening_mm': gap,
                    'conservative_lower_bound_mm': lower_bound,
                    'opening_reaches_drill': gap <= ARC_ERROR_MM,
                    'pass': side_pass}
                if not side_pass:
                    result['failures'].append(f'{side}: hole-edge to actual mask opening lower bound {lower_bound:.6f} mm is below {minimum_bridge_mm:.3f} mm')
        result['pass'] = not result['failures']
        if not result['pass']:
            errors.append(v['primitiveId']+': '+'; '.join(result['failures']))
        checks.append(result)
    gaps = [c['mask'][s]['conservative_lower_bound_mm'] for c in checks for s in c['mask']]
    return {'pass': not errors, 'expected_count': 128, 'checked_vias': len(checks),
            'passed_vias': sum(c['pass'] for c in checks),
            'scope': 'Only the listed 128 added/restored vias; actual Excellon holes and both mask opening images. Four EP VIPPO holes are separate.',
            'minimum_required_hole_edge_to_mask_opening_mm': minimum_bridge_mm,
            'minimum_observed_conservative_gap_mm': min(gaps) if gaps else None,
            'tolerances': {'drill_center_mm': position_tolerance, 'drill_diameter_mm': diameter_tolerance,
                           'arc_polygonisation_bound_mm': ARC_ERROR_MM,
                           'bridge_threshold_relaxation_mm': 0},
            'checks': checks, 'errors': errors}
