"""Independently verify route connectivity and path-length accounting in the exported plan."""
import json,math,sys,heapq,hashlib
from pathlib import Path
import numpy as np
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps');import shapely
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate,translate
P=Path(__file__).parent;E=P.parent/'evidence'
R=json.loads((P/'usb_route_plan.json').read_text());A=json.loads((E/'pcb-components-pads-r4-actual.json').read_text());D=json.loads((P/'calxus_design_input.json').read_text());C=json.loads((E/'eda_parts_catalog_full.json').read_text());parts={p['ref']:p for p in D['parts']}
N=sorted({t['net'] for t in R['tracks']});report={};elements=[]
for c in A['components']:
 lib={p['padNumber']:p for p in C[parts[c['ref']]['lcsc']]['footprint']['pads']}
 for p in c['pads']:
  if p.get('net') not in N:continue
  q=lib[p['number']];g=box(-q['width']/2,-q['height']/2,q['width']/2,q['height']/2);g=rotate(g,c['rotation']+q['rotation'],origin=(0,0));g=translate(g,p['x'],p['y'])
  elements.append({'name':c['ref']+'.'+p['number'],'net':p['net'],'layers':{1,2} if p['layer']==12 else {p['layer']},'g':g,'pad':True})
for i,t in enumerate(R['tracks']):elements.append({'name':'T'+str(i),'net':t['net'],'layers':{t['layer']},'g':LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]).buffer(t['width']/2,cap_style=1),'pad':False})
for i,v in enumerate(R['vias']):
 if v['net'] in N:elements.append({'name':'V'+str(i),'net':v['net'],'layers':{1,2},'g':Point(v['x'],v['y']).buffer(v['diameter']/2),'pad':False})
for net in N:
 els=[e for e in elements if e['net']==net];parent=list(range(len(els)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for i,a in enumerate(els):
  for j,b in enumerate(els[:i]):
   if a['layers']&b['layers'] and a['g'].distance(b['g'])<.01:parent[find(i)]=find(j)
 groups={}
 for i,e in enumerate(els):
  if e['pad']:groups.setdefault(find(i),[]).append(e['name'])
 report[net]={'connected_pad_groups':list(groups.values()),'all_pads_connected':len(groups)==1,'pad_count':sum(map(len,groups.values())),'net_copper_length_mil':sum(math.hypot(t['x2']-t['x1'],t['y2']-t['y1']) for t in R['tracks'] if t['net']==net)}
 assert len(groups)==1,(net,groups)
# Centerline graph shortest paths; pad-center endpoint definitions avoid accidental inclusion of inactive USB-C stub.
graph={}
def node(layer,x,y):return(layer,round(x,4),round(y,4))
def edge(a,b,w):graph.setdefault(a,[]).append((b,w));graph.setdefault(b,[]).append((a,w))
for t in R['tracks']:
 a=node(t['layer'],t['x1'],t['y1']);b=node(t['layer'],t['x2'],t['y2']);edge((t['net'],)+a,(t['net'],)+b,math.dist(a[1:],b[1:]))
for v in R['vias']:
 if v['net'] in N:edge((v['net'],)+node(1,v['x'],v['y']),(v['net'],)+node(2,v['x'],v['y']),1.6/.0254)
# T-junction where an endpoint lands on another segment (e.g. connector aliases) are explicitly segmented in source.
lookup={(c['ref'],p['number']):p for c in A['components'] for p in c['pads']}
def dist(net,sref,spin,tref,tpin):
 a=lookup[(sref,str(spin))];b=lookup[(tref,str(tpin))];start=(net,)+node(1,a['x'],a['y']);goal=(net,)+node(1,b['x'],b['y']);heap=[(0,start)];seen={start:0}
 while heap:
  d,k=heapq.heappop(heap)
  if k==goal:return d*.0254
  if d!=seen[k]:continue
  for v,w in graph.get(k,[]):
   nd=d+w
   if nd<seen.get(v,1e99):seen[v]=nd;heapq.heappush(heap,(nd,v))
 raise ValueError(('no centerline path',start,goal))
paths={}
for name,pnet,mnet,fr,fp,fm,to,tp,tm in [
 ('UP_A_orientation','USB_UP_DP','USB_UP_DM','J1','A6','A7','U1',7,9),
 ('UP_B_orientation','USB_UP_DP','USB_UP_DM','J1','B6','B7','U1',7,9),
 ('NATIVE','USB_NATIVE_DP','USB_NATIVE_DM','U1',6,10,'J3',3,2),
 ('USB_A','USB_A_DP','USB_A_DM','U1',5,11,'J2',3,2)]:
 pp=dist(pnet,fr,fp,to,tp);mm=dist(mnet,fr,fm,to,tm);paths[name]={'DP_mm':pp,'DM_mm':mm,'signed_skew_mm':pp-mm,'absolute_skew_mm':abs(pp-mm),'includes_via_barrel_mm':3.2}
for orient in ['A','B']:
 for tail in ['NATIVE','USB_A']:
  u=paths['UP_'+orient+'_orientation'];v=paths[tail];pp=u['DP_mm']+v['DP_mm'];mm=u['DM_mm']+v['DM_mm'];paths['USB_C_'+orient+'_to_'+tail]={'DP_mm':pp,'DM_mm':mm,'signed_skew_mm':pp-mm,'absolute_skew_mm':abs(pp-mm),'includes_via_barrel_mm':6.4}
assert max(x['absolute_skew_mm'] for x in paths.values())<=.254,paths
out={'route_plan_sha256':hashlib.sha256((P/'usb_route_plan.json').read_bytes()).hexdigest(),'all_usb_pads_connected':True,'net_checks':report,'active_path_lengths':paths,'route_geometry_violation_count':len(R['clearance_violations']),'limits':'Lengths use ideal trace centerlines plus four1.6mm via barrels per complete selected path. Connector/package internal lengths, mux silicon, actual dielectric/return-via delay and external cable skew not included. Pad-size shortcuts inside annuli are not a field-solver delay model. Native EDA DRC and hardware eye testing remain required.'}
(P/'usb_route_validation.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
