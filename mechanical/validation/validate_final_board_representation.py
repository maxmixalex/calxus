#!/usr/bin/env python3
"""Measure final native Board BREP and distinguish omitted VIA voids from holes.

The exact source-assembly roundtrip criteria stay unchanged. This diagnostic
records the native export's measured coordinate differences separately; a
0.001mm search window identifies its corresponding non-VIA features and does
not certify exact equality or fabricate the omitted189 VIA voids.
"""
from pathlib import Path
import gzip,hashlib,json,math,sys,tempfile
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Curve

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation'))
from inspect_step import read_named_shapes
from validate_pcba import bounds,cylinders


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def load_shape(path):
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'board.step';p.write_bytes(gzip.decompress(path.read_bytes()))
        leaves=read_named_shapes(p)
    solids=[x['shape'] for x in leaves if x['shape'].Solids()]
    assert len(solids)==1 and len(solids[0].Solids())==1 and solids[0].isValid()
    return solids[0]


def outer_blank(shape):
    bb=bounds(shape)
    bottom=max([f for f in shape.Faces() if f.geomType()=='PLANE' and
                abs(f.Center().z-bb[2])<1e-7 and abs(f.normalAt().z)>.99999],key=lambda f:f.Area())
    wire=bottom.outerWire();edges=[]
    for edge in wire.Edges():
        row={'type':edge.geomType(),'start_mm':edge.startPoint().toTuple(),
             'end_mm':edge.endPoint().toTuple(),'length_mm':edge.Length()}
        if edge.geomType()=='CIRCLE':
            circle=BRepAdaptor_Curve(edge.wrapped).Circle();c=circle.Location()
            row.update(radius_mm=circle.Radius(),center_mm=[c.X(),c.Y(),c.Z()])
        edges.append(row)
    blank=cq.Solid.extrudeLinear(wire,[],cq.Vector(0,0,bb[5]-bb[2]))
    return blank,edges,len(bottom.innerWires())


