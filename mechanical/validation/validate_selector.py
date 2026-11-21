#!/usr/bin/env python3
"""Exact BREP selector checks for four detents and an adjustable, clamped coupling.

The external actuator alone is translated between positions. This verifies the
printed linkage envelope, not the switch's internal contacts/detent mechanism.
An explicit --sw1-z-correction is permitted only for diagnosed old-model evidence;
final r7 evidence must use the native model at correction 0.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,tempfile
import cadquery as cq
from inspect_step import read_named_shapes
from validate_pcba import bounds,group_shapes


def box(a,b):
    return cq.Workplane('XY').box(*(b[i]-a[i] for i in range(3)),centered=False).translate(a).val()

def cylinder(x,y,z0,z1,d):
    return cq.Workplane('XY').center(x,y).circle(d/2).extrude(z1-z0).translate((0,0,z0)).val()

def common_volume(a,b):
    result=a.intersect(b)
    return max(0,result.Volume()) if result.Solids() else 0.

def section_slab(shape,z,h=.001):
    return shape.intersect(box([-100,-100,z],[200,200,z+h]))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('step',type=Path);ap.add_argument('report',type=Path)
    ap.add_argument('--sw1-only',action='store_true')
    ap.add_argument('--sw1-z-correction',type=float,default=0)
    args=ap.parse_args();root=Path(__file__).resolve().parent.parent
    c=json.loads((root/'mechanical_contract.json').read_text());s=c['selector'];sl=c['fasteners']['slider_screw'];sx=s['body_center'][0];sy=s['slider_center_y']
    raw=args.step.read_bytes();plain=gzip.decompress(raw) if args.step.suffix=='.gz' else raw
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'source.step';path.write_bytes(plain)
        if args.sw1_only:
            sw=cq.importers.importStep(str(path)).val();others={}
        else:
            design=json.loads((root.parent/'hardware/electrical/calxus_design_input.json').read_text())
            expected={p['ref'] for p in design['parts']}
            groups,unmapped=group_shapes(read_named_shapes(path),expected)
            if unmapped:raise ValueError('Unmapped actual-PCBA solids; inspect first')
            sw=groups.pop('SW1');others={ref:part for ref,part in groups.items() if ref not in c['assembly_population']['pad_only_dnp_model_refs']}
    if args.sw1_z_correction:sw=sw.translate((0,0,args.sw1_z_correction))
    solids=sw.Solids();lever=[]
    for i,part in enumerate(solids):
        b=bounds(part)
        if all(abs(d-target)<.002 for d,target in zip([b[3]-b[0],b[4]-b[1],b[5]-b[2]],[1.5,2.4,1.5])) and b[1]<31:
            lever.append((i,part))
    if len(lever)!=1:raise ValueError(f'Expected one 1.5x2.4x1.5 external lever; found {len(lever)}')
    actuator_index,actuator=lever[0];ab=bounds(actuator);center=(ab[0]+ab[3])/2
    model_b_offset=center-(sx-1)
    if abs(model_b_offset+.25)>.01:raise ValueError(f'Native model detent datum changed: {model_b_offset}')
    static=cq.Compound.makeCompound([part for i,part in enumerate(solids) if i!=actuator_index])
    shapes={name:cq.importers.importStep(str(root/'output'/f'calxus_{name}.step')).val() for name in ['base','lid','comb_lower_tpu','comb_upper_tpu','slider_fork','slider_thumb']}
    fork,thumb=shapes.pop('slider_fork'),shapes.pop('slider_thumb')
    # Every moving solid for all requested poses is contained in this box.
    # Clipping stationary shells to a box expanded by 1 mm preserves every
    # possible intersection exactly and avoids repeated distant text/rail work.
    swept=[sx-7.85,sy-4,3.1,sx+7.85,sy+4,17.4]
    margin=1.0;clip_bounds=[v-margin for v in swept[:3]]+[v+margin for v in swept[3:]]
    clip=box(clip_bounds[:3],clip_bounds[3:]);fixed={};skipped=[]
    for name,part in {**shapes,'SW1_STATIC':static,**others}.items():
        bb=bounds(part)
        if not all(clip_bounds[i]<bb[i+3] and bb[i]<clip_bounds[i+3] for i in range(3)):
            skipped.append(name);continue
        if name in shapes:
            part=part.intersect(clip)
            if not part.Solids():skipped.append(name);continue
        fixed[name]=part
    fixed_bounds={name:bounds(part) for name,part in fixed.items()}
    print(json.dumps({'phase':'imported','exact_candidates':list(fixed),'bbox_excluded':len(skipped),'actuator_x':center}),flush=True)
    def local_lid_distance(part):
        distance=part.distance(fixed['lid'])
        # Artificial clip faces are >=1 mm away. A shorter nearest distance is
        # necessarily to the original lid. Fallback preserves full accuracy.
        return distance if distance<margin-1e-6 else part.distance(shapes['lid'])
    bearing=sl['counterbore_bearing_z']
    bolt=cylinder(sx,sy,bearing-6,bearing,2).fuse(cylinder(sx,sy,bearing,bearing+1.8,4))
    insert=cylinder(sx,sy,9.7,12.2,3.2).cut(cylinder(sx,sy,9.6,12.3,2))
    report={'schema':'calxus.selector-motion.v1','revision':c['revision'],'source':args.step.name,'source_sha256':hashlib.sha256(raw).hexdigest(),'actual_pcba_used':not args.sw1_only,'explicit_sw1_model_z_correction_mm':args.sw1_z_correction,'actuator_source_solid_index':actuator_index,'actuator_source_bbox_mm_after_explicit_z_correction':ab,'model_b_detent_x_difference_mm':model_b_offset,'scope':'External linkage motion at four positions. Internal electrical contacts and switch detent mechanics are not simulated. Nominal0 case is an explicitly shifted actuator-datum sensitivity case, not a second vendor model.','collision_threshold_mm3':1e-5,'swept_moving_bounds_mm':swept,'fixed_clip_bounds_mm':clip_bounds,'broad_phase_excluded_fixed_parts':skipped,'exact_fixed_candidates':list(fixed),'clip_proof':'All moving solids lie inside swept bounds; stationary solids are clipped only outside an additional1mm margin. Any reported minimum distance below1mm is independent of artificial clip faces.','cases':[],'clamp_positions':[]}
    for case_name,cal,actuator_datum_shift in [('nominal_datum_0',0,-model_b_offset),('library_model_fit_minus_0p25',-.25,0),('calibration_limit_minus_0p35',-.35,-.35-model_b_offset),('calibration_limit_plus_0p35',.35,.35-model_b_offset)]:
        case={'name':case_name,'fork_calibration_x_mm':cal,'explicit_actuator_datum_x_shift_mm':actuator_datum_shift,'poses':[]}
        for mode,off in enumerate(s['position_offsets']):
            moving={'fork':fork.translate((off+cal,0,0)),'thumb':thumb.translate((off,0,0)),'screw':bolt.translate((off+cal,0,0))}
            act=actuator.translate((off+1+actuator_datum_shift,0,0))
            for part in moving.values():
                mb=bounds(part)
                if not all(mb[i]>=swept[i]-1e-6 and mb[i+3]<=swept[i+3]+1e-6 for i in range(3)):raise ValueError('Moving geometry exceeds proved sweep box')
            collisions=[];tests=0
            for name,part in moving.items():
                for other_name,other in {**fixed,'SW1_EXTERNAL_ACTUATOR':act}.items():
                    a=bounds(part);b=bounds(act) if other_name=='SW1_EXTERNAL_ACTUATOR' else fixed_bounds[other_name]
                    if not all(a[i]<b[i+3]-1e-8 and b[i]<a[i+3]-1e-8 for i in range(3)):continue
                    tests+=1;v=common_volume(part,other)
                    if v>1e-5:collisions.append({'moving':name,'against':other_name,'intersection_mm3':v})
            for n1,n2 in [('fork','thumb'),('screw','thumb'),('screw','fork')]:
                tests+=1;v=common_volume(moving[n1],moving[n2])
                if v>1e-5:collisions.append({'moving':n1,'against':n2,'intersection_mm3':v})
            # Actual 1.5 mm lever x walls relative to measured fork slot center.
            ba=bounds(act);slotcenter=sx+off+cal
            print(json.dumps({'phase':'pose','case':case_name,'mode':mode,'collision_count':len(collisions)}),flush=True)
            case['poses'].append({'label':mode,'thumb_center_x_mm':sx+off,'fork_center_x_mm':slotcenter,'actuator_bbox_mm':ba,'actuator_x_side_gaps_mm':[ba[0]-(slotcenter-.95),(slotcenter+.95)-ba[3]],'actuator_top_gap_mm':5.1-ba[5],'fork_vs_lid_distance_mm':local_lid_distance(moving['fork']),'thumb_vs_lid_distance_mm':local_lid_distance(moving['thumb']),'boolean_tests':tests,'collisions':collisions})
        report['cases'].append(case)
    # Test the whole declared calibration range at both endpoints and the two datum cases.
    h=.001
    top_faces=[f for f in thumb.Faces() if abs(f.Center().z-s['thumb_top_z'])<1e-6 and f.geomType()=='PLANE']
    if len(top_faces)!=1:raise ValueError('Unexpected thumb top topology')
    top=top_faces[0]
    wall=min(top.outerWire().distance(wire) for wire in top.innerWires())
    report['measured_pocket_minimum_wall_mm']=wall
    report['bearing_floor_thickness_mm']=bearing-s['thumb_base_z']
    stem_slab=section_slab(thumb,13.0)
    posts=stem_slab.Solids()
    if len(posts)!=2:raise ValueError('Expected two separate guide end posts in the lower stem cross-section')
    report['measured_stem_end_posts']=[{'bounds_mm':bounds(p),'thickness_x_mm':bounds(p)[3]-bounds(p)[0],'width_y_mm':bounds(p)[4]-bounds(p)[1]} for p in posts]
    report['stem_open_center_x_mm']=min(bounds(p)[0] for p in posts if bounds(p)[0]>sx)-max(bounds(p)[3] for p in posts if bounds(p)[3]<sx)
    report['stem_ligament_note']='Two full 0.8 mm end posts replace sub-nozzle side ligaments. The lower guide window is open along Y; the upper head floor joins the posts.'
    for cal in sorted(set([*s['fork_calibration_x_range_mm'],0,-.25])):
        shifted_fork=fork.translate((cal,0,0));shifted_bolt=bolt.translate((cal,0,0));shifted_insert=insert.translate((cal,0,0))
        # Bring the two contacting 0.001 mm layers to identical Z for area evaluation.
        fork_contact=section_slab(shifted_fork,12.2-h).translate((0,0,h))
        thumb_contact=section_slab(thumb,12.2)
        contact_area=common_volume(fork_contact,thumb_contact)/h
        thumb_bearing=section_slab(thumb,bearing-h)
        head_projection=cylinder(sx+cal,sy,bearing-h,bearing,4)
        bearing_area=common_volume(thumb_bearing,head_projection)/h
        bolt_thumb=common_volume(shifted_bolt,thumb)
        report['clamp_positions'].append({'fork_calibration_x_mm':cal,'fork_thumb_contact_area_mm2':contact_area,'head_thumb_bearing_area_mm2':bearing_area,'screw_thumb_intersection_mm3':bolt_thumb,'fork_thumb_intersection_mm3':common_volume(shifted_fork,thumb),'max_head_end_clearance_mm':(5-4)/2-abs(cal),'max_head_side_clearance_mm':(4.2-4)/2,'insert_engagement_mm':min(bearing,12.2)-max(bearing-6,9.7),'head_top_recess_mm':s['thumb_top_z']-(bearing+1.8)})
    report['pass']=all(not pose['collisions'] and min(pose['actuator_x_side_gaps_mm'])>.18 and pose['actuator_top_gap_mm']>.2 for case in report['cases'] for pose in case['poses']) and wall>=.8-1e-6 and all(p['thickness_x_mm']>=.8-1e-6 for p in report['measured_stem_end_posts']) and report['bearing_floor_thickness_mm']>=.8-1e-6 and all(p['fork_thumb_contact_area_mm2']>1 and p['head_thumb_bearing_area_mm2']>5 and p['screw_thumb_intersection_mm3']<1e-5 and p['fork_thumb_intersection_mm3']<1e-5 and p['insert_engagement_mm']>=2.49 for p in report['clamp_positions'])
    report['limits']=['Zero interference is evaluated for modeled rigid geometry. Print shrinkage, insert torque, polymer creep and long-term joint slip require a physical first article.','The nominal-zero actuator hypothesis is an explicit +0.24996 mm X sensitivity shift; no source datum is silently corrected.','The -0.25 mm setting is a library-model observation, not a guaranteed physical adjustment.','External actuator translation does not verify internal electrical contact sequence.']
    args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'pass':report['pass'],'report':str(args.report),'wall_mm':wall,'clamp':report['clamp_positions']},indent=2))
    if not report['pass']:raise SystemExit(1)

if __name__=='__main__':main()
