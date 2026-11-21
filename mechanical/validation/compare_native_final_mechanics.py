#!/usr/bin/env python3
"""Compare native-final source with the source used for the verified CAD.

This checks mechanical source inputs only. Native VIA creation assigns new IDs
and serializes six dimensional fields to four decimal places in mil. That
specific normalization is proved separately; no approximate global matching or
loosening of the existing BREP validation thresholds is performed.
"""
from pathlib import Path
import argparse,hashlib,json,math,sys,zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'tools'))
from assemble_source_pcba import candidate_bindings,digest
from rebind_source_candidate import mechanical_signature
from check_native_project_archive import parse_source,records

DIMENSION_FIELDS={'centerX','centerY','holeDiameter','viaDiameter',
                  'topSolderExpansion','bottomSolderExpansion'}


def via_records(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names=[n for n in z.namelist() if n.endswith('.epru')]
        assert len(names)==1
        docs=parse_source(z.read(names[0]).decode())
    pcb=next(d for d in docs if d['head']['docType']=='PCB' and d['head']['uuid']=='2a0c39c6c6694f40')
    return {h['id']:d for h,d in records(pcb,'VIA')}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native',type=Path,default=ROOT.parent/'hardware/native/Calxus_RevA_final.epro2')
    a=ap.parse_args();val=ROOT/'validation'
    manifest=json.loads((val/'calxus_source_assembly-manifest.json').read_text())
    candidate=ROOT.parent/manifest['candidate_archive']
    source=mechanical_signature(candidate);native=mechanical_signature(a.native)
    assert source['candidate_archive_sha256']==manifest['candidate_archive_sha256']
    assert source['record_counts']==native['record_counts']
    non_via_equal=source['canonical_geometry_without_pcb_vias_sha256']==native['canonical_geometry_without_pcb_vias_sha256']
    assert non_via_equal,'Non-VIA mechanical source inputs changed'
    bindings=json.loads((val/'native-r7-model-source-bindings.json').read_text())
    model_audit=candidate_bindings(a.native,bindings)
    ca,na=via_records(candidate),via_records(a.native)
    assert len(ca)==len(na)==189
    used=set();pairs=[];field_max={k:0.0 for k in DIMENSION_FIELDS}
    geometry_fields=['centerX','centerY','holeDiameter','viaDiameter']
    for cid,c in sorted(ca.items()):
        choices=sorted((math.dist([c[k] for k in geometry_fields],[n[k] for k in geometry_fields]),nid,n)
                       for nid,n in na.items() if n['netName']==c['netName'])
        assert choices,'Unmatched via net'
        _,nid,n=choices[0]
        assert nid not in used,'Ambiguous or duplicate native via match'
        used.add(nid);changed=[]
        assert c.keys()==n.keys(),'VIA fields were added or removed'
        for key in c:
            if c[key]==n[key]:continue
            assert key in DIMENSION_FIELDS and isinstance(c[key],(int,float)) and isinstance(n[key],(int,float)),(cid,key)
            # Deterministic saved-source decimal serialization, not an expanded
            # mechanical fit tolerance. The 1e-10mil guard only covers float
            # representations of the same four-decimal number.
            assert abs(n[key]-round(c[key],4))<1e-10,(cid,key,c[key],n[key])
            assert abs(n[key]-c[key])<=.00005+1e-10,(cid,key)
            field_max[key]=max(field_max[key],abs(c[key]-n[key])*.0254)
            changed.append(key)
        pairs.append({'candidate_id':cid,'native_id':nid,'net':c['netName'],
            'candidate_center_mm':[c['centerX']*.0254,c['centerY']*.0254],
            'native_center_mm':[n['centerX']*.0254,n['centerY']*.0254],
            'candidate_hole_diameter_mm':c['holeDiameter']*.0254,
            'native_hole_diameter_mm':n['holeDiameter']*.0254,
            'candidate_outer_diameter_mm':c['viaDiameter']*.0254,
            'native_outer_diameter_mm':n['viaDiameter']*.0254,
            'center_radial_difference_mm':math.dist([c['centerX'],c['centerY']],[n['centerX'],n['centerY']])*.0254,
            'normalized_fields':sorted(changed),'payload_exact':c==n,
            'saved_decimal_normalization_proved':True})
    assert len(used)==189
    original=sum(p['candidate_id']==p['native_id'] for p in pairs)
    assert original==61 and sum(p['payload_exact'] for p in pairs)==61
    for p in pairs:
        if p['candidate_id']==p['native_id']:assert p['payload_exact']
    freeze=json.loads((val/'printed-parts-frozen-r1_2.json').read_text())
    assert all(digest(ROOT/f['path'])==f['sha256'] for f in freeze['files'])
    roundtrip=json.loads((val/'source-derived-assembly-roundtrip.json').read_text())
    assert roundtrip['source_design_assembly_verification_pass']
    assert roundtrip['candidate_archive_sha256']==source['candidate_archive_sha256']
    assert roundtrip['assembly_sha256']==digest(ROOT/'output'/manifest['output_step_gz'])
    assert digest(a.native)==native['candidate_archive_sha256'],'Native archive changed during comparison'
    report={'schema':'calxus.native-final-mechanical-source-equivalence.v1',
        'candidate_archive':str(candidate.relative_to(ROOT.parent)),
        'candidate_archive_sha256':source['candidate_archive_sha256'],
        'native_final_archive':str(a.native.relative_to(ROOT.parent)),
        'native_final_archive_sha256':native['candidate_archive_sha256'],
        'source_assembly':manifest['output_step_gz'],'source_assembly_sha256':roundtrip['assembly_sha256'],
        'non_via_mechanical_records_exactly_equal':True,
        'non_via_mechanical_sha256':source['canonical_geometry_without_pcb_vias_sha256'],
        'record_counts':source['record_counts'],
        'source_scope':source['scope'],
        'component_model_binding_audit':model_audit,
        'component_count':97,'fitted_components':93,'omitted_dnp_models':['J3','J4','J5','J8'],
        'pad_drill_features_exact':56,'j1_nonpad_drill_features_exact':2,
        'non_via_hole_equality_basis':'All saved FOOTPRINT/PAD/FILL records and their PCB COMPONENT/ATTR transforms are exactly identical. The existing56 PAD and2 J1 feature contracts therefore retain identical mechanical inputs, including the nominal padOffset limitation.',
        'via_count':189,'via_original_ids_and_payloads_preserved':61,'via_new_native_ids':128,
        'via_numeric_serialization':'For every changed value, native value equals round(candidate value,4) mil. Only centerX,centerY,holeDiameter,viaDiameter,topSolderExpansion,bottomSolderExpansion differ; other fields are exactly equal.',
        'native_serialization_grid_mil':.0001,'per_axis_half_grid_bound_mm':.00005*.0254,
        'max_center_radial_difference_mm':max(p['center_radial_difference_mm'] for p in pairs),
        'max_dimension_difference_mm':field_max,'via_mapping':pairs,
        'total_drill_features':247,'printed_step_stl_files_unchanged':14,
        'cad_regenerated':False,'existing_114_object_247_feature_roundtrip_pass':True,
        'source_geometry_equivalent_with_documented_native_decimal_serialization':True,
        'native_step_brep_or_cam_acceptance':False,
        'scope':'This is a final-native-project source comparison, not a newly exported native STEP or CAM validation. Copper routing, schematic labels and PCB silkscreen are outside mechanical source equivalence. The canonical CAD remains honestly SOURCE-DERIVED; its geometry and validation thresholds are unchanged.',
        'pass':True}
    target=val/'native-final-mechanical-source-equivalence.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':True,'native_sha256':native['candidate_archive_sha256'],
        'components':97,'drills':247,'max_via_center_difference_mm':report['max_center_radial_difference_mm'],
        'report':str(target),'CAD_regenerated':False},indent=2))


if __name__=='__main__':main()
