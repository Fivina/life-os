"""Inspect decoded review-film frames at native dimensions."""
import bpy
import json

scene = bpy.data.scenes.new('Phengos_v16_Decoded_Export_QA')
bpy.context.window.scene = scene
scene.render.fps = 30
editor = scene.sequence_editor_create()
movie = editor.strips.new_movie('v16 actual film',
    filepath='E:/LifeOS-Art/phengos/reference-v16-motion.mp4', channel=1, frame_start=1)
assert abs(movie.fps-30) < 0.01
assert movie.frame_final_duration == 256
scene.frame_end = movie.frame_final_duration
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.render.use_compositing = False
scene.render.use_sequencer = True
frames = [1, 61, 109, 145, 151, 181, 211, 256]
for frame in frames:
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/reference-v16-decoded-'+str(frame)+'.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    assert list(image.size) == [1280,720]
    pixels = image.pixels[:]
    assert sum(sum(pixels[i:i+3]) > .05 for i in range(0,len(pixels),128)) > 20
    bpy.data.images.remove(image)
print('PHENGOS_REFERENCE_MOVIE_QA_PASS', json.dumps({'fps':movie.fps,
    'frames':movie.frame_final_duration, 'seconds':movie.frame_final_duration/movie.fps,
    'decoded_frames':frames, 'dimensions':[1280,720]}))
