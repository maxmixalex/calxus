#!/usr/bin/env python3
"""Rebind completed mechanical evidence only after proving geometry inputs equal.

Copper LINE edits may change the candidate archive SHA without changing any
solid. This tool rejects changed component poses/bindings, footprints, layers,
PAD/VIA geometry, mounting regions, outline, native models or printed parts.
It never calls native DRC/CAM or upgrades source-derived evidence to native PASS.
"""
from pathlib import Path
import argparse, collections, hashlib, json, sys, zipfile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'tools'))
from assemble_source_pcba import candidate_bindings, load_drills, digest
from check_native_project_archive import parse_source


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def mechanical_signature(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        raw=z.read(next(n for n in z.namelist() if n.endswith('.epru')))
        docs=parse_source(raw.decode())
    selected=[];counts=collections.Counter()
    for doc in docs:
        kind=doc['head']['docType'];uuid=doc['head']['uuid']
        for h,d in doc['records']:
            take=kind in {'FOOTPRINT','DEVICE'}
            if kind=='PCB':
                take=h['type'] in {'COMPONENT','ATTR','PAD','VIA','LAYER_PHYS','LAYER','REGION'} or (h['type']=='POLY' and d.get('layerId')==11)
            if take:
                selected.append([kind,uuid,h['type'],h['id'],d]);counts[kind+':'+h['type']]+=1
    selected.sort(key=lambda row:tuple(str(v) for v in row[:4]))
    without_vias=[row for row in selected if not (row[0]=='PCB' and row[2]=='VIA')]
    return {'candidate_archive_sha256':digest(path),'canonical_geometry_records_sha256':hashlib.sha256(canonical(selected)).hexdigest(),
            'canonical_geometry_without_pcb_vias_sha256':hashlib.sha256(canonical(without_vias)).hexdigest(),
            'record_counts':dict(sorted(counts.items())),
            'scope':'All FOOTPRINT and DEVICE effective records; PCB COMPONENT, ATTR, PAD, VIA, LAYER_PHYS, LAYER, REGION and layer11 outline. Record tickets and source timestamps excluded. Copper LINE/POURED/POLY15/16 changes are outside this mechanical equivalence scope.'}


def drill_geometry(rows):
    keys=['key','source_kind','shape','center_mm','diameter_mm','slot_overall_length_mm','slot_tool_diameter_mm','slot_axis_degrees_ccw_from_x','slot_end_centers_mm']
    values=[{k:r[k] for k in keys if k in r} for r in rows]
    values.sort(key=lambda r:r['key'])
    return hashlib.sha256(canonical(values)).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',action='store_true')
    a=ap.parse_args();val=ROOT/'validation';candidate=ROOT.parent/'hardware/native/Calxus_RevA_candidate.epro2'
    paths={'PAD':ROOT.parent/'validation/native-candidate-tht-drill-expectations.json',
           'J1_NONPAD':ROOT.parent/'validation/native-candidate-nonpad-hole-expectations.json',
           'VIA':ROOT.parent/'validation/native-candidate-via-drill-expectations.json'}
    sig=mechanical_signature(candidate);rows,sources=load_drills(paths,sig['candidate_archive_sha256'])
    sig['drill_geometry_sha256']=drill_geometry(rows);sig['drilling_features']=len(rows)
    sig['native_r7_model_source_sha256']=digest(val/'Calxus_RevA_r7_PCBA.step.gz')
    freeze=json.loads((val/'printed-parts-frozen-r1_2.json').read_text())
    assert all(digest(ROOT/r['path'])==r['sha256'] for r in freeze['files'])
    sig['frozen_printed_files_sha256']=hashlib.sha256(canonical(freeze['files'])).hexdigest()
    snapshot=val/'source-derived-mechanical-inputs.json'
    if a.capture:
        if snapshot.exists():raise ValueError('Existing geometry snapshot must not be overwritten')
        snapshot.write_text(json.dumps(sig,indent=2)+'\n');print(json.dumps(sig,indent=2));return
    old=json.loads(snapshot.read_text())
    keys=['canonical_geometry_records_sha256','drill_geometry_sha256','native_r7_model_source_sha256','frozen_printed_files_sha256','record_counts','drilling_features']
    for key in keys:
        if old[key]!=sig[key]:raise ValueError('Mechanical inputs changed: '+key+'; geometry must be regenerated/revalidated')
    mpath=val/'calxus_source_assembly-manifest.json';m=json.loads(mpath.read_text())
    prior=m['candidate_archive_sha256'];new=sig['candidate_archive_sha256']
    audit=candidate_bindings(candidate,json.loads((val/'native-r7-model-source-bindings.json').read_text()))
    proof={'schema':'calxus.source-derived-candidate-equivalence.v1','from_candidate_sha256':prior,
           'geometry_computation_candidate_sha256':old['candidate_archive_sha256'],'to_candidate_sha256':new,
           'unchanged_mechanical_inputs':{key:sig[key] for key in keys},'pass':True,
           'geometry_recomputed':False,'native_drc_or_cam_acceptance':False,
           'scope':sig['scope'],'reason':'Candidate copper edits only; complete captured mechanical input signature is identical.'}
    proof_path=val/'source-derived-candidate-rebinding.json';proof_path.write_text(json.dumps(proof,indent=2)+'\n')
    report_paths=[val/m['fit_report'],val/m['board_validation'],val/m['selector_validation']]
    roundtrip=val/'source-derived-assembly-roundtrip.json'
    if roundtrip.exists():report_paths.append(roundtrip)
    for path in report_paths:
        d=json.loads(path.read_text());d.setdefault('original_geometry_validation_candidate_sha256',d['candidate_archive_sha256'])
        d['candidate_archive_sha256']=new;d['mechanical_input_equivalence_proof']=proof_path.name
        if path.name==m['board_validation']:d['drill_sources']=sources
        path.write_text(json.dumps(d,indent=2)+'\n')
    m.setdefault('original_geometry_generation_candidate_sha256',m['candidate_archive_sha256'])
    m['candidate_archive_sha256']=new;m['source_preservation_audit']=audit;m['drill_sources']=sources
    m['fit_report_sha256']=digest(val/m['fit_report']);m['mechanical_input_equivalence_proof']=proof_path.name
    mpath.write_text(json.dumps(m,indent=2)+'\n')
    if roundtrip.exists():
        d=json.loads(roundtrip.read_text());d['assembly_manifest_sha256']=digest(mpath);roundtrip.write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps({'geometry_inputs_equal':True,'from':prior,'to':new,'geometry_recomputed':False,'proof':str(proof_path)},indent=2))


if __name__=='__main__':main()
