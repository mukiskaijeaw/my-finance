"""Reproducible stylized Paoween model; Blender 5.2+, no external textures."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parents[1]/'assets'/'paoween'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for data in bpy.data.materials: bpy.data.materials.remove(data)
def mat(name,color,metal=0,rough=.52):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 return m
leather=mat('Warm chestnut leather',(.38,.145,.075));edge=mat('Dark rolled leather',(.155,.055,.027));panel=mat('Caramel face',(.48,.215,.115));cream=mat('Cream saddle stitch',(.91,.64,.34));peach=mat('Peach limbs',(.94,.60,.38));ink=mat('Espresso eyes',(.043,.022,.015));white=mat('Eye highlights',(.98,.95,.86));blush=mat('Rosy cheeks',(.76,.255,.17));gold=mat('Brass button',(.94,.59,.10),.6,.28);green=mat('Fictional sage note',(.55,.64,.32));paper=mat('Note border',(.90,.85,.51));blue=mat('Lavender card',(.35,.40,.61));cardline=mat('Card stripe',(.65,.70,.85))
root=bpy.data.objects.new('Paoween',None);bpy.context.collection.objects.link(root)
def parent(o,p=root):o.parent=p;return o
def box(name,loc,scale,material,bevel=.12,p=root):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  mod=o.modifiers.new('Soft rounded silhouette','BEVEL');mod.width=bevel;mod.segments=4
  bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 o.data.materials.append(material)
 for f in o.data.polygons:f.use_smooth=True
 return parent(o,p)
def sphere(name,loc,scale,material,p=root):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(material)
 for f in o.data.polygons:f.use_smooth=True
 return parent(o,p)
def tube(name,points,rad,material,p=root):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=rad;c.bevel_resolution=3
 sp=c.splines.new('POLY');sp.points.add(len(points)-1)
 for pt,xyz in zip(sp.points,points):pt.co=(*xyz,1)
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.data.materials.append(material)
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o=bpy.context.object;o.select_set(False)
 return parent(o,p)
box('Leather back',(0,.10,1.7),(2.65,.68,1.94),edge,.25)
box('Wallet body',(0,-.04,1.7),(2.57,.65,1.84),leather,.23)
box('Front soft panel',(0,-.36,1.68),(2.46,.14,1.74),panel,.22)
# Top opening and overlapping fictional notes.
box('Top slot',(0,.01,2.60),(2.18,.37,.13),edge,.055)
for i,(x,z,ang) in enumerate([(-.24,2.77,-.12),(.28,2.70,.09)]):
 o=box('Fictional banknote '+str(i),(x,.065+i*.10,z),(1.72,.055,.69),paper,.08);o.rotation_euler[1]=ang
 o=box('Note design '+str(i),(x,.025+i*.10,z),(1.48,.026,.46),green,.06);o.rotation_euler[1]=ang
 sphere('Note medallion '+str(i),(x,-.003+i*.10,z),(.20,.015,.16),paper)
box('Lavender payment card',(.08,-.13,2.69),(1.65,.065,.48),blue,.09)
box('Card stripe',(.08,-.17,2.77),(1.37,.016,.05),cardline,.01)
# Raised cream dashes follow a rounded rectangle; front remains texture-free.
for side in [-1,1]:
 for i in range(13):
  x=-1.01+i*.168
  box('Stitch horizontal',(x,-.451,1.68+side*.72),(.087,.018,.025),cream,.012)
 for i in range(9):
  z=1.09+i*.145
  box('Stitch vertical',(side*1.10,-.45,z),(.025,.018,.073),cream,.012)
# Soft limbs are separately pivoted for action clips.
limbs=[]
for side in [-1,1]:
 arm=bpy.data.objects.new(('Left' if side<0 else 'Right')+'Arm',None);bpy.context.collection.objects.link(arm);arm.parent=root;arm.location=(side*1.21,0,1.48);limbs.append(arm)
 tube('Arm sleeve',[(0,0,0),(side*.30,-.05,-.18),(side*.31,-.10,-.35),(side*.16,-.15,-.42)],.092,peach,arm)
 sphere('Mitten',(side*.16,-.15,-.42),(.14,.115,.15),peach,arm)
 tube('Short leg',[(side*.67,0,.84),(side*.72,-.01,.49),(side*.79,-.03,.31)],.102,peach)
 sphere('Soft foot',(side*.78,-.15,.29),(.25,.29,.13),peach)
# Flap stays visibly on character's right.
box('Side clasp dark border',(1.02,-.48,1.54),(.67,.20,.66),edge,.22)
box('Side clasp leather',(1.02,-.60,1.55),(.59,.12,.57),leather,.19)
for i in range(5):box('Flap stitch',(.84+i*.08,-.669,1.77),(.044,.018,.022),cream,.01)
sphere('Gold snap rim',(.99,-.683,1.54),(.169,.04,.169),edge)
sphere('Gold snap',(.99,-.72,1.54),(.132,.04,.132),gold)
# Eyes, cheeks, eyebrows, smile.
for side in [-1,1]:
 sphere('Rosy cheek',(side*.70,-.461,1.61),(.20,.025,.11),blush)
 sphere('Eye '+str(side),(side*.42,-.48,1.91),(.143,.055,.181),ink)
 sphere('Eye sparkle '+str(side),(side*.42+.038,-.531,1.98),(.044,.018,.052),white)
 sphere('Tiny sparkle '+str(side),(side*.42-.032,-.535,1.88),(.021,.012,.024),white)
brows=[]
for side in [-1,1]:
 o=box('Brow '+str(side),(side*.42,-.49,2.18),(.24,.045,.045),ink,.022);brows.append(o)
smile=tube('Talking smile',[(.145*math.cos(t),-.495,1.69+.13*math.sin(t)) for t in [math.pi+i*math.pi/24 for i in range(25)]],.027,ink)
# Place mouth origin at its center so Talk changes its shape without moving the face.
smile_center=Vector((0,-.495,1.625))
for vertex in smile.data.vertices: vertex.co-=smile_center
smile.location=smile_center
# Mesh transform animation exported as grouped named NLA clips, shared across objects.
animated=[root,*limbs,*brows,smile]
base={o:(o.location.copy(),o.rotation_euler.copy(),o.scale.copy()) for o in animated}
states=['Idle','Listen','Think','Read','Talk','Approval','Done','Error','Comic']
for state in states:
 for o in animated:
  loc,rot,scale=base[o];o.location=loc;o.rotation_euler=rot;o.scale=scale
  o.animation_data_create();o.animation_data.action=None
  for f in [1,16,31,46,61]:
   phase=(f-1)/60*math.tau;s=math.sin(phase)
   o.location=loc;o.rotation_euler=rot;o.scale=scale
   if o==root:
    o.location.z+=.025*(1-math.cos(phase));o.rotation_euler[1]=.018*s
    if state=='Listen':o.rotation_euler[1]=-.10+.025*s
    if state in ['Think','Read']:o.rotation_euler[0]=.05;o.rotation_euler[2]=.03*s
    if state=='Approval':o.rotation_euler[1]=.025*s
    if state=='Done':o.location.z+=.12*max(0,s);o.rotation_euler[2]=.07*s
    if state in ['Error','Comic']:o.rotation_euler[2]=.06*s
   if o in limbs:
    side=-1 if o==limbs[0] else 1
    o.rotation_euler[1]=side*.06*s
    if state in ['Listen','Approval']:o.rotation_euler[1]=side*(-.45+.08*s)
    if state=='Talk':o.rotation_euler[1]=side*(-.2+.18*s)
    if state=='Done':o.rotation_euler[1]=side*(-.9+.17*s)
    if state in ['Think','Read'] and side==1:o.rotation_euler[1]=-.95+.06*s
   if o in brows:
    side=-1 if o==brows[0] else 1
    if state in ['Think','Read']:o.rotation_euler[1]=side*.18
    if state in ['Comic','Error']:o.rotation_euler[1]=-side*.30
    if state=='Done':o.location.z+=.06
   if o==smile and state=='Talk':o.scale.z=.8+.8*abs(s)
   if o==smile and state=='Comic':o.rotation_euler[1]=math.pi;o.scale*=.9
   for path in ['location','rotation_euler','scale']:o.keyframe_insert(data_path=path,frame=f)
  action=o.animation_data.action;action.name=state+'_'+o.name
  track=o.animation_data.nla_tracks.new();track.name=state;strip=track.strips.new(state,1,action);strip.action_frame_start=1;strip.action_frame_end=61
  o.animation_data.action=None
for o in animated:
 o.location,o.rotation_euler,o.scale=base[o]
# Studio used for QA only; never exported to GLB.
scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=61;scene.render.fps=30
world=scene.world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.64,.54,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65
for name,loc,power,size in [('Softbox',(0,-5,7),700,5),('Rim',(4,2,5),500,4),('Fill',(-4,-2,3),220,4)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,1.6))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(3,-10,4.1));camera=bpy.context.object;camera.name='QA Camera';camera.rotation_euler=(Vector((0,0,1.65))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=4.2;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.film_transparent=True
scene.view_settings.view_transform='AgX'
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
 if o==root or o.parent: o.select_set(True)
# Keep neutral base transforms; every clip retains constant reset channels.
for o in animated:
 for track in o.animation_data.nla_tracks: track.mute=track.name!='Idle'
scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=str(OUT/'paoween.glb'),use_selection=True,export_format='GLB',export_animations=True,export_animation_mode='NLA_TRACKS',export_nla_strips=True,export_optimize_animation_keep_anim_object=True,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paoween.blend'))
# Render friendly static pose with all NLA tracks muted.
for o in animated:
 for t in o.animation_data.nla_tracks:t.mute=True
 o.location,o.rotation_euler,o.scale=base[o]
scene.render.filepath=str(OUT/'paoween-preview.png');bpy.ops.render.render(write_still=True)
for state in ['Talk','Comic']:
 for o in animated:
  for track in o.animation_data.nla_tracks: track.mute=track.name!=state
 scene.frame_set(16);scene.render.filepath=str(OUT/('qa-'+state.lower()+'.png'));bpy.ops.render.render(write_still=True)
(OUT/'manifest.json').write_text(json.dumps({'name':'น้องเป๋าวีน','blender':bpy.app.version_string,'clips':states,'source':'tools/build_paoween.py','design':'User-provided Paoween cartoon references; procedural original 3D interpretation','notes':'Fictional blank cards and notes. Transform animated meshes; no external textures.'},ensure_ascii=False,indent=2))
print('PAOWEEN_EXPORT_OK',str(OUT))
