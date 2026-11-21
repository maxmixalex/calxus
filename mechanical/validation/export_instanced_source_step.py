#!/usr/bin/env python3
"""Export shared native BREP definitions with occurrence locations, without meshing.

Preserves every real component leaf shape and its native world placement. J2's
approved Z+0.1 is an explicit extra occurrence translation. Repeated native
TShapes are shared by the XCAF assembly exporter; no solid is simplified/deleted.
The original larger exchange file remains untouched until independent approval.
"""
from pathlib import Path
import collections,gzip,hashlib,json,re,sys,tempfile
import cadquery as cq
from OCP.TopLoc import TopLoc_Location
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation'))
from inspect_step import read_named_shapes
from validate_pcba import bounds
from gzip_step import compress_step


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    val=ROOT/'validation';out=ROOT/'output';temp=ROOT/'tmp';temp.mkdir(exist_ok=True)
    manifest_path=val/'calxus_source_assembly-manifest.json';m=json.loads(manifest_path.read_text())
    native=ROOT/m['native_r7_model_source'];assert digest(native)==m['native_r7_model_source_sha256']
    fit=json.loads((val/m['fit_report']).read_text());expected={r for r,d in fit['components'].items() if d['population']=='FITTED'};assert len(expected)==93
    leaves_by_ref=collections.defaultdict(list)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'native.step';p.write_bytes(gzip.decompress(native.read_bytes()))
        for rec in read_named_shapes(p):
            if not rec['shape'].Solids():continue
            ref=next((re.split(r'~|->',n)[0] for n in rec['path'] if re.split(r'~|->',n)[0] in expected),None)
            if ref:leaves_by_ref[ref].append(rec)
    assert set(leaves_by_ref)==expected
    assembly=cq.Assembly(name='Calxus_SOURCE_DERIVED_93_component_instanced_assembly')
    off=m['thumb_position_offset_mm'];cal=m['fork_calibration_relative_thumb_mm']
    contract=json.loads((ROOT/'mechanical_contract.json').read_text())
    palette={'base':(.12,.17,.22),'lid':(.23,.31,.38),'comb_lower_tpu':(.10,.10,.10),'comb_upper_tpu':(.10,.10,.10),'slider_fork':(.10,.43,.45),'slider_thumb':(.10,.48,.50)}
    for source in m['case_part_sources']:
        p=out/source['path'];assert digest(p)==source['sha256'];name=p.stem.removeprefix('calxus_')
        s=cq.importers.importStep(str(p)).val();dx=off+(cal if name=='slider_fork' else 0) if name.startswith('slider_') else 0
        assembly.add(s,name='PRINTED_'+name,color=cq.Color(*palette[name]),loc=cq.Location(cq.Vector(dx,0,0)))
    board_path=out/'calxus_source_board.step.gz'
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'source_board.step';p.write_bytes(gzip.decompress(board_path.read_bytes()));board=cq.importers.importStep(str(p)).val()
    assembly.add(board,name='SOURCE_DERIVED_BOARD',color=cq.Color(.06,.36,.26))
    hardware=set(m['hardware_reference_names'])
    for rec in read_named_shapes(out/'calxus_assembly.step'):
        name=rec['name']
        if name not in hardware:continue
        s=rec['shape'];dx=off+cal-contract['selector']['assembly_display_position_offset']-contract['selector'].get('assembly_display_fork_calibration_x',0) if 'slider' in name else 0
        color=(.72,.52,.22) if 'insert' in name else (.15,.15,.15) if name.startswith('Heat') else (.58,.60,.62)
        assembly.add(s,name=name,loc=cq.Location(cq.Vector(dx,0,0)),color=cq.Color(*color))
    canonical_shapes={};occurrences=[];identity=TopLoc_Location()
    for ref in sorted(expected):
        sub=cq.Assembly(name='ACTUAL_'+ref)
        color=(.65,.67,.69) if ref.startswith(('J','SW')) else (.13,.14,.15) if ref.startswith(('U','D')) else (.38,.32,.23) if ref.startswith('C') else (.23,.25,.28)
        for i,rec in enumerate(leaves_by_ref[ref]):
            world=rec['shape'];location=world.wrapped.Location()
            base=cq.Shape.cast(world.wrapped.Located(identity))
            # Reuse the very same Python shape object as well as the native
            # TShape. The CAD exporter then emits one definition per color/part.
            if base not in canonical_shapes:canonical_shapes[base]=base
            elif base.wrapped.Orientation()!=canonical_shapes[base].wrapped.Orientation():
                raise ValueError('Shared native geometry has a differing topological orientation')
            base=canonical_shapes[base]
            if ref=='J2':location=cq.Location(cq.Vector(0,0,.1)).wrapped.Multiplied(location)
            sub.add(base,name='leaf_'+str(i),loc=cq.Location(location),color=cq.Color(*color))
            tr=location.Transformation()
            occurrences.append({'component':ref,'leaf_index':i,'source_path':rec['path'],
                'canonical_shape_hash':base.hashCode(),
                'occurrence_matrix_3x4':[[tr.Value(row,col) for col in range(1,5)] for row in range(1,4)],
                'approved_extra_translation_mm':[0,0,.1] if ref=='J2' else [0,0,0]})
        assembly.add(sub)
    # Keep exact2D trimming curves as well as3D geometry. Omitting pcurves was
    # tested and rejected: the imported J1 model volume changed by0.60307mm3.
    step=temp/'calxus_source_assembly_instanced.step';assembly.save(str(step),write_pcurves=True)
    target=out/'calxus_source_assembly_instanced.step.gz';compressed,compression=compress_step(step.read_bytes());target.write_bytes(compressed)
    m2=dict(m);m2['output_step_gz']=target.name;m2['output_step_gz_sha256']=digest(target)
    m2['exchange_representation']='XCAF shared native BREP leaf definitions plus original occurrence locations; exact3D geometry and2D trimming pcurves retained. No tessellation, decimation or shape deletion.'
    m2['instancing_evidence']='source-derived-step-instancing.json'
    m2['gzip_compression']=compression
    target_manifest=val/'calxus_source_assembly_instanced-manifest.json';target_manifest.write_text(json.dumps(m2,indent=2)+'\n')
    original=out/m['output_step_gz']
    report={'schema':'calxus.source-derived-step-instancing.v1','original_step_gz_sha256':digest(original),'original_step_gz_bytes':original.stat().st_size,
        'instanced_step_gz_sha256':digest(target),'instanced_step_gz_bytes':target.stat().st_size,'instanced_step_bytes':step.stat().st_size,
        'native_source_sha256':digest(native),'fitted_components':len(expected),'native_leaf_occurrences':len(occurrences),
        'unique_native_leaf_definitions':len(canonical_shapes),'occurrences':occurrences,
        'write_pcurves':True,
        'lossless_gzip_compression':compression,
        'rejected_alternative':'source-derived-pcurves-omission-rejected.json',
        'method':m2['exchange_representation'],'independent_roundtrip_required':True,
        'native_final_export_or_cam_acceptance':False}
    (val/'source-derived-step-instancing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='occurrences'},indent=2),flush=True)


if __name__=='__main__':main()
