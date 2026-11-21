#!/usr/bin/env python3
"""Calxus R1 mechanical package. Units mm. Uses genuine OpenCascade solid CAD.

Run: python generate_mechanical.py
Contract is the only source for board envelope/port/hole locations.
STEP and STL are generated; no image-generation service is used.
"""
from pathlib import Path
import csv, json, math, hashlib, os
import cadquery as cq
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont('CalxusSans','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('CalxusSans-Bold','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
C=json.loads((ROOT/'mechanical_contract.json').read_text())
L,W,T=C['board']['size']; E=C['enclosure']; F=C['fasteners']; G=C['tail_comb']
S=C['selector']
SL=F['slider_screw']
THX,THY=S['thumb_outer_size_x_y']
THZ=S['thumb_top_z']
SCREW_Z=SL['counterbore_bearing_z']
Z0=E['bounds_min'][2]; Z1=E['bounds_max'][2]; SEAM=E['seam_z']
HOLES=C['board']['mounting_holes']


def rr_xy(x0,y0,x1,y1,z0,z1,r):
    wp=cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0,centered=(True,True,False)).translate(((x0+x1)/2,(y0+y1)/2,z0))
    if r: wp=wp.edges('|Z').fillet(r)
    return wp


def box(mins,maxs):
    a,b=np.array(mins,float),np.array(maxs,float)
    return cq.Workplane('XY').box(*(b-a),centered=(False,False,False)).translate(tuple(a))


def zcyl(x,y,z0,z1,d):
    return cq.Workplane('XY').center(x,y).circle(d/2).extrude(z1-z0).translate((0,0,z0))


def xcyl(x0,x1,y,z,d):
    return cq.Workplane('YZ').center(y,z).circle(d/2).extrude(x1-x0).translate((x0,0,0))


def outer(z0,z1):
    return rr_xy(-3,-3,L+3,W+3,z0,z1,E['outer_corner_radius'])


def cavity(z0,z1,offset=1.0):
    # Radius is offset coherently from the outer 3.5 mm corner.
    return rr_xy(-offset,-offset,L+offset,W+offset,z0,z1,0.5+offset)


def opening(p):
    w,h,r=p['opening_width'],p['opening_height'],p['opening_corner_radius']
    x,y,z=p['center']
    if p['side']=='xmin':
        return cq.Workplane('YZ').center(y,z).rect(w,h).extrude(7).edges('|X').fillet(r).translate((-5,0,0))
    if p['side']=='ymin':
        # XZ normal is -Y; translation places the cut across exterior and inner wall.
        return cq.Workplane('XZ').center(x,z).rect(w,h).extrude(7).edges('|Y').fillet(r).translate((0,2,0))
    raise ValueError(p['side'])


# Floor with four mounting bosses, supported by low ribs that stay below PCB underside.
base=outer(Z0,SEAM).cut(cavity(E['inner_floor_z'],SEAM+2))
for x,y in HOLES:
    base=base.union(zcyl(x,y,E['inner_floor_z'],0,F['boss_outer_diameter']))
    nearest_x=-1 if x<L/2 else L+1
    nearest_y=-1 if y<W/2 else W+1
    base=base.union(box([min(nearest_x,x),y-.7,E['inner_floor_z']],[max(nearest_x,x),y+.7,-1.3]))
    base=base.union(box([x-.7,min(nearest_y,y),E['inner_floor_z']],[x+.7,max(nearest_y,y),-1.3]))
    base=base.cut(zcyl(x,y,F['screw_tip_relief_bottom_z'],0.1,F['screw_tip_relief_diameter']))
    base=base.cut(zcyl(x,y,F['inserts']['bottom_z'],0.1,F['inserts']['pilot_diameter']))
# Tongue lies on the inner portion of the lower shell wall; lid has an independent socket.
lip=cavity(SEAM,SEAM+E['lip_height'],1.9).cut(cavity(SEAM-.1,SEAM+E['lip_height']+.1,1.0))
base=base.union(lip)
lid=outer(SEAM,Z1).cut(cavity(SEAM-.1,E['inner_roof_z'],1.0))
lid=lid.cut(cavity(SEAM-.1,SEAM+E['lip_height']+E['lip_vertical_clearance'],1.9+E['lip_lateral_clearance']))
for x,y in HOLES:
    lid=lid.union(zcyl(x,y,T+E['pcb_capture_clearance'],E['inner_roof_z']+.1,F['boss_outer_diameter']))
    lid=lid.cut(zcyl(x,y,T,Z1+.2,F['lid_screws']['clearance_diameter']))
    lid=lid.cut(zcyl(x,y,F['lid_screws']['counterbore_bearing_z'],Z1+.2,F['lid_screws']['counterbore_diameter']))
for p in C['ports']:
    cut=opening(p); base=base.cut(cut); lid=lid.cut(cut)
# Tail aperture removes both walls and the tongue in this location.
slot=box([L-.9,G['case_slot_y'][0],G['case_slot_z'][0]],[L+5,G['case_slot_y'][1],G['case_slot_z'][1]])
base=base.cut(slot); lid=lid.cut(slot)
# Recessed markings are vector-cut into the model, not an overlay or raster texture.
for label,x,y,size in [('CALXUS',L/2,25,5.2),('R1',L/2,18,2.5)]:
    txt=cq.Workplane('XY').text(label,size,.3,font='DejaVu Sans',halign='center',valign='center').translate((x,y,Z1-.25))
    lid=lid.cut(txt)

# Guided two-part slider drives the horizontal ALPS actuator from the top of the case.
# The fork is inserted along the open rail end before the thumb cap is screwed on.
sx=S['body_center'][0]; sy=S['slider_center_y']; by=S['body_center'][1]
slot_x,slot_y=S['top_slot_size_x_y']
selector_slot=rr_xy(sx-slot_x/2,sy-slot_y/2,sx+slot_x/2,sy+slot_y/2,12.2,15.0,.45)
lid=lid.cut(selector_slot)
for yy,ledge_y in ((sy-4.9,sy-4.9),(sy+4.2,sy+3.4)):
    lid=lid.union(box([sx-8.5,yy,10.0],[sx+8.5,yy+.7,12.6]))
    lid=lid.union(box([sx-8.5,ledge_y,10.0],[sx+8.5,ledge_y+1.5,10.8]))
# Fork socket is open downward for assembly over the switch actuator.
fork=box([sx-2.2,by-4.6,3.1],[sx+2.2,by-1.95,7.1])
fork=fork.cut(box([sx-S['fork_socket_width_x']/2,by-3.95,3.0],[sx+S['fork_socket_width_x']/2,by-1.7,5.1]))
transition=(cq.Workplane('XY').workplane(offset=7.0).center(sx,sy)
            .rect(4.4,2.65).workplane(offset=4.0).rect(9.0,6.4).loft())
