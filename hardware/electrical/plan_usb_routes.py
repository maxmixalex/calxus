"""Plan three USB2 pairs using actual JLCEDA pad centers; all dimensions mil.
Requires numpy, shapely; outputs track/via instructions, never edits EDA.
"""
import sys,math,json,heapq,itertools
from pathlib import Path
import numpy as np
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps');import shapely
from shapely.geometry import Point,Polygon,LineString,box
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
P=Path(__file__).parent;E=P.parent/'evidence'
D=json.loads((P/'usb_route_input_r4.json').read_text());CAT=json.loads((E/'eda_parts_catalog_full.json').read_text());ACT=json.loads((E/'pcb-components-pads-r4-actual.json').read_text());REF={p['ref']:p for p in D['parts']};COM={p['ref']:p for p in ACT['components']}
W=9.53125;GAP=6.0;CLR=6.0;VIA_D=19.68503937;VIA_DRILL=7.87401575;HALF=(W+GAP)/2;STEP=4.0
objs=[];pads={};tracks=[];via_list=[];warnings=[]
for c in ACT['components']:
 fp=CAT[REF[c['ref']]['lcsc']]['footprint'];lib={}
 for lp in fp['pads']:lib.setdefault(lp['padNumber'],[]).append(lp)
 for pad in c['pads']:
  lp=lib[pad['number']][0];w=lp['width'];h=lp['height'];shape=lp['shape']
  # Rectangular bounding polygons conservatively include rounded pad corners.
  geom=box(-w/2,-h/2,w/2,h/2);geom=rotate(geom,c['rotation']+lp['rotation'],origin=(0,0));geom=translate(geom,pad['x'],pad['y'])
  layers=[1,2] if pad['layer']==12 else [pad['layer']]
  obj={'kind':'pad','ref':c['ref'],'pin':pad['number'],'net':pad.get('net',''),'geom':geom,'layers':layers}
  objs.append(obj);pads.setdefault((c['ref'],pad['number']),[]).append(pad)
for p in D['parts']:
 if p.get('pcb_only'):
  x,y=[v/.0254 for v in p['placement_mm']];objs.append({'kind':'testpad','ref':p['ref'],'pin':'1','net':p['value'],'geom':Point(x,y).buffer(19.685),'layers':[2]})
for i,(x,y) in enumerate(D['pcb_mount_holes_mm']):objs.append({'kind':'keepout','ref':'H'+str(i+1),'pin':'','net':'','geom':Point(x/.0254,y/.0254).buffer(3/.0254),'layers':[1,2]})
def pad(ref,n):
 p=pads[(ref,str(n))][0];return (p['x'],p['y'])
def obstacles(layer,exclude,inflate=0):
 gs=[o['geom'] for o in objs if layer in o['layers'] and o.get('net') not in exclude]
 return unary_union(gs).buffer(inflate,quad_segs=4)
def path_clear(net,layer,points,width=W):
 line=LineString(points);bad=[]
 for o in objs:
  if layer in o['layers'] and o.get('net')!=net and line.distance(o['geom'])<width/2+CLR-.02:bad.append(o['ref']+'.'+o.get('pin',''))
 return bad

def add_path(net,layer,pts,tag,validate=True):
 pts=[tuple(map(float,p)) for p in pts];pts=[p for i,p in enumerate(pts) if i==0 or math.dist(p,pts[i-1])>1e-6]
 if len(pts)<2:return
 bad=path_clear(net,layer,pts)
 if bad and validate:raise ValueError(tag+' blocked by '+str(bad))
 for a,b in zip(pts,pts[1:]):
  tracks.append({'net':net,'layer':layer,'x1':round(a[0],5),'y1':round(a[1],5),'x2':round(b[0],5),'y2':round(b[1],5),'width':W,'tag':tag})
 objs.append({'kind':'track','ref':tag,'pin':'','net':net,'geom':LineString(pts).buffer(W/2,cap_style=1,join_style=2),'layers':[layer]})

def add_via(net,xy,tag):
 geom=Point(*xy).buffer(VIA_D/2,quad_segs=8)
 bad=[o['ref']+'.'+o.get('pin','') for o in objs if o.get('net')!=net and geom.distance(o['geom'])<CLR-.02]
 if bad:raise ValueError(tag+' via blocked '+str(bad))
 via_list.append({'net':net,'x':xy[0],'y':xy[1],'diameter':VIA_D,'holeDiameter':VIA_DRILL,'fromLayer':1,'toLayer':2,'tag':tag})
 objs.append({'kind':'via','ref':tag,'pin':'','net':net,'geom':geom,'layers':[1,2]})

