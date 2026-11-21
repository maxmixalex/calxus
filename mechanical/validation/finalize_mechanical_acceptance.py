#!/usr/bin/env python3
"""Link completed CAD, final native source/board and actual CAM mechanical evidence.

This does not regenerate geometry, reinterpret an old STEP as a new export, or
certify electrical operation or physical first-article performance.
"""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT.parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    val=ROOT/'validation'
    def read(name):return json.loads((val/name).read_text())
    assembly=read('calxus_source_assembly-manifest.json')
    roundtrip=read('source-derived-assembly-roundtrip.json')
    equivalent=read('native-final-mechanical-source-equivalence.json')
    basic=read('native-final-board-brep.json')
    board=read('native-final-board-representation.json')
    cam_path=REPO/'validation/native-final-gerber/gerber-validation.json'
    corner_path=REPO/'validation/native-final-gerber/outline-corners.json'
    cam=json.loads(cam_path.read_text());corners=json.loads(corner_path.read_text())
    gerber=REPO/'hardware/manufacturing/Calxus_RevA_Gerber.zip'
    candidate=REPO/assembly['candidate_archive'];native=REPO/equivalent['native_final_archive']
    candidate_sha=sha(candidate);native_sha=sha(native)
    assert candidate_sha==assembly['candidate_archive_sha256']==roundtrip['candidate_archive_sha256']==equivalent['candidate_archive_sha256']
    assert native_sha==equivalent['native_final_archive_sha256']==board['native_archive_sha256']
    assert equivalent['pass'] and equivalent['source_geometry_equivalent_with_documented_native_decimal_serialization']
    assert roundtrip['source_design_assembly_verification_pass'] and roundtrip['actual_named_objects']==114
    assert roundtrip['board_bottom_face_inner_wire_count']==247 and roundtrip['selector16_pose_pass']
    exchange=ROOT/'output'/assembly['output_step_gz']
    assert sha(exchange)==roundtrip['assembly_sha256']==assembly['output_step_gz_sha256']==equivalent['source_assembly_sha256']
    assert basic['board_geometry_pass'] and board['verification_completed']
    assert basic['source_sha256']==board['native_step_sha256']==sha(ROOT/board['native_step'])
    assert board['native_and_canonical_outer_wires_exactly_equal'] and board['outer_blank_symmetric_difference_mm3']==0
    assert board['native_nonvia_drill_features_represented']==58 and board['native_via_nominal_drill_features_omitted']==189
    assert cam['pass'] and sha(gerber)==cam['archive_sha256']==corners['gerber_archive_sha256']
    assert cam['through_holes']['pass'] and cam['through_holes']['passed_holes']==56
    assert cam['through_holes']['expectations_source_archive_sha256']==native_sha
    assert cam['all_via_drills']['pass'] and cam['all_via_drills']['passed_vias']==189
    assert cam['all_via_drills']['source_archive_sha256']==native_sha
    assert cam['nonpad_locating_holes']['pass'] and cam['nonpad_locating_holes']['passed_holes']==2
    assert cam['nonpad_locating_holes']['source_archive_sha256']==native_sha
    assert corners['pass'] and len(corners['segments'])==8
    arcs=[s for s in corners['segments'] if s['kind']=='arc']
    assert len(arcs)==4 and all(s['radius_mm']==1 and s['sweep_degrees']==90 for s in arcs)
    with zipfile.ZipFile(gerber) as z:
        assert z.testzip() is None
        raw=z.read(corners['outline_member'])
    assert hashlib.sha256(raw).hexdigest()==corners['outline_member_sha256']
    assert all(s['command'].encode() in raw for s in corners['segments'])
    freeze=read('printed-parts-frozen-r1_2.json')
    assert len(freeze['files'])==14 and all(sha(ROOT/f['path'])==f['sha256'] for f in freeze['files'])
    refs=[candidate,native,exchange,ROOT/'output/calxus_source_board.step.gz',ROOT/board['native_step'],gerber,
          cam_path,corner_path,val/'calxus_source_assembly-manifest.json',val/'source-derived-assembly-roundtrip.json',
          val/'source-derived-pcba-fit.json',val/'source-derived-selector-motion.json',
          val/'native-final-mechanical-source-equivalence.json',val/'native-final-board-brep.json',
          val/'native-final-board-representation.json',val/'printed-parts-frozen-r1_2.json']
    report={'schema':'calxus.mechanical-release-acceptance.v1','mechanical_release_accepted':True,
        'scope':'Digital mechanical design release. Does not establish electrical operation, routed-net DRC, USB compliance or physical first-article validation.',
        'canonical_assembly':'mechanical/output/'+exchange.name,'canonical_assembly_sha256':sha(exchange),
        'canonical_geometry_origin':'SOURCE_DERIVED_DESIGN_WITH_FINAL_NATIVE_SOURCE_AND_CAM_COMPARISON',
        'candidate_archive_sha256':candidate_sha,'native_final_archive_sha256':native_sha,
        'actual_final_gerber_archive_sha256':sha(gerber),
        'fitted_components':93,'source_native_components':97,'omitted_DNP_connector_models':['J3','J4','J5','J8'],
        'assembly_named_objects':114,'complete_nominal_drill_features':247,'selector_poses_verified':16,
        'printed_designs':7,'frozen_printed_STEP_STL_files':14,
        'actual_native_board_STEP_verified':True,'actual_native_CAM_all247_drills_verified':True,
        'native_final_component_pose_and_model_binding_comparison_pass':True,
        'native_and_canonical_outer_wire_boolean_difference_mm3':0,
        'actual_CAM_four_R1_quarter_arcs_verified':True,
        'CAD_geometry_regenerated_for_final_native_comparison':False,
        'fresh_native_full_pcba_exported':False,'fresh_native_full_pcba_exported_scope':'Scope is the published, independently verified mechanical package. An optional fresh native full-PCBA STEP exists in the local Windows exports directory, but it was not transferred, adopted or independently compared. This flag does not claim that no optional local export exists.','physical_first_article_validated':False,
        'native_STEP_limit':'Actual final board-only STEP contains58 non-VIA holes and omits189 VIA drill voids. It is preserved as evidence; the complete source-derived assembly remains canonical.',
        'source_roundtrip_checks_unchanged':True,
        'preview_limit':'Gerbonara pretty board-fill may show a lower-left closing chord. Actual GKO has four R1 quarter arcs; no fabrication or CAD geometry was changed for the preview.',
        'evidence':[{'path':str(p.relative_to(REPO)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in refs]}
    path=val/'mechanical-release-acceptance.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'mechanical_release_accepted':True,'report':str(path),'native_source_sha256':native_sha,
        'canonical_assembly_sha256':sha(exchange),'fresh_native_full_pcba_exported':False},indent=2))


if __name__=='__main__':main()