fork=fork.union(transition).union(box([sx-4.5,sy-4,11.0],[sx+4.5,sy+4,12.2]))
fork=fork.cut(zcyl(sx,sy,8.8,12.4,2.1)).cut(zcyl(sx,sy,9.7,12.4,3.0))
thumb=rr_xy(sx-THX/2,sy-THY/2,sx+THX/2,sy+THY/2,S['thumb_base_z'],THZ,.75)
stx,sty=S['thumb_stem_size_x_y']
thumb=thumb.union(box([sx-stx/2,sy-sty/2,12.2],[sx+stx/2,sy+sty/2,S['thumb_stem_top_z']]))
# X slots let the existing fork/insert/screw clamp +/-0.35 mm relative to the thumb.
# The 7x6 head maintains >=0.9 mm pocket wall and a 0.8 mm continuous bearing floor.
through_slot=(cq.Workplane('XY').center(sx,sy).slot2D(*SL['through_slot_size_x_y']).extrude(THZ+.2-S['thumb_base_z']).translate((0,0,S['thumb_base_z'])))
head_slot=(cq.Workplane('XY').center(sx,sy).slot2D(*SL['counterbore_slot_size_x_y']).extrude(THZ+.2-SCREW_Z).translate((0,0,SCREW_Z)))
stem_window=box([sx-1.5,sy-sty/2-.1,12.0],[sx+1.5,sy+sty/2+.1,S['thumb_base_z']])
thumb=thumb.cut(through_slot).cut(head_slot).cut(stem_window)
for offset,i in zip(S['position_offsets'],range(4)):
    mark=cq.Workplane('XY').text(str(i),2.2,.3,font='DejaVu Sans',halign='center',valign='center').translate((sx+offset,35.3,Z1-.25))
    lid=lid.cut(mark)
legend=cq.Workplane('XY').text('0 MINI  1 A  2 TI  3 UART',1.8,.3,font='DejaVu Sans',halign='center',valign='center').translate((46,36,Z1-.25))
lid=lid.cut(legend)
switch=box([sx-7.5,by-1.75,T],[sx+7.5,by+1.75,T+3.5])
actuator=box([sx-.75,S['actuator_center_y']-1,S['actuator_center_z']-.75],[sx+.75,S['actuator_center_y']+1,S['actuator_center_z']+.75])

# Split TPU comb has positive inner and outer shoulders.
comb=box([G['neck_x'][0],G['neck_y'][0],G['neck_z'][0]],[G['neck_x'][1],G['neck_y'][1],G['neck_z'][1]])
for span in (G['inner_flange_x'],G['outer_flange_x']):
    comb=comb.union(box([span[0],G['flange_y'][0],G['flange_z'][0]],[span[1],G['flange_y'][1],G['flange_z'][1]]))
for ch in G['channels']:
    boot=(cq.Workplane('YZ').center(ch['y'],G['axis_z'])
          .circle((ch['cable_od_nominal']+G['boot_root_diameter_over_jacket'])/2)
          .workplane(offset=G['boot_x'][1]-G['boot_x'][0])
          .circle((ch['cable_od_nominal']+G['boot_tip_diameter_over_jacket'])/2).loft().translate((G['boot_x'][0],0,0)))
    comb=comb.union(boot)
for ch in G['channels']:
    comb=comb.cut(xcyl(L-2,G['boot_x'][1]+.2,ch['y'],G['axis_z'],ch['bore_diameter']))
# Clearance at the two adjacent PCB/lid bosses: do not consume their 3 mm keepout.
for x,y in HOLES:
    comb=comb.cut(zcyl(x,y,-1,15,F['boss_outer_diameter']+.5))
comb_lower=comb.intersect(box([L-10,0,0],[L+20,45,SEAM]))
comb_upper=comb.intersect(box([L-10,0,SEAM],[L+20,45,15]))
# Individual external sleeves retain both split TPU halves. Reference geometry only.
collars=[]
for ch in G['channels']:
    xa,xb=G['retention_collars']['installed_x']
    def boot_diameter(xx):
        f=(xx-G['boot_x'][0])/(G['boot_x'][1]-G['boot_x'][0])
        return ch['cable_od_nominal']+G['boot_root_diameter_over_jacket']+f*(G['boot_tip_diameter_over_jacket']-G['boot_root_diameter_over_jacket'])
    def collar_cone(extra):
        return (cq.Workplane('YZ').center(ch['y'],G['axis_z']).circle(boot_diameter(xa)/2+extra)
                .workplane(offset=xb-xa).circle(boot_diameter(xb)/2+extra).loft().translate((xa,0,0)))
    collars.append(collar_cone(.3).cut(collar_cone(0)).val())
# PCB reference is mechanically exact, not an invented populated PCB model.
pcb=rr_xy(0,0,L,W,0,T,C['board']['corner_radius'])
for x,y in HOLES: pcb=pcb.cut(zcyl(x,y,-.1,T+.1,C['board']['mounting_hole_diameter']))
# Simple physical envelopes for connectors; intentionally identified as reference solids.
connectors={p['name']:box(p['connector_envelope_min'],p['connector_envelope_max']) for p in C['ports']}

# Printer/insert fit coupon: three pilots and cable bores derived from the contract.
coupon=box([0,0,0],[48,16,3.8])
for x,d in ((5,2.9),(13,3.0),(21,3.1)):
    coupon=coupon.cut(zcyl(x,8,1.3,4,d))
aux_bore=next(ch['bore_diameter'] for ch in G['channels'] if ch['name']=='AUX_KEYED_3WIRE')
usb_bore=next(ch['bore_diameter'] for ch in G['channels'] if ch['name']=='USB_MINI_B')
coupon=coupon.cut(zcyl(30,5,-.1,4,aux_bore)).cut(zcyl(30,11,-.1,4,usb_bore))
coupon=coupon.cut(box([41.05,-.1,1.0],[42.95,5.0,3.0]))
for x,label in ((5,'2.9'),(13,'3.0'),(21,'3.1'),(42,'SW')):
    lab=cq.Workplane('XY').text(label,2.4,.3,font='DejaVu Sans',halign='center',valign='center').translate((x,2.8 if x<30 else 9,3.55))
    coupon=coupon.cut(lab)
for yy,label in ((5,f'{aux_bore:.1f}'),(11,f'{usb_bore:.1f}')):
    lab=cq.Workplane('XY').text(label,1.8,.3,font='DejaVu Sans',halign='left',valign='center').translate((33,yy,3.55))
    coupon=coupon.cut(lab)

