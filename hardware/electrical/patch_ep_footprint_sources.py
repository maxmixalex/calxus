"""Prepare precise source patches for project-local U2/U3 EP paste fills only.
Never calls the EDA app. Reads the exported native footprint sources and writes
reviewable source/manifest files. Preserve every original non-target source line.
"""
import json,hashlib,copy,re
from pathlib import Path
P=Path(__file__).resolve().parent;E=P.parent/'evidence'
snap=json.loads((E/'qfn-footprint-sources.json').read_text())
proposal=json.loads((P/'ep_stencil_proposal.json').read_text())
targets={'U2':'e15','U3':'e47'};out=[]
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
for entry in snap['sources']:
    ref=entry['ref'];source=entry['documentSource'];lines=source.splitlines()
    rows=[]
    for line in lines:
        raw=line[:-1]if line.endswith('|')else line
        h,b=raw.split('||',1);rows.append((json.loads(h),json.loads(b)))
    matching=[i for i,(h,b)in enumerate(rows)if h.get('type')=='FILL'and h.get('id')==targets[ref]]
    assert len(matching)==1,(ref,matching)
    index=matching[0];header,old=rows[index]
    assert old['layerId']==7 and old['fillStyle']=='SOLID' and old['netName']==''
    config=next(c for c in proposal['components']if c['reference']==ref)
    ep=next(b for h,b in rows if h['type']=='PAD'and b['num']==config['native_ep_pin'])
    assert ep['topPasteExpansion']==-3937 and ep['defaultPad']['padType']=='RECT'
    # These two EP pad rotations are zero within the footprint source.
    assert ep['padAngle']==0 and ep['relativeAngle']==0
    cx=ep['centerX']+ep.get('padOffsetX',0);cy=ep['centerY']+ep.get('padOffsetY',0)
    maxid=max(int(h['id'][1:])for h,b in rows if re.fullmatch('e[0-9]+',str(h.get('id',''))))
    ticket=max(h.get('ticket',0)for h,b in rows);zmax=max(b.get('zIndex',0)for h,b in rows)
    new=[]
    for j,w in enumerate(config['windows']):
        h=copy.deepcopy(header);b=copy.deepcopy(old)
        if j:h['id']='e'+str(maxid+j);h['ticket']=ticket+j;b['zIndex']=zmax+j
        x=cx+w['center_relative_to_actual_EP_mm'][0]/.0254
        y=cy+w['center_relative_to_actual_EP_mm'][1]/.0254
        ww=w['width_mm']/.0254;hh=w['height_mm']/.0254;r=w['corner_radius_mm']/.0254
        b['path']=[['R',round(x-ww/2,9),round(y+hh/2,9),round(ww,9),round(hh,9),0,round(r,9)]]
        b['width']=0
        new.append((h,b))
    replacement=[json.dumps(h,separators=(',',':'),ensure_ascii=False)+'||'+json.dumps(b,separators=(',',':'),ensure_ascii=False)+'|'for h,b in new]
    updated='\n'.join(lines[:index]+replacement+lines[index+1:])
    # Byte-exact protection of every non-target line is stronger than comparing
    # only pad/net fields, including all masks, signals, models and attributes.
    assert updated.splitlines()[:index]==lines[:index]
    assert updated.splitlines()[index+4:]==lines[index+1:]
    path=P/(ref+'-footprint-ep-four-window.efoo');path.write_text(updated)
    pad_before=[b for h,b in rows if h['type']=='PAD']
    revised=rows[:index]+new+rows[index+1:]
    assert [b for h,b in revised if h['type']=='PAD']==pad_before
    signal_before=[(h,b)for h,b in rows if h['type']=='FILL'and b.get('layerId')==7 and h['id']!=targets[ref]]
    signal_after=[(h,b)for h,b in revised if h['type']=='FILL'and b.get('layerId')==7 and h['id']not in{a['id']for a,b in new}]
    assert signal_before==signal_after
    out.append({'ref':ref,'footprintUuid':entry['footprintUuid'],'libraryUuid':entry['actualFootprint']['libraryUuid'],
        'source_method':entry['sourceMethod'],'source_sha256_before':sha(source),'source_sha256_after':sha(updated),
        'source_file':path.name,'old_fill_id':targets[ref],'old_fill':old,
        'new_fill_ids':[h['id']for h,b in new],'new_fills':[{'header':h,'data':b}for h,b in new],
        'ep_source_copper_center_mil':[cx,cy],'ep_pad_unchanged':True,'all_original_nontarget_lines_unchanged':True,
        'signal_paste_fill_count_preserved':len(signal_before),'new_window_count':4,
        'proposal_coverage_percent':config['coverage_of_actual_copper_percent']})
manifest={'schema':'calxus.ep-stencil-native-patch.v1','status':'PREPARED_NOT_APPLIED','source_snapshot_sha256':sha((E/'qfn-footprint-sources.json').read_text()),
          'patches':out,'native_method':'Apply project/tools/patch_native_ep_stencil.py to a fresh project epro2 archive, then import as a new local project. Do not update global/live libraries.',
          'required_verification':['Refresh actual document footprint source; verify exactly four EP fills and unchanged pads/peripheral paste.','Save PCB true, reopen and verify preservation.','Render/export Top Paste Gerber and count four separate EP openings; inspect no overlap with old single opening.'],
          'sources':['https://prodocs.easyeda.com/en/api/reference/pro-api.lib_footprint.html','https://prodocs.easyeda.com/en/api/reference/pro-api.tpcb_polygonsourcearray.html']}
(P/'ep_stencil_native_patch.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':manifest['status'],'patches':[{k:p[k]for k in ['ref','source_file','new_fill_ids','signal_paste_fill_count_preserved','all_original_nontarget_lines_unchanged']}for p in out]},indent=2))
