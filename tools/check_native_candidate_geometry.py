#!/usr/bin/env python3
"""Independent source-geometry review and real-copper preview of a native candidate.

No API snapshots supply geometry. Reads LINE/VIA, COMPONENT/FOOTPRINT/PAD,
PAD_NET and REGION records from the reopened epro2 archive. Uses exact source
mil values. GND planes are analytical reconstructions of preserved boundaries,
not a claim that native cached pour fills or CAM have been regenerated.
"""
import argparse,collections,hashlib,json,math,zipfile,sys
try:import shapely
except ImportError:sys.path.insert(0,'/tmp/calxus_deps')
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon,box
from shapely.affinity import rotate,translate,scale
from shapely.ops import unary_union
from shapely.strtree import STRtree
from check_native_project_archive import parse_source,records,attributes
MM=.0254;GAP=.1524;PCB='2a0c39c6c6694f40'
def transformed(g,c):return translate(rotate(g,c.get('angle',0),origin=(0,0)),c.get('x',0),c.get('y',0))
def pad_geometry(p,c):
 s=p['defaultPad'];typ=s['padType'];cx,cy=p['centerX'],p['centerY'];pa=p.get('padAngle',0)or 0
 if typ=='POLYGON':
  nums=[v for v in s['path']if isinstance(v,(int,float))];g=Polygon(list(zip(nums[::2],nums[1::2])))
 else:
  w,h=s['width'],s['height']
  if typ=='ELLIPSE':g=scale(Point(0,0).buffer(1,resolution=96),w/2,h/2)
  elif typ=='OVAL':g=LineString([(-(w-h)/2,0),((w-h)/2,0)]).buffer(h/2,resolution=96)if w>=h else LineString([(0,-(h-w)/2),(0,(h-w)/2)]).buffer(w/2,resolution=96)
  elif typ=='RECT':
   rad=s.get('radius',0)or 0;g=box(-w/2+rad,-h/2+rad,w/2-rad,h/2-rad).buffer(rad,resolution=48)if rad else box(-w/2,-h/2,w/2,h/2)
  else:raise ValueError('Unsupported pad shape '+typ)
  g=translate(rotate(g,pa,origin=(0,0)),cx,cy)
 # Evaluate the observed source convention here; a separate conservative
 # envelope below covers zero/rotated/reversed offset interpretations. The
 # public format calls these hole offsets without fully defining the transform.
 g=translate(g,p.get('padOffsetX',0)or 0,p.get('padOffsetY',0)or 0)
 outer=scale(transformed(g,c),MM,MM,origin=(0,0))
 center=transformed(Point(cx,cy),c);xy=[center.x*MM,center.y*MM]
 hole=p.get('hole')or{};w=hole.get('width',0)or 0;h=hole.get('height',w)or w;hg=None
 if w>0 and h>0:
  if hole['holeType']=='ROUND':hg=Point(0,0).buffer(w/2,resolution=96)
  elif hole['holeType']=='SLOT':hg=LineString([(-(w-h)/2,0),((w-h)/2,0)]).buffer(h/2,resolution=96)if w>=h else LineString([(0,-(h-w)/2),(0,(h-w)/2)]).buffer(w/2,resolution=96)
  else:raise ValueError('Unsupported hole '+str(hole))
  hg=translate(rotate(hg,pa+(p.get('relativeAngle',0)or 0),origin=(0,0)),cx,cy);hg=scale(transformed(hg,c),MM,MM,origin=(0,0))
 return outer,xy,hg

