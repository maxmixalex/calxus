#!/usr/bin/env python3
"""Independently re-import the actual93-component combined STEP and verify it.
The comparison uses the separately measured native-PCBA fit report and frozen
mechanical BREP checks. No diagram/envelope substitutes for an actual model.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,tempfile
import cadquery as cq
from inspect_step import read_named_shapes
from validate_pcba import bounds


def grouped_named(leaves,known):
    groups={};unknown=[]
    for rec in leaves:
        if not rec['shape'].Solids():continue
        hits=[p for p in rec['path'] if p in known]
        if not hits:unknown.append({'name':rec['name'],'path':rec['path']});continue
        key=hits[-1];groups.setdefault(key,[]).append(rec['shape'])
    return {key:cq.Compound.makeCompound(shapes) for key,shapes in groups.items()},unknown


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('assembly_step',type=Path);ap.add_argument('assembly_manifest',type=Path);ap.add_argument('native_fit',type=Path);ap.add_argument('report',type=Path);a=ap.parse_args()
    root=Path(__file__).resolve().parent.parent;contract=json.loads((root/'mechanical_contract.json').read_text());m=json.loads(a.assembly_manifest.read_text());fit=json.loads(a.native_fit.read_text());geom=json.loads((root/'output/validation_report.json').read_text())
    raw=a.assembly_step.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==m['output_step_gz_sha256'];assert hashlib.sha256(a.native_fit.read_bytes()).hexdigest()==m['fit_report_sha256'];assert fit['source_sha256']==m['native_source_sha256']
    fitted={ref:d for ref,d in fit['components'].items() if d.get('population')=='FITTED'};assert len(fitted)==93
    expected={}
    for ref,d in fitted.items():expected['ACTUAL_'+ref]={'volume_mm3':d['volume_mm3'],'bbox_mm':d['bbox_mm']}
    d=fit['components']['BOARD'];expected['NATIVE_PCBA_BOARD']={'volume_mm3':d['volume_mm3'],'bbox_mm':d['bbox_mm']}
    off=m['thumb_position_offset_mm'];cal=m['fork_calibration_relative_thumb_mm']
    for entry in m['case_part_sources']:
        p=root/'output'/entry['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
        stem=p.stem;name=stem.removeprefix('calxus_');d=geom['solids'][stem];bb=d['bounds_mm'].copy();shift=off+(cal if name=='slider_fork' else 0) if name.startswith('slider_') else 0
        bb[0]+=shift;bb[3]+=shift
        expected['PRINTED_'+name]={'volume_mm3':d['volume_mm3'],'bbox_mm':bb}
    hardware_names=set(m['hardware_reference_names'])
    for rec in read_named_shapes(root/'output/calxus_assembly.step'):
        name=rec['name']
        if name not in hardware_names:continue
        s=rec['shape'];shift=off+cal-contract['selector']['assembly_display_position_offset']-contract['selector'].get('assembly_display_fork_calibration_x',0) if 'slider' in name else 0
        if shift:s=s.translate((shift,0,0))
        expected[name]={'volume_mm3':s.Volume(),'bbox_mm':bounds(s)}
    assert hardware_names<=set(expected)
    plain=gzip.decompress(raw) if a.assembly_step.suffix=='.gz' else raw
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'assembly.step';p.write_bytes(plain);actual,unknown=grouped_named(read_named_shapes(p),set(expected))
    checks=[]
    for name,source in expected.items():
        if name not in actual:checks.append({'name':name,'present':False,'pass':False});continue
        s=actual[name];volume=s.Volume();bb=bounds(s);vdelta=abs(volume-source['volume_mm3']);bdelta=max(abs(x-y) for x,y in zip(bb,source['bbox_mm']));valid=s.isValid();vtol=max(.0001,abs(source['volume_mm3'])*1e-6)
        checks.append({'name':name,'present':True,'valid':valid,'solid_count':len(s.Solids()),'volume_mm3':volume,'volume_difference_mm3':vdelta,'volume_tolerance_mm3':vtol,'bbox_mm':bb,'max_bbox_difference_mm':bdelta,'pass':valid and vdelta<=vtol and bdelta<=.00011})
    match=not unknown and len(actual)==len(expected) and all(x['pass'] for x in checks)
    report={'schema':'calxus.actual-assembly-roundtrip.v1','assembly':a.assembly_step.name,'assembly_sha256':sha,'source_native_sha256':m['native_source_sha256'],'gzip_crc_verified':a.assembly_step.suffix=='.gz','fitted_component_count':93,'omitted_dnp':m['omitted_dnp_connector_models'],'expected_named_objects':len(expected),'actual_named_objects':len(actual),'unknown_solids':unknown,'per_object_checks':checks,'geometry_roundtrip_pass':match,'native_mount_validation_pass':fit.get('static_fit_pass',False),'diagnostic_not_release':m['diagnostic_not_release'],'release_geometry_pass':match and fit.get('static_fit_pass',False) and not m['diagnostic_not_release'],'limits':['Does not establish physical printed fit, retention, temperature or electrical behavior.','STEP includes rigid printed parts, populated board models and reference fasteners/collars; free flexible cable routes are not modeled.']}
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'report':str(a.report),'objects':len(actual),'geometry_roundtrip_pass':match,'release_geometry_pass':report['release_geometry_pass'],'failures':[x['name'] for x in checks if not x['pass']]},indent=2))
    if not match:raise SystemExit(1)
if __name__=='__main__':main()
