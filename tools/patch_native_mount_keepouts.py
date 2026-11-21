#!/usr/bin/env python3
"""Repair only the eight known Calxus mount-keepout CIRCLE center Y values.

Use after the physical-stackup and EP-stencil patches on a fresh epro2 archive.
No editor connection. Every header and every non-target source line is retained.
The target geometry is four radius-3 mm circles on both outer copper layers.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import zipfile
from patch_native_ep_stencil import parse

PCB_UUID = '2a0c39c6c6694f40'
CENTERS = [(3.5,3.5),(76.5,3.5),(3.5,38.5),(76.5,38.5)]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def patch(source, uuid):
    rows, docs = parse(source)
    assert docs[uuid]['docType']=='PCB'
    regions=[r for r in rows if r['doc']==uuid and r['h'].get('type')=='REGION' and r['d']]
    assert len(regions)==8, 'Expected exactly the eight known mounting regions'
    changes=[]; replacements={}; seen=set(); keys=set()
    for r in regions:
        d=r['d']; path=d.get('path')
        assert isinstance(path,list) and len(path)==1
        c=path[0]
        assert len(c)==4 and c[0]=='CIRCLE' and c[2]<0, 'Already fixed or unexpected region geometry'
        assert abs(c[3]*.0254-3)<.00001
        matches=[i for i,(x,y) in enumerate(CENTERS) if abs(c[1]*.0254-x)<.00001 and abs(-c[2]*.0254-y)<.00001]
        assert len(matches)==1 and d['layerId'] in [1,2]
        identity=(matches[0],d['layerId']); assert identity not in seen
        seen.add(identity)
        updated=copy.deepcopy(d); updated['path'][0][2]=-c[2]
        # Preserve all fields except the one approved coordinate. Source headers,
        # including existing tickets, remain verbatim for this fresh-project load.
        original_header=r['raw'].split('||',1)[0]
        ending='\r\n' if r['raw'].endswith('\r\n') else '\n' if r['raw'].endswith('\n') else ''
        replacements[r['index']]=original_header+'||'+json.dumps(updated,ensure_ascii=False,separators=(',',':'))+'|'+ending
        keys.add((r['doc'],r['h']['type'],r['h']['id']))
        other_before=copy.deepcopy(d);other_after=copy.deepcopy(updated)
        del other_before['path'][0][2];del other_after['path'][0][2]
        assert other_before==other_after
        changes.append({'id':r['h']['id'],'layer':d['layerId'],'mount_hole':matches[0]+1,
                        'before_path':path,'after_path':updated['path'],
                        'only_center_y_changed':True,'source_header_unchanged':True})
    assert seen=={(i,layer)for i in range(4)for layer in [1,2]}
    result=''.join(replacements.get(r['index'],r['raw'])for r in rows).encode()
    after,after_docs=parse(result);assert docs==after_docs
    keep=lambda r:(r['doc'],r['h'].get('type'),r['h'].get('id'))not in keys
    protected_before=''.join(r['raw']for r in rows if keep(r)).encode()
    protected_after=''.join(r['raw']for r in after if keep(r)).encode()
    assert protected_before==protected_after
    return result,{'pcb_uuid':uuid,'changed_region_records':8,'changes':changes,
                   'all_nontarget_source_bytes_unchanged':True,'protected_bytes_sha256':sha(protected_before),
                   'source_sha256_before':sha(source),'source_sha256_after':sha(result),
                   'native_region_readback_verified':False,'native_jrouter_obstacles_verified':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--pcb-uuid',default=PCB_UUID)
    a=p.parse_args()
    assert a.input.resolve()!=a.output.resolve() and not a.output.exists()
    before=sha(a.input.read_bytes())
    with zipfile.ZipFile(a.input) as z:
        assert z.testzip() is None
        names=[n for n in z.namelist()if n.endswith('.epru')];assert len(names)==1
        name=names[0];updated,report=patch(z.read(name),a.pcb_uuid)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.output,'w')as out:
            for info in z.infolist():out.writestr(copy.copy(info),updated if info.filename==name else z.read(info.filename))
            out.comment=z.comment
        with zipfile.ZipFile(a.output)as out:
            assert out.testzip()is None and out.namelist()==z.namelist()
            for entry in z.namelist():
                if entry!=name:assert out.read(entry)==z.read(entry)
    assert sha(a.input.read_bytes())==before
    report.update(input_archive=str(a.input),input_sha256=before,output_archive=str(a.output),
                  output_sha256=sha(a.output.read_bytes()),epru_entry=name,
                  input_archive_unchanged=True,other_zip_entries_unchanged=True,
                  status='Offline repair candidate only; verify native Region refetch and JRouter obstacle export after official import.')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['output_archive','output_sha256','changed_region_records','all_nontarget_source_bytes_unchanged']}))

if __name__=='__main__':
    main()
