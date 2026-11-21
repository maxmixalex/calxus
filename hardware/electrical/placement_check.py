"""Check declared placement against actual JLCEDA geometry (mil units) and keepouts.
This is a component-envelope check, not copper DRC or a routing validation.
"""
from pathlib import Path
import json, math, itertools
P=Path(__file__).parent
GEOM=P.parent/'evidence'/'eda_parts_catalog_full.json'
DATA=P/'calxus_design_input.json'

def box_for(p, catalog):
    if p.get('pcb_only'):
        return [-0.5,-0.5,0.5,0.5]
    fp=catalog[p['lcsc']]['footprint']
    if p.get('bom_exclude') and fp.get('pads'):
        bs=[x['bbox'] for x in fp['pads']]
        b={'minX':min(v['minX'] for v in bs),'minY':min(v['minY'] for v in bs),'maxX':max(v['maxX'] for v in bs),'maxY':max(v['maxY'] for v in bs)}
    else:b=fp['fullBBox']
    a=math.radians(p.get('pcb_rotation',0));c=math.cos(a);s=math.sin(a)
    pts=[((x*c-y*s)*.0254,(x*s+y*c)*.0254) for x in (b['minX'],b['maxX']) for y in (b['minY'],b['maxY'])]
    return [min(q[0] for q in pts),min(q[1] for q in pts),max(q[0] for q in pts),max(q[1] for q in pts)]

def translated(b,xy,margin=0):return [b[0]+xy[0]-margin,b[1]+xy[1]-margin,b[2]+xy[0]+margin,b[3]+xy[1]+margin]
def overlap(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
def hole_hit(b,h,r=3):
    x=max(b[0],min(h[0],b[2]));y=max(b[1],min(h[1],b[3]));return math.hypot(x-h[0],y-h[1])<r

def validate(d,catalog):
    missing=[p['ref'] for p in d['parts'] if not p.get('pcb_only') and p.get('lcsc') not in catalog]
    boxes={p['ref']:translated(box_for(p,catalog),p['placement_mm'],.15) for p in d['parts'] if p['ref'] not in missing}
    parts={p['ref']:p for p in d['parts']};coll=[];bounds=[];holes=[]
    for a,b in itertools.combinations(boxes,2):
        if parts[a].get('pcb_layer','TOP')==parts[b].get('pcb_layer','TOP') and overlap(boxes[a],boxes[b]):coll.append([a,b])
    for r,b in boxes.items():
        if r not in ['J1','J2'] and (b[0]<.5 or b[1]<.5 or b[2]>79.5 or b[3]>41.5):bounds.append(r)
        for h in d['pcb_mount_holes_mm']:
            if hole_hit(b,h):holes.append({'ref':r,'hole':h})
    return dict(missing_geometry=missing,collisions=coll,boundary_violations=bounds,mount_keepout_violations=holes,clearance_margin_mm=.15,scope='Conservative component fullBBox/pad-only envelopes. Not copper DRC or SI verification.')

if __name__=='__main__':
 d=json.loads(DATA.read_text());c=json.loads(GEOM.read_text());r=validate(d,c);(P/'placement_validation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
