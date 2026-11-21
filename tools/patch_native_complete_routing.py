#!/usr/bin/env python3
"""Build a reproducible offline Calxus native candidate from audited r7 source.

This changes only the approved J2 instance model-Z property, adds reviewed
LINE/VIA records, applies the explicitly approved USB_UP local repair, and removes stale derived POURED caches. It never edits a
live document. Native import, pour rebuild, DRC and CAM remain mandatory.
"""
import argparse,copy,hashlib,json,math,zipfile
from pathlib import Path
from patch_native_ep_stencil import parse,dump
from apply_native_usb_up_repair import apply as repair_usb_up

PCB='2a0c39c6c6694f40'
BASE_SHA='18d8a0ccdbf3b630a9615d0ea36fb3fe75de02d21a5d2e9f1b2f07a6cd53cfa9'
PLAN_SHA='27e055ef8128dac9e3503b30208e29fd40e5a7d9eeab500c0546b907e6416423'
J2='b5596e790541d216'
MODEL_KEY='3D Model Transform'
OLD_MODEL='562.991,393.7,0,0,0,0,-0.001,-157.48,-98.425'
NEW_MODEL='562.991,393.7,0,0,0,0,-0.001,-157.48,-94.487992126'
PRECISION_DELTAS_MM={'additional_2_via0':{'dx':0,'dy':-.01,'reason':'Exact native baseline via diameter requires6mil foreign copper clearance.'},'iteration4_via35':{'dx':.004,'dy':0,'reason':'Exact native R32.1 pad and2mil mask expansion require>=0.10mm solder-mask bridge.'},'additional_5_via0':{'dx':0,'dy':-.05,'reason':'TP6 bottom mask opening requires>=0.10mm drill-edge-to-opening isolation; top C7 and TP6 placement unchanged.'}}
VIPPO={'17077d66f911113b':'U2.33','89573436f3d877d6':'U2.33','400bbe0a7d6d643b':'U3.17','42761d9427b0bc87':'U3.17'}
def sha(b):return hashlib.sha256(b).hexdigest()
def effective(rows,doc):
 out={}
 for r in rows:
  if r['doc']==doc and 'id'in r['h']:
   key=(r['h']['type'],r['h']['id'])
   if r['d'] is None:out.pop(key,None)
   else:out[key]=r
 return out

