"""Independent GND pad-to-through-via connectivity and copper corridor check."""
import json,sys,math,hashlib
from pathlib import Path
import numpy as np
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps');import shapely
from shapely.geometry import Point,LineString,box,Polygon
from shapely.affinity import rotate,translate
P=Path(__file__).parent;E=P.parent/'evidence';R=json.loads((P/'ground_stitch_plan.json').read_text());HS=json.loads((P/'usb_route_plan.json').read_text());A=json.loads((E/'pcb-components-pads-r5-planned.json').read_text());D=json.loads((P/'calxus_design_input.json').read_text());C=json.loads((E/'eda_parts_catalog_full.json').read_text());refs={p['ref']:p for p in D['parts']};els=[];holes=[]
for c in A['components']:
 lib={p['padNumber']:p for p in C[refs[c['ref']]['lcsc']]['footprint']['pads']}
 for p in c['pads']:
  q=lib[p['number']]
  if q.get('holeType')=='ROUND':holes.append({'name':c['ref']+'.'+p['number'],'x':p['x'],'y':p['y'],'r':q['holeDiameter']/2})
  if p.get('net')!='GND':continue
  g=box(-q['width']/2,-q['height']/2,q['width']/2,q['height']/2);g=rotate(g,c['rotation']+q['rotation'],origin=(0,0));g=translate(g,p['x'],p['y']);els.append({'name':c['ref']+'.'+p['number'],'g':g,'layers':{1,2} if p['layer']==12 else {p['layer']},'pad':True,'via':False})
for t in R['tracks']:els.append({'name':t['tag'],'g':LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]).buffer(t['width']/2),'layers':{t['layer']},'pad':False,'via':False})
for v in R['vias']+[v for v in HS['vias'] if v['net']=='GND']:els.append({'name':v['tag'],'g':Point(v['x'],v['y']).buffer(v['diameter']/2),'layers':{1,2},'pad':False,'via':True})
parent=list(range(len(els)))
def find(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
for i,a in enumerate(els):
 for j,b in enumerate(els[:i]):
  if a['layers']&b['layers'] and a['g'].distance(b['g'])<.01:parent[find(i)]=find(j)
checks=[]
for row in R['pad_connections']:
 i=next(i for i,e in enumerate(els) if e['name']==row['pad']);vias=[e['name'] for j,e in enumerate(els) if e['via'] and find(j)==find(i)];checks.append({'pad':row['pad'],'connected_through_vias':vias,'connected':bool(vias)})
 assert vias,row
hole_viol=[]
for v in R['vias']:
 for h in holes:
  d=math.hypot(v['x']-h['x'],v['y']-h['y'])-v['holeDiameter']/2-h['r']
  if d<.45/.0254-.02:hole_viol.append({'via':v['tag'],'hole':h['name'],'edge_distance_mm':d*.0254})
assert not hole_viol,hole_viol
assert not R['unresolved'] and not R['geometry_violations']
corr=json.loads((P/'usb_copper_corridors.json').read_text());assert not corr['preexisting_conflicts']
out={'plan_sha256':hashlib.sha256((P/'ground_stitch_plan.json').read_bytes()).hexdigest(),'critical_ground_pad_count':len(checks),'every_target_reaches_through_via':all(c['connected'] for c in checks),'checks':checks,'new_vias':len(R['vias']),'VIPPO_vias':[v for v in R['vias'] if v['process_group']=='VIPPO_EP'],'new_top_segments':len(R['tracks']),'reported_geometry_violations':R['geometry_violations'],'via_to_existing_round_pad_hole_0p45mm_violations':hole_viol,'corridor_preexisting_conflicts':corr['preexisting_conflicts'],'scope':'Checks geometry and local pad-to-via paths in proposed r5 overlay. Does not assert actual inner GND copper has been poured or native DRC passed.'}
(P/'ground_stitch_validation.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ['checks','VIPPO_vias']},indent=2))
