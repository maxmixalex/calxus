#!/usr/bin/env python3
"""Read the USB-C mouth/opening and test a conditional overmold go gauge.

C430908's drawing specifies exposed metal7.0+/-0.3mm but no overmold width or
height. The test is an allowable-envelope check, not a fabricated cable model or
a claim that the selected physical cable has been insertion-tested.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,sys,tempfile
import cadquery as cq
from inspect_step import read_named_shapes
from validate_pcba import bounds,group_shapes
ROOT=Path(__file__).resolve().parent.parent


def box(a,b):
    return cq.Workplane('XY').box(*(b[i]-a[i] for i in range(3)),centered=False).translate(a).val()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cached-j1',type=Path);a=ap.parse_args()
    source=ROOT/'validation/Calxus_RevA_r7_PCBA.step.gz';fit=json.loads((ROOT/'validation/native-r7-pcba-fit.json').read_text())
    if a.cached_j1:j=cq.importers.importStep(str(a.cached_j1)).val()
    else:
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r7.step';p.write_bytes(gzip.decompress(source.read_bytes()))
            expected=set(json.loads((ROOT/'validation/native-r7-model-source-bindings.json').read_text())['components'])
            groups,_=group_shapes(read_named_shapes(p),expected);j=groups['J1']
    want=fit['components']['J1'];assert abs(j.Volume()-want['volume_mm3'])<1e-4
    assert max(abs(x-y) for x,y in zip(bounds(j),want['bbox_mm']))<1e-6
    front=bounds(j)[0]
    faces=[f for f in j.Faces() if f.geomType()=='PLANE' and abs(f.Center().x-front)<1e-5 and len(f.innerWires())==1]
    face=max(faces,key=lambda f:f.Area());inner=bounds(face.innerWires()[0]);cy=(inner[1]+inner[4])/2;cz=(inner[2]+inner[5])/2
    parts={n:cq.importers.importStep(str(ROOT/'output'/f'calxus_{n}.step')).val() for n in ['base','lid']}
    case=parts['base'].fuse(parts['lid']).clean();left=-3.0
    plane_faces=[f for f in case.Faces() if f.geomType()=='PLANE' and abs(f.Center().x-left)<1e-6 and abs(f.normalAt().x)>.99]
    wires=[w for f in plane_faces for w in f.innerWires()]
    mouth=next(w for w in wires if bounds(w)[1]<21<bounds(w)[4] and bounds(w)[2]<3.3<bounds(w)[5]);opening=bounds(mouth)
    assert abs(opening[4]-opening[1]-14.4)<1e-6 and abs(opening[5]-opening[2]-8)<1e-6
    clip=box([-4,12,-2],[0,30,9]);local=case.intersect(clip);checks=[]
    for dy in [-.25,0,.25]:
        for dz in [-.25,0,.25]:
            gauge=box([-6,cy+dy-6.5,cz+dz-3],[front,cy+dy+6.5,cz+dz+3])
            common=gauge.intersect(local);volume=max(0,common.Volume()) if common.Solids() else 0
            gap=gauge.distance(local)
            # Artificial clipping planes are farther than0.75mm from the
            # relevant gauge-to-wall contact region; otherwise use full case.
            if gap>=.75:gap=gauge.distance(case)
            checks.append({'gauge_center_offset_y_z_mm':[dy,dz],'intersection_mm3':volume,'case_clearance_mm':gap,'pass':volume<1e-7 and gap>.15})
    proof={'schema':'calxus.usb-c-overmold-access.v1','native_model_source':source.name,'native_model_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'case_source_sha256':{n:hashlib.sha256((ROOT/'output'/f'calxus_{n}.step').read_bytes()).hexdigest() for n in parts},
        'native_socket_front_x_mm':front,'case_outer_left_face_x_mm':left,'socket_recess_from_outer_wall_mm':front-left,
        'native_mating_opening_inner_wire_bounds_mm':inner,'native_socket_axis_y_z_mm':[cy,cz],
        'actual_case_opening_wire_bounds_mm':opening,'actual_case_opening_width_height_mm':[opening[4]-opening[1],opening[5]-opening[2]],
        'case_opening_corner_radius_mm':1.5,'case_cut_interval_x_mm':[-5,2],
        'conditional_gauge':{'width_y_mm':13,'height_z_mm':6,'corners':'Sharp rectangle, conservative for a rounded overmold inside this bounding box.',
            'required_leading_overmold_profile_depth_mm':2.2,'axial_test_interval_x_mm':[-6,front],
            'lateral_axis_offsets_tested_mm':[-.25,0,.25],'poses':checks,'pass':all(c['pass'] for c in checks)},
        'selected_cable':{'manufacturer':'Ckmtw','part':'S100920007','lcsc':'C430908','drawing_date':'2017-12-07','drawing_revision':'A',
            'source_url':'https://datasheet.lcsc.com/datasheet/pdf/87deec2addefe4b7731637ed71cc524c.pdf?productCode=C430908',
            'documented_exposed_type_c_metal_length_mm':7,'documented_exposed_type_c_metal_length_tolerance_mm':.3,
            'overmold_width_height_dimensions_provided':False,'specific_cable_overmold_fit_certified':False},
        'scope':'The frozen opening admits the specified conservative rectangular overmold gauge through the full2.17mm recess, including+/-0.25mm axis offsets. This is a CAD access-envelope check, not physical cable mating validation.',
        'first_article_check':'Measure the actual C430908 leading plastic profile over at least2.2mm from its front shoulder. A profile contained within13x6mm fits this gauge. Confirm complete insertion, retention and electrical connection with the chosen physical cable; the drawing alone does not certify its overmold.',
        'printed_geometry_changed':False}
    path=ROOT/'validation/upstream-usb-c-access.json';path.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'report':str(path),'recess_mm':front-left,'opening_mm':proof['actual_case_opening_width_height_mm'],'gauge_pass':proof['conditional_gauge']['pass'],'minimum_gauge_clearance_mm':min(c['case_clearance_mm'] for c in checks),'specific_cable_certified':False},indent=2))
    if not proof['conditional_gauge']['pass']:raise SystemExit(1)


if __name__=='__main__':main()