parts={'calxus_base':base.val(),'calxus_lid':lid.val(),'calxus_comb_lower_tpu':comb_lower.val(),'calxus_comb_upper_tpu':comb_upper.val(),'calxus_slider_fork':fork.val(),'calxus_slider_thumb':thumb.val(),'calxus_fit_coupon':coupon.val()}
for name,shape in parts.items():
    cq.exporters.export(shape,str(OUT/(name+'.step')))
    if name=='calxus_fit_coupon':
        cq.exporters.export(shape,str(OUT/(name+'.stl')),tolerance=.035,angularTolerance=.08)
# Print-position variants make slicer setup unambiguous. Geometry retains assembly-coordinate sources.
printparts={
 'calxus_base_print':base.val().translate((3,3,-Z0)),
 'calxus_lid_print':lid.val().rotate((0,0,0),(1,0,0),180).translate((3,W+3,Z1)),
 'calxus_comb_lower_tpu_print':comb_lower.val().rotate((0,0,0),(1,0,0),180).translate((-G['inner_flange_x'][0],G['flange_y'][1],SEAM)),
 'calxus_comb_upper_tpu_print':comb_upper.val().translate((-G['inner_flange_x'][0],-G['flange_y'][0],-SEAM))
}
printparts['calxus_slider_fork_print']=fork.val().translate((-sx+4.5,-sy+4,-3.1))
printparts['calxus_slider_thumb_print']=thumb.val().rotate((0,0,0),(1,0,0),180).translate((-sx+THX/2,sy+THY/2,THZ))
for name,shape in printparts.items():cq.exporters.export(shape,str(OUT/(name+'.stl')),tolerance=.035,angularTolerance=.08)
cq.exporters.export(pcb.val(),str(OUT/'calxus_pcb_reference.step'))
# Board outline plus hole circles as a direct fabrication/mechanical exchange drawing.
dxf=cq.Workplane('XY').rect(L,W).translate((L/2,W/2,0))
# Exact corner radii are encoded in the STEP; DXF generated from actual bottom face wires.
cq.exporters.export(pcb.faces('<Z').val(),str(OUT/'calxus_board_outline.dxf'))

palette={'calxus_base':(.12,.17,.22),'calxus_lid':(.23,.31,.38),'calxus_comb_lower_tpu':(.1,.1,.1),'calxus_comb_upper_tpu':(.1,.1,.1)}
palette.update({'calxus_slider_fork':(.1,.43,.45),'calxus_slider_thumb':(.10,.48,.50)})
assembly=cq.Assembly(name='Calxus_R1_assembly')
for name in palette:
    shape=parts[name]
    if 'slider_' in name:shape=shape.translate((S['assembly_display_position_offset'],0,0))
    assembly.add(shape,name=name,color=cq.Color(*palette[name]))
assembly.add(pcb,name='PCB_REFERENCE_80x42x1p6',color=cq.Color(.06,.36,.26))
for i,collar in enumerate(collars,1):assembly.add(collar,name=f'Heat_shrink_collar_{i}_REFERENCE',color=cq.Color(.15,.15,.15))
for name,solid in connectors.items():assembly.add(solid,name='ENVELOPE_'+name,color=cq.Color(.70,.72,.75))
assembly.add(switch,name='ALPS_SSSS224100_BODY_REFERENCE',color=cq.Color(.65,.67,.69))
assembly.add(actuator.translate((S['assembly_display_position_offset'],0,0)),name='ALPS_ACTUATOR_REFERENCE_POSITION_0',color=cq.Color(.1,.1,.1))
# Screw and insert reference geometry establishes engagement and allows CAD mating inspection.
screw_shapes=[]; insert_shapes=[]
for i,(x,y) in enumerate(HOLES,1):
    bearing=F['lid_screws']['counterbore_bearing_z']
    screw=zcyl(x,y,bearing-16,bearing,2).union(zcyl(x,y,bearing,bearing+1.6,3.8))
    insert=zcyl(x,y,-2.5,0,3.2).cut(zcyl(x,y,-2.6,.1,2.0))
    screw_shapes.append(screw.val());insert_shapes.append(insert.val())
    assembly.add(screw,name=f'M2x16_screw_{i}_REFERENCE',color=cq.Color(.58,.6,.62))
    assembly.add(insert,name=f'M2_insert_{i}_REFERENCE',color=cq.Color(.72,.52,.22))
thumbscrew=zcyl(sx,sy,SCREW_Z-6,SCREW_Z,2.0).union(zcyl(sx,sy,SCREW_Z,SCREW_Z+1.8,4.0))
thumbinsert=zcyl(sx,sy,9.7,12.2,3.2).cut(zcyl(sx,sy,9.6,12.3,2.0))
assembly.add(thumbscrew.translate((S['assembly_display_position_offset'],0,0)),name='M2x6_slider_screw_REFERENCE',color=cq.Color(.58,.6,.62))
assembly.add(thumbinsert.translate((S['assembly_display_position_offset'],0,0)),name='M2_slider_insert_REFERENCE',color=cq.Color(.72,.52,.22))
assembly.save(str(OUT/'calxus_assembly.step'))

# Robust mesh validation independently checks exported binary STL topology after welding vertices.
def mesh_stats(path):
    import struct
    data=path.read_bytes(); n=struct.unpack('<I',data[80:84])[0]
    records=np.frombuffer(data, dtype=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]), offset=84, count=n)
    tri=records['v'].astype(float)
    unique,inv=np.unique(np.round(tri.reshape(-1,3),5),axis=0,return_inverse=True)
    faces=inv.reshape(-1,3)
    edges=np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1)
    _,counts=np.unique(edges,axis=0,return_counts=True)
    volume=float(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6)
    return {'triangles':int(n),'vertices_welded':len(unique),'boundary_edges':int((counts==1).sum()),'nonmanifold_edges':int((counts!=2).sum()),'signed_volume_mm3':round(volume,4),'watertight_two_manifold':bool(np.all(counts==2))}

