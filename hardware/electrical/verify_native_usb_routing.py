"""Independent audit of native exported USB copper against the approved route plan.
Usage: python verify_native_usb_routing.py COPPER_JSON PADS_JSON OUTPUT_JSON
Copper: explicit units='mil'; full lines/vias, optionally arcs/polygons/pours.
Pads: fresh native component/test-pad position/size/rotation in mil; catalog fallback is disclosed.
Does not operate the EDA application.
"""
import json, math, sys, hashlib
from pathlib import Path
try:
    from shapely.geometry import Point, LineString, box
except ImportError:
    sys.path.insert(0, '/tmp/calxus_deps')
    from shapely.geometry import Point, LineString, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union

P = Path(__file__).resolve().parent
E = P.parent / 'evidence'
if len(sys.argv) != 4:
    raise SystemExit(__doc__)
copper_path, pads_path, output_path = map(Path, sys.argv[1:])
A = json.loads(copper_path.read_text())
B = json.loads(pads_path.read_text())
R = json.loads((P/'usb_route_plan.json').read_text())
G = json.loads((P/'ground_stitch_plan.json').read_text())
V = json.loads((P/'usb_route_validation.json').read_text())
D = json.loads((P/'calxus_design_input.json').read_text())
C = json.loads((E/'eda_parts_catalog_full.json').read_text())
if A.get('units') != 'mil' or not isinstance(A.get('lines'), list) or not isinstance(A.get('vias'), list):
    raise ValueError("Native copper must explicitly declare mil units and full lines/vias arrays")
if B.get('units') != 'mil' or not isinstance(B.get('components'), list):
    raise ValueError("Native pad export must explicitly declare mil units")
HS = {t['net'] for t in R['tracks']}
parts = {p['ref']: p for p in D['parts']}
tol = .11  # native positions may be rounded to 0.1mil by the read API
errors, notices, els = [], [], []
pad_dimension_fallbacks = []

def layers(v):
    if v in (12,): return {1, 2}
    return {v}

def track_shape(t):
    return LineString([(t['x1'], t['y1']), (t['x2'], t['y2'])]).buffer(t['width']/2)

def via_shape(v):
    return Point(v['x'], v['y']).buffer(v['diameter']/2)

for comp in B['components']:
    if comp['ref'] not in parts:
        raise ValueError('Unknown component '+comp['ref'])
    lib = {str(p['padNumber']): p for p in C[parts[comp['ref']]['lcsc']]['footprint']['pads']}
    for p in comp['pads']:
        q = lib[str(p['number'])]
        if all(isinstance(p.get(k), (int,float)) for k in ('width','height','rotation')):
            width,height,angle=p['width'],p['height'],p['rotation']
        else:
            width,height,angle=q['width'],q['height'],comp['rotation']+q['rotation']
            pad_dimension_fallbacks.append(comp['ref']+'.'+str(p['number']))
        # Conservative rectangle around rectangular/oval library pads. Native
        # circle geometry is used exactly; unsupported special shapes retain a
        # conservative enclosing rectangle and require native DRC review.
        if p.get('shape')=='ELLIPSE' and abs(width-height)<.001:
            geom=Point(0,0).buffer(width/2)
        else:
            geom=box(-width/2,-height/2,width/2,height/2)
        geom = rotate(geom, angle, origin=(0, 0))
        geom = translate(geom, p['x'], p['y'])
        els.append({'id': comp['ref']+'.'+str(p['number']), 'kind': 'pad',
                    'net': p.get('net'), 'layers': layers(p['layer']), 'g': geom})
if not isinstance(B.get('testpads'), list):
    raise ValueError('Fresh test-pad geometry is required as testpads array; an ID-only map is insufficient')
for p in B['testpads']:
    dia = p.get('diameter', 1/.0254)
    els.append({'id': p.get('ref', p.get('id')), 'kind': 'testpad',
                'net': p.get('net'), 'layers': layers(p['layer']),
                'g': Point(p['x'], p['y']).buffer(dia/2)})
