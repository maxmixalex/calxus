"""Check native exported outer-layer line/via copper against reserved USB corridors.
Usage: python check_usb_corridors.py NATIVE_JSON OUTPUT_JSON
NATIVE_JSON must have units='mil', lines:[{net,layer,x1,y1,x2,y2,width}],
vias:[{net,x,y,diameter,holeDiameter}]. Export ALL lines/vias after autorouting.
Component/test-pad conflicts are separately checked by plan_ground_stitching.py.
"""
import json,sys
from pathlib import Path
import numpy as np
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps');import shapely
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union
P=Path(__file__).parent
if len(sys.argv)!=3:raise SystemExit('Usage: check_usb_corridors.py NATIVE_JSON OUTPUT_JSON')
A=json.loads(Path(sys.argv[1]).read_text());C=json.loads((P/'usb_copper_corridors.json').read_text())
if A.get('units')!='mil' or not isinstance(A.get('lines'),list) or not isinstance(A.get('vias'),list):raise ValueError('Expected explicit mil lines/vias schema; refusing unknown or partial format')
g=unary_union([Polygon(p['exterior'],p['holes']) for p in C['polygons']]);allowed={t['net'] for t in C['mainline_tracks']};ret=C['exemptions']['ground_return_vias'];bad=[]
for i,t in enumerate(A['lines']):
 if t['layer']!=2 or t['net'] in allowed:continue
 line=LineString([(t['x1'],t['y1']),(t['x2'],t['y2'])]).buffer(t['width']/2)
 if line.intersects(g):bad.append({'kind':'line','id':t.get('id',i),'net':t['net'],'overlap_area_mm2':line.intersection(g).area*.0254**2})
for i,v in enumerate(A['vias']):
 if v['net'] in allowed:continue
 if v['net']=='GND' and any(abs(v['x']-e['x'])<.02 and abs(v['y']-e['y'])<.02 for e in ret):continue
 geom=Point(v['x'],v['y']).buffer(v['diameter']/2)
 if geom.intersects(g):bad.append({'kind':'via','id':v.get('id',i),'net':v['net'],'overlap_area_mm2':geom.intersection(g).area*.0254**2})
out={'source':str(Path(sys.argv[1])),'lines_checked':len(A['lines']),'vias_checked':len(A['vias']),'violations':bad,'passed':not bad,'scope':'Outer L4 unrelated line/via copper only. Does not check pours, arcs, polygons or moved pads; export/check these separately. L2/L3 continuous ground must not be removed by these corridors.'};Path(sys.argv[2]).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));raise SystemExit(bool(bad))