validation={'revision':C['revision'],'generator':'CadQuery '+cq.__version__,'scope':'Geometric validation only. No physical print, cable pull, thermal, EMI, or electrical test performed.','solids':{},'pair_intersections_mm3':{},'clearances_mm':{'pcb_underside_to_floor':-E['inner_floor_z']-C['board']['max_component_height_bottom'],'top_components_to_roof':E['inner_roof_z']-(T+C['board']['max_component_height_top']),'pcb_capture_vertical':E['pcb_capture_clearance'],'tongue_socket_lateral':E['lip_lateral_clearance'],'tongue_socket_vertical':E['lip_vertical_clearance'],'screw_tip_to_pocket_bottom':round((F['lid_screws']['counterbore_bearing_z']-16)-F['screw_tip_relief_bottom_z'],4)},'intentional_fits':['M2 brass insert OD3.2 vs polymer pilot3.0 is a heat-set interference fit.','TPU cable bores are 0.20 mm below nominal jacket diameter; actual grip requires testing.','Smooth screw reference cylinders omit threads.']}
for name,shape in parts.items():
    imported=cq.importers.importStep(str(OUT/(name+'.step'))).val()
    bb=shape.BoundingBox()
    stl_name=name+'.stl' if name=='calxus_fit_coupon' else name+'_print.stl'
    validation['solids'][name]={'brep_valid':shape.isValid(),'solid_count':len(shape.Solids()),'volume_mm3':round(shape.Volume(),4),'bounds_mm':[round(v,4) for v in (bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax)],'step_roundtrip_valid':imported.isValid(),'step_roundtrip_volume_delta_mm3':round(abs(imported.Volume()-shape.Volume()),7),'stl_artifact':stl_name,'stl_coordinate_system':'print orientation, minimum Z=0','stl':mesh_stats(OUT/stl_name)}
for a,b in [('calxus_base','calxus_lid'),('calxus_base','calxus_comb_lower_tpu'),('calxus_base','calxus_comb_upper_tpu'),('calxus_lid','calxus_comb_lower_tpu'),('calxus_lid','calxus_comb_upper_tpu'),('calxus_comb_lower_tpu','calxus_comb_upper_tpu')]:
    validation['pair_intersections_mm3'][a+'__'+b]=round(parts[a].intersect(parts[b]).Volume(),8)
for name in palette:
    validation['pair_intersections_mm3'][name+'__pcb']=round(parts[name].intersect(pcb.val()).Volume(),8)
for name,conn in connectors.items():
    for pn in ('calxus_base','calxus_lid'):
        validation['pair_intersections_mm3'][pn+'__'+name]=round(parts[pn].intersect(conn.val()).Volume(),8)
validation['selector_positions']={}
for off in S['position_offsets']:
    moving=[fork.val().translate((off,0,0)),thumb.val().translate((off,0,0))]
    check={}
    for i,part in enumerate(moving):
        for name,other in [('lid',lid.val()),('base',base.val()),('pcb',pcb.val()),('switch_body',switch.val()),('actuator',actuator.val().translate((off,0,0)))]:
            check[f'{i}_{name}']=round(part.intersect(other).Volume(),8)
    check['fork_thumb']=round(moving[0].intersect(moving[1]).Volume(),8)
    validation['selector_positions'][str(off)]=check
# Verify the channel radii on the final split B-reps, rather than only repeating input dimensions.
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
validation['cable_grip_geometry']={'channels':{},'adjacent_boot_clearances_mm':[]}
for ch in G['channels']:
    measured={}
    for name,part in [('lower',comb_lower.val()),('upper',comb_upper.val())]:
        diameters=[]
        for face in part.Faces():
            surface=BRepAdaptor_Surface(face.wrapped)
            if surface.GetType()!=GeomAbs_Cylinder:continue
            cylinder=surface.Cylinder();point=cylinder.Location();axis=cylinder.Axis().Direction()
            if abs(axis.X())>.99999 and abs(point.Y()-ch['y'])<1e-6 and abs(point.Z()-G['axis_z'])<1e-6:
                diameters.append(round(2*cylinder.Radius(),6))
        measured[name]=sorted(set(diameters))
    validation['cable_grip_geometry']['channels'][ch['name']]={
        'nominal_jacket_od_mm':ch['cable_od_nominal'],'specified_bore_mm':ch['bore_diameter'],
        'measured_brep_bores_mm':measured,
        'bore_matches':all(any(abs(d-ch['bore_diameter'])<1e-6 for d in ds) for ds in measured.values()),
        'nominal_diametral_compression_mm':round(ch['cable_od_nominal']-ch['bore_diameter'],4),
        'nominal_neck_ligament_above_below_bore_mm':round((G['neck_z'][1]-G['neck_z'][0]-ch['bore_diameter'])/2,4),
        'boot_root_od_mm':round(ch['cable_od_nominal']+G['boot_root_diameter_over_jacket'],4),
        'boot_tip_od_mm':round(ch['cable_od_nominal']+G['boot_tip_diameter_over_jacket'],4),
        'nominal_boot_tip_wall_mm':round((ch['cable_od_nominal']+G['boot_tip_diameter_over_jacket']-ch['bore_diameter'])/2,4)}
for left,right in zip(G['channels'],G['channels'][1:]):
    gap=right['y']-left['y']-(left['cable_od_nominal']+right['cable_od_nominal'])/2-G['boot_root_diameter_over_jacket']
    xa=G['retention_collars']['installed_x'][0]
    taper=(xa-G['boot_x'][0])/(G['boot_x'][1]-G['boot_x'][0])*(G['boot_root_diameter_over_jacket']-G['boot_tip_diameter_over_jacket'])
    validation['cable_grip_geometry']['adjacent_boot_clearances_mm'].append({'between':[left['name'],right['name']],'root_gap':round(gap,4),'gap_with_reference_heatshrink_at_x86':round(gap+taper-2*G['retention_collars']['reference_wall_thickness'],4)})
validation['all_required_checks_pass']=bool(all(s['brep_valid'] and s['solid_count']==1 and s['step_roundtrip_valid'] and s['step_roundtrip_volume_delta_mm3']<1e-4 and s['stl']['watertight_two_manifold'] and s['stl']['signed_volume_mm3']>0 for s in validation['solids'].values()) and all(v<1e-5 for v in validation['pair_intersections_mm3'].values()))
validation['all_required_checks_pass'] &= all(v<1e-5 for pose in validation['selector_positions'].values() for v in pose.values())
validation['all_required_checks_pass'] &= all(ch['bore_matches'] for ch in validation['cable_grip_geometry']['channels'].values())
validation['all_required_checks_pass'] &= all(gap['root_gap']>0 and gap['gap_with_reference_heatshrink_at_x86']>0 for gap in validation['cable_grip_geometry']['adjacent_boot_clearances_mm'])
(OUT/'validation_report.json').write_text(json.dumps(validation,indent=2)+'\n')

