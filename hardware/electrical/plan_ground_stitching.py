"""Plan critical local GND connections and USB outer-layer copper keepaway corridors.
No EDA operations. Coordinates are mil. Requires numpy and shapely.
"""
import json,math,sys,itertools,hashlib
from pathlib import Path
import numpy as np
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps');import shapely
from shapely.geometry import Point,LineString,box,Polygon
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
P=Path(__file__).parent;E=P.parent/'evidence'
D=json.loads((P/'calxus_design_input.json').read_text());CAT=json.loads((E/'eda_parts_catalog_full.json').read_text());ACT=json.loads((E/'pcb-components-pads-r5-planned.json').read_text());HS=json.loads((P/'usb_route_plan.json').read_text());REF={p['ref']:p for p in D['parts']}
VIA_D=.5/.0254;DRILL=.2/.0254;W=12.;CLR=6.;KEEP=.65/.0254
objects=[];padmap={};newtracks=[];newvias=[];reports=[];errors=[]
for c in ACT['components']:
 lib={p['padNumber']:p for p in CAT[REF[c['ref']]['lcsc']]['footprint']['pads']}
 # Root confirmed this final placement after the snapshot.
 shift_y=(13.1/.0254-c['y']) if c['ref']=='C14' else 0
 for p in c['pads']:
  q=lib[p['number']];x,y=p['x'],p['y']+shift_y;g=box(-q['width']/2,-q['height']/2,q['width']/2,q['height']/2);g=rotate(g,c['rotation']+q['rotation'],origin=(0,0));g=translate(g,x,y)
  z={'name':c['ref']+'.'+p['number'],'ref':c['ref'],'pin':p['number'],'net':p.get('net',''),'g':g,'layers':{1,2} if p['layer']==12 else {p['layer']},'kind':'pad','x':x,'y':y};objects.append(z);padmap[(c['ref'],p['number'])]=z
for d in D['parts']:
 if d.get('pcb_only'):
  x,y=[t/.0254 for t in d['placement_mm']];objects.append({'name':d['ref'],'net':d['value'],'g':Point(x,y).buffer(19.685),'layers':{2},'kind':'testpad'})
for i,(x,y) in enumerate(D['pcb_mount_holes_mm']):objects.append({'name':'H'+str(i+1),'net':'','g':Point(x/.0254,y/.0254).buffer(3/.0254),'layers':{1,2},'kind':'keepout'})
for i,t in enumerate(HS['tracks']):objects.append({'name':t['tag']+':'+str(i),'net':t['net'],'g':LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]).buffer(t['width']/2),'layers':{t['layer']},'kind':'hs_track'})
for v in HS['vias']:objects.append({'name':v['tag'],'net':v['net'],'g':Point(v['x'],v['y']).buffer(v['diameter']/2),'layers':{1,2},'kind':'hs_via','x':v['x'],'y':v['y']})
# All actual bottom HS copper, excluding 0.8mm radius transition zones around signal vias.
base=unary_union([o['g'] for o in objects if o['kind']=='hs_track' and 2 in o['layers']]);full_corridor=base.buffer(KEEP,quad_segs=8)
transitions=unary_union([Point(v['x'],v['y']).buffer(.8/.0254,quad_segs=8) for v in HS['vias'] if v['net']!='GND'])
corridor=full_corridor.difference(transitions)
preexisting=[{'object':o['name'],'kind':o['kind'],'net':o['net'],'overlap_mm2':o['g'].intersection(corridor).area*.0254**2} for o in objects if 2 in o['layers'] and o['kind'] not in ['hs_track','hs_via'] and o['g'].intersects(corridor)]
foreign_union={l:unary_union([o['g'] for o in objects if l in o['layers'] and o['net']!='GND']) for l in (1,2)}
all_smd_union=unary_union([o['g'] for o in objects if o['kind']=='pad' and 1 in o['layers']])
def collision(g,layers,net='GND'):
 if all(g.distance(foreign_union[l])>=CLR-.03 for l in layers):return []
 return [o['name'] for o in objects if layers&o['layers'] and o['net']!=net and g.distance(o['g'])<CLR-.03]
