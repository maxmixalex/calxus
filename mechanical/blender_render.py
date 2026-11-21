import bpy,json,sys,math
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:]
scene_data=json.load(open(args[0]));out=args[1]
bpy.context.preferences.filepaths.save_version=0
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=48;scene.cycles.use_denoising=False
scene.render.resolution_x=scene_data['width'];scene.render.resolution_y=scene_data['height'];scene.render.resolution_percentage=100
scene.world.color=(.8,.8,.8);scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.956,.965,.969,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
for i,part in enumerate(scene_data['parts']):
 mesh=bpy.data.meshes.new('mesh_%d'%i);mesh.from_pydata(part['vertices'],[],part['triangles']);mesh.update()
 ob=bpy.data.objects.new('part_%d'%i,mesh);bpy.context.collection.objects.link(ob)
 mat=bpy.data.materials.new('material_%d'%i);mat.diffuse_color=(*part['color'],1);mat.use_nodes=True;pr=mat.node_tree.nodes.get('Principled BSDF');pr.inputs['Base Color'].default_value=(*part['color'],1);pr.inputs['Roughness'].default_value=.42;pr.inputs['Metallic'].default_value=.12;ob.data.materials.append(mat)
 # Smooth curved faces while retaining sharp CAD normals.
 for poly in mesh.polygons:poly.use_smooth=False
center=Vector(scene_data['center']);v=Vector(scene_data['camera_direction']);distance=scene_data['distance']
camdata=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam
cam.location=center+v*distance;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=scene_data['ortho_scale'];camdata.clip_end=10000
for i,(dv,power,size) in enumerate([((-70,-80,140),180000,90),((60,50,100),110000,70),((-30,80,60),70000,60)]):
 d=bpy.data.lights.new('Light_%d'%i,'AREA');d.energy=power;d.shape='DISK';d.size=size
 o=bpy.data.objects.new('Light_%d'%i,d);bpy.context.collection.objects.link(o);o.location=center+Vector(dv);o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler()
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast' if 'Medium High Contrast' in [x.name for x in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items] else 'None'
scene.render.image_settings.file_format='PNG';scene.render.filepath=out;scene.render.film_transparent=False
bpy.ops.render.render(write_still=True)
