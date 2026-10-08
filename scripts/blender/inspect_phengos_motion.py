"""Decode exported draft frames through Blender VSE, not the source 3D scene."""
import bpy
import json
import sys

flight='--flight' in sys.argv
erase='--erase' in sys.argv
cinematic='--cinematic' in sys.argv
prefix='cinematic-v15' if cinematic else 'blue-eraser-v14' if erase else 'character-flight-v13' if flight else 'luminous-horizon-v12'
frames=(1,25,35,39,41,49,57,61,73,91,103) if erase or cinematic else (1,13,37,61,73,91,103) if flight else (1,19,37,61,73,103)
scene = bpy.data.scenes.new(prefix+'_Export_QA')
bpy.context.window.scene = scene
scene.render.fps = 12
editor = scene.sequence_editor_create()
movie = editor.strips.new_movie(
    name='Exported '+prefix+' timing draft',
    filepath='E:/LifeOS-Art/phengos/'+prefix+'-motion-draft.mp4',
    channel=1, frame_start=1,
)
assert abs(movie.fps - 12) < 0.01
assert movie.frame_final_duration == 103
scene.frame_end = movie.frame_final_duration
scene.render.resolution_x = 480
scene.render.resolution_y = 270
scene.render.resolution_percentage = 100
assert 'PNG' in [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
scene.render.image_settings.file_format = 'PNG'
# Blender 5.2's dynamic OCIO menu reports only NONE through RNA;
# Standard was separately verified against this runtime before authoring.
scene.view_settings.view_transform = 'Standard'
scene.render.use_compositing = False
scene.render.use_sequencer = True
for frame in frames:
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/'+prefix+'-video-qa-' + str(frame) + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    assert list(image.size) == [480, 270]
    pixels = image.pixels[:]
    lit_samples = sum(pixels[i] + pixels[i+1] + pixels[i+2] > 0.05
                      for i in range(0, len(pixels), 64))
    assert lit_samples > 10, 'Exported frame is unexpectedly blank'
    bpy.data.images.remove(image)
print('PHENGOS_EXPORTED_VIDEO_QA_PASS ' + json.dumps(
    {'fps':movie.fps, 'frames':movie.frame_final_duration,
     'seconds':movie.frame_final_duration/movie.fps, 'decoded_frames':list(frames)}))