def load(archive):
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None;names=[n for n in z.namelist()if n.endswith('.epru')];assert len(names)==1;raw=z.read(names[0]);docs=parse_source(raw.decode())
 by={d['head']['uuid']:d for d in docs};pcb=by[PCB];at=attributes(pcb);padnets={}
 for h,d in records(pcb,'PAD_NET'):
  k=json.loads(h['id']);padnets[(k[1],k[3])]=d['padNet']
 es=[];pads=[];comp=[];holes=[]
 def addpad(id,ref,p,c,net,cid=None):
  outer,xy,hg=pad_geometry(p,c);layer=p['layerId'];plated=bool(p.get('plated'));g=outer.difference(hg)if hg is not None else outer
  uncertainty=2*math.hypot(p.get('padOffsetX',0)or 0,p.get('padOffsetY',0)or 0)*MM
  e={'id':id,'ref':ref,'kind':'pad','net':net or'','layers':{1,2,15,16}if layer==12 and plated else{layer},'g':g,'outer':outer,'xy':xy,'through':layer==12 and plated,'smd':layer==1,'bottomSmd':layer==2,'maskExpansion_mil':max(p.get('topSolderExpansion')or 0,p.get('bottomSolderExpansion')or 0),'componentId':cid,'hole':hg,'offset_uncertainty_mm':uncertainty}
  if not g.is_empty:es.append(e);pads.append(e)
  if hg is not None:holes.append({'id':id,'g':hg,'net':net or'','plated':plated,'offset_uncertainty_mm':uncertainty})
 for h,c in records(pcb,'COMPONENT'):
  cid=h['id'];ref=at[cid]['Designator'];fp=by[at[cid]['Footprint']];assert c['layerId']==1,'Unexpected bottom component';comp.append({'id':cid,'ref':ref,'x':c['x']*MM,'y':c['y']*MM,'angle':c.get('angle',0)})
  for ph,p in records(fp,'PAD'):addpad(ref+'.'+str(p['num']),ref,p,c,padnets.get((cid,ph['id']),''),cid)
  if ref=='J1':
   for fh,f in records(fp,'FILL'):
    if fh['id']in['e55','e56']:
     assert f['layerId']==12 and f['path'][0][0]=='CIRCLE';_,hx,hy,hr=f['path'][0];hg=scale(transformed(Point(hx,hy).buffer(hr,resolution=96),c),MM,MM,origin=(0,0));holes.append({'id':'J1.'+fh['id'],'g':hg,'net':'','plated':False,'sourceType':'Multi-Layer locating-hole FILL; physically verified on baseline Board BREP'})
 for h,p in records(pcb,'PAD'):addpad(str(p.get('num')or h['id']),str(p.get('num')or h['id']),p,{},p.get('netName',''))
 lines=[];vias=[]
 for h,d in records(pcb,'LINE'):
  t={'id':h['id'],'net':d['netName'],'layer':d['layerId'],'x1':d['startX'],'y1':d['startY'],'x2':d['endX'],'y2':d['endY'],'width':d['width'],'locked':d['locked']};lines.append(t);g=LineString([(t['x1']*MM,t['y1']*MM),(t['x2']*MM,t['y2']*MM)]).buffer(t['width']*MM/2,resolution=48);es.append({'id':t['id'],'kind':'line','net':t['net'],'layers':{t['layer']},'g':g,'through':False,'xy':None,'locked':d['locked']})
 for h,d in records(pcb,'VIA'):
  v={'id':h['id'],'net':d['netName'],'x':d['centerX'],'y':d['centerY'],'diameter':d['viaDiameter'],'holeDiameter':d['holeDiameter'],'locked':d['locked'],'mask':{'top':d.get('topSolderExpansion'),'bottom':d.get('bottomSolderExpansion')}};vias.append(v);xy=[v['x']*MM,v['y']*MM];g=Point(xy).buffer(v['diameter']*MM/2,resolution=96);hg=Point(xy).buffer(v['holeDiameter']*MM/2,resolution=96);es.append({'id':v['id'],'kind':'via','connect_g':g.difference(hg),'net':v['net'],'layers':{1,2,15,16},'g':g,'through':True,'xy':xy,'locked':d['locked']});holes.append({'id':v['id'],'g':hg,'net':v['net'],'plated':True})
 return dict(source=raw,docs=docs,pcb=pcb,es=es,pads=pads,components=comp,holes=holes,lines=lines,vias=vias)

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('archive',type=Path);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--preview',type=Path,required=True);ap.add_argument('--copper',type=Path,required=True);ap.add_argument('--corridors',type=Path,required=True);ap.add_argument('--patch-report',type=Path,required=True);a=ap.parse_args();d=load(a.archive);es=d['es'];mapping=json.loads(a.patch_report.read_text())['mapping'];newids={x['primitiveId']for x in mapping};tags={x['primitiveId']:x['tag']for x in mapping}
 new=[e for e in es if e['id']in newids];tree=STRtree([e['g']for e in es]);fails=[];minimum=None;allfails=[];offset_fails=[];offset_min=None
 for i,e in enumerate(es):
  if e['kind']not in ['line','via']:continue
  for j in tree.query(e['g'].buffer(GAP+.01)):
   f=es[j]
   if j>=i or not(e['layers']&f['layers']&{1,2})or(e['net']and e['net']==f['net']):continue
   gap=e['g'].distance(f['g']);r={'a':e['id'],'aTag':tags.get(e['id']),'net':e['net'],'b':f['id'],'bTag':tags.get(f['id']),'foreign':f['net'],'gap_mm':gap}
   if e['id']in newids or f['id']in newids:
    if minimum is None or gap<minimum['gap_mm']:minimum=r
    if gap<GAP-1e-6:fails.append(r)
    robust_gap=gap-e.get('offset_uncertainty_mm',0)-f.get('offset_uncertainty_mm',0);rr={**r,'lower_bound_gap_mm':robust_gap}
    if offset_min is None or robust_gap<offset_min['lower_bound_gap_mm']:offset_min=rr
    if robust_gap<GAP-1e-6:offset_fails.append(rr)
   if gap<GAP-1e-6:allfails.append(r)
 regions=[];mounts=[]
 for h,p in records(d['pcb'],'REGION'):
  assert p['regionType']=='PROHIBIT'and len(p['path'])==1;shape=p['path'][0];assert shape[0]=='CIRCLE';mounts.append((h['id'],p['layerId'],Point(shape[1]*MM,shape[2]*MM).buffer(shape[3]*MM,resolution=96)))
 corridors=json.loads(a.corridors.read_text());corridor=unary_union([Polygon([(x*MM,y*MM)for x,y in p['exterior']])for p in corridors['polygons']])
 for e in new:
  for rid,layer,g in mounts:
   if layer in e['layers']and e['g'].intersects(g):regions.append({'id':e['id'],'tag':tags[e['id']],'region':rid})
  if 2 in e['layers']and e['g'].intersects(corridor):regions.append({'id':e['id'],'tag':tags[e['id']],'region':'reviewed-HS-NoWires-corridor'})
 smd=d['pads'];minhole=None;holefail=[];maskmin=None;maskfail=[];offset_mask_min=None;offset_mask_fail=[]
 for v in d['vias']:
  if v['id']not in newids:continue
  q=Point(v['x']*MM,v['y']*MM);hr=v['holeDiameter']*MM/2
  for p in smd:
   gap=q.distance(p['outer'])-hr;r={'via':v['id'],'tag':tags[v['id']],'net':v['net'],'pad':p['id'],'padNet':p['net'],'holeToCopper_mm':gap}
   if minhole is None or gap<minhole['holeToCopper_mm']:minhole=r
   if gap<0:holefail.append(r)
   # Source null inherits2mil; use at least2mil allowance conservatively.
   expand=max(2,p['maskExpansion_mil']or 0)*MM;mg=q.distance(p['outer'].buffer(expand,resolution=96))-hr;mr={**r,'maskAllowance_mm':expand,'holeToOpening_mm':mg}
   if maskmin is None or mg<maskmin['holeToOpening_mm']:maskmin=mr
   if mg<.10-1e-6:maskfail.append(mr)
   robust_mask=mg-p['offset_uncertainty_mm'];mr2={**mr,'lower_bound_hole_to_opening_mm':robust_mask,'offset_envelope_mm':p['offset_uncertainty_mm']}
   if offset_mask_min is None or robust_mask<offset_mask_min['lower_bound_hole_to_opening_mm']:offset_mask_min=mr2
   if robust_mask<.10-1e-6:offset_mask_fail.append(mr2)
 # Every new via versus all native pad/via/nonpad drills and old via windows.
 drill_min=None;drill_overlaps=[];old_mask_min=None;old_mask_fails=[]
 for i,h in enumerate(d['holes']):
  for f in d['holes'][:i]:
   if h['id']not in newids and f['id']not in newids:continue
   gap=h['g'].distance(f['g'])-h.get('offset_uncertainty_mm',0)-f.get('offset_uncertainty_mm',0);r={'a':h['id'],'b':f['id'],'a_net':h['net'],'b_net':f['net'],'lower_bound_edge_gap_mm':gap}
   if drill_min is None or gap<drill_min['lower_bound_edge_gap_mm']:drill_min=r
   if gap<=0:drill_overlaps.append(r)
 for v in d['vias']:
  if v['id']not in newids:continue
  for f in d['vias']:
   if f['id']in newids:continue
   for layer in ['top','bottom']:
    ex=f['mask'][layer];radius=(f['diameter']/2+(2 if ex is None else ex))*MM
    if radius<=0:continue
    gap=math.hypot(v['x']-f['x'],v['y']-f['y'])*MM-v['holeDiameter']*MM/2-radius;r={'via':v['id'],'original_via':f['id'],'layer':layer,'hole_to_opening_mm':gap}
    if old_mask_min is None or gap<old_mask_min['hole_to_opening_mm']:old_mask_min=r
    if gap<.1-1e-6:old_mask_fails.append(r)
 # Exact planar connectivity; drill voids are not treated as filled pad copper.
 nets=sorted({e['net']for e in es if e['net']});conn={};unconnected={};ground_groups=[]
 for net in nets:
  ix=[i for i,e in enumerate(es)if e['net']==net];parent={i:i for i in ix}
  def root(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  for i in ix:
   e=es[i]
   for j in tree.query(e['g'].buffer(.000001)):
    if j>=i or j not in parent:continue
    f=es[j]
    # Shrink uncertain pad copper so a retained connection is valid for every
    # documented/observed offset interpretation inside the stated envelope.
    eg=e.get('connect_g',e['g']).buffer(-e.get('offset_uncertainty_mm',0));fg=f.get('connect_g',f['g']).buffer(-f.get('offset_uncertainty_mm',0))
    if e['layers']&f['layers']&{1,2}and eg.distance(fg)<=.000001:parent[root(i)]=root(int(j))
  groups=collections.defaultdict(list)
  for i in ix:groups[root(i)].append(i)
  pg=[g for g in groups.values()if any(es[i]['kind']=='pad'for i in g)];conn[net]=[[es[i]['id']for i in g if es[i]['kind']=='pad']for g in pg]
  if net=='GND':ground_groups=[{'pads':[es[i]['id']for i in g if es[i]['kind']=='pad'],'through':[es[i]['id']for i in g if es[i].get('through')]}for g in pg]
  elif len(pg)>1:unconnected[net]=conn[net]
 # Analytical full-plane feasibility: preserve the actual POUR boundary, remove
 # all foreign through-copper with6mil antipads and all nonplated drill holes.
 plane_reports=[]
 for h,p in records(d['pcb'],'POUR'):
  rect=p['path'][0];assert p['netName']=='GND'and rect[0]=='R';_,x,y,w,hh,*_=rect;plane=box(x*MM,(y-hh)*MM,(x+w)*MM,y*MM)
  avoid=[e['g'].buffer(GAP,resolution=64)for e in es if e.get('through')and e['net']!='GND']+[h['g'].buffer(0 if h['plated']else GAP,resolution=64)for h in d['holes']]
  plane=plane.difference(unary_union(avoid));connected_area=max(list(plane.geoms),key=lambda g:g.area)if plane.geom_type=='MultiPolygon'else plane
  misses=[]
  for gi,g in enumerate(ground_groups):
   candidates=[e for e in es if e['id']in g['through']]
   if not any(e['g'].intersection(connected_area).area>1e-8 for e in candidates):misses.append(gi)
  plane_reports.append({'id':h['id'],'layer':p['layerId'],'area_mm2':plane.area,'connected_components':len(plane.geoms)if plane.geom_type=='MultiPolygon'else 1,'ground_group_misses':misses,'method':'Analytical GND boundary minus exact foreign through-copper antipads and NPTH holes; native pour cache intentionally absent.'})
 report={'schema':'calxus.offline-native-source-geometry.v1','archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(d['source']).hexdigest(),'geometry_source':'Independently parsed saved ZIP archive records; not live editor; no rounded API geometry','counts':{'lines':len(d['lines']),'vias':len(d['vias']),'components':len(d['components']),'copper_pads':len(d['pads']),'nc_copper_pads':sum(not p['net']for p in d['pads']),'new_copper':len(new)},'new_copper_clearance_requirement_mm':GAP,'new_copper_clearance_failures':fails,'minimum_new_copper_gap':minimum,'all_copper_clearance_failures_including_preserved_baseline':allfails,'preserved_baseline_rounding_exceptions':[r for r in allfails if r['a']not in newids and r['b']not in newids and GAP-r['gap_mm']<=.00005],'preserved_baseline_rounding_exception_note':'Unmodified historical HS source nominal6mil pair gaps have source/segment approximation deficits up to0.000025mm. Approved USB_UP edits are included in strict new-copper checks. New copper has a strict1e-6mm numerical tolerance only.','region_failures':regions,'via_hole_smd_overlaps':holefail,'minimum_new_via_hole_smd_gap':minhole,'conservative_new_via_mask_margin_minimum':maskmin,'conservative_new_via_mask_margin_failures':maskfail,'unconnected_non_gnd':unconnected,'outer_pad_groups':conn,'ground_groups':ground_groups,'analytical_ground_planes':plane_reports,'native_import_verified':False,'native_drc_verified':False,'native_pour_rebuild_required':True,'cam_verified':False};report['pad_offset_sensitivity']={'method':'For each pad, expand clearance obstacles and shrink connection copper by2*hypot(padOffsetX,padOffsetY), covering zero/rotated/reversed offset conventions. Nominal source centers remain unchanged. Native CAM must resolve actual transform semantics.','official_format_reference':'https://prodocs.lceda.cn/en/format/pcb/pad_via/','max_envelope_mm':max(p['offset_uncertainty_mm']for p in d['pads']),'minimum_new_copper_clearance':offset_min,'clearance_failures':offset_fails,'minimum_new_drill_to_mask':offset_mask_min,'mask_failures':offset_mask_fail,'connectivity_uses_eroded_pad_copper':True}
 report['minimum_new_via_to_any_drill_gap']=drill_min;report['new_drill_overlaps']=drill_overlaps;report['minimum_new_via_to_original_via_mask_gap']=old_mask_min;report['new_via_to_original_mask_failures']=old_mask_fails
 report['passed']=not(fails or offset_fails or regions or holefail or maskfail or offset_mask_fail or drill_overlaps or old_mask_fails or unconnected or any(p['ground_group_misses']for p in plane_reports))
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n');a.copper.write_text(json.dumps({'schema':'calxus.archive-copper-extraction.v1','units':'mil','sourceArchiveSHA256':report['archive_sha256'],'lines':d['lines'],'vias':d['vias']},indent=2)+'\n')
 # Exact source artwork preview, not a screenshot or CAM rendering.
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 from matplotlib.patches import Polygon as MP
 fig,axs=plt.subplots(2,1,figsize=(17,18));fig.patch.set_facecolor('#f4f6f8')
 colors={'GND':'#5a8b7a','USB_SIL_DP':'#ed6a42','USB_SIL_DM':'#f29a5b','USB_UART_DP':'#7a58ba','USB_UART_DM':'#aa86da'}
 for ax,layer,title in zip(axs,[1,2],['L1 - Top copper','L4 - Bottom copper (same board XY view)']):
  ax.set_facecolor('#fffefa');ax.add_patch(plt.Rectangle((0,0),80,42,fill=False,color='#233342',lw=1.4));
  for rid,la,g in mounts:
   if la==layer:ax.add_patch(MP(list(g.exterior.coords),facecolor='#eceff2',edgecolor='#7d8b98',lw=.5))
  if layer==2:
   geoms=list(corridor.geoms)if corridor.geom_type=='MultiPolygon'else[corridor]
   for g in geoms:ax.add_patch(MP(list(g.exterior.coords),facecolor='#e3edf6',edgecolor='none',alpha=.65))
  for e in es:
   if layer not in e['layers']:continue
   if e['kind']=='line':color=colors.get(e['net'],'#456c92'if layer==1 else'#a26262');alpha=.85
   elif e['kind']=='via':color='#916d26';alpha=.95
   else:color='#4b555e'if e['net']else'#b3b7bb';alpha=.9
   geoms=list(e['g'].geoms)if e['g'].geom_type=='MultiPolygon'else[e['g']]
   for g in geoms:
    if not hasattr(g,'exterior'):continue
    ax.add_patch(MP(list(g.exterior.coords),facecolor=color,edgecolor='none',alpha=alpha))
  for h in d['holes']:
   geoms=list(h['g'].geoms)if h['g'].geom_type=='MultiPolygon'else[h['g']]
   for g in geoms:ax.add_patch(MP(list(g.exterior.coords),facecolor='#fffefa',edgecolor='none'))
  for c in d['components']:ax.text(c['x'],c['y'],c['ref'],fontsize=5.3,ha='center',va='center',color='#141c23',bbox={'facecolor':'white','alpha':.65,'pad':.35,'edgecolor':'none'})
  ax.set_aspect('equal');ax.set_xlim(-1.3,81.3);ax.set_ylim(-1.2,43.4);ax.set_xlabel('mm');ax.set_ylabel('mm');ax.set_title(title,loc='left',fontsize=14,weight='bold');ax.grid(alpha=.12)
 fig.suptitle('Calxus Rev A - saved native routing' if a.archive.stem.endswith('_final') else 'Calxus Rev A - complete native-source routing candidate',fontsize=20,weight='bold',y=.97)
 fig.text(.5,.027,f"{len(d['lines'])} line records / {len(d['vias'])} vias / {len(d['components'])} components  |  Source-derived preview; final native DRC and CAM separate",ha='center',fontsize=11,color='#374756');fig.tight_layout(rect=[.01,.045,.99,.95]);a.preview.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.preview,dpi=180);fig.savefig(a.preview.with_suffix('.svg'));plt.close(fig)
 print(json.dumps({k:report[k]for k in ['archive_sha256','counts','passed','minimum_new_copper_gap','minimum_new_via_hole_smd_gap','unconnected_non_gnd']}));print('violations',len(fails),'baseline-inclusive',len(allfails),'mask',len(maskfail),'regions',len(regions))
if __name__=='__main__':main()
