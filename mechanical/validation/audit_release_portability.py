#!/usr/bin/env python3
"""Check CAD release inputs from an isolated copy, without regenerating geometry."""
from pathlib import Path
import argparse,ast,gzip,hashlib,importlib.metadata,json,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parent.parent


def main():
    package=json.loads((ROOT/'output/artifact_manifest.json').read_text())
    mechanical=['mechanical/'+x['path'] for x in package['files']]+['mechanical/output/artifact_manifest.json']
    cross=['hardware/native/Calxus_RevA_candidate.epro2','hardware/native/Calxus_RevA_final.epro2',
           'hardware/electrical/calxus_design_input.json','tools/check_native_project_archive.py',
           'validation/native-candidate-tht-drill-expectations.json',
           'validation/native-candidate-nonpad-hole-expectations.json',
           'validation/native-candidate-via-drill-expectations.json',
           'validation/native-final-tht-drill-expectations.json',
           'validation/native-final-nonpad-hole-expectations.json',
           'validation/native-final-via-drill-expectations.json',
           'hardware/manufacturing/Calxus_RevA_Gerber.zip',
           'validation/native-final-gerber/gerber-validation.json',
           'validation/native-final-gerber/outline-corners.json']
    required=sorted(set(mechanical+cross));missing=[p for p in required if not (ROOT.parent/p).is_file()]
    if missing:raise ValueError('Missing release inputs: '+str(missing))
    ignored=subprocess.run(['git','check-ignore','--no-index','--stdin'],cwd=ROOT.parent,input='\n'.join(required)+'\n',text=True,capture_output=True)
    if ignored.returncode not in (0,1):raise RuntimeError(ignored.stderr)
    ignored_paths=ignored.stdout.splitlines()
    absolute_dependencies=[]
    for rel in mechanical:
        p=ROOT.parent/rel
        if p.suffix!='.py':continue
        tree=ast.parse(p.read_text())
        for node in ast.walk(tree):
            markers=['/workspace/','/home/agent/','D:/Works/','71a70b0d2513','calxus_work/']
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value not in markers and any(marker in node.value for marker in markers):
                absolute_dependencies.append({'path':rel,'line':node.lineno,'value':node.value})
    with tempfile.TemporaryDirectory(prefix='calxus-release-inputs-') as td:
        clean=Path(td)
        for rel in required:
            dest=clean/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT.parent/rel,dest)
        program="""
from pathlib import Path
import contextlib,gzip,io,json,sys,hashlib
root=Path.cwd()/'mechanical';sys.path[:0]=[str(root),str(root/'validation')]
import assemble_source_pcba as cad
assert cad.ROOT==root
b=json.loads((root/'validation/native-r7-model-source-bindings.json').read_text())
audit=cad.candidate_bindings(root.parent/'hardware/native/Calxus_RevA_candidate.epro2',b)
paths={'PAD':root.parent/'validation/native-candidate-tht-drill-expectations.json','J1_NONPAD':root.parent/'validation/native-candidate-nonpad-hole-expectations.json','VIA':root.parent/'validation/native-candidate-via-drill-expectations.json'}
rows,_=cad.load_drills(paths,audit['archive_sha256']);assert len(rows)==247
freeze=json.loads((root/'validation/printed-parts-frozen-r1_2.json').read_text())
assert all(cad.digest(root/r['path'])==r['sha256'] for r in freeze['files'])
raw=(root/'validation/Calxus_RevA_r7_PCBA.step.gz').read_bytes();assert hashlib.sha256(raw).hexdigest()==b['native_step_sha256']
text=gzip.decompress(raw);assert text.startswith(b'ISO-10303-21;')
assert not (root/'tmp').exists()
import compare_native_final_mechanics,finalize_mechanical_acceptance
with contextlib.redirect_stdout(io.StringIO()):
 compare_native_final_mechanics.main()
 finalize_mechanical_acceptance.main()
print(json.dumps({'relative_root_resolved':True,'candidate_components':len(audit['component_checks']),'drill_features':len(rows),'frozen_files':len(freeze['files']),'native_model_crc_verified':True,'native_final_source_equivalence_rechecked':True,'mechanical_acceptance_evidence_rechecked':True,'runtime_cache_used':False}))
"""
        r=subprocess.run([sys.executable,'-c',program],cwd=clean,text=True,capture_output=True)
        if r.returncode:raise RuntimeError(r.stdout+'\n'+r.stderr)
        clean_check=json.loads(r.stdout)
    attrs=subprocess.check_output(['git','check-attr','text','--',*required],cwd=ROOT.parent,text=True).splitlines()
    byte_preserved=all(line.endswith(': unset') for line in attrs)
    report={'schema':'calxus.cad-release-portability.v1','scope':'Release-input and clean-copy loading audit only; no repeated mechanical simulation or regeneration.',
        'required_file_count':len(required),'mechanical_release_file_count':len(mechanical),'cross_directory_inputs':cross,
        'missing_inputs':missing,'ignored_inputs':ignored_paths,'absolute_workspace_dependencies':absolute_dependencies,
        'checkout_eol_normalization_disabled_for_all_required_inputs':byte_preserved,'isolated_copy_check':clean_check,
        'runtime_dependencies':{'python':sys.version.split()[0],'cadquery':importlib.metadata.version('cadquery'),
            'blender_on_path':bool(shutil.which('blender')),'freecadcmd_on_path':bool(shutil.which('freecadcmd')),
            'dejavu_sans_font_present':Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').exists(),
            'platform_note':'Linux reference environment documented in README; system executables/fonts are explicit dependencies, not project workspace paths.'},
        'commit_scope_note':'Root has not created the final Git tree/commit yet. This proves release-manifest coverage and unignored exact-byte inputs, not that pending blobs are already present on remote main.',
        'rebuild_entry_points':['generate_mechanical.py: rebuild mechanical geometry in a separate working copy.','assemble_source_pcba.py: regenerate source-derived assembly using the clean checkout frozen STEP/STL inputs.'],
        'pass':not missing and not ignored_paths and not absolute_dependencies and byte_preserved and clean_check['candidate_components']==97 and clean_check['drill_features']==247}
    p=ROOT/'validation/release-portability.json';p.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(p),'pass':report['pass'],'inputs':len(required),'clean_copy':clean_check},indent=2))
    if not report['pass']:raise SystemExit(1)


if __name__=='__main__':main()