ports={
 'UP':{'p':'USB_UP_DP','m':'USB_UP_DM','aP':(600,730),'aM':(626,730),'bP':(520,800),'bM':(520,826),'aEscape':(0,1),'bEscape':(1,0),'side':1,'gnd':[(660,730),(520,860)]},
 'NATIVE':{'p':'USB_NATIVE_DP','m':'USB_NATIVE_DM','aP':(756,730),'aM':(730,730),'bP':(2440,1240),'bM':(2440,1266),'aEscape':(0,1),'bEscape':(-1,0),'side':-1,'gnd':[(790,730),(2400,1298)]},
 'A':{'p':'USB_A_DP','m':'USB_A_DM','aP':(860,700),'aM':(834,700),'bP':(1612,500),'bM':(1586,500),'aEscape':(0,-1),'bEscape':(0,1),'side':1,'gnd':[(894,700),(1646,500)]}}
for name,q in ports.items():
 for k,n in [('aP','p'),('aM','m'),('bP','p'),('bM','m')]:add_via(q[n],q[k],name+'_'+k)
for name,q in ports.items():
 for i,xy in enumerate(q['gnd']):add_via('GND',xy,name+'_RETURN_'+str(i))

manual=[
('USB_UP_DP',[pad('J1','B6'),(225,797.2),(225,836.6),pad('J1','A6')],'UP_C_alias_P'),
('USB_UP_DM',[pad('J1','A7'),(302,816.9),(302,856.3),pad('J1','B7')],'UP_C_alias_M'),
('USB_UP_DP',[pad('J1','B6'),pad('D1',6),pad('D1',1),ports['UP']['bP']],'UP_C_ESD_P'),
('USB_UP_DM',[pad('J1','B7'),pad('D1',4),pad('D1',3),ports['UP']['bM']],'UP_C_ESD_M'),
('USB_UP_DP',[pad('U1',7),(662.4,770),(600,770),(584,750),ports['UP']['aP']],'UP_mux_fanout_P'),
('USB_UP_DM',[pad('U1',9),(612.4,650),ports['UP']['aM']],'UP_mux_fanout_M'),
('USB_NATIVE_DP',[pad('U1',6),(712.4,770),(756,770),ports['NATIVE']['aP']],'NATIVE_mux_fanout_P'),
('USB_NATIVE_DM',[pad('U1',10),(662.4,650),ports['NATIVE']['aM']],'NATIVE_mux_fanout_M'),
('USB_NATIVE_DP',[ports['NATIVE']['bP'],pad('D2',6),pad('D2',1),(2661.2,1195),(2861,1195),(2861,1249.2),pad('J3',3)],'NATIVE_ESD_tail_P'),
('USB_NATIVE_DM',[ports['NATIVE']['bM'],(2440,1320),(2520,1320),pad('D2',4),pad('D2',3),(2633.8,1394.6),(2715,1394.6),pad('J3',2)],'NATIVE_ESD_tail_M'),
('USB_A_DP',[pad('U1',5),(762.4,795),(780,777.4),(780,754),(872.5,754),(872.5,700),ports['A']['aP']],'A_mux_fanout_P'),
('USB_A_DM',[pad('U1',11),(712.4,650),ports['A']['aM']],'A_mux_fanout_M'),
('USB_A_DP',[ports['A']['bP'],pad('D3',1),pad('D3',6),pad('J2',3)],'A_ESD_connector_P'),
('USB_A_DM',[ports['A']['bM'],(1574,473),(1537.4,473),pad('D3',3),pad('D3',4),pad('J2',2)],'A_ESD_connector_M')]
for net,pts,tag in manual:
 try:add_path(net,1,pts,tag)
 except ValueError as e:warnings.append(str(e));add_path(net,1,pts,tag,validate=False)

