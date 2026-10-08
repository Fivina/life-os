"""Render readable staging/lighting checks, then a cost-bounded timing draft."""
import bpy
import sys

cinematic='--cinematic' in sys.argv
prefix='cinematic-v15' if cinematic else 'blue-eraser-v14'
scene=bpy.data.scenes['Phengos_Cinematic_Hierarchy_v15' if cinematic else 'Phengos_Blue_Eraser_v14']
bpy.context.window.scene=scene
scene.render.use_persistent_data=True
scene.cycles.use_denoising=True
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
    scene.cycles.samples=24
    scene.cycles.adaptive_threshold=0.025
    scene.frame_step=5
    scene.render.fps=12
    scene.render.filepath='E:/LifeOS-Art/phengos/'+prefix+'-motion-draft.mp4'
    bpy.ops.render.render(animation=True,scene=scene.name)
    print('PHENGOS_MOTION_COMPLETE '+prefix)
else:
    assert 'PNG' in [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
    scene.render.image_settings.file_format='PNG'
    scene.render.resolution_percentage=50
    scene.cycles.samples=64
    scene.cycles.adaptive_threshold=0.012
    cases=[(1,'opening'),(169,'grown'),(193,'erase-S'),(241,'erase-LIFE'),(301,'handoff'),(391,'flight'),(511,'idle')]
    if '--hero' in sys.argv:
        cases=[(1,'opening')]
        scene.render.resolution_percentage=100
        scene.cycles.samples=128
        scene.cycles.adaptive_threshold=0.006
    for frame,label in cases:
        scene.frame_set(frame)
        scene.render.filepath='E:/LifeOS-Art/phengos/'+prefix+'-'+label+'.png'
        bpy.ops.render.render(write_still=True,scene=scene.name)
    print('PHENGOS_STILLS_COMPLETE '+prefix)
