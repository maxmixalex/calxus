"""Measure actual native USB centerline paths; no ideal-plan length substitution.
Usage: python verify_native_usb_paths.py COPPER_JSON PADS_JSON OUTPUT_JSON
"""
import json,math,sys,heapq,hashlib
from pathlib import Path
try:
    from shapely.geometry import Point,LineString
except ImportError:
    sys.path.insert(0,'/tmp/calxus_deps')
    from shapely.geometry import Point,LineString
from shapely.ops import unary_union

if len(sys.argv)!=4:raise SystemExit(__doc__)
cp,pp,op=map(Path,sys.argv[1:]);C=json.loads(cp.read_text());P=json.loads(pp.read_text())
if C.get('units')!='mil' or P.get('units')!='mil':raise ValueError('mil required')
HS={b+s for b in ('USB_UP','USB_NATIVE','USB_A')for s in ('_DP','_DM')}
lookup={(c['ref'],str(p['number'])):p for c in P['components']for p in c['pads']}
specs=[('UP_A_orientation','USB_UP','J1','A6','A7','U1','7','9'),
       ('UP_B_orientation','USB_UP','J1','B6','B7','U1','7','9'),
       ('NATIVE','USB_NATIVE','U1','6','10','J3','3','2'),
       ('USB_A','USB_A','U1','5','11','J2','3','2')]
graph={};attachments=[]
def node(net,layer,x,y):return(net,layer,round(x,6),round(y,6))
def edge(a,b,w):
    graph.setdefault(a,[]).append((b,w));graph.setdefault(b,[]).append((a,w))
terminals={net:[] for net in HS}
for name,base,fr,fp,fm,to,tp,tm in specs:
    for suffix,sp,tp0 in [('_DP',fp,tp),('_DM',fm,tm)]:
        for ref,pin in [(fr,sp),(to,tp0)]:
            p=lookup[(ref,pin)];terminals[base+suffix].append((1,p['x'],p['y'],ref+'.'+pin))
for net in sorted(HS):
    vs=[v for v in C['vias']if v['net']==net]
    for layer in (1,2):
        ts=[t for t in C['lines']if t['net']==net and t['layer']==layer]
        segments=[LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])])for t in ts]
        endpoints=[Point(*xy)for s in segments for xy in (s.coords[0],s.coords[-1])]
        critical=[(v['x'],v['y'],'via:'+v['id'])for v in vs]+[(x,y,name)for l,x,y,name in terminals[net]if l==layer]
        all_attachments=[]
        for x,y,name in critical:
            point=Point(x,y);ds=[point.distance(s)for s in segments]
            if not ds or min(ds)>.11:raise ValueError(('No centerline attachment',net,layer,name,min(ds)if ds else None))
            i=min(range(len(ds)),key=ds.__getitem__);proj=segments[i].interpolate(segments[i].project(point))
            all_attachments.append((i,proj,point,name))
            attachments.append({'net':net,'layer':layer,'name':name,'offset_mil':ds[i]})
        for i,s in enumerate(segments):
            cuts=[0.0,s.length]
            cuts.extend(s.project(p)for p in endpoints if p.distance(s)<1e-6)
            cuts.extend(s.project(proj)for j,proj,point,name in all_attachments if j==i)
            cuts=sorted(set(round(x,8)for x in cuts))
            for a,b in zip(cuts,cuts[1:]):
                x=s.interpolate(a);y=s.interpolate(b)
                edge(node(net,layer,x.x,x.y),node(net,layer,y.x,y.y),b-a)
        for i,proj,point,name in all_attachments:
            edge(node(net,layer,point.x,point.y),node(net,layer,proj.x,proj.y),point.distance(proj))
    for v in vs:edge(node(net,1,v['x'],v['y']),node(net,2,v['x'],v['y']),1.6/.0254)
def distance(net,fr,fp,to,tp):
    a=lookup[(fr,fp)];b=lookup[(to,tp)];start=node(net,1,a['x'],a['y']);goal=node(net,1,b['x'],b['y'])
    heap=[(0,start)];seen={start:0}
    while heap:
        d,k=heapq.heappop(heap)
        if k==goal:return d*.0254
        if d!=seen[k]:continue
        for v,w in graph.get(k,[]):
            nd=d+w
            if nd<seen.get(v,1e99)-1e-10:seen[v]=nd;heapq.heappush(heap,(nd,v))
    raise ValueError(('No actual centerline path',net,start,goal))
paths={}
for name,base,fr,fp,fm,to,tp,tm in specs:
    p=distance(base+'_DP',fr,fp,to,tp);m=distance(base+'_DM',fr,fm,to,tm)
    paths[name]={'DP_mm':p,'DM_mm':m,'signed_skew_mm':p-m,'absolute_skew_mm':abs(p-m),'ideal_via_barrel_mm':3.2}
for ori in ('A','B'):
    for tail in ('NATIVE','USB_A'):
        u=paths['UP_'+ori+'_orientation'];v=paths[tail];p=u['DP_mm']+v['DP_mm'];m=u['DM_mm']+v['DM_mm']
        paths['USB_C_'+ori+'_to_'+tail]={'DP_mm':p,'DM_mm':m,'signed_skew_mm':p-m,'absolute_skew_mm':abs(p-m),'ideal_via_barrel_mm':6.4}
gaps=[]
for base in ('USB_UP','USB_NATIVE','USB_A'):
    for layer in (1,2):
        geoms={}
        for suffix in ('_DP','_DM'):
            net=base+suffix
            geoms[suffix]=unary_union([LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]).buffer(t['width']/2)for t in C['lines']if t['net']==net and t['layer']==layer]+[Point(v['x'],v['y']).buffer(v['diameter']/2)for v in C['vias']if v['net']==net])
        gap=geoms['_DP'].distance(geoms['_DM']);gaps.append({'base':base,'layer':layer,'minimum_DP_DM_line_via_copper_gap_mil':gap,'minimum_gap_mm':gap*.0254,'passes_6mil':gap>=6-.11})
out={'schema':'calxus.native-usb-paths.v1','source_copper_sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),'source_pads_sha256':hashlib.sha256(pp.read_bytes()).hexdigest(),'paths':paths,'pair_clearance':gaps,'centerline_attachments':attachments,'skew_limit_mm':.254,'passed':all(v['absolute_skew_mm']<=.254 for v in paths.values())and all(v['passes_6mil']for v in gaps),'limits':'Actual native line centers and vias, with explicit T-junction splitting and ideal 1.6mm through-via barrel lengths. Numeric attachment offsets <=0.11mil accommodate API coordinate quantization and are included. Does not include package/mux/cable propagation or field-solved pad/annulus delay.'}
op.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'passed':out['passed'],'paths':paths,'pair_clearance':gaps},indent=2));raise SystemExit(not out['passed'])