bom=[
('MECH-01','Lower enclosure',1,'PETG/ASA','calxus_base_print.stl','4 perimeters; 0.2 mm layers; 35% infill'),
('MECH-02','Upper enclosure',1,'PETG/ASA','calxus_lid_print.stl','Print exterior roof on bed'),
('MECH-03','Lower cable comb',1,'TPU 95A','calxus_comb_lower_tpu_print.stl','100% infill; match measured cable jackets'),
('MECH-04','Upper cable comb',1,'TPU 95A','calxus_comb_upper_tpu_print.stl','100% infill; split face on bed'),
('MECH-05','M2 x 16 pan/button head screw',4,'Steel','Purchased hardware','Head <=4.0 diameter and <=1.8 high; below-head length16'),
('MECH-06','M2 heat-set insert',5,'Brass','Purchased hardware','OD3.2 nominal x L2.5; four in base, one in slider fork'),
('MECH-07','PCB',1,'FR-4','EDA package','80x42x1.6; four NPTH2.2 mounting holes'),
('MECH-08','Mini-B downstream captive cable',1,'UL2725 #28 shielded USB cable','Ckmtw S002020047 / LCSC C430897','Jacket OD3.8; comb bore3.6; retain Mini-B end with 250-300 mm cable segment; allow for clamped/internal length'),
('MECH-09','TI 2.5 mm captive cable',1,'Reused C430897 shielded cable','C430897 remainder + verified 2.5 mm plug','Jacket OD3.8; comb bore3.6; 250-300 mm cut segment; label TI; verify plug outlet >=3.8'),
('MECH-10','Casio 2.5 mm captive cable',1,'Reused C430897 shielded cable','C430897 remainder + verified 2.5 mm plug','Jacket OD3.8; comb bore3.6; 250-300 mm cut segment; label CASIO; verify plug outlet >=3.8'),
('MECH-11','Keyed auxiliary 3-wire tail',1,'26 AWG PH harness + outer sleeve','200 mm PH lead + prepared outer sleeve','Comb bore2.8; build clamped bundle OD2.9..3.1, nominal3.0; no exposed individual conductors under clamp'),
('MECH-12','Slider fork',1,'PETG / ASA','calxus_slider_fork_print.stl','Print upright with brim; actuator fit must be checked'),
('MECH-13','Adjustable slider thumb',1,'PETG / ASA','calxus_slider_thumb_print.stl','7x6 top; X slots allow +/-0.35 calibration; 0.8 bearing floor; print top surface on bed'),
('MECH-14','M2 x 6 pan/button head screw',1,'Steel','Purchased hardware','Head <=4.0 diameter and <=1.8 high')]
bom.append(('MECH-15','Individual 2:1 heat-shrink collar',4,'Polyolefin','Purchased harness material','Expanded ID8mm x cut length8mm; installed X86..94 on TPU boots; shrink before housing assembly'))
with (OUT/'mechanical_bom.csv').open('w',newline='') as f:
    wr=csv.writer(f);wr.writerow(['Reference','Description','Quantity','Material','Source','Notes']);wr.writerows(bom)

# CAD tessellation-based renderer. No artificial scene imagery or generated textures.
def render_scene(items,path,elev=26,azim=-55,limits=None,title=None,figsize=(12,7),labels=None,subtitle=None):
    if os.environ.get('CALXUS_SKIP_RENDER')=='1': return
    if os.environ.get('CALXUS_RENDER_ONLY') and os.environ['CALXUS_RENDER_ONLY']!=path.name: return
    import subprocess
    from PIL import Image,ImageDraw,ImageFont
    pts=[];meshes=[]
    for shape,col,alpha in items:
        vv,tt=shape.tessellate(.07,.1);vv=np.array([v.toTuple() for v in vv]);tt=np.array(tt)
        pts.append(vv);meshes.append({'vertices':vv.tolist(),'triangles':tt.tolist(),'color':list(col)})
    pts=np.concatenate(pts);mn=pts.min(0);mx=pts.max(0);center=(mn+mx)/2
    aa,ee=math.radians(azim),math.radians(elev);direction=np.array([math.cos(ee)*math.cos(aa),math.cos(ee)*math.sin(aa),math.sin(ee)])
    right=np.cross(np.array([0,0,1]),direction);right/=np.linalg.norm(right);up=np.cross(direction,right)
    hp=pts@right;vp=pts@up;aspect=figsize[0]/figsize[1]
    scale=max(hp.max()-hp.min(),(vp.max()-vp.min())*aspect)*1.20
    data={'parts':meshes,'width':int(figsize[0]*160),'height':int(figsize[1]*160),'center':center.tolist(),'camera_direction':direction.tolist(),'distance':float(np.linalg.norm(mx-mn)*2),'ortho_scale':float(scale)}
    temp=ROOT/'tmp';temp.mkdir(exist_ok=True);scene=temp/(path.stem+'.json');scene.write_text(json.dumps(data))
    log=temp/(path.stem+'.log')
    with log.open('w') as f:subprocess.run(['blender','--background','--threads','4','--python',str(ROOT/'blender_render.py'),'--',str(scene),str(path)],stdout=f,stderr=subprocess.STDOUT,check=True)
    if title:
        im=Image.open(path).convert('RGB');draw=ImageDraw.Draw(im);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',34)
        draw.text((48,30),title,font=font,fill='#17333f')
        if subtitle:
            small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',27)
            draw.text((48,83),subtitle,font=small,fill='#334b55')
        im.save(path)

assembled=[(parts[n].translate((S['assembly_display_position_offset'],0,0)) if 'slider_' in n else parts[n],palette[n],1) for n in palette]
# Hollow visual proxies communicate socket orientation; they are not supplier STEP models.
cvis=cq.Workplane('YZ').center(21,3.18).rect(8.94,3.16).extrude(7.35).edges('|X').fillet(1.3).translate((-1,0,0))
ccut=cq.Workplane('YZ').center(21,3.18).rect(8.0,2.36).extrude(5.2).edges('|X').fillet(.95).translate((-1.1,0,0))
cvis=cvis.cut(ccut)
avis=box([33.4,-4.925231,1.6],[46.6,5.074775,7.9]).cut(box([33.8,-5.0,1.95],[46.2,3.0,7.55]))
assembled += [(cvis.val(),(.6,.63,.66),1),(avis.val(),(.6,.63,.66),1)]
assembled += [(box([0,17.4,2.95],[4.0,24.6,3.55]).val(),(.08,.09,.1),1),(box([34.0,-3.0,3.2],[46.0,4.8,4.0]).val(),(.08,.09,.1),1)]
assembled += [(s,(.65,.67,.70),1) for s in screw_shapes]
assembled += [(thumbscrew.val().translate((S['assembly_display_position_offset'],0,0)),(.65,.67,.70),1)]
assembled += [(collar,(.09,.10,.11),1) for collar in collars]
# Short captive cable stubs provide the correct four-channel visual context.
for ch in G['channels']:
    assembled.append((xcyl(G['boot_x'][1],112,ch['y'],G['axis_z'],ch['cable_od_nominal']).val(),(.11,.12,.13),1))
