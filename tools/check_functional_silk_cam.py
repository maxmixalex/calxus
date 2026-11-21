#!/usr/bin/env python3
"""Verify approved functional-label placement against actual native top silk/mask.

This is scoped to six relocated labels and the unchanged four-mode legend.
Glyph reading is separately recorded by actual visual review, not OCR inference.
"""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from gerbonara import LayerStack
from shapely.geometry import box
from check_native_project_archive import parse_source,records
from gerber_mask_geometry import positive_image_geometry,ARC_ERROR_MM
from inspect_gerber import NATIVE_LAYER_ROLES

p=argparse.ArgumentParser(description=__doc__)
for k in ['archive','gerber','plan','output']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args()
with zipfile.ZipFile(a.archive) as z:
 assert z.testzip() is None
 docs=parse_source(z.read(next(n for n in z.namelist() if n.endswith('.epru'))).decode())
pcb=next(d for d in docs if d['head']['docType']=='PCB')
strings={h['id']:d for h,d in records(pcb,'STRING')}
plan=json.loads(a.plan.read_text())
stack=LayerStack.open(a.gerber,lazy=False,autoguess=False,overrides={re.escape(n):r for n,r in NATIVE_LAYER_ROLES.items()})
items=plan['items']+[{'primitiveId':'a9c543a9b6e057b4','text':'0 MINI  1 A  2 TI  3 UART','new_mm':{'x':11,'y':39,'angle':0},'conservative_text_envelope_mm':[10.9,38.9,33,40.5]}]
from shapely.ops import unary_union
from gerbonara.utils import MM
selection=unary_union([box(*x['conservative_text_envelope_mm']) for x in items])
layer=stack.graphic_layers[('top','silk')].instance
selected=[]
for obj in layer.objects:
 (x1,y1),(x2,y2)=obj.bounding_box(unit=MM)
 if selection.intersects(box(x1,y1,x2,y2)):
  selected.append(obj)
layer.objects=selected
silk,sm=positive_image_geometry(layer,role='functional-top-silk')
mask,mm=positive_image_geometry(stack.graphic_layers[('top','mask')].instance,role='top-mask')
checks=[]
for item in items:
 s=strings[item['primitiveId']];ink=silk.intersection(box(*item['conservative_text_envelope_mm']));env=box(*item['conservative_text_envelope_mm']);want=item['new_mm']
 pose=abs(s['x']*.0254-want['x'])<.0001 and abs(s['y']*.0254-want['y'])<.0001 and s['angle']==want['angle']
 text=s['text']==item['text'];font=('font_size_mil_preserved'not in item or abs(s['fontSize']-item['font_size_mil_preserved'])<1e-7)
 padgap=ink.distance(mask)-2*ARC_ERROR_MM if not ink.is_empty else 0
 edgegap=ink.distance(box(0,0,80,42).boundary)-ARC_ERROR_MM if not ink.is_empty else 0
 inside=box(0,0,80,42).covers(ink)
 checks.append({'primitiveId':item['primitiveId'],'text':s['text'],'source_pose_mm':[s['x']*.0254,s['y']*.0254,s['angle']],'source_pose_matches':pose,'source_text_matches':text,'font_size_preserved':font,'actual_top_silk_ink_area_mm2':ink.area,'actual_ink_bounds_mm':list(ink.bounds),'minimum_actual_ink_to_mask_opening_mm':padgap,'minimum_actual_ink_to_board_edge_mm':edgegap,'inside_board':inside,'pass':pose and text and font and not ink.is_empty and padgap>=.15 and edgegap>=.15 and inside})
report={'schema':'calxus.functional-silk-native-cam.v1','pass':all(c['pass']for c in checks),'source_archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'gerber_archive_sha256':hashlib.sha256(a.gerber.read_bytes()).hexdigest(),'scope':'Seven functional legends only: native STRING identity/pose and actual Gerber ink clearance within conservative label envelopes. Actual glyph legibility and absence of clipping require linked visual review. General reference designator spacing is not certified.','minimum_mask_clearance_mm':.15,'minimum_board_edge_clearance_mm':.15,'arc_polygonisation_bound_mm':ARC_ERROR_MM,'checks':checks}
a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'checks':[{k:c[k]for k in ['text','pass','minimum_actual_ink_to_mask_opening_mm','minimum_actual_ink_to_board_edge_mm']}for c in checks]}));raise SystemExit(0 if report['pass']else 1)
