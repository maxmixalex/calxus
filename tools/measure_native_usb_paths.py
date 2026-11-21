#!/usr/bin/env python3
"""Measure actual source centerline paths from a reopened candidate epro2.

This is offline source geometry, not native DRC, electrical-delay or CAM signoff.
SIL follows U1 to R7/R8 plus the resistor output to U2; R9 pull-up is excluded.
"""
import argparse,hashlib,heapq,json,math
from pathlib import Path
from check_native_candidate_geometry import load,records,MM,Point,LineString
from shapely.ops import nearest_points
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('archive',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();D=load(args.archive)
stack=sorted([(json.loads(h['id'])[1],p)for h,p in records(D['pcb'],'LAYER_PHYS')],key=lambda x:x[1]['zIndex']);z=0;centers={}
for layer,p in stack:
 thickness=p['thickness']*MM;centers[layer]=z+thickness/2;z+=thickness
BARREL=abs(centers[2]-centers[1]);SOURCE={'kind':'offline-native-archive-source','archive':str(args.archive),'archiveSHA256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),'epruSHA256':hashlib.sha256(D['source']).hexdigest()}
class Graph:
 def __init__(self):self.a={}
 def __getitem__(self,k):return self.a[k]
 def has_edge(self,a,b):return a in self.a and b in self.a[a]
 def add_edge(self,a,b,**x):self.a.setdefault(a,{})[b]=x;self.a.setdefault(b,{})[a]=x
class NX:
 Graph=Graph
 class NoPath(Exception):pass
 NetworkXNoPath=NoPath;NodeNotFound=NoPath
 @staticmethod
 def shortest_path(g,start,end,weight='weight'):
  if start not in g.a or end not in g.a:raise NX.NoPath('endpoint not attached')
  dist={start:0};prev={};q=[(0,0,start)];serial=0
  while q:
   d,_,u=heapq.heappop(q)
   if d!=dist[u]:continue
   if u==end:
    path=[u]
    while u in prev:u=prev[u];path.append(u)
    return path[::-1]
   for v,e in g[u].items():
    dd=d+e[weight]
    if dd<dist.get(v,float('inf')):dist[v]=dd;prev[v]=u;serial+=1;heapq.heappush(q,(dd,serial,v))
  raise NX.NoPath('disconnected')
nx=NX
from shapely.ops import nearest_points
def measure(net,start,end):
 seg=[];vias=[];pads=[e for e in D['pads']if e['net']==net]
 def addline(t,scale,tag):
  a=(t['x1']*scale,t['y1']*scale);b=(t['x2']*scale,t['y2']*scale)
  if math.dist(a,b)>1e-7:seg.append(dict(tag=tag,layer=t['layer'],g=LineString([a,b]),w=t['width']*scale,points=[Point(a),Point(b)]))
 for t in D['lines']:
  if t['net']==net:addline(t,.0254,t['id'])
 for v in D['vias']:
  if v['net']==net:vias.append(dict(tag=v['id'],xy=(v['x']*.0254,v['y']*.0254),d=v['diameter']*.0254))
 G=nx.Graph();connectors=[]
 def key(layer,p):return (layer,round(p.x,7),round(p.y,7))
 def edge(a,b,w,kind,tag):
  if not G.has_edge(a,b)or G[a][b]['weight']>w:G.add_edge(a,b,weight=w,kind=kind,tag=tag)
 for i,s in enumerate(seg):
  for t in seg[:i]:
   if s['layer']!=t['layer']:continue
   pa,pb=nearest_points(s['g'],t['g']);d=pa.distance(pb)
   if d<=(s['w']+t['w'])/2+.000001:
    s['points'].append(pa);t['points'].append(pb);connectors.append((key(s['layer'],pa),key(t['layer'],pb),d,'join',s['tag']+'|'+t['tag']))
 for v in vias:
  vp=Point(v['xy'])
  edge(key(1,vp),key(2,vp),BARREL,'barrel',v['tag'])
  for s in seg:
   q=s['g'].interpolate(s['g'].project(vp));d=q.distance(vp)
   if d<=(v['d']+s['w'])/2+.000001:
    s['points'].append(q);connectors.append((key(s['layer'],q),key(s['layer'],vp),d,'viaLanding',v['tag']))
 for p in pads:
  pp=Point(p['xy']);pk=('pad',p['id'])
  for s in seg:
   if s['layer']not in p['layers']or s['g'].distance(p['g'])>s['w']/2+.000001:continue
   q=s['g'].interpolate(s['g'].project(pp));s['points'].append(q);connectors.append((pk,key(s['layer'],q),pp.distance(q),'padLanding',p['id']))
 for s in seg:
  pts=sorted({key(s['layer'],q):q for q in s['points']}.values(),key=lambda q:s['g'].project(q))
  for a,b in zip(pts,pts[1:]):edge(key(s['layer'],a),key(s['layer'],b),a.distance(b),'trace',s['tag'])
 for a,b,w,k,t in connectors:edge(a,b,w,k,t)
 try:path=nx.shortest_path(G,('pad',start),('pad',end),weight='weight')
 except (nx.NetworkXNoPath,nx.NodeNotFound)as e:return dict(net=net,start=start,end=end,error=str(e))
 edges=[dict(a=a,b=b,**G[a][b])for a,b in zip(path,path[1:])];planar=sum(e['weight']for e in edges if e['kind']!='barrel');barrel=sum(e['weight']for e in edges if e['kind']=='barrel')
 return dict(net=net,start=start,end=end,planar_mm=planar,barrel_mm=barrel,total_mm=planar+barrel,viaTransitions=sum(e['kind']=='barrel'for e in edges),edges=edges)
definitions={'SIL_DP_upstream':('USB_SIL_DP','U1.4','R7.1'),'SIL_DM_upstream':('USB_SIL_DM','U1.12','R8.1'),'SIL_DP_device':('SIL_DP','R7.2','U2.6'),'SIL_DM_device':('SIL_DM','R8.2','U2.7'),'UART_DP':('USB_UART_DP','U1.3','U3.7'),'UART_DM':('USB_UART_DM','U1.13','U3.8'),'UP_DP':('USB_UP_DP','J1.A6','U1.7'),'UP_DM':('USB_UP_DM','J1.A7','U1.9'),'UP_B_DP':('USB_UP_DP','J1.B6','U1.7'),'UP_B_DM':('USB_UP_DM','J1.B7','U1.9'),'NATIVE_DP':('USB_NATIVE_DP','U1.6','J3.3'),'NATIVE_DM':('USB_NATIVE_DM','U1.10','J3.2'),'A_DP':('USB_A_DP','U1.5','J2.3'),'A_DM':('USB_A_DM','U1.11','J2.2')}
paths={k:measure(*v)for k,v in definitions.items()};pairs={}
for name,dp,dm in [('SIL',['SIL_DP_upstream','SIL_DP_device'],['SIL_DM_upstream','SIL_DM_device']),('UART',['UART_DP'],['UART_DM']),('UP',['UP_DP'],['UP_DM']),('UP_B',['UP_B_DP'],['UP_B_DM']),('NATIVE',['NATIVE_DP'],['NATIVE_DM']),('A',['A_DP'],['A_DM'])]:
 if any('error'in paths[k]for k in dp+dm):continue
 sides={side:{f:sum(paths[k][f]for k in keys)for f in ['planar_mm','barrel_mm','total_mm','viaTransitions']}for side,keys in [('DP',dp),('DM',dm)]};sides['skew_planar_mm']=sides['DP']['planar_mm']-sides['DM']['planar_mm'];sides['skew_including_barrels_mm']=sides['DP']['total_mm']-sides['DM']['total_mm'];pairs[name]=sides
combined={}
for orientation in ['A','B']:
 for destination in ['NATIVE','USB_A']:
  upstream='UP' if orientation=='A' else 'UP_B';downstream='NATIVE' if destination=='NATIVE'else 'A';name='TypeC_'+orientation+'_to_'+destination
  entry={side:{field:pairs[upstream][side][field]+pairs[downstream][side][field]for field in ['planar_mm','barrel_mm','total_mm','viaTransitions']}for side in ['DP','DM']}
  entry['skew_planar_mm']=entry['DP']['planar_mm']-entry['DM']['planar_mm'];entry['skew_including_barrels_mm']=entry['DP']['total_mm']-entry['DM']['total_mm'];entry['within_0254mm']=abs(entry['skew_including_barrels_mm'])<=.254;combined[name]=entry
report={'schema':'calxus.native-source-usb-centerline-paths.v2','source_archive_sha256':SOURCE['archiveSHA256'],'geometrySource':SOURCE,'barrel_length_mm':BARREL,'barrel_method':'Absolute L1/L4 copper center-plane Z difference from native LAYER_PHYS; excludes solder mask and half of each outer copper layer. Geometric path, not dielectric-adjusted electrical delay.','total_stack_including_masks_mm':z,'copper_layer_centers_mm':{str(k):centers[k]for k in [1,15,16,2]},'paths':paths,'pairs':pairs,'type_c_orientation_end_to_end_paths':combined,'applicable_skew_limit_mm':.254,'notes':['Planar copper length follows the shortest connected centerline graph including pad/via center landing distances, not the sum of all same-net copper.','SIL totals combine U1 to R7/R8 and resistor output to U2. Equal resistor bodies and R9 pull-up branch are excluded.','UP and UP_B explicitly measure J1.A6/A7 and J1.B6/B7 respectively. End-to-end paths include upstream plus selected MUX downstream traces, excluding matched internal silicon path.','Barrel counts are the actual layer transitions in each selected path.','Approved USB_UP repair removes the historical same-net wide-copper shortcut; all existing HS vias and the other four HS nets remain unchanged.','Geometric path matching is not an impedance-field or electromagnetic delay simulation. Native DRC and real CAM are separate evidence.'],'native_drc_verified':False,'cam_verified':False,'full_speed_pair_matching_passed':all('error'not in p for p in paths.values())and all(abs(pairs[n]['skew_including_barrels_mm'])<.254 for n in ['SIL','UART']),'all_usb_main_paths_within_0254mm':all(abs(p['skew_including_barrels_mm'])<.254 for p in pairs.values())and all(p['within_0254mm']for p in combined.values()),'historical_upstream_self_contact_resolved':{'deleted_old_line_ids':['1a6f28a2d6cd9325','517d0ae7cba763ef','02e07c79d1fc1f12','b6e1148e2fb122cf'],'approved_contract':'hardware/electrical/native-usb-up-repair.json','original_centerline_separation_mm':.07364694429482904,'original_width_mm':.24209502,'old_finding':'Wide-copper overlap created an unintended branch shortcut. Original evidence retained in validation/history/usb-up-wide-copper-shortcut-confirmation.json.'}}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'source_archive_sha256':SOURCE['archiveSHA256'],'barrel_length_mm':BARREL,'pairs':pairs,'type_c_end_to_end':combined,'full_speed_pair_matching_passed':report['full_speed_pair_matching_passed'],'all_usb_main_paths_within_0254mm':report['all_usb_main_paths_within_0254mm']},indent=2))