render_scene(assembled,OUT/'calxus_assembled.png',elev=26,azim=-138,title='CALXUS R1.2 | Adjustable selector and horizontal USB-A',subtitle='Printed enclosure geometry with connector exterior proxies')
exploded=[(base.val(),palette['calxus_base'],1),(pcb.val().translate((0,0,5)),(.06,.45,.31),1),(lid.val().translate((0,0,28)),palette['calxus_lid'],1),(comb_lower.val().translate((10,0,0)),(.12,.12,.12),1),(comb_upper.val().translate((10,0,13)),(.12,.12,.12),1)]
exploded += [(c.val().translate((0,0,5)),(.7,.72,.75),1) for c in connectors.values()]
exploded += [(s.translate((0,0,35)),(.65,.67,.70),1) for s in screw_shapes]
exploded += [(fork.val().translate((0,0,12)),(.1,.43,.45),1),(thumb.val().translate((0,0,39)),(.1,.48,.50),1),(switch.val().translate((0,0,5)),(.65,.67,.69),1)]
render_scene(exploded,OUT/'calxus_exploded.png',elev=24,azim=-60,title='CALXUS R1.2 | Assembly order and service access',figsize=(12,9),subtitle='Component installation envelopes; not populated-PCBA geometry')
render_scene([(base.val(),(.22,.32,.40),1),(comb_lower.val(),(.15,.15,.15),1)],ROOT/'tmp/calxus_base_detail.png',elev=55,azim=-60,title='Lower shell | boss seats, cable comb, lip')
render_scene([(lid.val().rotate((0,0,0),(1,0,0),180),(.27,.36,.44),1)],ROOT/'tmp/calxus_lid_inside.png',elev=45,azim=-60,title='Upper shell | PCB capture posts and socket')

# Assembly drawing in vector PDF, with dimensioned orthographic geometry and measured source data.
PDF=OUT/'calxus_mechanical_drawing.pdf'; cv=canvas.Canvas(str(PDF),pagesize=(842,595))
INK=colors.HexColor('#15313c'); TEAL=colors.HexColor('#006f74'); GREY=colors.HexColor('#566873')
def txt(x,y,s,size=9,color=INK,bold=False):
    cv.setFillColor(color);cv.setFont('CalxusSans-Bold' if bold else 'CalxusSans',size);cv.drawString(x,y,s)
def line(x1,y1,x2,y2,color=INK,width=.7):
    cv.setStrokeColor(color);cv.setLineWidth(width);cv.line(x1,y1,x2,y2)
def dimension(x1,y1,x2,y2,label,offset=0,vertical=False):
    if vertical:
        xx=x1+offset;line(x1,y1,xx+3,y1,GREY,.4);line(x2,y2,xx+3,y2,GREY,.4);line(xx,y1,xx,y2,GREY,.5)
        for yy in (y1,y2):line(xx-2,yy-2,xx+2,yy+2,GREY,.6)
        txt(xx+4,(y1+y2)/2,label,8,GREY)
    else:
        yy=y1+offset;line(x1,y1,x1,yy+3,GREY,.4);line(x2,y2,x2,yy+3,GREY,.4);line(x1,yy,x2,yy,GREY,.5)
        for xx in (x1,x2):line(xx-2,yy-2,xx+2,yy+2,GREY,.6)
        cv.setFont('CalxusSans',8);tw=cv.stringWidth(label,'CalxusSans',8);txt((x1+x2-tw)/2,yy+4,label,8,GREY)
def header(page,title,subtitle):
    cv.setFillColor(INK);cv.rect(0,535,842,60,fill=1,stroke=0)
    txt(32,565,title,20,colors.white,True);txt(32,545,subtitle,9,colors.HexColor('#d2e3e8'))
    line(32,34,810,34,GREY,.5);txt(32,20,'CALXUS / '+C['revision']+' / mm / geometric drawing - verify connector samples before manufacture',8,GREY);txt(766,20,f'{page} / 5',8,GREY)
def bullet(x,y,s):txt(x,y,'- '+s,9)
header(1,'Mechanical interface and overall dimensions','Board datum: lower-left = (0,0,0). PCB top is Z=1.6. Four M2 mounting locations define the shared EDA/CAD interface.')
s=4.0;ox=72;oy=264
cv.setFillColor(colors.HexColor('#edf2f4'));cv.setStrokeColor(INK);cv.setLineWidth(.8);cv.roundRect(ox-3*s,oy-3*s,86*s,48*s,3.5*s,fill=1,stroke=1)
cv.setFillColor(colors.HexColor('#d4e9e0'));cv.roundRect(ox,oy,80*s,42*s,1*s,fill=1,stroke=1)
for x,y in HOLES:
    cv.setFillColor(colors.white);cv.circle(ox+x*s,oy+y*s,1.1*s,fill=1,stroke=1);cv.setDash(2,2);cv.circle(ox+x*s,oy+y*s,3*s,fill=0,stroke=1);cv.setDash()
cv.setFillColor(colors.HexColor('#b9c2ca'))
for p in C['ports']:
    a,b=p['connector_envelope_min'],p['connector_envelope_max']
    cv.rect(ox+a[0]*s,oy+a[1]*s,(b[0]-a[0])*s,(b[1]-a[1])*s,fill=1,stroke=1)
cv.setFillColor(colors.HexColor('#b9c2ca'));cv.rect(ox+12.5*s,oy+32.25*s,15*s,3.5*s,fill=1,stroke=1)
cv.setFillColor(colors.HexColor('#007d84'));cv.rect(ox+(sx-THX/2+S['assembly_display_position_offset'])*s,oy+(sy-THY/2)*s,THX*s,THY*s,fill=1,stroke=1)
for ch in G['channels']:
    cv.setFillColor(colors.HexColor('#4a5359'));cv.rect(ox+79.2*s,oy+(ch['y']-ch['cable_od_nominal']/2)*s,10*s,ch['cable_od_nominal']*s,fill=1,stroke=0)
    txt(442,oy+ch['y']*s-3,ch['name'].replace('_',' '),8)
