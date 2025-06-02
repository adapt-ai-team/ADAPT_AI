
import bpy
import math

# Delete default cube
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import GLB
bpy.ops.import_scene.gltf(filepath=r'D:\spz_pipeline\pipeline_outputs\solar_radiation_example_image.glb')

# Select all objects
bpy.ops.object.select_all(action='SELECT')

# Rotate 90 degrees around X axis to swap Y and Z
bpy.context.active_object.rotation_euler = (math.pi/2, 0, 0)
bpy.ops.object.transform_apply(rotation=True)

# Export fixed GLB
bpy.ops.export_scene.gltf(filepath=r'D:\spz_pipeline\pipeline_outputs\fixed_solar_radiation_example_image.glb')
