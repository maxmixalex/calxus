#!/usr/bin/env python3
"""Verify saved native final routing against reviewed candidate geometry.

Native primitives may be split/merged. Compare physical copper unions and exact
via/pad/component contracts instead of requiring identical line record counts.
"""
import argparse,json,math,hashlib,collections
from pathlib import Path
from check_native_candidate_geometry import load,records,MM
from shapely.ops import unary_union
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate',type=Path);ap.add_argument('native',type=Path);ap.add_argument('--patch-report',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--native-review-mapping',type=Path,required=True);a=ap.parse_args();c=load(a.candidate);n=load(a.native);patch=json.loads(a.patch_report.read_text());native_sha=hashlib.sha256(a.native.read_bytes()).hexdigest();candidate_sha=hashlib.sha256(a.candidate.read_bytes()).hexdigest();assert candidate_sha==patch['output_archive_sha256'];TOL=.00001
# Exact source component placement and full physical footprint definitions.
def rowmap(doc):return{(h['type'],str(h.get('id'))):d for h,d in doc['records']}
def rows_type(doc,typ):return{h['id']:d for h,d in records(doc,typ)}
compc=rows_type(c['pcb'],'COMPONENT');compn=rows_type(n['pcb'],'COMPONENT');compdiff=[]
for key in set(compc)|set(compn):
 if compc.get(key)!=compn.get(key):compdiff.append({'id':key,'candidate':compc.get(key),'native':compn.get(key)})
cdocs={x['head']['uuid']:x for x in c['docs']};ndocs={x['head']['uuid']:x for x in n['docs']};fpdiff=[]
for uuid,doc in cdocs.items():
 if doc['head'].get('docType')=='FOOTPRINT' and rowmap(doc)!=rowmap(ndocs[uuid]):fpdiff.append(uuid)
fixed_types=['PAD','PAD_NET','REGION','LAYER_PHYS','POUR'];fixed_diff=[]
for typ in fixed_types:
 if rows_type(c['pcb'],typ)!=rows_type(n['pcb'],typ):fixed_diff.append(typ)
# Compare full189via populations by net and physical dimensions, independent IDs.
matched=[];unmatched=list(n['vias']);viafail=[]
for v in c['vias']:
 options=[u for u in unmatched if u['net']==v['net']]
 if not options:viafail.append({'candidateId':v['id'],'reason':'no matching net'});continue
 u=min(options,key=lambda z:math.hypot(z['x']-v['x'],z['y']-v['y']));center=math.hypot(u['x']-v['x'],u['y']-v['y'])*MM;hole=abs(u['holeDiameter']-v['holeDiameter'])*MM;outer=abs(u['diameter']-v['diameter'])*MM
 r={'candidateId':v['id'],'nativeId':u['id'],'net':v['net'],'center_difference_mm':center,'hole_difference_mm':hole,'outer_difference_mm':outer}
 if max(center,hole,outer)>TOL:viafail.append(r)
 matched.append(r);unmatched.remove(u)
# Record physical trace differences. A strict10nm allowance absorbs native source
# four-decimalmil serialization. Any remaining copper delta is explicitly listed.
def groups(D):
 out=collections.defaultdict(list)
 for e in D['es']:
  if e['kind']=='line':
   for lay in e['layers']:out[(e['net'],lay)].append(e['g'])
 return{k:unary_union(v)for k,v in out.items()}
cg=groups(c);ng=groups(n);trace_deltas=[]
for k in set(cg)|set(ng):
 if k not in cg or k not in ng:trace_deltas.append({'net':k[0],'layer':k[1],'missing_group':True});continue
 added=ng[k].difference(cg[k].buffer(TOL,resolution=32));removed=cg[k].difference(ng[k].buffer(TOL,resolution=32))
 if added.area>1e-10 or removed.area>1e-10:trace_deltas.append({'net':k[0],'layer':k[1],'native_added_area_mm2':added.area,'native_removed_area_mm2':removed.area,'added_bounds_mm':list(added.bounds)if not added.is_empty else[],'removed_bounds_mm':list(removed.bounds)if not removed.is_empty else[]})
# Strict geometry audit mapping: every native trace except130 explicitly preserved
# baseline lines, every new via, and all5approved baselineUP modifications.
modified=set(patch['usb_up_local_repair']['modified_baseline_line_ids']);old_native=set(t['id']for t in c['lines']if t['id']not in {x['primitiveId']for x in patch['mapping']});assert len(old_native)==130
mapping=[{'kind':'LINE','primitiveId':t['id'],'tag':'native_final_'+t['id']}for t in n['lines']if t['id']not in old_native]
oldvia_ids=set(v['id']for v in c['vias']if v['id']not in {x['primitiveId']for x in patch['mapping']});assert len(oldvia_ids)==61
mapping.extend({'kind':'VIA','primitiveId':v['id'],'tag':'native_final_'+v['id']}for v in n['vias']if v['id']not in oldvia_ids)
a.native_review_mapping.write_text(json.dumps({'source_archive_sha256':native_sha,'mapping':mapping},indent=2)+'\n')
report={'schema':'calxus.native-final-to-reviewed-candidate.v1','candidate_archive_sha256':candidate_sha,'native_archive_sha256':native_sha,'geometry_source':'Independently parsed saved native project ZIP archives; no rounded API getters','candidate_counts':{'lines':len(c['lines']),'vias':len(c['vias']),'components':len(compc)},'native_counts':{'lines':len(n['lines']),'vias':len(n['vias']),'components':len(compn)},'component_source_differences':compdiff,'footprint_source_differences':fpdiff,'fixed_source_type_differences':fixed_diff,'via_matches':matched,'via_failures':viafail,'unmatched_native_vias':unmatched,'physical_trace_deltas_beyond_10nm':trace_deltas,'native_review_mapping':str(a.native_review_mapping),'fixed_component_footprint_stack_pad_and_via_contract_passed':not(compdiff or fpdiff or fixed_diff or viafail or unmatched),'native_drc_and_cam':'Separate actual native results must be checked; this report does not hide differences.'};a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['component_source_differences','via_matches']},indent=2))