def via_ok(x,y,ep=False):
 g=Point(x,y).buffer(VIA_D/2)
 if not box(.5/.0254,.5/.0254,79.5/.0254,41.5/.0254).contains(g):return False
 if any(g.distance(foreign_union[l])<CLR-.03 for l in (1,2)):return False
 if g.intersects(corridor):return False
 # No solder-wicking overlap for ordinary ground vias; EP exceptions are VIPPO.
 if not ep and g.distance(all_smd_union)<8:return False
 # Respect drill-to-drill spacing for all vias (same net included).
 if any(math.hypot(x-v['x'],y-v['y'])<(.2+.2)/.0254 for v in HS['vias']+newvias):return False
 return True
def track_ok(pts,width=W):return LineString(pts).buffer(width/2).distance(foreign_union[1])>=CLR-.03
def addvia(x,y,tag,vippo=False):
 v={'net':'GND','x':round(x,5),'y':round(y,5),'diameter':VIA_D,'holeDiameter':DRILL,'fromLayer':1,'toLayer':2,'tag':tag,'process_group':'VIPPO_EP' if vippo else 'ORDINARY_TENTED'};newvias.append(v);objects.append({'name':tag,'net':'GND','g':Point(x,y).buffer(VIA_D/2),'layers':{1,2},'kind':'ground_via','x':x,'y':y});return v
def addtrack(pts,tag,width=W):
 for a,b in zip(pts,pts[1:]):
  if math.dist(a,b)<.001:continue
  newtracks.append({'net':'GND','layer':1,'x1':round(a[0],5),'y1':round(a[1],5),'x2':round(b[0],5),'y2':round(b[1],5),'width':width,'tag':tag})
 objects.append({'name':tag,'net':'GND','g':LineString(pts).buffer(width/2),'layers':{1},'kind':'ground_track'})
# Two filled/capped vias per exposed pad, selected in safe corners away from HS mainlines.
for ref,pin in [('U2','33'),('U3','17')]:
 p=padmap[(ref,pin)];xmin,ymin,xmax,ymax=p['g'].bounds
 cand=[]
 for x in np.arange(xmin+VIA_D/2+3,xmax-VIA_D/2-2,5):
  for y in np.arange(ymin+VIA_D/2+3,ymax-VIA_D/2-2,5):
   if via_ok(x,y,ep=True):cand.append((x,y))
 if not cand:raise ValueError('No EP via space '+ref)
 # Opposed points maximize separation; prefer symmetric center placement.
 best=max(itertools.combinations(cand,2),key=lambda ab:math.dist(*ab)-.25*math.dist(((ab[0][0]+ab[1][0])/2,(ab[0][1]+ab[1][1])/2),(p['x'],p['y'])))
 for i,(x,y) in enumerate(best):addvia(x,y,ref+'_EP_GND_'+str(i+1),True)
 reports.append({'pad':ref+'.'+pin,'status':'VIPPO_IN_PAD','vias':2,'track_length_mm':0})
