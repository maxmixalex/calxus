#!/usr/bin/env python3
"""Separate native J2 STEP-hole and model-datum errors using explicit copies.
No native source/STEP is modified, and a corrected diagnostic is not a native pass.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,tempfile
import cadquery as cq
from inspect_step import read_named_shapes
from validate_pcba import group_shapes,bounds,cylinders

def volume(a,b):
    c=a.intersect(b)
    return c.Volume() if c.Solids() else 0.

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('step',type=Path);ap.add_argument('drills',type=Path);ap.add_argument('report',type=Path);a=ap.parse_args()
    root=Path(__file__).resolve().parent.parent
    design=json.loads((root.parent/'hardware/electrical/calxus_design_input.json').read_text());raw=a.step.read_bytes();plain=gzip.decompress(raw) if a.step.suffix=='.gz' else raw
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'source.step';p.write_bytes(plain);g,_=group_shapes(read_named_shapes(p),{p['ref'] for p in design['parts']})
    j,b=g['J2'],g['BOARD'];e=json.loads(a.drills.read_text());holes=[h for h in e['holes'] if h['ref']=='J2'];assert len(holes)==6
    copied=b
    for h in holes:
        x,y=h['center_mm'];w=cq.Workplane('XY').center(x,y)
        if h['shape']=='ROUND':w=w.circle(h['diameter_mm']/2)
        elif h['shape']=='SLOT':w=w.slot2D(h['slot_overall_length_mm'],h['slot_tool_diameter_mm'],angle=h['slot_axis_degrees_ccw_from_x'])
        else:raise ValueError('Unsupported drill shape')
        copied=copied.cut(w.extrude(3).translate((0,0,-.5)).val())
    rows=[]
    for board_name,board in [('native_unmodified',b),('explicit_source_holes_copy',copied)]:
        for dz in [0,.1]:rows.append({'board':board_name,'explicit_j2_model_z_mm':dz,'intersection_mm3':volume(j.translate((0,0,dz)),board)})
    report={'scope':'Diagnostic copies only; no native source/STEP edits, no Excellon validation and no native-model pass implied.','source':a.step.name,'source_sha256':hashlib.sha256(raw).hexdigest(),'drill_evidence':str(a.drills),'drill_evidence_sha256':hashlib.sha256(a.drills.read_bytes()).hexdigest(),'native_j2_bbox_mm':bounds(j),'native_j2_region_board_cylinders':[c for c in cylinders(b) if 30<c[0]<50 and c[1]<10],'explicit_source_hole_records':holes,'board_volume_removed_mm3':b.Volume()-copied.Volume(),'copied_board_valid':copied.isValid(),'results':rows}
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'report':str(a.report),'results':rows},indent=2))
if __name__=='__main__':main()
