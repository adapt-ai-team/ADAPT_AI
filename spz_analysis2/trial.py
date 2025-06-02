import trimesh
import numpy as np

# Load the model
glb_path = "D:\\spz_pipeline\\pipeline_outputs\\example_image.glb"
scene = trimesh.load(glb_path)

# Check bounding box again
bounding_box = scene.bounds
width_x = bounding_box[1, 0] - bounding_box[0, 0]

# If width is too small, apply scaling
if width_x < 1.0:  # Assume the model should be at least 1 meter wide
    scale_factor = 1.0 / width_x  # Scale up so width is ~1 meter
    scale_matrix = np.eye(4) * scale_factor
    scale_matrix[3, 3] = 1  # Preserve homogeneous transformation
    scene.apply_transform(scale_matrix)
    print(f"✅ Applied scaling correction (Factor: {scale_factor:.2f})")

# Save the corrected model
fixed_glb_path = "D:\\spz_pipeline\\pipeline_outputs\\example_image_fixed.glb"
scene.export(fixed_glb_path)
print(f"✅ Saved fixed model as {fixed_glb_path}")
