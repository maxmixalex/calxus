#!/usr/bin/env python3
"""Replace only U2/U3 exposed-pad paste fills in a new Calxus native archive.

INPUT.epro2 OUTPUT.epro2 --report REPORT.json
Use a fresh routed export (optionally after patch_native_stackup.py). The input
is never overwritten. All other epru source lines and ZIP entries are preserved
byte-for-byte. This is an offline candidate, not proof of successful EDA import.
"""
import argparse,copy,hashlib,json,math,re,zipfile
from pathlib import Path

PCB_UUID='2a0c39c6c6694f40'
TARGETS={
    'U2':{'mpn':'TUSB3410RHBR','uuid':'6d6747048cb070d5','source':'dc96823453a64dbcb382e28438ab8b56',
          'fill':'e15','pin':'33','pad_count':33,'pad_size':137.795,'window_mm':1.49,'offset_mm':.845,
          'old_path':[[-55.118,55.118,'L',55.118,55.118,55.118,-55.118,-55.118,-55.118,-55.118,55.118]]},
    'U3':{'mpn':'CH343P','uuid':'c020f55e3a184cd3','source':'c75e883c09144668b0613740ff1e4391',
          'fill':'e47','pin':'17','pad_count':17,'pad_size':66.929,'window_mm':.65,'offset_mm':.425,
          'old_path':[[-26.761,26.776,'L',26.783,26.776,26.783,-26.768,-26.761,-26.768,-26.761,26.776]]},
}
def sha(b):return hashlib.sha256(b).hexdigest()
def parse(source):
    rows=[];doc=None;docs={}
    for i,raw in enumerate(source.decode('utf-8').splitlines(keepends=True)):
        if not raw.strip():rows.append({'index':i,'raw':raw,'doc':doc,'h':{},'d':None});continue
        h,d=raw.rstrip('\r\n').split('||',1);h=json.loads(h);d=d.removesuffix('|');d=json.loads(d)if d else None
        if h['type']=='DOCHEAD':
            assert d and d.get('uuid') and d.get('docType'),'Malformed document head'
            doc=d['uuid'];assert doc not in docs,'Duplicate DOCHEAD UUID requires manual review: '+doc
            docs[doc]=d
        rows.append({'index':i,'raw':raw,'doc':doc,'h':h,'d':d})
    return rows,docs
def dump(h,d,ending):return json.dumps(h,ensure_ascii=False,separators=(',',':'))+'||'+json.dumps(d,ensure_ascii=False,separators=(',',':'))+'|'+ending
def old_geometry_matches(row,spec):
    d=row['d']
    return bool(row['h'].get('type')=='FILL'and d and d.get('layerId')==7 and d.get('netName')==''
                and d.get('fillStyle')=='SOLID'and d.get('path')==spec['old_path'])

