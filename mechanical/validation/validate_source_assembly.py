#!/usr/bin/env python3
"""Independently re-read the source-derived STEP; never call it native acceptance."""
from pathlib import Path
import argparse, gzip, hashlib, json, tempfile
import cadquery as cq
from inspect_step import read_named_shapes
from validate_actual_assembly import grouped_named
from validate_pcba import bounds, cylinders


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    ap.add_argument('--manifest',default='calxus_source_assembly-manifest.json')
    ap.add_argument('--report',default='source-derived-assembly-roundtrip.json')
    a=ap.parse_args();root=a.root;out=root/'output';val=root/'validation'
    mp=val/a.manifest;m=json.loads(mp.read_text())
    fit_path=val/m['fit_report'];fit=json.loads(fit_path.read_text())
    board_proof=json.loads((val/m['board_validation']).read_text())
    assert fit['geometry_origin']=='SOURCE_DERIVED_NOT_FRESH_NATIVE_STEP'
    assert fit['candidate_archive_sha256']==m['candidate_archive_sha256']
    assert sha(root.parent/m['candidate_archive'])==m['candidate_archive_sha256']
    assert sha(fit_path)==m['fit_report_sha256']
    assert sha(root/m['native_r7_model_source'])==m['native_r7_model_source_sha256']
    fp=root/m['printed_design_freeze'];assert sha(fp)==m['printed_design_freeze_sha256']
    frozen=json.loads(fp.read_text());assert len(frozen['files'])==14
    for item in frozen['files']:assert sha(root/item['path'])==item['sha256']
    target=out/m['output_step_gz'];assert sha(target)==m['output_step_gz_sha256']
    expected={'SOURCE_DERIVED_BOARD':fit['components']['BOARD']}
    for ref,d in fit['components'].items():
        if d['population']=='FITTED':expected['ACTUAL_'+ref]=d
    assert len(expected)==94
    off=m['thumb_position_offset_mm'];cal=m['fork_calibration_relative_thumb_mm']
    contract=json.loads((root/'mechanical_contract.json').read_text())
    geom=json.loads((out/'validation_report.json').read_text())
    for entry in m['case_part_sources']:
        p=out/entry['path'];assert sha(p)==entry['sha256'];stem=p.stem;name=stem.removeprefix('calxus_')
        d=geom['solids'][stem];bb=d['bounds_mm'].copy()
        dx=off+(cal if name=='slider_fork' else 0) if name.startswith('slider_') else 0
        bb[0]+=dx;bb[3]+=dx
        expected['PRINTED_'+name]={'bbox_mm':bb,'volume_mm3':d['volume_mm3'],'solid_count':1}
    hardware=set(m['hardware_reference_names'])
    for rec in read_named_shapes(out/'calxus_assembly.step'):
        if rec['name'] not in hardware:continue
        s=rec['shape'];name=rec['name']
        if 'slider' in name:s=s.translate((off+cal-contract['selector']['assembly_display_position_offset']-contract['selector'].get('assembly_display_fork_calibration_x',0),0,0))
        expected[name]={'bbox_mm':bounds(s),'volume_mm3':s.Volume(),'solid_count':len(s.Solids())}
    assert len(expected)==114
    raw=target.read_bytes();plain=gzip.decompress(raw)
    assert plain.startswith(b'ISO-10303-21;') and b'END-ISO-10303-21;' in plain[-128:]
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'readback.step';p.write_bytes(plain)
        actual,unknown=grouped_named(read_named_shapes(p),set(expected))
    checks=[]
    for name,d in expected.items():
        if name not in actual:
            checks.append({'name':name,'present':False,'pass':False});continue
        s=actual[name];bb=bounds(s);volume=s.Volume();vd=abs(volume-d['volume_mm3']);bd=max(abs(x-y) for x,y in zip(bb,d['bbox_mm']));vt=max(1e-4,abs(d['volume_mm3'])*1e-6)
        counts_match=len(s.Solids())==d['solid_count']
        checks.append({'name':name,'present':True,'valid':s.isValid(),'solid_count':len(s.Solids()),'source_solid_count':d['solid_count'],
                       'bbox_mm':bb,'volume_mm3':volume,'bbox_delta_mm':bd,'volume_delta_mm3':vd,
                       'pass':s.isValid() and counts_match and bd<.00011 and vd<vt})
    board=actual['SOURCE_DERIVED_BOARD'];cy=cylinders(board);hole_checks=[]
    for source in m['drill_sources']:
        p=root.parent/source['path'];assert sha(p)==source['sha256'];d=json.loads(p.read_text())
        assert d['source_archive_sha256']==m['candidate_archive_sha256']
        rows=d.get('holes',d.get('vias'))
        for row in rows:
            if row['shape']=='SLOT':
                probes=[[x,y,row['slot_tool_diameter_mm']] for x,y in row['slot_end_centers_mm']]
            else:
                probes=[[*row['center_mm'],row.get('diameter_mm',row.get('hole_diameter_mm'))]]
            errors=[min(sum((x-y)**2 for x,y in zip(probe,c))**.5 for c in cy) for probe in probes]
            hole_checks.append({'source_kind':source['kind'],'id':row.get('primitiveId',str(row.get('ref'))+'.'+str(row.get('pin',row.get('source_id')))),
                                'surface_match_errors_mm':errors,'pass':max(errors)<2e-6})
    board_faces=[f for f in board.Faces() if f.geomType()=='PLANE' and abs(f.Center().z-bounds(board)[2])<1e-7 and abs(f.normalAt().z)>.99999]
    face=max(board_faces,key=lambda f:f.Area());inner_count=len(face.innerWires())
    motion=json.loads((val/m['selector_validation']).read_text())
    assert motion['candidate_archive_sha256']==m['candidate_archive_sha256']
    match=not unknown and len(actual)==len(expected) and all(x['pass'] for x in checks)
    drill_pass=len(hole_checks)==247 and inner_count==247 and all(x['pass'] for x in hole_checks)
    report={'schema':'calxus.source-derived-assembly-independent-roundtrip.v1',
        'geometry_origin':'SOURCE_DERIVED_NOT_FRESH_NATIVE_STEP','native_final_export_validated':False,'native_cam_or_drc_acceptance':False,
        'assembly':target.name,'assembly_sha256':sha(target),'assembly_manifest_sha256':sha(mp),
        'candidate_archive_sha256':m['candidate_archive_sha256'],'gzip_crc_verified':True,
        'fitted_components':93,'dnp_models_omitted':m['omitted_dnp_connector_models'],
        'expected_named_objects':len(expected),'actual_named_objects':len(actual),'unknown_solids':unknown,
        'per_object_checks':checks,'board_bottom_face_inner_wire_count':inner_count,
        'drill_feature_checks':hole_checks,'complete_drill_readback_pass':drill_pass,
        'source_pcba_static_fit_pass':fit['source_geometry_fit_pass'],'selector16_pose_pass':motion['pass'],
        'seven_printed_designs_fourteen_step_stl_files_unchanged':True,
        'geometry_roundtrip_pass':match,
        'source_design_assembly_verification_pass':match and drill_pass and fit['source_geometry_fit_pass'] and motion['pass'] and board_proof['pass'],
        'limits':['This validates the separately generated source-design assembly, not fresh native STEP, native DRC or manufacturing CAM.',
                  'Seven printed designs retain their existing frozen geometry. Physical first-article validation remains required.']}
    path=val/a.report;path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(path),'named_objects':len(actual),'holes':inner_count,'pass':report['source_design_assembly_verification_pass'],'failures':[x['name'] for x in checks if not x['pass']]},indent=2))
    if not report['source_design_assembly_verification_pass']:raise SystemExit(1)


if __name__=='__main__':main()
