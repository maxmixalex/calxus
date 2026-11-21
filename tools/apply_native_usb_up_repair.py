"""Apply the fixed, source-reviewed local USB_UP remedy to native source records."""
import copy,hashlib,json
from pathlib import Path
from patch_native_ep_stencil import parse,dump
REPAIR=Path(__file__).resolve().parents[1]/'hardware/electrical/native-usb-up-repair.json'
REPAIR_SHA='b9d99163583cc287cd92e6121c48e3b9cb5d9cd4b773069d5c7f88072fcfea97'
PCB='2a0c39c6c6694f40'
def apply(source,mapping):
 raw=REPAIR.read_bytes();assert hashlib.sha256(raw).hexdigest()==REPAIR_SHA
 r=json.loads(raw);rows,docs=parse(source);source_fields={'net':'netName','layer':'layerId','x1':'startX','y1':'startY','x2':'endX','y2':'endY','width':'width'}
 effective={}
 for a in rows:
  if a['doc']==PCB and a['h']['type'] in ['LINE','VIA']:
   if a['d'] is None:effective.pop(a['h']['id'],None)
   else:effective[a['h']['id']]=a
 def checkline(d,p):
  for k,f in source_fields.items():assert d[f]==p[k],(k,d[f],p[k])
 deleted={x['id'] for x in r['delete_lines']};changed={x['id']:x for x in r['modify_lines']};via=r['modify_vias'][0];replacements={}
 for p in r['delete_lines']:checkline(effective[p['id']]['d'],p)
 for pid,x in changed.items():
  a=effective[pid];checkline(a['d'],x['old']);d=copy.deepcopy(a['d'])
  for k,f in source_fields.items():d[f]=x['new'][k]
  replacements[a['index']]=dump(a['h'],d,'\n')
 a=effective[via['id']];d=copy.deepcopy(a['d']);p=via['old'];n=via['new'];assert d['netName']==p['net'] and d['centerX']==p['x']and d['centerY']==p['y']and d['holeDiameter']==p['holeDiameter']and d['viaDiameter']==p['diameter']
 d.update(centerX=n['x'],centerY=n['y'],holeDiameter=n['holeDiameter'],viaDiameter=n['diameter'],topSolderExpansion=-n['diameter']/2,bottomSolderExpansion=-n['diameter']/2);replacements[a['index']]=dump(a['h'],d,'\n')
 allids={a['h'].get('id')for a in rows};ticket=max(a['h'].get('ticket',0)for a in rows)+1;adds=[];newmap=[]
 for p in r['add_lines']:
  pid=hashlib.sha256(('Calxus-reviewed-USB-UP-repair|'+REPAIR_SHA+'|'+p['tag']).encode()).hexdigest()[:16];assert pid not in allids;allids.add(pid)
  d={'partitionId':'','groupId':0,**{f:p[k]for k,f in source_fields.items()},'locked':p['locked'],'zIndex':-1};adds.append(dump({'type':'LINE','ticket':ticket,'id':pid},d,'\n'));ticket+=1
  newmap.append({'kind':'LINE','primitiveId':pid,'tag':'usb_up_repair_'+p['tag'],'repairSHA256':REPAIR_SHA,'planSHA256':r['source_original_plan_sha256']})
 last=max(a['index']for a in rows if a['doc']==PCB);out=[]
 for a in rows:
  if a['doc']==PCB and a['h'].get('id')in deleted:continue
  out.append(replacements.get(a['index'],a['raw']))
  if a['index']==last:out.extend(adds)
 m=[x for x in mapping if x['primitiveId']not in deleted]+newmap
 m.extend({'kind':'LINE','primitiveId':pid,'tag':'usb_up_repair_modified_'+pid,'repairSHA256':REPAIR_SHA,'baselineApprovedModification':True}for pid in changed)
 audit={'contract':str(REPAIR.relative_to(Path(__file__).resolve().parents[1])),'contract_sha256':REPAIR_SHA,'removed_baseline_line_ids':[x for x in deleted if x not in {v['primitiveId']for v in mapping}],'modified_baseline_line_ids':list(changed),'removed_candidate_line_ids':[x for x in deleted if x in {v['primitiveId']for v in mapping}],'new_line_ids':[x['primitiveId']for x in newmap],'modified_via':via,'power_neck':r['power_neck'],'all_hs_vias_preserved':True,'all_components_preserved':True}
 assert len(audit['removed_baseline_line_ids'])==4 and len(audit['modified_baseline_line_ids'])==5 and len(audit['removed_candidate_line_ids'])==2 and len(audit['new_line_ids'])==15
 return ''.join(out).encode(),m,audit
