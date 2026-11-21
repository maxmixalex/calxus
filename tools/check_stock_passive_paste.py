#!/usr/bin/env python3
"""Inspect the observed stock 0603 resistor notched paste versus actual CAM."""
import argparse,hashlib,json,math,sys,zipfile,re
from pathlib import Path
from shapely.geometry import Polygon,box
from shapely.affinity import rotate,translate
from gerbonara import LayerStack
from check_native_project_archive import parse_source,records,attributes
from gerber_mask_geometry import positive_image_geometry
from inspect_gerber import NATIVE_LAYER_ROLES
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--gerber',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
with zipfile.ZipFile(a.archive)as z:docs=parse_source(z.read(next(n for n in z.namelist()if n.endswith('.epru'))).decode())
by={d['head']['uuid']:d for d in docs};pcb=next(d for d in docs if d['head']['docType']=='PCB');pa=attributes(pcb)
comps={pa[h['id']]['Designator']:(h,c,pa[h['id']]) for h,c in records(pcb,'COMPONENT')}
stack=LayerStack.open(a.gerber,lazy=False,autoguess=False,overrides={re.escape(n):r for n,r in NATIVE_LAYER_ROLES.items()})
paste,metadata=positive_image_geometry(stack.graphic_layers[('top','paste')].instance,role='top-paste')
checks=[]
for ref in ['R1','R2','C5','C1']:
 h,c,ca=comps[ref];fp=by[ca['Footprint']];cx,cy=c['x']*.0254,c['y']*.0254
 def world(g):return translate(rotate(g,c['angle'],origin=(0,0)),cx,cy)
 pads=[]
 for ph,d in records(fp,'PAD'):
  assert d['defaultPad']['padType']=='RECT' and not d['hole']
  w,t=d['defaultPad']['width']*.0254,d['defaultPad']['height']*.0254
  g=box(-w/2,-t/2,w/2,t/2);g=rotate(g,d['padAngle'],origin=(0,0));g=translate(g,(d['centerX']+d['padOffsetX'])*.0254,(d['centerY']+d['padOffsetY'])*.0254);pads.append((d,world(g)))
 fills=[]
 for fh,d in records(fp,'FILL'):
  if d['layerId']!=7:continue
  assert len(d['path'])==1
  path=d['path'][0];vals=[x for x in path if not isinstance(x,str)];assert all(x=='L' for x in path if isinstance(x,str));g=Polygon(list(zip(vals[::2],vals[1::2])));g=Polygon([(x*.0254,y*.0254)for x,y in g.exterior.coords]);fills.append((fh,d,world(g)))
 regions=[]
 for pd,land in pads:
  candidates=[f for f in fills if f[2].intersection(land).area>land.area*.5]
  assert len(candidates)<=1
  expected=candidates[0][2] if candidates else land
  crop=expected.envelope.buffer(.03)
  actual=paste.intersection(crop)
  haus=actual.hausdorff_distance(expected)
  symmetric=actual.symmetric_difference(expected).area
  regions.append({'pin':pd['num'],'stock_pad_paste_expansion_mil':pd['topPasteExpansion'],'explicit_stock_paste_fill':candidates[0][0]['id'] if candidates else None,'land_area_mm2':land.area,'expected_paste_area_mm2':expected.area,'actual_paste_area_mm2':actual.area,'actual_area_to_copper_land_percent':actual.area/land.area*100,'actual_paste_shape_bounds_mm':list(actual.bounds),'hausdorff_distance_mm':haus,'symmetric_difference_area_mm2':symmetric,'matches_stock_shape_within_3um':haus<=.003,'shape':'stock inner-notch polygon'if candidates else 'rectangle from default PAD paste','pass':haus<=.003 and not actual.is_empty})
 checks.append({'ref':ref,'footprint_uuid':ca['Footprint'],'component_pose_mil':[c['x'],c['y'],c['angle']],'stock_explicit_paste_fill_count':len(fills),'pads':regions,'pass':all(r['pass']for r in regions)})
r={'schema':'calxus.stock-passive-paste-native-cam.v1','pass':all(c['pass']for c in checks),'native_archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'gerber_archive_sha256':hashlib.sha256(a.gerber.read_bytes()).hexdigest(),'scope':'Actual native stock-footprint paste geometry versus exported Top Paste. Does not qualify stencil thickness, solder volume or reflow profile. No footprint geometry was modified.','checks':checks,'conclusion':'R1/R2 stock 0603 resistor footprint uses explicit notched paste fills and suppresses automatic rectangular paste. C5/C1 use a different capacitor footprint with ordinary rectangular paste; actual CAM is checked separately at each source coordinate.'}
a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['pass']else 1)
