#!/usr/bin/env python3
"""Extract nominal through-hole contracts from saved native FOOTPRINT/PAD sources.

Does not use JLCEDA component-pad API getters. Those getters have exhibited
inconsistent hole-size/angle unit conversion. Includes plated connector/switch
holes, pad-only tail/program headers, and native unplated mounting pads. Vias
are deliberately excluded because final routing changes their population.
"""
import argparse, collections, hashlib, json, math, zipfile
from pathlib import Path
from check_native_project_archive import parse_source, records, attributes

MM = .0254

def xy_transform(x, y, cx, cy, angle):
    a=math.radians(angle);c=math.cos(a);s=math.sin(a)
    return [(cx+x*c-y*s)*MM,(cy+x*s+y*c)*MM]

def extract(archive):
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC failure')
        names=[n for n in z.namelist() if n.endswith('.epru')]
        if len(names)!=1: raise ValueError('Expected one epru source')
        raw=z.read(names[0]);docs=parse_source(raw.decode('utf-8'))
    byid={d['head']['uuid']:d for d in docs}
    pcbs=[d for d in docs if d['head']['docType']=='PCB']
    if len(pcbs)!=1: raise ValueError('Expected one PCB')
    pcb=pcbs[0];attrs=attributes(pcb);answer=[]
    padnets={}
    for h,d in records(pcb,'PAD_NET'):
        key=json.loads(h['id']);padnets[(key[1],key[3])]=d['padNet']

    def add(ref,component_id,footprint_id,pad_id,p,cx=0,cy=0,angle=0,net=''):
        hole=p.get('hole') or {};w=hole.get('width',0) or 0;h=hole.get('height',w) or w
        if w<=0 or h<=0:return
        kind=hole.get('holeType')
        if kind not in ('ROUND','SLOT'):raise ValueError(f'Unsupported hole {ref}.{p.get("num")} {kind}')
        center=xy_transform(p['centerX'],p['centerY'],cx,cy,angle)
        # Nominal centre contract uses saved centerX/Y. The official padOffset
        # wording and observed cache behaviour do not establish one universal
        # copper-versus-hole offset interpretation. Preserve the raw fields and
        # their maximum radial shift; final native CAM must resolve the actual
        # machining centre. No tenfold API getter conversion is applied.
        rotation=(angle+p.get('padAngle',0)+p.get('relativeAngle',0))%180
        row={'ref':ref,'pin':str(p.get('num','')),'component_id':component_id,
             'footprint_uuid':footprint_id,'pad_source_id':pad_id,'net':net,
             'plated':bool(p.get('plated')),'shape':kind,'center_mm':center,
             'offset_semantics_radial_bound_mm':math.hypot(p.get('padOffsetX',0) or 0,p.get('padOffsetY',0) or 0)*MM,
             'source_local':{'units':'mil','centerX':p['centerX'],'centerY':p['centerY'],
                 'hole':hole,'padAngle':p.get('padAngle',0),'relativeAngle':p.get('relativeAngle',0),
                 'padOffsetX':p.get('padOffsetX',0),'padOffsetY':p.get('padOffsetY',0)},
             'component_pose':{'units':'mil','x':cx,'y':cy,'angle_deg':angle}}
        if kind=='ROUND':
            if abs(w-h)>.001:raise ValueError(f'Unequal ROUND dimensions {ref}.{row["pin"]}')
            row['diameter_mm']=w*MM
        else:
            length=max(w,h)*MM;diameter=min(w,h)*MM
            axis=(rotation+(90 if h>w else 0))%180
            a=math.radians(axis);half=(length-diameter)/2
            row.update(slot_tool_diameter_mm=diameter,slot_overall_length_mm=length,
                       slot_centerline_length_mm=length-diameter,slot_axis_degrees_ccw_from_x=axis,
                       slot_end_centers_mm=[[center[0]-half*math.cos(a),center[1]-half*math.sin(a)],
                                            [center[0]+half*math.cos(a),center[1]+half*math.sin(a)]])
        answer.append(row)

    for h,c in records(pcb,'COMPONENT'):
        cid=h['id'];a=attrs[cid];ref=a.get('Designator');fid=a.get('Footprint')
        if not ref or fid not in byid:raise ValueError('Missing actual component footprint '+str(ref))
        if c['layerId']!=1:raise ValueError('Bottom component mirror is not implemented; refuse inferred hole pose')
        fp=byid[fid]
        for ph,p in records(fp,'PAD'):
            add(ref,cid,fid,ph['id'],p,c['x'],c['y'],c.get('angle',0),padnets.get((cid,ph['id']),''))
    for h,p in records(pcb,'PAD'):
        add(str(p.get('num') or h['id']),None,None,h['id'],p,net=p.get('netName',''))
    answer.sort(key=lambda x:(x['ref'],x['pin']))
    return {'schema':'calxus.native-tht-drill-expectations.v1','units':'mm','pcb_uuid':pcb['head']['uuid'],
            'source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'source_epru_sha256':hashlib.sha256(raw).hexdigest(),
            'source_method':'Saved project FOOTPRINT PAD + actual PCB COMPONENT transform; native PCB PAD for free mounting holes. No API hole getter.',
            'coordinate_system':'PCB XY, Y up; origin matches native source and layout. Resolve any Gerber/Excellon export origin offset explicitly before comparison.',
            'counts':{'holes':len(answer),'plated':sum(x['plated'] for x in answer),
                      'unplated':sum(not x['plated'] for x in answer),
                      'by_ref':dict(collections.Counter(x['ref'] for x in answer))},
            'verification_requirements':[
                'Compare every listed plated and unplated hole, not only the four mounting holes.',
                'ROUND: verify diameter and center. SLOT: verify tool diameter, overall length, center and axis or equivalent G85/router endpoints.',
                'J2 signals1-4 nominal1.0mm; shield5/6 nominal2.1x0.8mm with long axis parallel boardY.',
                'The centre contract uses saved centerX/Y and records padOffset semantic uncertainty. Verify the actual exported centre; do not infer field semantics from the previously faulty cached getter.',
                'Final signal/GND vias, VIPPO fabrication instructions, drill registration and process tolerances require separate final-route checks.'],
            'offset_semantics':{'centre_basis':'Saved PAD centerX/Y, transformed by actual COMPONENT pose',
                'status':'Nominal source contract; universal padOffset copper/hole interpretation is not asserted',
                'maximum_radial_bound_mm':max((h['offset_semantics_radial_bound_mm'] for h in answer),default=0),
                'CAM_confirmation_required':True},
            'holes':answer}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=extract(a.archive);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(d['counts'],ensure_ascii=False))