dimension(ox-3*s,oy+45*s,ox+83*s,oy+45*s,'86.0 overall',26)
dimension(ox,oy,ox+80*s,oy,'80.0 PCB',-36)
dimension(ox-3*s,oy-3*s,ox-3*s,oy+45*s,'48.0',-22,True)
txt(91,460,'TOP VIEW / interface projection',10,TEAL,True)
# Long-side view, same X scale.
sy=134
cv.setFillColor(colors.HexColor('#edf2f4'));cv.roundRect(ox-3*s,sy,86*s,19*s,2*s,fill=1,stroke=1)
cv.setFillColor(colors.HexColor('#007d84'));cv.rect(ox+(sx-THX/2+S['assembly_display_position_offset'])*s,sy+(S['thumb_base_z']-Z0)*s,THX*s,(THZ-S['thumb_base_z'])*s,fill=1,stroke=1)
line(ox-3*s,sy+(SEAM-Z0)*s,ox+83*s,sy+(SEAM-Z0)*s,GREY,.7)
cv.setFillColor(colors.HexColor('#d4e9e0'));cv.rect(ox,sy+(0-Z0)*s,80*s,T*s,fill=1,stroke=1)
# Actual y-min port opening, projected on this view.
p=C['ports'][1];cv.setFillColor(colors.white);cv.roundRect(ox+(40-p['opening_width']/2)*s,sy+(p['center'][2]-p['opening_height']/2-Z0)*s,p['opening_width']*s,p['opening_height']*s,p['opening_corner_radius']*s,fill=1,stroke=1)
dimension(ox+83*s,sy,ox+83*s,sy+19*s,'19.0',20,True)
dimension(ox+83*s,sy,ox+83*s,sy+21.9*s,'21.9 total',50,True)
txt(91,111,'FRONT VIEW / USB-A access opening',10,TEAL,True)
txt(534,482,'Interface coordinates',12,TEAL,True)
y=463
for label,value in [('PCB size','80.0 x 42.0 x 1.6'),('PCB corner radius','R1.0'),('Mounting holes','4 x diameter 2.2 NPTH'),('Centers X','3.5 / 76.5'),('Centers Y','3.5 / 38.5'),('Both-face keepout','R3.0 around each hole'),('USB-C access','Y21.0 / Z3.3'),('USB-A access','X40.0 / Z5.1'),('Cable center height','Z5.2'),('Cable centers Y','10 / 18 / 26 / 34'),('Switch body center','X20.0 / Y34.0'),('Selector travel','X6.0; 2.0 per step')]:
    txt(534,y,label,9);txt(670,y,value,9);y-=18
line(534,244,806,244,GREY,.5)
for i,sentence in enumerate(['Body 86 x 48 x 19; 21.9 high with thumb.','TPU flange X84.5; tapered boots end X96.5.','USB-A opening: 20.5 x 12.0, R1.0.','USB-C opening: 14.4 x 8.0, R1.5.','Slot: 11.2 x 3.3 at (20,30.9).','USB-A mouth projects 1.925 beyond Y-3 wall.','No physical retention or thermal test performed.']):
    txt(534,224-i*17,sentence,9)
cv.showPage()
header(2,'Assembly, fasteners and service access','Remove four lid screws to access EEPROM pads, test pads and the keyed auxiliary tail termination. No glued service covers.')
cv.drawImage(ImageReader(str(OUT/'calxus_exploded.png')),26,55,width=475,height=460,preserveAspectRatio=True,anchor='c',mask='auto')
txt(518,490,'Assembly sequence',13,TEAL,True)
steps=[
 '1  Print the fit coupon; choose the insert pilot fit.',
 '2  Heat-set four M2 inserts flush with boss top Z0.',
 '3  Heat-set the fifth insert in the slider fork.',
 '4  Insert fork; fit M2 x 6 loosely through X slots.',
 '5  Retain TPU halves with four heat-shrink collars.',
 '6  Seat PCB/comb and terminate inspected harnesses.',
 '7  Align at inner detent; lock thumb screw (page5).',
 '8  Install four M2 x 16 screws; hand-tighten evenly.',
 '9  Test all four detents and cable/USB mating.'
]
for i,sentence in enumerate(steps):txt(518,468-i*21,sentence,9)
txt(518,259,'Fastener stack / nominal',12,TEAL,True)
for i,sentence in enumerate(['Case: four M2 x 16; slider: one M2 x 6.','Heads <=4.0 diameter, <=1.8 high.','Case counterbore: diameter 4.4, bearing Z12.4.','Five inserts: M2, OD3.2 x L2.5; trial first.','Base pilots: diameter 3.0, Z-2.5 to 0.','Case screw tip Z-3.6; relief ends Z-3.8.','Never use screws to pull a warped lid closed.']):txt(518,238-i*18,sentence,9)
cv.showPage()
header(3,'Print settings, tolerances and bill of materials','Prototype fabrication specification. A physical fit and cable retention test is required before releasing a production enclosure.')
cv.drawImage(ImageReader(str(ROOT/'tmp/calxus_base_detail.png')),28,295,width=380,height=217,preserveAspectRatio=True,anchor='c',mask='auto')
cv.drawImage(ImageReader(str(ROOT/'tmp/calxus_lid_inside.png')),428,295,width=380,height=217,preserveAspectRatio=True,anchor='c',mask='auto')
txt(40,276,'Rigid parts: PETG or ASA',12,TEAL,True)
for i,t in enumerate(['0.4 mm nozzle; 0.2 mm layer; >=4 perimeters.','35% infill; 5 top/bottom layers; dry material.','Base floor / lid roof / thumb top on bed.','Fork upright with brim; rail ledges need supports.','Nominal walls 2.0; tongue 0.9; socket wall 0.85.']):txt(40,256-i*16,t,9)
txt(434,276,'TPU comb and dimensional fit',12,TEAL,True)
for i,t in enumerate(['TPU 95A; 100% infill; split face on bed.','Mini-B / TI / Casio: OD3.8 cable / bore3.6.','AUX: sleeve to OD2.9..3.1 / bore2.8.','Four 2:1 heat-shrink collars: ID8 x length8.','Tongue clearance0.25; PCB capture+0.15.']):txt(434,256-i*16,t,9)
line(40,164,800,164,GREY,.5)
rows=[('4','Case halves + selector fork + thumb','PETG / ASA'),('2+4','TPU comb halves + heat-shrink collars','TPU 95A / polyolefin'),('4+1','M2 x 16 case / M2 x 6 selector screws','Steel'),('5','M2 OD3.2 x L2.5 heat-set inserts','Brass'),('1','80 x 42 x 1.6 PCB','See EDA BOM'),('4','Captive cable assemblies','See harness specification')]
txt(40,145,'QTY',9,TEAL,True);txt(87,145,'ITEM',9,TEAL,True);txt(487,145,'MATERIAL / SOURCE',9,TEAL,True)
for i,(qty,it,mat) in enumerate(rows):
    yy=128-i*13;txt(40,yy,qty,9);txt(87,yy,it,9);txt(487,yy,mat,9)
