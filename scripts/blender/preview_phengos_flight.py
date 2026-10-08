"""Check growth, geometric sunrise occlusion and visible flight before motion export."""
import bpy
import sys

scene=bpy.data.scenes['Phengos_Character_Flight_v13']
bpy.context.window.scene=scene
assert 'PNG' in [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
scene.render.image_settings.file_format='PNG'
scene.render.use_persistent_data=True
if '--motion' in sys.argv:
    for owner,key,value in (
        (scene.render.image_settings,'media_type','VIDEO'),
        (scene.render.image_settings,'file_format','FFMPEG'),
        (scene.render.ffmpeg,'format','MPEG4'),
        (scene.render.ffmpeg,'codec','H264'),
    ):
        assert value in [i.identifier for i in owner.bl_rna.properties[key].enum_items]
        setattr(owner,key,value)
    scene.render.resolution_percentage=25
    scene.cycles.samples=16
    scene.cycles.adaptive_threshold=0.03
    scene.cycles.use_denoising=True
    # Baked 60fps motion sampled every fifth frame preserves the intended pace.
    scene.frame_step=5
    scene.render.fps=12
    scene.render.filepath='E:/LifeOS-Art/phengos/character-flight-v13-motion-draft.mp4'
    bpy.ops.render.render(animation=True,scene=scene.name)
    print('PHENGOS_FLIGHT_MOTION_COMPLETE: 480x270, 12fps timing draft')
    raise SystemExit(0)
cases=[(61,'early'),(181,'growing'),(301,'handoff'),(391,'flight'),(511,'idle')]
for frame,label in cases:
    scene.frame_set(frame)
    full='--selected' in sys.argv and label in ('early','growing','flight')
    scene.cycles.samples=192 if full else 48
    scene.cycles.adaptive_threshold=0.006 if full else 0.015
    scene.cycles.use_denoising=True
    scene.render.resolution_percentage=100 if full else 50
    scene.render.filepath='E:/LifeOS-Art/phengos/character-flight-v13-'+label+'.png'
    bpy.ops.render.render(write_still=True,scene=scene.name)
print('PHENGOS_FLIGHT_PREVIEW_COMPLETE')
