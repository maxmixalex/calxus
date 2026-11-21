"""Read-only TP6 r6 placement check against saved native geometry/candidate.
Usage: python verify_tp6_r6.py COPPER_JSON PADS_JSON CANDIDATE_JSON OUTPUT_JSON
No native EDA mutations. Candidate copper is a snapshot, not final native DRC.
"""
import hashlib, json, math, sys
from pathlib import Path
try:
    from shapely.geometry import Point, LineString, Polygon, box
except ImportError:
    sys.path.insert(0, '/tmp/calxus_deps')
    from shapely.geometry import Point, LineString, Polygon, box
from shapely.affinity import rotate, translate, scale

if len(sys.argv) != 5:
    raise SystemExit(__doc__)
cp, pp, sp, op = map(Path, sys.argv[1:])
base = Path(__file__).resolve().parent
corridor_path = base / 'usb_copper_corridors.json'
design_path = base / 'calxus_design_input.json'
C, P, S, R, D = [json.loads(p.read_text()) for p in (cp, pp, sp, corridor_path, design_path)]
assert C['units'] == P['units'] == R['units'] == 'mil'
assert R['layer'] == 2
tp = next(p for p in D['parts'] if p['ref'] == 'TP6')
assert tp['pins'] == {'1': '3V3'} and tp['pcb_layer'] == 'BOTTOM'
assert tp['placement_mm'] == [28.0, 23.5]
old, new, radius = [29, 23], tp['placement_mm'], .5
obstacles = []
def add(id, net, layers, kind, geometry):
    obstacles.append(dict(id=id, net=net, layers=set(layers), kind=kind, geometry=geometry))
def pad_shape(p):
    raw = p.get('pad')
    if raw and raw[0] == 'POLYGON':
        vals = [v for v in raw[1] if isinstance(v, (int, float))]
        return scale(Polygon(list(zip(vals[::2], vals[1::2]))), .0254, .0254, origin=(0, 0))
    w, h = p['width']*.0254, p['height']*.0254
    shape = p.get('shape', raw[0] if raw else 'RECT')
    if shape == 'ELLIPSE':
        g = scale(Point(0,0).buffer(1, resolution=64), w/2, h/2)
    elif shape == 'OVAL':
        g = (LineString([(-(w-h)/2,0), ((w-h)/2,0)]).buffer(h/2)
             if w >= h else LineString([(0,-(h-w)/2), (0,(h-w)/2)]).buffer(w/2))
    else:
        g = box(-w/2,-h/2,w/2,h/2)
    return translate(rotate(g,p['rotation'],origin=(0,0)),p['x']*.0254,p['y']*.0254)
for c in P['components']:
    for p in c['pads']:
        add(c['ref']+'.'+str(p['number']),p['net'],[1,2] if p['layer']==12 else [p['layer']],'pad',pad_shape(p))
for p in P['testpads']:
    if p['ref'] != 'TP6':
        add(p['ref'],p['net'],[p['layer']],'testpad',pad_shape(p))
for t in C['lines']:
    add(t['id'],t['net'],[t['layer']],'native_line',LineString([(t['x1']*.0254,t['y1']*.0254),(t['x2']*.0254,t['y2']*.0254)]).buffer(t['width']*.0254/2))
for v in C['vias']:
    add(v['id'],v['net'],[1,2],'native_via',Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2))
for i,t in enumerate(S['result']['traces']):
    add('candidate_trace_'+str(i),t['net'],[t['layer']],'candidate_trace',LineString(t['path']).buffer(t['width']/2))
for i,v in enumerate(S['result']['vias']):
    add('candidate_via_'+str(i),v['net'],[1,2],'candidate_via',Point(v['location']).buffer(v['size'][0]/2))
corridors = [scale(Polygon(p['exterior'],p.get('holes',[])),.0254,.0254,origin=(0,0)) for p in R['polygons']]
def closest(xy, layer, pad_radius):
    found=[]
    for e in obstacles:
        if layer in e['layers'] and e['net'] != '3V3':
            found.append((Point(xy).distance(e['geometry'])-pad_radius,e))
    gap,e=min(found,key=lambda v:v[0])
    return dict(id=e['id'],net=e['net'],kind=e['kind'],copper_gap_mm=gap)
no_wires = {name:min(Point(xy).distance(g) for g in corridors)-radius for name,xy in [('old',old),('new',new)]}
bottom = closest(new,2,radius)
top = closest(new,1,0)
top_same_net_overlap = [e['id'] for e in obstacles if e['kind']=='pad' and e['net']=='3V3' and 1 in e['layers'] and e['geometry'].contains(Point(new))]
report = dict(schema='calxus.tp6-r6-geometric-check.v1',design_revision=D['revision'],
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (cp,pp,sp,corridor_path,design_path)},
    old_xy_mm=old,new_xy_mm=new,net='3V3',layer=2,testpad_diameter_mm=1,
    pad_to_no_wires_mm=no_wires,native_track_to_prohibited_region_rule_mm=.3,
    new_pad_clearance_exceeds_rule=no_wires['new']>.3,
    nearest_bottom_foreign_copper=bottom,
    same_xy_top_foreign_copper_center_distance=top,
    top_same_net_pads_containing_new_testpad_center=top_same_net_overlap,
    candidate_traces=len(S['result']['traces']),candidate_vias=len(S['result']['vias']),
    passed=no_wires['new']>.3 and bottom['copper_gap_mm']>.1524,
    via_process_note='TP6 itself is a bottom copper test pad. Its new center is under C7.1 top SMD copper. Do not place an ordinary through via at this center: that would add an unapproved via-in-pad site. Route a short bottom stub to an external via that clears SMD copper/paste, or separately review any additional filled/capped via process.',
    limits='Saved candidate plus previously audited native outer copper/pads only; not a new native commit, full DRC, or proof of final route completion. Moving TP6 does not modify the frozen USB/GND route plans. All final clearances require fresh committed native data.')
op.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('passed','pad_to_no_wires_mm','nearest_bottom_foreign_copper','same_xy_top_foreign_copper_center_distance','top_same_net_pads_containing_new_testpad_center')},indent=2))
raise SystemExit(not report['passed'])