for i,t in enumerate(A['lines']):
    for key in ('net','layer','x1','y1','x2','y2','width'):
        if key not in t: raise ValueError('Missing line key '+key)
    els.append({'id': t.get('id', 'line'+str(i)), 'kind': 'line',
                'net': t['net'], 'layers': {t['layer']}, 'g': track_shape(t)})
for i,v in enumerate(A['vias']):
    for key in ('net','x','y','diameter','holeDiameter'):
        if key not in v: raise ValueError('Missing via key '+key)
    els.append({'id': v.get('id', 'via'+str(i)), 'kind': 'via',
                'net': v['net'], 'layers': {1,2}, 'g': via_shape(v)})
connectivity = {}
for net in sorted(HS):
    es = [e for e in els if e['net'] == net]
    parent = list(range(len(es)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i,a in enumerate(es):
        for j,b in enumerate(es[:i]):
            if a['layers'] & b['layers'] and a['g'].distance(b['g']) <= .02:
                parent[find(i)] = find(j)
    groups = {}
    for i,e in enumerate(es):
        groups.setdefault(find(i), []).append(e)
    pad_groups = [[e['id'] for e in es if e['kind'] in ('pad','testpad')]
                  for es in groups.values()]
    pad_groups = [g for g in pad_groups if g]
    islands = [[e['id'] for e in es] for es in groups.values()
               if not any(e['kind'] in ('pad','testpad') for e in es)]
    connectivity[net] = {'pad_groups': pad_groups, 'unattached_copper_groups': islands,
                         'passed': len(pad_groups) == 1 and not islands}
    if not connectivity[net]['passed']:
        errors.append({'kind': 'connectivity', 'net': net, 'details': connectivity[net]})
# Compare actual line copper and centerline sets. This permits merged/segmented
# collinear primitives but rejects unintended stubs/autorouter changes.
equivalence = []
for net in sorted(HS):
    for layer in (1,2):
        expected = [t for t in R['tracks'] if t['net']==net and t['layer']==layer]
        actual = [t for t in A['lines'] if t['net']==net and t['layer']==layer]
        ge = unary_union([track_shape(t) for t in expected])
        ga = unary_union([track_shape(t) for t in actual])
        ce = unary_union([LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]) for t in expected])
        ca = unary_union([LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]) for t in actual])
        if ge.is_empty and ga.is_empty: continue
        equal = not ge.is_empty and not ga.is_empty and ge.hausdorff_distance(ga)<=tol and ce.hausdorff_distance(ca)<=tol
        row = {'net':net, 'layer':layer, 'equivalent_within_mil':tol,
               'passed':bool(equal), 'expected_line_primitives':len(expected),
               'actual_line_primitives':len(actual),
               'expected_centerline_union_mm':ce.length*.0254,
               'actual_centerline_union_mm':ca.length*.0254}
        equivalence.append(row)
        if not equal: errors.append({'kind':'route_changed', **row})
expected_vias = R['vias'] + G['vias']
via_matches = []
used = set()
for v in expected_vias:
    candidates = [(i,a) for i,a in enumerate(A['vias'])
                  if i not in used and a['net']==v['net']
                  and math.hypot(a['x']-v['x'],a['y']-v['y'])<=tol
                  and abs(a['diameter']-v['diameter'])<=tol
                  and abs(a['holeDiameter']-v['holeDiameter'])<=tol]
    match = candidates[0] if candidates else None
    row = {'tag':v.get('tag'), 'net':v['net'], 'expected_xy_mil':[v['x'],v['y']],
           'process_group':v.get('process_group'), 'matched':bool(match)}
    if match:
        used.add(match[0]); row['native_id']=match[1].get('id',match[0])
    else: errors.append({'kind':'missing_or_changed_planned_via', **row})
    via_matches.append(row)
