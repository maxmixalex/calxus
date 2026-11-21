#!/usr/bin/env python3
"""Independently inspect EP paste geometry in current native footprint sources.

The supplied snapshot may explicitly use the reimported project's library
source fallback. Report that provenance; do not call it rendered Gerber proof.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import zipfile

SPECS={'U2':{'pin':'33','pads':33,'ep_mm':3.5,'window_mm':1.49,'offset_mm':.845},
       'U3':{'pin':'17','pads':17,'ep_mm':1.7,'window_mm':.65,'offset_mm':.425}}

def records(source):
    rows=[];head=None;head_count=0;seen=set()
    for line in source.splitlines():
        if not line.strip():continue
        h,d=line.split('||',1);h=json.loads(h);d=d.removesuffix('|');d=json.loads(d)if d else None
        if h['type']=='DOCHEAD':
            if head is None:head=d
            else:assert head==d,'Repeated DOCHEAD has inconsistent metadata'
            head_count+=1
        else:
            key=(h['type'],h.get('id'));assert key not in seen,'Duplicate non-header primitive'
            seen.add(key)
        rows.append((h,d))
    assert head and head['docType']=='FOOTPRINT'
    return rows,head,head_count

def bounds(path):
    assert len(path)==1
    p=path[0]
    if p[0]=='R':
        _,x,y,w,h,rotation,r=p;assert rotation==0 and w>0 and h>0
        return [x,y-h,x+w,y]
    assert all(not isinstance(v,str)or v=='L'for v in p),'Unsupported aperture curve'
    nums=[v for v in p if isinstance(v,(int,float))];assert len(nums)%2==0
    return [min(nums[::2]),min(nums[1::2]),max(nums[::2]),max(nums[1::2])]

def intersection_area(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot',type=Path);p.add_argument('baseline',type=Path)
    p.add_argument('--project-uuid',required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();raw=a.snapshot.read_bytes();snap=json.loads(raw)
    assert snap['units']=='mil' and {e['ref']for e in snap['sources']}==set(SPECS)
    with zipfile.ZipFile(a.baseline)as z:
        names=[n for n in z.namelist()if n.endswith('.epru')];assert len(names)==1
        source=z.read(names[0]).decode()
    original={};active=None
    for line in source.splitlines():
        if not line.strip():continue
        h,d=line.split('||',1);h=json.loads(h);d=d.removesuffix('|');d=json.loads(d)if d else None
        if h['type']=='DOCHEAD':active=d['uuid']
        original.setdefault(active,[]).append((h,d))
    results=[]
    for entry in snap['sources']:
        ref=entry['ref'];spec=SPECS[ref]
        assert entry['actualFootprint']['libraryUuid']==a.project_uuid,'Source is not the imported project library'
        rows,head,head_count=records(entry['documentSource'])
        assert head['uuid']==entry['footprintUuid']==entry['actualFootprint']['uuid']
        pads={h['id']:d for h,d in rows if h['type']=='PAD'and d}
        assert len(pads)==spec['pads']
        candidates=[(i,d)for i,d in pads.items()if str(d.get('num'))==spec['pin']];assert len(candidates)==1
        pid,ep=candidates[0];pad=ep['defaultPad'];assert pad['padType']=='RECT'
        assert abs(pad['width']*.0254-spec['ep_mm'])<.0001 and abs(pad['height']*.0254-spec['ep_mm'])<.0001
        cx=ep['centerX']+ep.get('padOffsetX',0);cy=ep['centerY']+ep.get('padOffsetY',0)
        epbounds=[cx-pad['width']/2,cy-pad['height']/2,cx+pad['width']/2,cy+pad['height']/2]
        paste={h['id']:d for h,d in rows if h['type']=='FILL'and d and d.get('layerId')==7}
        central={i:d for i,d in paste.items()if intersection_area(bounds(d['path']),epbounds)>1e-8}
        assert len(central)==4,'EP has a missing, extra or overlapping single-window aperture'
        apertures=[]
        for i,d in central.items():
            path=d['path'][0];assert path[0]=='R'and d['fillStyle']=='SOLID'
            _,x,y,w,h,rotation,r=path
            assert abs(w*.0254-spec['window_mm'])<1e-8 and abs(h*.0254-spec['window_mm'])<1e-8
            assert abs(r*.0254-.05)<1e-8
            dx=(x+w/2-cx)*.0254;dy=(y-h/2-cy)*.0254
            assert abs(abs(dx)-spec['offset_mm'])<1e-8 and abs(abs(dy)-spec['offset_mm'])<1e-8
            b=bounds(d['path']);assert b[0]>=epbounds[0]and b[1]>=epbounds[1]and b[2]<=epbounds[2]and b[3]<=epbounds[3]
            apertures.append({'id':i,'center_relative_ep_mm':[dx,dy],'size_mm':[w*.0254,h*.0254],
                              'corner_radius_mm':r*.0254,'bbox_local_mm':[v*.0254 for v in b]})
        overlaps=[intersection_area(bounds(d['path']),bounds(e['path']))*.0254**2 for d,e in itertools.combinations(central.values(),2)]
        assert max(overlaps)==0,'EP paste windows overlap'
        assert len(paste)==spec['pads']+3
        baseline=original[head['uuid']]
        original_paste={h['id']:d for h,d in baseline if h['type']=='FILL'and d and d.get('layerId')==7}
        original_pads={h['id']:d for h,d in baseline if h['type']=='PAD'and d}
        original_center={i:d for i,d in original_paste.items()if intersection_area(bounds(d['path']),epbounds)>1e-8}
        assert len(original_center)==1 and all(d['path'][0][0]!='R'for d in original_center.values())
        assert {i:d for i,d in paste.items()if i not in central}=={i:d for i,d in original_paste.items()if i not in original_center}
        assert pads==original_pads,'Copper or mask pad fields changed'
        assert all(ep[k]<-100 for k in ['topPasteExpansion','bottomPasteExpansion'])
        area=sum(d['size_mm'][0]*d['size_mm'][1]-(4-math.pi)*d['corner_radius_mm']**2 for d in apertures)
        results.append({'reference':ref,'footprint_uuid':head['uuid'],'source_method':entry['sourceMethod'],
                        'source_project_library_uuid':entry['actualFootprint']['libraryUuid'],
                        'duplicate_identical_dochead_count':head_count,'nonheader_duplicate_keys':False,
                        'ep_pin':spec['pin'],'ep_paste_window_count':4,'single_original_window_remaining':False,
                        'all_top_paste_fill_count':len(paste),'peripheral_paste_fill_count':len(paste)-4,
                        'peripheral_paste_and_all_pad_fields_unchanged':True,
                        'ep_auto_paste_expansion_mil':{'top':ep['topPasteExpansion'],'bottom':ep['bottomPasteExpansion']},
                        'apertures':apertures,'pairwise_overlap_areas_mm2':overlaps,
                        'web_mm':2*spec['offset_mm']-spec['window_mm'],
                        'coverage_percent':area/(pad['width']*pad['height']*.0254**2)*100,'pass':True})
    report={'schema':'calxus.native-qfn-paste-check.v1','snapshot_file':a.snapshot.name,
            'snapshot_bytes':len(raw),'snapshot_sha256':hashlib.sha256(raw).hexdigest(),
            'native_exported_at':snap['exportedAt'],'project_uuid':a.project_uuid,
            'baseline_archive_sha256':hashlib.sha256(a.baseline.read_bytes()).hexdigest(),
            'document_footprint_api_count':snap['documentFootprintCount'],
            'scope':'Actual source returned by the imported project-linked library fallback. This is native source verification, not rendered TopPaste Gerber verification.',
            'results':results,'pass':all(r['pass']for r in results),'native_canvas_mutations_performed':False,
            'top_paste_gerber_verified':False}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'snapshot_sha256':report['snapshot_sha256'],
                      'components':[{k:r[k]for k in ['reference','ep_paste_window_count','peripheral_paste_fill_count','coverage_percent','web_mm']}for r in results]},indent=2))

if __name__=='__main__':main()
