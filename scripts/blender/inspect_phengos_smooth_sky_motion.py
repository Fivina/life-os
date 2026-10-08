"""Decode actual v17 delivery film and check its metadata/nonblank checkpoints."""
import bpy
import json
from pathlib import Path
import shutil

OUT = 'E:/LifeOS-Art/phengos'
scene = bpy.data.scenes.new('Phengos_v17_Decoded_Export_QA')
bpy.context.window.scene = scene
scene.render.fps = 60
editor = scene.sequence_editor_create()
movie = editor.strips.new_movie('v17 actual film',
    filepath=OUT+'/environment-v17-60.mp4', channel=1, frame_start=1)
assert abs(movie.fps-60) < 0.01
assert movie.frame_final_duration == 511
scene.frame_end = movie.frame_final_duration
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.render.use_compositing = False
scene.render.use_sequencer = True
frames = [1, 121, 217, 289, 301, 361, 421, 511]
for frame in frames:
    scene.frame_set(frame)
    scene.render.filepath = OUT+'/smooth-sky-v17-decoded-'+str(frame)+'.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    assert list(image.size) == [1280,720]
    pixels = image.pixels[:]
    assert sum(sum(pixels[i:i+3]) > .05 for i in range(0,len(pixels),128)) > 20
    bpy.data.images.remove(image)
    if frame == 1:
        shutil.copyfile(scene.render.filepath, OUT+'/opening-poster-v17.png')
result = {'fps':movie.fps, 'frames':movie.frame_final_duration,
          'seconds':movie.frame_final_duration/movie.fps,
          'decoded_frames':frames, 'dimensions':[1280,720],
          'poster':OUT+'/opening-poster-v17.png'}
Path(OUT+'/smooth-sky-v17-film-qa.json').write_text(json.dumps(result, indent=2))
print('PHENGOS_V17_MOVIE_QA_PASS', json.dumps(result), flush=True)