def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('base',type=Path);a.add_argument('plan',type=Path);a.add_argument('output',type=Path);a.add_argument('--report',type=Path,required=True);a.add_argument('--via-manifest',type=Path,required=True);args=a.parse_args()
 assert args.output.resolve()!=args.base.resolve(),'Never overwrite baseline'
 basebytes=args.base.read_bytes();planbytes=args.plan.read_bytes();assert sha(basebytes)==BASE_SHA,'Wrong reviewed r7 source';assert sha(planbytes)==PLAN_SHA,'Wrong immutable complete plan';plan=json.loads(planbytes)
 assert plan['pcbId']==PCB and plan['units']=='mil' and len(plan['tracks'])==1356 and len(plan['vias'])==128
 assert plan['review']['hard_geometry_passed'] and plan['review']['candidate_foreign_clearance_passed'] and plan['review']['usb_corridor_passed']
 with zipfile.ZipFile(args.base)as zin:
  assert zin.testzip() is None;entries=zin.namelist();names=[n for n in entries if n.endswith('.epru')];assert len(names)==1;name=names[0];original=zin.read(name);rows,docs=parse(original);board=effective(rows,PCB)
  count=lambda typ:sum(k[0]==typ for k in board)
  assert (count('LINE'),count('VIA'),count('COMPONENT'),count('PAD'),count('POUR'),count('POURED'),count('REGION'),count('LAYER_PHYS'))==(139,61,97,27,2,2,8,13)
  baseline_quantization=[]
  for kind,keys,srcfields in [('LINE','lines',{'net':'netName','layer':'layerId','x1':'startX','y1':'startY','x2':'endX','y2':'endY','width':'width'}),('VIA','vias',{'net':'netName','x':'centerX','y':'centerY','holeDiameter':'holeDiameter','diameter':'viaDiameter'})]:
   for p in plan['baseline'][keys]:
    d=board[(kind,p['id'])]['d'];assert d['locked'] is True
    for pk,sk in srcfields.items():
     assert d[sk]==p[pk] or(isinstance(d[sk],(int,float))and abs(d[sk]-p[pk])<=.11),(p['id'],pk,d[sk],p[pk])
     if d[sk]!=p[pk]:baseline_quantization.append({'id':p['id'],'field':pk,'authoritative_source_mil':d[sk],'API_audit_mil':p[pk],'delta_mil':d[sk]-p[pk]})
  j2=board[('COMPONENT',J2)];j2new=copy.deepcopy(j2['d']);assert MODEL_KEY not in j2new['attrs']
  device=effective(rows,'f88be022b0b8e1ec')[('META','META')]['d'];assert device['attributes'][MODEL_KEY]==OLD_MODEL
  j2new['attrs'][MODEL_KEY]=NEW_MODEL;test=copy.deepcopy(j2new);del test['attrs'][MODEL_KEY];assert test==j2['d']
  allids={r['h'].get('id') for r in rows};ticket=max(r['h'].get('ticket',0) for r in rows)+1;newrows=[];mapping=[]
  for kind,items in [('VIA',plan['vias']),('LINE',plan['tracks'])]:
   for p in items:
    pid=sha(('Calxus-native-candidate|'+PLAN_SHA+'|'+kind+'|'+p['tag']).encode())[:16];assert pid not in allids;allids.add(pid)
    h={'type':kind,'ticket':ticket,'id':pid};ticket+=1
    if kind=='LINE':
     d={'partitionId':'','groupId':0,'netName':p['net'],'layerId':p['layer'],'startX':p['x1'],'startY':p['y1'],'endX':p['x2'],'endY':p['y2'],'width':p['width'],'locked':False,'zIndex':-1}
     assert d['layerId']in[1,2] and d['width']>0
    else:
     d={'partitionId':'','groupId':0,'netName':p['net'],'ruleName':'','centerX':p['x'],'centerY':p['y'],'holeDiameter':p['holeDiameter'],'viaDiameter':p['diameter'],'viaType':'NORMAL','topSolderExpansion':-p['diameter']/2,'bottomSolderExpansion':-p['diameter']/2,'locked':False,'unusedInnerLayers':[],'propagationDelay':0}
     if p['tag']in PRECISION_DELTAS_MM:
      delta=PRECISION_DELTAS_MM[p['tag']];d['centerX']+=delta['dx']/.0254;d['centerY']+=delta['dy']/.0254
     assert 0<d['holeDiameter']<d['viaDiameter'];assert d['viaDiameter']+2*d['topSolderExpansion']==0 and d['viaDiameter']+2*d['bottomSolderExpansion']==0
    newrows.append(dump(h,d,'\n'));mapping.append({'kind':kind,'primitiveId':pid,'tag':p['tag'],'planSHA256':PLAN_SHA})
  assert len(newrows)==1484 and len({m['primitiveId']for m in mapping})==1484
  last=max(r['index']for r in rows if r['doc']==PCB);cached=[r for r in rows if r['doc']==PCB and r['h'].get('type')=='POURED'];cacheidx={r['index']for r in cached};out=[]
  for r in rows:
   if r['index'] in cacheidx:continue
   if r['index']==j2['index']:
    header=r['raw'].split('||',1)[0];ending='\r\n'if r['raw'].endswith('\r\n')else'\n';out.append(header+'||'+json.dumps(j2new,ensure_ascii=False,separators=(',',':'))+'|'+ending)
   else:out.append(r['raw'])
   if r['index']==last:out.extend(newrows)
  updated=''.join(out).encode();updated,mapping,usb_repair=repair_usb_up(updated,mapping);ar,ad=parse(updated);ab=effective(ar,PCB);assert docs==ad
  approved_baseline_ids=set(usb_repair['removed_baseline_line_ids']+usb_repair['modified_baseline_line_ids']);newids={m['primitiveId']for m in mapping};protected_before=b''.join(r['raw'].encode()for r in rows if r['index']!=j2['index']and r['index']not in cacheidx and not(r['doc']==PCB and r['h'].get('id')in approved_baseline_ids));protected_after=b''.join(r['raw'].encode()for r in ar if not(r['doc']==PCB and (r['h'].get('id')==J2 or r['h'].get('id')in newids)))
  assert protected_before==protected_after,'Protected source changed'
  counts={k:sum(key[0]==k for key in ab)for k in ['COMPONENT','LINE','VIA','PAD','POUR','POURED','REGION','LAYER_PHYS','PAD_NET']};assert counts['LINE']==1504 and counts['VIA']==189 and counts['POURED']==0
  assert len([key for key in ab if key[0]in['LINE','VIA']])==1693
  args.output.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(args.output,'w')as zout:
   for info in zin.infolist():zout.writestr(copy.copy(info),updated if info.filename==name else zin.read(info.filename))
   zout.comment=zin.comment
  with zipfile.ZipFile(args.output)as reread:
   assert reread.testzip()is None and reread.namelist()==entries;assert reread.read(name)==updated
   for entry in entries:
    if entry!=name:assert reread.read(entry)==zin.read(entry)
  assert args.base.read_bytes()==basebytes
  report={'schema':'calxus.offline-native-complete-route-patch.v1','source_archive':str(args.base),'source_archive_sha256':BASE_SHA,'source_epru_sha256':sha(original),'plan_sha256':PLAN_SHA,'output_archive':str(args.output),'output_archive_sha256':sha(args.output.read_bytes()),'output_epru_sha256':sha(updated),'output_bytes':args.output.stat().st_size,'counts':counts,'added':{'LINE':1369,'VIA':128},'usb_up_local_repair':usb_repair,'precision_via_adjustments_mm':PRECISION_DELTAS_MM,'unique_new_and_modified_ids':len(mapping),'baseline139_lines_61_vias_byte_preserved':False,'baseline_130_unmodified_lines_61_vias_byte_preserved':True,'approved_baseline_line_modifications':9,'baseline_api_quantization_differences':baseline_quantization,'all_other_source_records_byte_preserved':True,'protected_source_sha256':sha(protected_before),'other_zip_entries_byte_preserved':True,'archive_independently_reopened_and_crc_checked':True,'j2_model_change':{'componentId':J2,'only_field':'COMPONENT.attrs.3D Model Transform','inherited_original':OLD_MODEL,'instance_override':NEW_MODEL,'delta_model_z_mm':.1,'native_renderer_adoption_verified':False},'invalidated_derived_cache':{'type':'POURED','count':2,'ids':[r['h']['id']for r in cached],'original_records_sha256':sha(''.join(r['raw']for r in cached).encode()),'reason':'Old filled-plane cache predates128new vias and cannot be reused safely; original POUR boundaries/rules preserved. Rebuild both GND pours after native import.'},'native_import_verified':False,'native_drc_verified':False,'cam_verified':False,'mapping':mapping}
  args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  vm=[]
  for m in mapping:
   if m['kind']!='VIA':continue
   d=ab[('VIA',m['primitiveId'])]['d'];vm.append({**m,'net':d['netName'],'center_mm':[d['centerX']*.0254,d['centerY']*.0254],'x_mm':d['centerX']*.0254,'y_mm':d['centerY']*.0254,'hole_diameter_mm':d['holeDiameter']*.0254,'outer_diameter_mm':d['viaDiameter']*.0254,'classification':'ordinary-through-via','VIPPO':False,'solderMaskExpansion_mil':{'topSolderMask':d['topSolderExpansion'],'bottomSolderMask':d['bottomSolderExpansion']}})
  ep=[]
  for pid,pad in VIPPO.items():
   d=ab[('VIA',pid)]['d'];ep.append({'primitiveId':pid,'footprintPad':pad,'net':d['netName'],'center_mm':[d['centerX']*.0254,d['centerY']*.0254],'hole_diameter_mm':d['holeDiameter']*.0254,'outer_diameter_mm':d['viaDiameter']*.0254,'classification':'approved-original-EP-VIPPO','VIPPO':True})
  manifest={'schema':'calxus.offline-candidate-route-via-manifest.v1','source':'Independently reopened candidate archive VIA records, not a live EDA readback','source_archive_sha256':report['output_archive_sha256'],'planSHA256':PLAN_SHA,'pcbId':PCB,'expected_count':128,'actualTotalVias':189,'records':vm,'originalVIPPO':ep,'native_import_verified':False,'cam_verified':False};args.via_manifest.parent.mkdir(parents=True,exist_ok=True);args.via_manifest.write_text(json.dumps(manifest,indent=2)+'\n')
  print(json.dumps({k:v for k,v in report.items()if k!='mapping'},indent=2))
if __name__=='__main__':main()