# Give a local ground return to every decoupler, crystal load/reset cap and active/protection IC.
targets=[(f'C{i}','2') for i in range(1,23)]+[('D'+str(i),'2' if i<=3 else '3') for i in range(1,8)]+[('U1','8'),('U2','8'),('U2','18'),('U2','28'),('U3','2'),('U4','1'),('U4','2'),('U4','3'),('U4','4'),('U5','2'),('U6','2'),('U7','3'),('U8','3'),('U9','2'),('U10','2')]
# Priority ESD before caps gives its close via sharing preference.
targets.sort(key=lambda t:(0 if t[0].startswith('D') else 1 if t[0].startswith('U') else 2,t[0],t[1]))
for ref,pin in targets:
 if (ref,pin) not in padmap or padmap[(ref,pin)]['net']!='GND':continue
 p=padmap[(ref,pin)];start=(p['x'],p['y']);best=None
 # Reuse a nearby existing GND via if copper is short and clear.
 for v in HS['vias']+newvias:
  if v['net']!='GND' or math.dist(start,(v['x'],v['y']))>85:continue
  end=(v['x'],v['y'])
  for path in [[start,end],[start,(start[0],end[1]),end],[start,(end[0],start[1]),end]]:
   if not track_ok(path):continue
   score=sum(math.dist(a,b) for a,b in zip(path,path[1:]))
   if best is None or score<best[0]:best=(score,path,v)
 # Search radial pad-external positions, preferring a direct short trace.
 for radius in np.arange(28,96,4):
  for angle in np.arange(0,360,15):
   r=math.radians(angle);x=start[0]+radius*math.cos(r);y=start[1]+radius*math.sin(r)
   if not via_ok(x,y):continue
   path=[start,(x,y)]
   if not track_ok(path):continue
   score=radius+30
   if best is None or score<best[0]:best=(score,path,None)
  if best and radius+30>best[0]+4:break
 if best is None:
  # Try short Manhattan doglegs to a slightly farther local GND via.
  for radius in np.arange(80,141,8):
   for angle in np.arange(0,360,15):
    r=math.radians(angle);end=(start[0]+radius*math.cos(r),start[1]+radius*math.sin(r))
    if not via_ok(*end):continue
    for mid in [(start[0],end[1]),(end[0],start[1])]:
     path=[start,mid,end]
     if track_ok(path):
      score=sum(math.dist(a,b) for a,b in zip(path,path[1:]))
      if best is None or score<best[0]:best=(score,path,None)
   if best:break
 if best is None:errors.append({'pad':ref+'.'+pin,'reason':'No short clear pad-external GND via path'});continue
 _,path,v=best;tag=ref+'_'+pin+'_GND'
 if v is None:v=addvia(*path[-1],tag+'_V')
 addtrack(path,tag)
 reports.append({'pad':ref+'.'+pin,'status':'SHORT_TOP_TO_THROUGH_VIA','via_tag':v['tag'],'track_length_mm':sum(math.dist(a,b) for a,b in zip(path,path[1:]))*.0254})
# Final geometry against all pads, planned copper and all newly generated vias/tracks.
viol=[]
for o in objects:
 if o['kind'] not in ['ground_via','ground_track']:continue
 hits=collision(o['g'],o['layers'])
 if hits:viol.append({'new':o['name'],'other':hits})
 if 2 in o['layers'] and o['g'].intersects(corridor):viol.append({'new':o['name'],'other':['HS_0.65mm_corridor']})
result={'status':'GEOMETRY_CLEAR_PENDING_NATIVE_EDA_DRC' if not(viol or errors) else 'REVIEW_REQUIRED','units':'mil','width':W,'tracks':newtracks,'vias':newvias,'pad_connections':reports,'unresolved':errors,'geometry_violations':viol,'base_usb_plan_sha256':hashlib.sha256((P/'usb_route_plan.json').read_bytes()).hexdigest(),'process_required':'U2/U3 EP group VIPPO_EP MUST use epoxy filled, planarized and copper capped vias. Ordinary vias remain pad-external, tented. Actual plane connectivity requires native pour/DRC verification.','coordinate_overlay':'C14 moved from snapshot y13.0mm to root-confirmed13.1mm.'}
(P/'ground_stitch_plan.json').write_text(json.dumps(result,indent=2))
polys=[corridor] if corridor.geom_type=='Polygon' else list(corridor.geoms)
corr={'units':'mil','layer':2,'description':'L4 only: keep all unrelated outer-layer copper >=0.65mm from USB mainline copper; L3 continuous GND remains required. Excludes0.8mm-radius via transition areas; existing return-vias deliberately local. Does not block L1 or reference planes.','edge_clearance_mm':.65,'transition_exemption_radius_mm':.8,'polygons':[{'exterior':list(p.exterior.coords),'holes':[list(r.coords) for r in p.interiors]} for p in polys],'preexisting_conflicts':preexisting,'mainline_tracks':[t for t in HS['tracks'] if t['layer']==2],'exemptions':{'signal_vias':[v for v in HS['vias'] if v['net']!='GND'],'ground_return_vias':[v for v in HS['vias'] if v['net']=='GND']}}
(P/'usb_copper_corridors.json').write_text(json.dumps(corr,indent=2))
print(json.dumps({'vias':len(newvias),'VIPPO':sum(v['process_group']=='VIPPO_EP' for v in newvias),'tracks':len(newtracks),'connections':len(reports),'errors':errors,'violations':viol,'preexisting_corridor_conflicts':preexisting},indent=2))
