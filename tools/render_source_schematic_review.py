#!/usr/bin/env python3
"""Render the frozen Calxus source as a labelled A2 review PDF, not native CAM.

Deliberately scoped to the audited 97 unrotated symbols (J2 horizontal mirror),
explicit PIN/primitive geometry, WIRE LINE records, displayed ATTR and NC state.
Unknown electrical drawing primitives fail instead of silently disappearing.
"""
import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path
import zipfile

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from check_native_project_archive import parse_source, records, attributes, audit, on_line

SHEET_W, SHEET_H = 2339, 1654
SYMBOL = (0.42, 0.13, 0.10)
NET = (0.06, 0.22, 0.47)
WIRE = (0.05, 0.39, 0.28)
INK = (0.10, 0.12, 0.15)


def circumcircle(p, q, r):
    (ax, ay), (bx, by), (cx, cy) = p, q, r
    d = 2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(d) < 1e-12:
        raise ValueError('Collinear source ARC cannot be rendered unambiguously')
    ux = ((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/d
    uy = ((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/d
    return ux, uy, math.hypot(ax-ux, ay-uy)


class Renderer:
    def __init__(self, pdf, source_sha, archive_sha):
        self.canvas = canvas.Canvas(str(pdf), pagesize=(594*mm, 420*mm), pageCompression=1, invariant=1)
        self.canvas.setTitle('Calxus RevA r7 — source-derived schematic review')
        self.canvas.setAuthor('Calxus engineering source review')
        self.canvas.setSubject('Source-derived review; not a new native JLCEDA PDF export; no manufacturing release')
        self.scale = min(594*mm/SHEET_W, 420*mm/SHEET_H)
        self.source_sha, self.archive_sha = source_sha, archive_sha
        self.text_records = []
        self.page_reports = []
        self.page_number = 0
        self.geometry_points = []

    def start(self, name):
        self.page_number += 1
        self.canvas.saveState(); self.canvas.scale(self.scale, self.scale)
        self.canvas.setLineCap(1); self.canvas.setLineJoin(1)
        self.geometry_points = []
        self.canvas.setStrokeColorRGB(.50, .54, .60); self.canvas.setLineWidth(.6)
        self.canvas.rect(35, 35, SHEET_W-70, SHEET_H-70, stroke=1, fill=0)
        self.text('Calxus RevA / '+name, 60, 1592, size=18, bold=True, owner='review header')
        self.text('SOURCE-DERIVED REVIEW | A2 | 97 components / 345 logical pins / 21 NC', 60, 1570, size=10, owner='review header')
        self.text('NOT a fresh native export. Native ERC/DRC/CAM and hardware validation remain required.', 60, 1552, size=10, color=(.56,.22,.08), owner='review header')
        self.text('Candidate archive SHA256: '+self.archive_sha, 60, 66, size=8, owner='review footer')
        self.text('Electrical symbols, pins, wires and labels are read from the saved candidate. Review typography and border are generated independently.', 60, 50, size=8, owner='review footer')
        self.text(f'{self.page_number} / 3', SHEET_W-60, 50, size=10, align='RIGHT_BOTTOM', owner='review footer')

    def text(self, value, x, y, size=8, align='LEFT_BOTTOM', rotation=0, color=INK, bold=False, owner=None):
        if value is None: raise ValueError('Visible unresolved text')
        value = str(value); size = size or 8; align = align or 'LEFT_BOTTOM'; rotation = rotation or 0
        if '\n' in value or '\r' in value:
            raise ValueError('Multiline source text needs an explicit layout rule')
        if align not in ('LEFT_BOTTOM', 'RIGHT_BOTTOM'):
            raise ValueError('Unsupported native text alignment '+align)
        font = 'ReviewSansBold' if bold else 'ReviewSans'
        width = pdfmetrics.stringWidth(value, font, size)
        dx = -width if align == 'RIGHT_BOTTOM' else 0
        # Native *_BOTTOM anchor is the text baseline in this unrotated source.
        a, d = pdfmetrics.getAscentDescent(font, size)
        angle = math.radians(rotation); cs, sn = math.cos(angle), math.sin(angle)
        corners = [(x+xx*cs-yy*sn, y+xx*sn+yy*cs) for xx,yy in ((dx,d),(dx+width,d),(dx+width,a),(dx,a))]
        self.text_records.append({'page': self.page_number, 'owner': owner, 'value': value,
                                  'anchor_source_units': [x,y], 'align': align, 'rotation': rotation,
                                  'font_size_source_units': size, 'bounds_source_units': [min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]})
        c=self.canvas; c.saveState();c.translate(x,y);c.rotate(rotation)
        c.setFillColorRGB(*color);c.setFont(font,size);c.drawString(dx,0,value);c.restoreState()

    def line(self, a, b, color=SYMBOL, width=.65):
        self.geometry_points.extend((a,b));c=self.canvas;c.setStrokeColorRGB(*color);c.setLineWidth(width);c.line(*a,*b)

    def poly(self, pts, closed=False, width=.65):
        self.geometry_points.extend(pts);c=self.canvas;c.setStrokeColorRGB(*SYMBOL);c.setLineWidth(width)
        p=c.beginPath();p.moveTo(*pts[0])
        for point in pts[1:]:p.lineTo(*point)
        if closed:p.close()
        c.drawPath(p,stroke=1,fill=0)

    def finish(self, details):
        points=self.geometry_points
        details['geometry_bounds_source_units']=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        details['page_number']=self.page_number;self.page_reports.append(details)
        self.canvas.restoreState();self.canvas.showPage()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('--design',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args()
    audit_report,_=audit(args.archive,args.design,args.plan)
    if not audit_report['pass']:raise ValueError('Source connectivity/pose audit failed: '+str(audit_report['issues']))
    with zipfile.ZipFile(args.archive) as z:source=z.read(next(n for n in z.namelist() if n.endswith('.epru')))
    docs=parse_source(source.decode());by={d['head']['uuid']:d for d in docs}
    expected={p['ref']:p for p in json.loads(args.design.read_text())['parts'] if not p.get('pcb_only')}
    for name,filename in [('ReviewSans','DejaVuSans.ttf'),('ReviewSansBold','DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/truetype/dejavu/'+filename))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    rr=Renderer(args.output,hashlib.sha256(source).hexdigest(),audit_report['archive_sha256'])
    drawing_types={'PIN','POLY','RECT','CIRCLE','ELLIPSE','ARC'}
    meta_types={'ATTR','ELE_PLACEHOLDER','CANVAS','PART','META'}
    totals=collections.Counter(); rendered_refs=[];vertical=[];j2=[]
    for pg in (d for d in docs if d['head']['docType']=='SCH_PAGE'):
        name=records(pg,'META')[0][1]['title'];rr.start(name)
        attrs=attributes(pg);wires={h['id']:d for h,d in records(pg,'WIRE')}
        lines=[d for h,d in records(pg,'LINE') if d.get('lineGroup') in wires]
        counts=collections.Counter(); comp_ids={};pin_world=[];junctions=set()
        for d in lines:rr.line((d['startX'],-d['startY']),(d['endX'],-d['endY']),WIRE,.60)
        counts['wire_segments']=len(lines);counts['wire_groups']=len(wires)
        # Junction dots are derived only from real, same-net LINE branches.
        candidates={(d[k+'X'],d[k+'Y']) for d in lines for k in ('start','end')}
        for x,y in candidates:
            branch_by_net=collections.defaultdict(set)
            for d in lines:
                if not on_line(x,y,d):continue
                net=attrs[d['lineGroup']]['NET']
                for end in ('start','end'):
                    dx,dy=d[end+'X']-x,d[end+'Y']-y;length=math.hypot(dx,dy)
                    if length>1e-7:branch_by_net[net].add((round(dx/length,6),round(dy/length,6)))
            if any(len(v)>=3 for v in branch_by_net.values()):
                rr.canvas.setFillColorRGB(*WIRE);rr.canvas.circle(x,-y,1.25,stroke=0,fill=1);junctions.add((x,y))
        for h,c in records(pg,'COMPONENT'):
            ca=attrs[h['id']];ref=ca.get('Designator')
            if ref not in expected:continue  # Native frame is replaced by an explicitly independent A2 review border.
            if c.get('rotation',0)!=0:raise ValueError('Unexpected component rotation')
            mirror=c.get('isMirror',False)
            if mirror and ref!='J2':raise ValueError('Unexpected mirrored component')
            rendered_refs.append(ref);counts['components']+=1
            sym=by[ca['Symbol']];sa=attributes(sym)
            dev=by[ca.get('Device') or json.loads(c['attrs']['DeviceName'])['uuid']]
            properties=dict(records(dev,'META')[0][1]['attributes']);properties.update({k:v for k,v in ca.items() if v not in ('',None)})
            comp_ids[h['id']]=(ref,properties)
            def transform(x,y):return (c['x']+(-x if mirror else x),-c['y']-y)
            for sh,d in sym['records']:
                if d.get('partId') not in (None,c['partId']):continue
                t=sh['type']
                if t not in drawing_types|meta_types:raise ValueError(ref+': unsupported symbol record '+t)
                if t in meta_types:continue
                counts[t]+=1
                if d.get('fillStyle') not in (None,'NONE'):raise ValueError('Unsupported symbol fill '+str(d['fillStyle']))
                width=d.get('strokeWidth') or .65
                if t=='PIN':
                    if d['pinShape']!='NONE' or not d['display']:raise ValueError('Unsupported pin display/shape')
                    a=math.radians(d['rotation']);outer=transform(d['x'],d['y']);inner=transform(d['x']+d['length']*math.cos(a),d['y']-d['length']*math.sin(a))
                    rr.line(outer,inner);pin_world.append((ref,str(sa[sh['id']]['Pin Number']),outer))
                    nc=attrs.get(h['id']+'-'+sh['id'],{}).get('NO_CONNECT')=='yes'
                    if nc:
                        counts['explicit_nc']+=1
                        for sign in (-1,1):rr.line((outer[0]-2,outer[1]-2*sign),(outer[0]+2,outer[1]+2*sign),(0.45,.15,.55),.75)
                    if ref=='J2':j2.append({'pin':str(sa[sh['id']]['Pin Number']),'name':sa[sh['id']].get('Pin Name'),'world_source_units':outer,'net':expected[ref]['pins'][str(sa[sh['id']]['Pin Number'])]})
                elif t=='POLY':rr.poly([transform(p['x'],p['y']) for p in d['points']],d['closed'],width)
                elif t=='RECT':
                    if d.get('rotation',0)!=0 or d.get('radiusX',0) or d.get('radiusY',0):raise ValueError('Unsupported rotated/rounded symbol rectangle')
                    a=transform(d['dotX1'],d['dotY1']);b=transform(d['dotX2'],d['dotY2']);rr.poly([a,(a[0],b[1]),b,(b[0],a[1])],True,width)
                elif t in ('CIRCLE','ELLIPSE'):
                    if d.get('rotation',0)!=0:raise ValueError('Unsupported rotated symbol ellipse')
                    x,y=transform(d['centerX'],d['centerY']);rx=abs(d.get('radiusX',d.get('radius',0)));ry=abs(d.get('radiusY',d.get('radius',0)))
                    rr.geometry_points.extend(((x-rx,y-ry),(x+rx,y+ry)));rr.canvas.setStrokeColorRGB(*SYMBOL);rr.canvas.setLineWidth(width);rr.canvas.ellipse(x-rx,y-ry,x+rx,y+ry,stroke=1,fill=0)
                elif t=='ARC':
                    a=transform(d['startX'],d['startY']);b=transform(d['referX'],d['referY']);e=transform(d['endX'],d['endY']);cx,cy,r=circumcircle(a,b,e)
                    angles=[math.atan2(v[1]-cy,v[0]-cx)%(2*math.pi) for v in (a,b,e)];sweep=(angles[2]-angles[0])%(2*math.pi)
                    if (angles[1]-angles[0])%(2*math.pi)>sweep:sweep-=2*math.pi
                    # Sub-0.001 source-unit chord error for these small 1-unit arcs.
                    steps=max(12,math.ceil(abs(sweep)/.04));rr.poly([(cx+r*math.cos(angles[0]+sweep*i/steps),cy+r*math.sin(angles[0]+sweep*i/steps)) for i in range(steps+1)],False,width)
            # Symbol-local visible names/numbers retain their native anchors. Horizontal
            # mirror moves anchors and swaps L/R alignment; text glyphs stay readable.
            for sh,d in records(sym,'ATTR'):
                if d.get('partId')!=c['partId'] or not d.get('valueVisible'):continue
                if d.get('keyVisible'):raise ValueError('Visible attribute key needs explicit handling')
                rot=d.get('rotation') or 0;align=d.get('align') or 'LEFT_BOTTOM'
                if mirror:
                    if rot!=0:raise ValueError('Mirrored rotated symbol text unsupported')
                    align='RIGHT_BOTTOM' if align=='LEFT_BOTTOM' else 'LEFT_BOTTOM'
                x,y=transform(d['x'],d['y']);rr.text(d['value'],x,y,d.get('fontSize') or 8,align,rot,SYMBOL,owner=ref+':'+d['key']+':'+d.get('parentId',''))
                counts['pin_or_symbol_texts']+=1
        for ah,d in records(pg,'ATTR'):
            if not d.get('valueVisible'):continue
            owner=d.get('parentId');key=d['key']
            if owner in wires:
                if key!='NET':raise ValueError('Unknown visible wire attribute '+key)
                value=d['value'];color=NET;label_owner='NET:'+ah['id'];counts['net_labels']+=1
                if (d.get('rotation') or 0)==90:vertical.append({'page':rr.page_number,'id':ah['id'],'value':value,'x':d['x'],'y':-d['y'],'align':d.get('align') or 'LEFT_BOTTOM'})
            elif owner in comp_ids:
                ref,props=comp_ids[owner];value=d['value'];color=INK;label_owner=ref+':'+key;counts['component_labels']+=1
                if value.startswith('='):
                    value=re.sub(r'\{([^{}]+)\}',lambda m:str(props[m.group(1)]),value[1:])
            else:continue
            rr.text(value,d['x'],-d['y'],d.get('fontSize') or 8,d.get('align') or 'LEFT_BOTTOM',d.get('rotation') or 0,color,owner=label_owner)
        for h,d in records(pg,'TEXT'):
            rr.text(d['value'],d['x'],-d['y'],d.get('fontSize') or 12,d.get('align') or 'LEFT_BOTTOM',d.get('rotation') or 0,INK,bold=True,owner='block:'+h['id']);counts['block_notes']+=1
        counts['junction_dots']=len(junctions);totals.update(counts)
        rr.finish({'name':name,'counts':dict(counts),'rendered_pins':[{'ref':r,'pin':p,'position_source_units':xy} for r,p,xy in pin_world]})
    if set(rendered_refs)!=set(expected) or len(rendered_refs)!=97 or totals['PIN']!=345 or totals['explicit_nc']!=21:raise ValueError('Incomplete source rendering')
    overflow=[t for t in rr.text_records if min(t['bounds_source_units'][:2])<0 or t['bounds_source_units'][2]>SHEET_W or t['bounds_source_units'][3]>SHEET_H]
    if overflow:raise ValueError('Source text cropped by A2 page: '+str(overflow))
    rr.canvas.save()
    report={'pass':True,'scope':'Independent source-derived review PDF; not a new native JLCEDA PDF export, ERC, DRC or CAM validation',
            'source_archive':str(args.archive),'source_archive_sha256':audit_report['archive_sha256'],'source_epru_sha256':hashlib.sha256(source).hexdigest(),
            'pdf':str(args.output),'pdf_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'pdf_bytes':args.output.stat().st_size,
            'page_size_mm':[594,420],'page_count':rr.page_number,'counts':dict(totals),'rendered_references':rendered_refs,
            'source_electrical_audit':{k:audit_report[k] for k in ('pass','components','pins','explicit_nc')},
            'style_scope':'Native primitive/label anchors and rotations preserved; independent embedded DejaVu typography, colours, A2 review border and source provenance footer; small source ARC sampled at <=0.04 radian steps',
            'text_clipping_count':len(overflow),'pages':rr.page_reports,'text_records':rr.text_records,'J2_current_pin_map':j2,'vertical_NET_labels':vertical,
            'visual_review':{'status':'required_after_rendering','native_comparison_pdf':'validation/schematic-layout-reviewed: pre-J2 native PDF is historical comparison only'}}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('pass','page_count','pdf_sha256','counts','source_archive_sha256')}))


if __name__=='__main__':main()
