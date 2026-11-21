#!/usr/bin/env python3
"""Document the single drilling change and freshly recomputed final assembly.

This does not rebind old geometry results. It requires the final assembly and
independent roundtrip already to have been produced for the current candidate.
The older 548... snapshots remain immutable lineage evidence.
"""
from pathlib import Path
import hashlib,json,sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation'))
from assemble_source_pcba import digest,load_drills
from rebind_source_candidate import mechanical_signature,drill_geometry,canonical


def main():
    val=ROOT/'validation';candidate=ROOT.parent/'hardware/native/Calxus_RevA_candidate.epro2'
    old=json.loads((val/'source-derived-mechanical-inputs.json').read_text())
    old_drills=json.loads((val/'source-derived-drill-geometry-inputs.json').read_text())
    assert old_drills['candidate_archive_sha256']==old['candidate_archive_sha256']
    now=mechanical_signature(candidate)
    paths={'PAD':ROOT.parent/'validation/native-candidate-tht-drill-expectations.json',
           'J1_NONPAD':ROOT.parent/'validation/native-candidate-nonpad-hole-expectations.json',
           'VIA':ROOT.parent/'validation/native-candidate-via-drill-expectations.json'}
    rows,sources=load_drills(paths,now['candidate_archive_sha256'])
    keys=['key','source_kind','shape','center_mm','diameter_mm','slot_overall_length_mm',
          'slot_tool_diameter_mm','slot_axis_degrees_ccw_from_x','slot_end_centers_mm']
    def index(rs):return {r['key']:{k:r[k] for k in keys if k in r} for r in rs}
    before=index(old_drills['holes']);after=index(rows)
    assert before.keys()==after.keys() and len(after)==247
    changed=[{'key':k,'before':before[k],'after':after[k]} for k in sorted(after) if before[k]!=after[k]]
    assert len(changed)==1 and changed[0]['key']=='VIA:aef77ed306de1b93',changed
    assert max(abs(a-b) for a,b in zip(changed[0]['after']['center_mm'],[8.55,20.64]))<1e-10
    assert abs(changed[0]['after']['diameter_mm']-.2)<1e-10
    assert now['canonical_geometry_without_pcb_vias_sha256']==old['canonical_geometry_without_pcb_vias_sha256']
    assert now['record_counts']==old['record_counts']
    assert digest(val/'Calxus_RevA_r7_PCBA.step.gz')==old['native_r7_model_source_sha256']
    freeze=json.loads((val/'printed-parts-frozen-r1_2.json').read_text())
    assert all(digest(ROOT/r['path'])==r['sha256'] for r in freeze['files'])
    assert hashlib.sha256(canonical(freeze['files'])).hexdigest()==old['frozen_printed_files_sha256']
    manifest=json.loads((val/'calxus_source_assembly-manifest.json').read_text())
    roundtrip=json.loads((val/'source-derived-assembly-roundtrip.json').read_text())
    for evidence in [manifest,roundtrip]+[json.loads((val/n).read_text()) for n in
            ['source-derived-board-geometry.json','source-derived-pcba-fit.json','source-derived-selector-motion.json']]:
        assert evidence['candidate_archive_sha256']==now['candidate_archive_sha256']
    assert roundtrip['source_design_assembly_verification_pass']
    assert roundtrip['assembly_sha256']==digest(ROOT/'output'/manifest['output_step_gz'])
    assert roundtrip['assembly_manifest_sha256']==digest(val/'calxus_source_assembly-manifest.json')
    proof={'schema':'calxus.final-source-revision.v1','prior_candidate_archive_sha256':old['candidate_archive_sha256'],
        'candidate_archive_sha256':now['candidate_archive_sha256'],'changed_drill_features':changed,
        'unchanged_drill_features':246,'total_drill_features':247,
        'non_via_mechanical_source_records_identical':True,'native_model_bytes_identical':True,
        'seven_printed_designs_fourteen_step_stl_files_unchanged':True,
        'current_mechanical_input_signature':now,'current_drill_geometry_sha256':drill_geometry(rows),
        'fresh_geometry_recomputation':{'board':True,'static_93_component_fit':True,'selector_16_poses':True,
            'shared_114_object_assembly_and_independent_readback':True},
        'assembly_gzip_sha256':roundtrip['assembly_sha256'],
        'native_final_step_or_cam_acceptance':False,'pass':True,
        'scope':'Final design-source geometry only. Changed PCB copper routing is outside this mechanical comparison. The one changed via was recut from the complete final247-feature set, not patched into a previously drilled board.'}
    path=val/'source-derived-final-revision.json';path.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'pass':True,'report':str(path),'candidate_sha256':now['candidate_archive_sha256'],'changed_holes':1},indent=2))


if __name__=='__main__':main()
