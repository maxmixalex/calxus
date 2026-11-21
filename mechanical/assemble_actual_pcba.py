#!/usr/bin/env python3
"""Combine an explicitly validated native PCBA with the frozen enclosure.

No component/board geometry is silently relocated. The two printed slider parts
and their hardware use the reported native switch detent/calibration. Four DNP
connector bodies are omitted; physical source geometry comes from the supplied
native STEP, never from installation envelopes.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,math,subprocess,sys,tempfile
import cadquery as cq
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'validation'))
from inspect_step import read_named_shapes
from validate_pcba import group_shapes


def render(items,path,title,subtitle):
    meshes=[];points=[]
    for shape,color in items:
        vs,ts=shape.tessellate(.08,.12);vv=np.array([v.toTuple() for v in vs]);tt=np.array(ts)
        if not len(vv):continue
        points.append(vv);meshes.append({'vertices':vv.tolist(),'triangles':tt.tolist(),'color':list(color)})
    pts=np.concatenate(points);lo,hi=pts.min(0),pts.max(0);center=(lo+hi)/2
    az,el=math.radians(-60),math.radians(25);direction=np.array([math.cos(el)*math.cos(az),math.cos(el)*math.sin(az),math.sin(el)])
    right=np.cross([0,0,1],direction);right/=np.linalg.norm(right);up=np.cross(direction,right);aspect=4/3
    scale=max(np.ptp(pts@right),np.ptp(pts@up)*aspect)*1.22
    scene={'parts':meshes,'width':1920,'height':1440,'center':center.tolist(),'camera_direction':direction.tolist(),'distance':float(np.linalg.norm(hi-lo)*2),'ortho_scale':float(scale)}
    temp=ROOT/'tmp';temp.mkdir(exist_ok=True);p=temp/'actual_pcba_scene.json';p.write_text(json.dumps(scene))
    with (temp/'actual_pcba_render.log').open('w') as log:
        subprocess.run(['blender','--background','--threads','4','--python',str(ROOT/'blender_render.py'),'--',str(p),str(path)],stdout=log,stderr=subprocess.STDOUT,check=True)
    im=Image.open(path).convert('RGB');draw=ImageDraw.Draw(im)
    draw.text((48,30),title,font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',33),fill='#17333f')
    draw.text((48,82),subtitle,font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',26),fill='#334b55');im.save(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('native_step',type=Path);ap.add_argument('--fit-report',type=Path,required=True)
    ap.add_argument('--allow-native-diagnostic',action='store_true',help='Explicitly render an unreleased diagnostic, labeled in image/manifest. Never changes source geometry.')
    ap.add_argument('--skip-render',action='store_true');args=ap.parse_args()
    c=json.loads((ROOT/'mechanical_contract.json').read_text());fit=json.loads(args.fit_report.read_text());raw=args.native_step.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if fit['source_sha256']!=sha:raise ValueError('Fit report belongs to a different native STEP')
    if not fit.get('static_enclosure_fit_pass'):raise ValueError('Complete fitted population has not passed enclosure fit')
    diagnostic=not fit.get('static_fit_pass')
    if diagnostic and not args.allow_native_diagnostic:raise ValueError('Native model/board mount issue remains; use a validated fresh export, or explicitly label a diagnostic')
    plain=gzip.decompress(raw) if args.native_step.suffix=='.gz' else raw
    design=json.loads((ROOT.parent/'hardware/electrical/calxus_design_input.json').read_text());expected={p['ref']:p for p in design['parts']}
    dnp=set(c['assembly_population']['pad_only_dnp_model_refs']);physical={ref for ref,p in expected.items() if not p.get('pcb_only')}-dnp
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'native.step';p.write_bytes(plain);groups,unmapped=group_shapes(read_named_shapes(p),set(expected))
    if unmapped or physical-set(groups) or len(physical)!=93:raise ValueError('Unexpected native model population')
    off=fit['slider_offset_mm'];cal=fit['fork_calibration_x_mm'];out=ROOT/'output';temp=ROOT/'tmp';temp.mkdir(exist_ok=True)
    assembly=cq.Assembly(name='Calxus_actual_93_component_assembly');items=[];part_sources=[]
    palette={'base':(.12,.17,.22),'lid':(.23,.31,.38),'comb_lower_tpu':(.10,.10,.10),'comb_upper_tpu':(.10,.10,.10),'slider_fork':(.10,.43,.45),'slider_thumb':(.10,.48,.50)}
    for name,color in palette.items():
        source=out/f'calxus_{name}.step';shape=cq.importers.importStep(str(source)).val()
        shift=off+(cal if name=='slider_fork' else 0) if name.startswith('slider_') else 0
        if shift:shape=shape.translate((shift,0,0))
        assembly.add(shape,name='PRINTED_'+name,color=cq.Color(*color))
        delta={'lid':(0,0,28),'slider_fork':(0,0,12),'slider_thumb':(0,0,39),'comb_lower_tpu':(10,0,0),'comb_upper_tpu':(10,0,13)}.get(name,(0,0,0))
        items.append((shape.translate(delta),color));part_sources.append({'path':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    board=groups['BOARD'];assembly.add(board,name='NATIVE_PCBA_BOARD',color=cq.Color(.06,.36,.26));items.append((board.translate((0,0,5)),(.06,.36,.26)))
    for ref in sorted(physical):
        color=(.65,.67,.69) if ref.startswith(('J','SW')) else (.13,.14,.15) if ref.startswith(('U','D')) else (.38,.32,.23) if ref.startswith('C') else (.23,.25,.28)
        assembly.add(groups[ref],name='ACTUAL_'+ref,color=cq.Color(*color));items.append((groups[ref].translate((0,0,5)),color))
    hardware=[]
    for rec in read_named_shapes(out/'calxus_assembly.step'):
        name=rec['name']
        if not name.startswith(('M2','Heat_shrink_collar_')):continue
        shape=rec['shape']
        if 'slider' in name:shape=shape.translate((off+cal-c['selector']['assembly_display_position_offset']-c['selector'].get('assembly_display_fork_calibration_x',0),0,0))
        color=(.72,.52,.22) if 'insert' in name else (.15,.15,.15) if name.startswith('Heat') else (.58,.60,.62)
        assembly.add(shape,name=name,color=cq.Color(*color));hardware.append(name)
        if 'screw' in name:items.append((shape.translate((0,0,35 if 'slider' not in name else 43)),color))
    stem='calxus_actual_assembly' if not diagnostic else 'calxus_diagnostic_actual_assembly'
    step=temp/(stem+'.step');assembly.save(str(step));blob=gzip.compress(step.read_bytes(),compresslevel=9,mtime=0);target=out/(stem+'.step.gz');target.write_bytes(blob)
    image_path=out/(stem+'_exploded.png')
    if not args.skip_render:
        render(items,image_path,'CALXUS R1.2 | '+('DIAGNOSTIC native PCBA' if diagnostic else 'Actual 93-component assembly'),'Native model geometry + printed enclosure; J3/J4/J5/J8 connector bodies are not fitted')
    manifest={'schema':'calxus.actual-assembly.v1','revision':c['revision'],'diagnostic_not_release':diagnostic,'native_source':args.native_step.name,'native_source_sha256':sha,'fit_report':args.fit_report.name,'fit_report_sha256':hashlib.sha256(args.fit_report.read_bytes()).hexdigest(),'actual_fitted_components':len(physical),'omitted_dnp_connector_models':sorted(dnp),'native_board_and_component_transform':'identity; no source drill/solid repair','thumb_position_offset_mm':off,'fork_calibration_relative_thumb_mm':cal,'case_part_sources':part_sources,'hardware_reference_names':hardware,'output_step_gz':target.name,'output_step_gz_sha256':hashlib.sha256(blob).hexdigest(),'render':None if args.skip_render else image_path.name,'render_note':'Exploded display translates PCBA+5Z/lid+28Z; exchange STEP remains assembled. Material colors are illustrative; geometry is imported native BREP.'}
    (ROOT/'validation'/(stem+'-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'step':str(target),'bytes':len(blob),'actual_components':len(physical),'diagnostic':diagnostic,'preview':str(image_path)},indent=2))
if __name__=='__main__':main()