def patch(source,pcb_uuid):
    rows,docs=parse(source)
    assert pcb_uuid in docs and docs[pcb_uuid]['docType']=='PCB','Calxus PCB UUID not found'
    board=[r for r in rows if r['doc']==pcb_uuid]
    refs={};changes=[];replacements={};changed_keys=set();added_keys=set()
    for ref,spec in TARGETS.items():
        ds=[r for r in board if r['h'].get('type')=='ATTR'and r['d']and r['d'].get('key')=='Designator'and r['d'].get('value')==ref]
        assert len(ds)==1,f'Expected unique {ref} designator in target PCB'
        cid=ds[0]['d']['parentId'];comps=[r for r in board if r['h'].get('type')=='COMPONENT'and r['h'].get('id')==cid and r['d']]
        assert len(comps)==1,f'Expected component for {ref}'
        device=json.loads(comps[0]['d']['attrs']['DeviceName'])
        assert device['name']==spec['mpn'],f'MPN mismatch for {ref}: {device}'
        fas=[r for r in board if r['h'].get('type')=='ATTR'and r['d']and r['d'].get('parentId')==cid and r['d'].get('key')=='Footprint']
        assert len(fas)==1,f'Expected unique Footprint reference for {ref}'
        uuid=fas[0]['d']['value'];assert uuid in docs and docs[uuid]['docType']=='FOOTPRINT'
        assert uuid not in refs.values(),'U2 and U3 unexpectedly share a footprint'
        refs[ref]=uuid
        # Reject a shared footprint used by another component/PCB. The patch is
        # intentionally scoped to these two Calxus instances only.
        uses=[r for r in rows if r['h'].get('type')=='ATTR'and r['d']and r['d'].get('key')=='Footprint'and r['d'].get('value')==uuid and docs[r['doc']]['docType']=='PCB']
        assert len(uses)==1 and uses[0]['d']['parentId']==cid,f'{ref} footprint shared by another PCB component'
        fs=[r for r in rows if r['doc']==uuid]
        metas=[r['d']for r in fs if r['h'].get('type')=='META'and r['d']]
        assert len(metas)==1 and metas[0].get('source','').split('|')[0]==spec['source'],f'{ref} footprint provenance mismatch'
        pads=[r for r in fs if r['h'].get('type')=='PAD'and r['d']]
        assert len(pads)==spec['pad_count'],f'{ref} copper pad count differs'
        eps=[r for r in pads if str(r['d'].get('num'))==spec['pin']];assert len(eps)==1
        ep=eps[0]['d'];pad=ep['defaultPad']
        assert pad['padType']=='RECT'and abs(pad['width']-spec['pad_size'])<.0005 and abs(pad['height']-spec['pad_size'])<.0005
        assert ep['topPasteExpansion']==-3937 and ep['bottomPasteExpansion']==-3937,'Unexpected automatic EP paste'
        assert ep['padAngle']==0 and ep['relativeAngle']==0,'Unsupported EP local rotation'
        matches=[r for r in fs if old_geometry_matches(r,spec)]
        assert len(matches)==1,f'{ref}: expected exactly one known original single EP aperture, found {len(matches)}; already-patched or changed source is refused'
        old=matches[0]
        if uuid==spec['uuid']:assert old['h']['id']==spec['fill'],f'{ref} known UUID has changed fill identity'
        paste=[r for r in fs if r['h'].get('type')=='FILL'and r['d']and r['d'].get('layerId')==7]
        assert len(paste)==spec['pad_count'],f'{ref} unexpected extra/missing paste fills'
        maxid=max(int(r['h']['id'][1:])for r in fs if re.fullmatch('e[0-9]+',str(r['h'].get('id',''))))
        ticket=max(r['h'].get('ticket',0)for r in fs)+1
        zmax=max((r['d']or{}).get('zIndex',0)for r in fs)
        ending='\r\n'if old['raw'].endswith('\r\n')else '\n'
        cx=ep['centerX']+ep.get('padOffsetX',0);cy=ep['centerY']+ep.get('padOffsetY',0)
        width=spec['window_mm']/.0254;offset=spec['offset_mm']/.0254;radius=.05/.0254
        new=[]
        for j,(sx,sy)in enumerate([(-1,-1),(1,-1),(-1,1),(1,1)]):
            h=copy.deepcopy(old['h']);d=copy.deepcopy(old['d']);h['ticket']=ticket+j
            if j:h['id']='e'+str(maxid+j);h['firstTicket']=ticket+j;d['zIndex']=zmax+j
            d['path']=[['R',round(cx+sx*offset-width/2,9),round(cy+sy*offset+width/2,9),round(width,9),round(width,9),0,round(radius,9)]]
            d['width']=0
            new.append((h,d));added_keys.add((uuid,h['type'],h['id']))
        changed_keys.add((uuid,old['h']['type'],old['h']['id']))
        replacements[old['index']]=''.join(dump(h,d,ending)for h,d in new)
        area=4*(spec['window_mm']**2-(4-math.pi)*.05**2)
        changes.append({'reference':ref,'component_id':cid,'footprint_uuid':uuid,'known_uuid':spec['uuid'],
                        'uuid_remapped':uuid!=spec['uuid'],'provenance_uuid':spec['source'],
                        'old_fill_id':old['h']['id'],'new_fill_ids':[h['id']for h,d in new],
                        'old_fill_data':old['d'],'new_fill_data':[d for h,d in new],
                        'ep_copper_unchanged':True,'ep_mask_unchanged':True,'peripheral_paste_fills_preserved':len(paste)-1,
                        'aperture_size_mm':spec['window_mm'],'corner_radius_mm':.05,'web_mm':2*spec['offset_mm']-spec['window_mm'],
                        'coverage_percent':area/(pad['width']*pad['height']*.0254**2)*100})
    result=''.join(replacements.get(r['index'],r['raw'])for r in rows).encode('utf-8')
    after,after_docs=parse(result);assert docs==after_docs
    before_protected=''.join(r['raw']for r in rows if(r['doc'],r['h'].get('type'),r['h'].get('id'))not in changed_keys).encode()
    after_protected=''.join(r['raw']for r in after if(r['doc'],r['h'].get('type'),r['h'].get('id'))not in added_keys).encode()
    assert before_protected==after_protected,'A non-target source byte changed'
    assert len(after)==len(rows)+6,'Expected six added FILL records'
    for ref,uuid in refs.items():
        f=[r for r in after if r['doc']==uuid]
        assert len([r for r in f if r['h'].get('type')=='PAD'and r['d']])==TARGETS[ref]['pad_count']
        assert len([r for r in f if r['h'].get('type')=='FILL'and r['d']and r['d'].get('layerId')==7])==TARGETS[ref]['pad_count']+3
    return result,{'pcb_uuid':pcb_uuid,'changes':changes,'changed_existing_fill_records':2,'added_fill_records':6,
                   'all_nontarget_source_bytes_unchanged':True,'protected_bytes_sha256':sha(before_protected),
                   'source_sha256_before':sha(source),'source_sha256_after':sha(result),
                   'editor_import_verified':False,'native_reopen_verified':False,'paste_gerber_verified':False}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('input',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--report',type=Path,required=True);ap.add_argument('--pcb-uuid',default=PCB_UUID);args=ap.parse_args()
    assert args.input.resolve()!=args.output.resolve(),'Never overwrite source archive'
    assert not args.output.exists(),'Choose a new output filename'
    before=sha(args.input.read_bytes())
    with zipfile.ZipFile(args.input)as archive:
        assert archive.testzip()is None
        sources=[n for n in archive.namelist()if n.endswith('.epru')];assert len(sources)==1,f'Expected one epru, found {sources}'
        name=sources[0];updated,report=patch(archive.read(name),args.pcb_uuid)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.output,'w')as output:
            for info in archive.infolist():output.writestr(copy.copy(info),updated if info.filename==name else archive.read(info.filename))
            output.comment=archive.comment
        with zipfile.ZipFile(args.output)as output:
            assert output.testzip()is None and output.namelist()==archive.namelist()
            for n in archive.namelist():
                if n!=name:assert output.read(n)==archive.read(n),'Other ZIP entry changed: '+n
    assert sha(args.input.read_bytes())==before
    report.update(input_archive=str(args.input),output_archive=str(args.output),input_sha256=before,
                  output_sha256=sha(args.output.read_bytes()),epru_entry=name,input_archive_unchanged=True,other_zip_entries_unchanged=True,
                  status='Offline candidate only. Import into a new project, verify actual footprint paste, save/reopen, and render Top Paste Gerber before fabrication.')
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['output_archive','output_sha256','changed_existing_fill_records','added_fill_records','all_nontarget_source_bytes_unchanged','status']},ensure_ascii=False))
if __name__=='__main__':main()