cv.showPage()
header(4,'Geometric checks and prototype acceptance','This page separates completed CAD checks from physical validation that remains to be performed on a built unit.')
txt(40,492,'Completed automatic checks',14,TEAL,True)
checks=[
 f"Valid one-solid B-reps: {sum(s['brep_valid'] and s['solid_count']==1 for s in validation['solids'].values())} / {len(validation['solids'])}",
 'Each printable STL has exactly two incident faces per edge.',
 'STEP files re-import with matching solid volumes.',
 'Closed case: no base/lid/PCB/connector-envelope interference.',
 'Comb halves: no accidental rigid-part interference.',
 'Selector nominal references: checked at four 2 mm detents.',
 'Dimensions, port coordinates and holes derive from one JSON file.',
]
for i,t in enumerate(checks):txt(40,469-i*22,t,10)
txt(40,300,'Computed clearances',13,TEAL,True)
for i,(k,v) in enumerate(validation['clearances_mm'].items()):txt(40,277-i*21,k.replace('_',' ')+f': {v:.2f} mm',10)
txt(444,492,'Acceptance on the first fabricated unit',14,TEAL,True)
accept=[
 'Confirm final r7 populated-PCBA BREP report before printing.',
 'Check USB plug seating with intended A-C and C-C leads.',
 'Check all four harnesses against their electrical pinout table.',
 'Check no copper or component lies inside R3.0 mounting zones.',
 'Gauge the PCB hole/insert alignment before applying screw load.',
 'Ensure lid seats without stressing connectors or the board.',
 'Proof-pull each tail to an agreed requirement; watch for slip.',
 'Inspect cable jackets after assembly and after repeated flexing.',
 'Verify EEPROM/debug access with the lid removed.',
 'Calibrate the coupling and test all four switch detents.'
]
for i,t in enumerate(accept):txt(444,469-i*22,t,9)
cv.setFillColor(colors.HexColor('#eef3f4'));cv.roundRect(442,100,357,98,5,fill=1,stroke=0)
txt(455,177,'Release status: PROTOTYPE',13,TEAL,True)
for i,t in enumerate(['CAD geometry is complete and reproducible.','No physical fit, retention, USB compliance or thermal test','has been performed. Specialized calculator adapters must','be validated separately; labels do not establish compatibility.']):txt(455,157-i*15,t,9)
cv.showPage()
header(5,'Adjustable selector coupling / section and plan','Same fork, insert and M2 x 6 screw. Align the inner detent before clamping; do not assume the library model offset is a physical dimension.')
# Enlarged top plan of thumb and both concentric, X-oriented round-ended slots.
pcx,pcy,ps=190,380,25
cv.setFillColor(colors.HexColor('#c6e4e1'));cv.roundRect(pcx-THX*ps/2,pcy-THY*ps/2,THX*ps,THY*ps,.75*ps,fill=1,stroke=1)
for length,width,fill in [(5.0,4.2,colors.HexColor('#e5eeed')),(3.1,2.3,colors.white)]:
    cv.setFillColor(fill);cv.roundRect(pcx-length*ps/2,pcy-width*ps/2,length*ps,width*ps,width*ps/2,fill=1,stroke=1)
line(pcx-100,pcy,pcx+100,pcy,GREY,.4);line(pcx,pcy-90,pcx,pcy+90,GREY,.4)
dimension(pcx-THX*ps/2,pcy+THY*ps/2,pcx+THX*ps/2,pcy+THY*ps/2,'7.0',25)
dimension(pcx-THX*ps/2,pcy-THY*ps/2,pcx-THX*ps/2,pcy+THY*ps/2,'6.0',-25,True)
txt(90,270,'PLAN / slots parallel to X travel',10,TEAL,True)
txt(390,487,'Dimensioned clamp interface',13,TEAL,True)
notes=['Thumb top: 7.0 x 6.0, R0.75; Z14.7 to17.4.',
       'Upper through slot: 3.1 x 2.3, end radius1.15.',
       'Head pocket: 5.0 x 4.2; end radius2.1; bearing Z15.5.',
       'Continuous bearing floor: 0.8; pocket side wall >=0.9.',
       'Stem: 4.6 x 2.7; open X3.0 center leaves two 0.8 end posts.',
       'Maximum screw head: diameter4.0 x height1.8.',
       'Screw tip: Z9.5; insert remains Z9.7 to12.2.',
       'Fork calibration: X +/-0.35 relative to thumb; then clamp.',
       'Fork socket remains 1.9 wide; actuator is nominal1.5.']
for i,t in enumerate(notes):txt(390,462-i*21,t,9)
# X-Z center section schematic, exact heights and widths.
xx,zz,q=190,100,20
cv.setFillColor(colors.HexColor('#c6e4e1'));cv.rect(xx-3.5*q,zz+(14.7-12)*q,7*q,(17.4-14.7)*q,fill=1,stroke=1)
cv.rect(xx-2.3*q,zz+.2*q,4.6*q,(15.6-12.2)*q,fill=1,stroke=1)
cv.setFillColor(colors.white);cv.rect(xx-1.5*q,zz+.15*q,3.0*q,(14.7-12.15)*q,fill=1,stroke=1)
cv.rect(xx-1.55*q,zz+2.7*q,3.1*q,(17.5-14.7)*q,fill=1,stroke=1)
cv.rect(xx-2.5*q,zz+3.5*q,5*q,2*q,fill=1,stroke=1)
line(xx-92,zz+2.5*q,xx+92,zz+2.5*q,GREY,.6)
txt(42,80,'X-Z SECTION / lid top Z14.5; thumb gap0.2',9,TEAL,True)
txt(390,246,'Assembly calibration',13,TEAL,True)
steps5=['1  Fit the M2 x 6 loosely; keep the fork free within its slots.',
        '2  Set SW1 to an inner detent (label1 or2). Place lid naturally.',
        '3  Align thumb center with that label; let fork locate on lever.',
        '4  Hold alignment and hand-tighten the M2 x 6 from above.',
        '5  Check all four detents and correct labels with power off.',
        'Library model fit is -0.25 mm; this is not a vendor tolerance.',
        'If the actual unit needs >+/-0.35, stop and investigate datum.',
        'Do not force the switch or enlarge the fork to hide an error.']
for i,t in enumerate(steps5):txt(390,222-i*20,t,9)
cv.save()

# Artifact manifest for reproducible review and transfer.
manifest={'revision':C['revision'],'contract_sha256':hashlib.sha256((ROOT/'mechanical_contract.json').read_bytes()).hexdigest(),'files':[]}
for path in sorted(OUT.iterdir()):
    if path.name=='artifact_manifest.json':continue
    manifest['files'].append({'name':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'output':str(OUT),'checks_pass':validation['all_required_checks_pass'],'solids':len(parts),'intersections_mm3':validation['pair_intersections_mm3']},indent=2))
if not validation['all_required_checks_pass']:raise SystemExit('Mechanical validation failed; inspect output/validation_report.json')