# A* grid on bottom. Corner-cutting is prohibited; line simplification later retains line-of-sight checks.
def astar(start,end,ob):
 nx=int(80/.0254/STEP)+1;ny=int(42/.0254/STEP)+1
 xs=np.arange(nx)*STEP;ys=np.arange(ny)*STEP;xx,yy=np.meshgrid(xs,ys)
 blocked=shapely.intersects_xy(ob,xx,yy);blocked[:3,:]=True;blocked[-3:,:]=True;blocked[:,:3]=True;blocked[:,-3:]=True
 s=(round(start[0]/STEP),round(start[1]/STEP));g=(round(end[0]/STEP),round(end[1]/STEP))
 # Exempt exact short grid connectors only when line-of-sight validates them.
 for k in [s,g]:blocked[k[1],k[0]]=False
 dirs=[(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
 heap=[(math.dist(s,g),0,s,-1)];best={(s,-1):0};prev={};done=None
 while heap:
  _,cost,k,d=heapq.heappop(heap);state=(k,d)
  if cost!=best.get(state):continue
  if k==g:done=state;break
  for nd,(dx,dy) in enumerate(dirs):
   n=(k[0]+dx,k[1]+dy)
   if n[0]<0 or n[1]<0 or n[0]>=nx or n[1]>=ny or blocked[n[1],n[0]]:continue
   if dx and dy and (blocked[k[1],n[0]] or blocked[n[1],k[0]]):continue
   nc=cost+(1.41421356237 if dx and dy else 1)+(0 if d in [-1,nd] else .6)
   ns=(n,nd)
   if nc<best.get(ns,float('inf')):
    best[ns]=nc;prev[ns]=state;heapq.heappush(heap,(nc+math.dist(n,g),nc,n,nd))
 if done is None:raise RuntimeError('no center route')
 path=[];st=done
 while st in prev:path.append((st[0][0]*STEP,st[0][1]*STEP));st=prev[st]
 path.append((st[0][0]*STEP,st[0][1]*STEP));path.reverse();path=[start]+path+[end]
 # Greedy exact line-of-sight shortcut smooths only where the full pair envelope stays clear.
 out=[path[0]];i=0
 while i<len(path)-1:
  j=len(path)-1
  while j>i+1 and LineString([path[i],path[j]]).intersects(ob):j-=1
  out.append(path[j]);i=j
 return out

def center(a,b):return ((a[0]+b[0])/2,(a[1]+b[1])/2)
def vadd(a,b,s):return (a[0]+s*b[0],a[1]+s*b[1])
main_records={}
for name in ['UP','A','NATIVE']:
 q=ports[name];ac=center(q['aP'],q['aM']);bc=center(q['bP'],q['bM']);ae=q['aEscape'];be=q['bEscape']
 aa=vadd(ac,ae,50);bb=vadd(bc,be,50)
 obs=obstacles(2,{q['p'],q['m']},W+GAP/2+CLR+.5)
 mid=astar(aa,bb,obs)
 ctr=[vadd(ac,ae,30)]+mid+[vadd(bc,be,30)]
 line=LineString(ctr);plus=line.offset_curve(q['side']*HALF,join_style=2);minus=line.offset_curve(-q['side']*HALF,join_style=2)
 if plus.geom_type!='LineString' or minus.geom_type!='LineString':raise ValueError('offset split '+name)
 pp=[q['aP'],vadd(q['aP'],ae,15)]+list(plus.coords)+[vadd(q['bP'],be,15),q['bP']]
 mm=[q['aM'],vadd(q['aM'],ae,15)]+list(minus.coords)+[vadd(q['bM'],be,15),q['bM']]
 for net,points,tag in [(q['p'],pp,name+'_MAIN_P'),(q['m'],mm,name+'_MAIN_M')]:
  try:add_path(net,2,points,tag)
  except ValueError as e:warnings.append(str(e));add_path(net,2,points,tag,validate=False)
 main_records[name]={'centerline':ctr,'p_length_mil':LineString(pp).length,'m_length_mil':LineString(mm).length}
# Report geometric collisions excluding intentional same-net copper overlap.
viol=[]
for tr in tracks:
 line=LineString([(tr['x1'],tr['y1']),(tr['x2'],tr['y2'])])
 for o in objs:
  if tr['layer'] in o['layers'] and o.get('net')!=tr['net'] and line.distance(o['geom'])<W/2+CLR-.02:
   viol.append({'track':tr['tag'],'other':o['ref'],'net':tr['net'],'distance_mil':round(line.distance(o['geom']),4)})
lengths={}
for net in [q[k] for q in ports.values() for k in ['p','m']]:lengths[net]=sum(math.hypot(t['x2']-t['x1'],t['y2']-t['y1']) for t in tracks if t['net']==net)
result={'status':'DRAFT_REQUIRES_GEOMETRIC_CLEARANCE_REVIEW' if viol else 'GEOMETRY_CLEAR_PENDING_NATIVE_EDA_DRC','units':'mil','layers':{'1':'L1 top','2':'L4 bottom'},'width':W,'pair_edge_gap':GAP,'clearance':CLR,'tracks':tracks,'vias':via_list,'main_routes':main_records,'total_net_copper_length_mil':lengths,'warnings':warnings,'clearance_violations':viol,'important':'Includes conservative pad geometry and declared test pads. Board planes, manufacture and actual EDA DRC remain required. Totals include USB-C duplicate pad stubs; active paths are assessed separately.'}
(P/'usb_route_plan.json').write_text(json.dumps(result,indent=2));print('tracks',len(tracks),'vias',len(via_list),'violations',len(viol));print('\n'.join(warnings));print(json.dumps(lengths,indent=2))