def main():
    val=ROOT/'validation';native=val/'Calxus_RevA_final_board.step.gz'
    canonical=ROOT/'output/calxus_source_board.step.gz'
    source=ROOT.parent/'hardware/native/Calxus_RevA_final.epro2';native_sha=sha(source)
    basic=json.loads((val/'native-final-board-brep.json').read_text())
    assert basic['source_sha256']==sha(native) and basic['board_geometry_pass']
    ns,ss=load_shape(native),load_shape(canonical)
    nb,ne,ni=outer_blank(ns);sb,se,si=outer_blank(ss)
    difference=nb.cut(sb).Volume()+sb.cut(nb).Volume()
    assert difference<1e-8 and ne==se
    assert sum(e['type']=='CIRCLE' for e in ne)==4
    assert sum(e['type']=='LINE' for e in ne)==4
    cy=cylinders(ns);checks=[];refs=[];used=set();search_window=.001
    for kind,name in [('PAD','native-final-tht-drill-expectations.json'),
                      ('J1_NONPAD','native-final-nonpad-hole-expectations.json'),
                      ('VIA','native-final-via-drill-expectations.json')]:
        p=ROOT.parent/'validation'/name;d=json.loads(p.read_text())
        assert d['source_archive_sha256']==native_sha
        refs.append({'path':str(p.relative_to(ROOT.parent)),'sha256':sha(p),'kind':kind})
        for row in d.get('holes',d.get('vias')):
            if row['shape']=='SLOT':
                probes=[[*c,row['slot_tool_diameter_mm']] for c in row['slot_end_centers_mm']]
            else:probes=[[*row['center_mm'],row.get('diameter_mm',row.get('hole_diameter_mm'))]]
            matches=[]
            for expected in probes:
                error,index,actual=min((math.dist(expected,c),i,c) for i,c in enumerate(cy))
                if error<search_window:used.add(index)
                matches.append({'expected_xy_diameter_mm':expected,'nearest_native_xy_diameter_mm':actual,
                    'combined_difference_mm':error,
                    'center_radial_difference_mm':math.dist(expected[:2],actual[:2]),
                    'diameter_difference_mm':abs(expected[2]-actual[2]),
                    'within_feature_identification_window':error<search_window,
                    'within_unchanged_source_roundtrip_2e_minus6_mm':error<2e-6})
            represented=all(m['within_feature_identification_window'] for m in matches)
            center=row['center_mm'];solid_at_center=ns.isInside(cq.Vector(*center,basic['thickness_mm']/2),1e-7)
            checks.append({'kind':kind,'ref':row.get('ref'),'pin':row.get('pin'),
                'primitive_id':row.get('primitiveId',row.get('source_id')),
                'expected_shape':row['shape'],'represented':represented,
                'solid_at_nominal_center_mid_thickness':solid_at_center,'probes':matches})
    nonvia=[c for c in checks if c['kind']!='VIA'];vias=[c for c in checks if c['kind']=='VIA']
    assert len(nonvia)==58 and all(c['represented'] for c in nonvia)
    assert len(vias)==189 and not any(c['represented'] for c in vias)
    assert all(c['solid_at_nominal_center_mid_thickness'] for c in vias)
    assert ni==58 and si==247 and len(used)==64
    unmatched=[c for i,c in enumerate(cy) if i not in used]
    corners=[e for e in ne if e['type']=='CIRCLE']
    assert len(unmatched)==4
    assert all(min(math.dist(c,[*e['center_mm'][:2],2*e['radius_mm']]) for e in corners)<1e-7 for c in unmatched)
    all_probes=[p for c in nonvia for p in c['probes']]
    report={'schema':'calxus.final-native-board-representation.v1',
        'native_archive_sha256':native_sha,'native_step':'validation/'+native.name,'native_step_sha256':sha(native),
        'canonical_source_board':'output/'+canonical.name,'canonical_source_board_sha256':sha(canonical),
        'board_base_geometry_report':'native-final-board-brep.json','board_base_geometry_report_sha256':sha(val/'native-final-board-brep.json'),
        'native_thickness_mm':basic['thickness_mm'],'native_bbox_mm':basic['board_bbox_mm'],
        'outer_wire_edges':ne,'native_and_canonical_outer_wires_exactly_equal':True,
        'outer_blank_symmetric_difference_mm3':difference,
        'lower_left_corner':'CIRCLE arc, not a45-degree chamfer; the native STEP has four quarter-circle corners.',
        'corner_radius_note':'Native BREP R0.9873025 follows its approximately0.0127mm inset from the nominal R1 board outline. No shape was shifted or repaired.',
        'native_bottom_face_inner_wires':ni,'canonical_bottom_face_inner_wires':si,
        'native_vertical_cylinders':len(cy),'native_nonvia_drill_features_represented':58,
        'native_via_void_features_represented':0,'native_via_nominal_drill_features_omitted':189,
        'all189_via_nominal_centers_inside_native_board_solid':True,
        'nonvia_feature_identification_window_mm':search_window,
        'maximum_nonvia_center_difference_mm':max(p['center_radial_difference_mm'] for p in all_probes),
        'maximum_nonvia_diameter_difference_mm':max(p['diameter_difference_mm'] for p in all_probes),
        'maximum_nonvia_combined_difference_mm':max(p['combined_difference_mm'] for p in all_probes),
        'strict_source_roundtrip_criterion_unchanged_mm':2e-6,
        'native_nonvia_features_meeting_that_exact_source_criterion':sum(all(p['within_unchanged_source_roundtrip_2e_minus6_mm'] for p in c['probes']) for c in nonvia),
        'j2_features':[c for c in nonvia if c['ref']=='J2'],
        'drill_contracts':refs,'feature_checks':checks,
        'native_step_complete_for247_nominal_drills':False,
        'canonical_source_assembly_geometry_changed':False,
        'fresh_native_full_pcba_exported':False,
        'verification_completed':True,
        'limits':['This is a real board-only native STEP, not a new full-PCBA export.',
            'The final native STEP now has the correct J2 nominal Ø1mm signal holes and2.1×0.8mm Y-axis shield slots; the earlier factor-of-ten diagnostic is superseded for this board export.',
            'Native STEP omits189 VIA drill voids. The canonical source-derived CAD retains all247 nominal machining features. Copper, plating and VIPPO fill/caps are not separately modeled.',
            'The0.001mm diagnostic window identifies features and reports actual deviations; it does not replace the unchanged2e-6mm source-derived STEP readback criterion or constitute fabrication-file acceptance.']}
    path=val/'native-final-board-representation.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(path),'outline_difference_mm3':difference,'native_nonvia_features':58,
        'omitted_via_voids':189,'j2_nominal_holes_correct':True,'full_native_pcba_exported':False},indent=2))


if __name__=='__main__':main()
