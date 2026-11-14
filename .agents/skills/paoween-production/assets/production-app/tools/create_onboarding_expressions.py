"""Create native Blender mesh-action expressions for the onboarding Paoween preview."""
import bpy, math, json
from pathlib import Path

here = Path(__file__).resolve().parent
assets = here.parent / 'assets'
source = assets / 'paoween-source.blend'
blend_out = assets / 'paoween-onboarding.blend'
glb_out = assets / 'paoween-onboarding.glb'
qa_dir = assets / 'qa'
qa_dir.mkdir(exist_ok=True)

# Open the authored Blender scene so edits are made to its actual facial meshes.
bpy.ops.wm.open_mainfile(filepath=str(source))
root = bpy.data.objects['Paoween']
limbs = [bpy.data.objects['LeftArm'], bpy.data.objects['RightArm']]
brows = [bpy.data.objects['Brow -1'], bpy.data.objects['Brow 1']]
smile = bpy.data.objects['Talking smile']
animated = [*brows, smile]
base = {o: (o.location.copy(), o.rotation_euler.copy(), o.scale.copy()) for o in animated}

def add_clip(name):
    for o in animated:
        loc, rot, scale = base[o]
        anim = o.animation_data_create()
        anim.action = None
        action = bpy.data.actions.new(name + '_' + o.name.replace(' ', '_'))
        anim.action = action
        for frame in [1, 16, 31, 46, 61]:
            phase = (frame - 1) / 60 * math.tau
            s = math.sin(phase)
            o.location = loc
            o.rotation_euler = rot
            o.scale = scale
            if o in brows:
                side = -1 if o == brows[0] else 1
                furrow = .58 if name == 'SlipAngry' else .28
                o.rotation_euler[1] = -side * (furrow + .018 * s)
            elif o == smile:
                if name == 'SlipAngry':
                    # Flip the smile mesh to a frown in the authored Blender model.
                    o.rotation_euler[1] = math.pi
                else:
                    # Compress the mouth mesh vertically into a focused line.
                    o.scale.z = scale.z * .24
            for channel in ('location', 'rotation_euler', 'scale'):
                o.keyframe_insert(data_path=channel, frame=frame, group=name)
        action = anim.action
        action.name = name + '_' + o.name.replace(' ', '_')
        track = anim.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 1, action)
        strip.action_frame_start = 1
        strip.action_frame_end = 61
        anim.action = None

add_clip('SlipAngry')
add_clip('ReadyDetermined')
for o in animated:
    o.location, o.rotation_euler, o.scale = base[o]
    for track in o.animation_data.nla_tracks:
        track.mute = track.name != 'Idle'
bpy.context.scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o == root or o.parent:
        o.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.ops.export_scene.gltf(filepath=str(glb_out), use_selection=True,
    export_format='GLB', export_animations=True,
    export_animation_mode='NLA_TRACKS', export_nla_strips=True,
    export_optimize_animation_keep_anim_object=True,
    export_cameras=False, export_lights=False)

for clip_name in ['SlipAngry', 'ReadyDetermined']:
    for o in animated:
        for track in o.animation_data.nla_tracks:
            track.mute = track.name != clip_name
    bpy.context.scene.frame_set(16)
    bpy.context.scene.render.filepath = str(qa_dir / (clip_name + '.png'))
    bpy.ops.render.render(write_still=True)

(assets / 'paoween-onboarding.json').write_text(json.dumps({
    'source': 'paoween-onboarding.blend',
    'model': 'paoween-onboarding.glb',
    'expressions': ['SlipAngry', 'ReadyDetermined'],
    'description': 'Native Blender animation of brow and mouth meshes for the slip request and ready states.'
}, ensure_ascii=False, indent=2))
print('ONBOARDING_EXPRESSIONS_EXPORTED', glb_out)