extra_hs_vias = [v for i,v in enumerate(A['vias']) if v['net'] in HS and i not in used]
if extra_hs_vias: errors.append({'kind':'unexpected_usb_vias','vias':extra_hs_vias})
# Actual native copper for the approved GND stubs must also exist.
ground_stub_checks = []
for t in G['tracks']:
    actual = [x for x in A['lines'] if x['net']=='GND' and x['layer']==t['layer']]
    ga = unary_union([track_shape(x) for x in actual])
    missing = track_shape(t).difference(ga.buffer(tol))
    ok = missing.is_empty
    ground_stub_checks.append({'tag':t.get('tag'),'passed':ok})
    if not ok: errors.append({'kind':'missing_planned_ground_stub','tag':t.get('tag')})
# Foreign copper clearance only for HS line/via copper; existing package pad
# geometry is not a general all-board DRC and shapes are conservative.
hs_copper = [e for e in els if e['net'] in HS and e['kind'] in ('line','via')]
clearance_errors = []
minimum_clearance = None
for a in hs_copper:
    for b in els:
        if a['net']==b['net'] or not a['layers'] & b['layers']: continue
        # Avoid reporting each HS-HS pair twice.
        if b in hs_copper and str(a['id']) >= str(b['id']): continue
        distance = a['g'].distance(b['g'])
        if minimum_clearance is None or distance<minimum_clearance['distance_mil']:
            minimum_clearance={'usb':a['id'],'usb_net':a['net'],'other':b['id'],
                               'other_net':b['net'],'distance_mil':distance,'distance_mm':distance*.0254}
        if distance < 6-tol:
            clearance_errors.append({'usb':a['id'],'usb_net':a['net'],
                                     'other':b['id'],'other_net':b['net'],
                                     'distance_mil':distance})
if clearance_errors: errors.append({'kind':'usb_foreign_copper_clearance','count':len(clearance_errors)})
unmodeled = {k:len(A.get(k,[])) for k in ('arcs','polygons','pours','copperRegions') if A.get(k)}
if unmodeled: notices.append({'unmodeled_geometry':unmodeled})
if pad_dimension_fallbacks: notices.append({'catalog_dimension_fallbacks':pad_dimension_fallbacks})
equivalent = all(e['passed'] for e in equivalence) and not extra_hs_vias and all(v['matched'] for v in via_matches if v['net'] in HS)
out = {
    'schema':'calxus.native-usb-audit.v1',
    'source_copper':str(copper_path), 'source_pads':str(pads_path),
    'sha256_copper':hashlib.sha256(copper_path.read_bytes()).hexdigest(),
    'sha256_pads':hashlib.sha256(pads_path.read_bytes()).hexdigest(),
    'approved_route_sha256':hashlib.sha256((P/'usb_route_plan.json').read_bytes()).hexdigest(),
    'native_line_count':len(A['lines']), 'native_via_count':len(A['vias']),
    'usb_pad_connectivity':connectivity, 'approved_route_geometry_equivalence':equivalence,
    'planned_via_matches':via_matches, 'ground_stub_presence':ground_stub_checks,
    'usb_clearance_violations':clearance_errors,
    'minimum_usb_foreign_copper_clearance':minimum_clearance,
    'route_length_basis':'Approved route path lengths remain applicable only when native copper equivalence passes; centerline union lengths above are measured anew from native copper.',
    'active_path_lengths_mm':V['active_path_lengths'] if equivalent else None,
    'required_skew_limit_mm':.254, 'passed':not errors, 'errors':errors,'notices':notices,
    'limits':'Conservative 2D outer copper/pad audit, not field-solver timing or general native DRC. Does not prove internal plane continuity, plating, filled/capped via processing, mask/paste/NPTH clearance, unexported arcs/polygons/pours, or USB signal/EMI/software compatibility. Approved route lengths include ideal1.6mm barrels; package/cable internal delays excluded.'
}
output_path.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'lines':len(A['lines']),'vias':len(A['vias']),
                  'connectivity_passed':all(x['passed'] for x in connectivity.values()),
                  'native_route_equivalent':equivalent,'errors':errors},indent=2))
raise SystemExit(bool(errors))
