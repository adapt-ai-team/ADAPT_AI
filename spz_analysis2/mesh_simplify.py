import rhino3dm
import os

try:
    import pymeshlab
except ImportError:
    raise ImportError("pymeshlab is not installed. Install it with 'pip install pymeshlab'.")

# Input and output paths
input_3dm = r"D:\ADAPT_AI\spz_analysis2\merged_model (3).3dm"  # <- Replace with your 3DM file path
output_obj = r"D:\ADAPT_AI\spz_analysis2\merged_model (3)_allmeshes_with_simplified.obj"
output_glb = r"D:\ADAPT_AI\spz_analysis2\merged_model (3)_allmeshes_with_simplified.glb"
target_faces = 2500

# Load .3dm file and get the last mesh
model = rhino3dm.File3dm.Read(input_3dm)  # type: ignore  # rhino3dm uses dynamic bindings
# Find all meshes
all_meshes = [obj.Geometry for obj in model.Objects if type(obj.Geometry).__name__ == "Mesh"]

if not all_meshes:
    raise RuntimeError("No mesh found in .3dm file")

# Print stats about all meshes
print("Mesh face counts in the .3dm file:")
for idx, m in enumerate(all_meshes):
    print(f"  Mesh {idx+1}: {len(m.Faces)} faces")

mesh = all_meshes[-1]  # Simplify only the last mesh
original_face_count = len(mesh.Faces)
# More aggressive simplification: target 2% of original, but at least 200 faces, at most 500
simplification_ratio = 0.04
calculated_target = max(200, min(1500, int(original_face_count * simplification_ratio)))
target_faces = calculated_target
print(f"\nSimplifying the last mesh (Mesh {len(all_meshes)}) with {original_face_count} faces.")
print(f"Target face count for simplification: {target_faces}")

# Extract vertices and faces
vertices = [(v.X, v.Y, v.Z) for v in mesh.Vertices]
faces = []

for f in mesh.Faces:
    if len(f) == 4:
        faces.append([f[0], f[1], f[2]])
        faces.append([f[0], f[2], f[3]])
    elif len(f) == 3:
        faces.append([f[0], f[1], f[2]])

# Write temporary .obj
temp_obj = "temp.obj"
with open(temp_obj, "w") as f:
    for v in vertices:
        f.write(f"v {v[0]} {v[1]} {v[2]}\n")
    for face in faces:
        f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")  # OBJ is 1-indexed

# Load with PyMeshLab and simplify, clean, and smooth
ms = pymeshlab.MeshSet()  # type: ignore
ms.load_new_mesh(temp_obj)

# First pass: moderate reduction
ms.meshing_decimation_quadric_edge_collapse(
    targetfacenum=20000,
    preservenormal=True,
    preserveboundary=True,
    preservetopology=True,
    planarquadric=True
)
# Second pass: aggressive reduction
ms.meshing_decimation_quadric_edge_collapse(
    targetfacenum=10000,
    preservenormal=True,
    preserveboundary=True,
    preservetopology=True,
    planarquadric=True
)
print("Decimation complete.")

# Clean mesh: remove duplicate faces, unreferenced vertices
ms.meshing_remove_duplicate_faces()
ms.meshing_remove_unreferenced_vertices()
# Try to remove isolated pieces if available
if hasattr(ms, 'meshing_remove_isolated_pieces'):
    ms.meshing_remove_isolated_pieces(mincomponentsize=10)
print("Cleaning complete.")

# Smooth mesh (try Taubin, then Laplacian if available)
smoothed = False
if hasattr(ms, 'meshing_taubin_smooth'):
    ms.meshing_taubin_smooth()
    smoothed = True
if hasattr(ms, 'meshing_laplacian_smooth'):
    ms.meshing_laplacian_smooth(iterations=2)
    smoothed = True
if smoothed:
    print("Smoothing complete.")
else:
    print("No smoothing filter available.")

# Recompute normals for better shading
if hasattr(ms, 'compute_normals_for_faces'):
    ms.compute_normals_for_faces()
    print("Normals recomputed.")

# Export simplified mesh to temp OBJ
simplified_obj = "temp_lastmesh_simplified.obj"
ms.save_current_mesh(simplified_obj)

# Read back the simplified mesh for merging
with open(simplified_obj, "r") as f:
    lines = f.readlines()

# Prepare OBJ parts
obj_parts = []
vertex_offset = 0
for idx, m in enumerate(all_meshes):
    if idx == len(all_meshes) - 1:
        part = [f"o mesh_{idx+1}_simplified\n"]
        v_count = 0
        for line in lines:
            if line.startswith("v "):
                part.append(line)
                v_count += 1
        for line in lines:
            if line.startswith("f "):
                # Only use the vertex index before any '/' (OBJ can be v/vt/vn)
                nums = [int(n.split('/')[0]) for n in line.strip().split()[1:]]
                nums = [n + vertex_offset for n in nums]
                part.append(f"f {' '.join(str(n) for n in nums)}\n")
        obj_parts.extend(part)
        vertex_offset += v_count
        # Print comparison
        simplified_face_count = sum(1 for line in lines if line.startswith("f "))
        print(f"Simplified mesh face count: {simplified_face_count}")
        print(f"Reduction: {original_face_count} -> {simplified_face_count} faces (target: {target_faces})")
    else:
        vertices = [(v.X, v.Y, v.Z) for v in m.Vertices]
        faces = []
        for f in m.Faces:
            if len(f) == 4:
                faces.append([f[0], f[1], f[2]])
                faces.append([f[0], f[2], f[3]])
            elif len(f) == 3:
                faces.append([f[0], f[1], f[2]])
        part = [f"o mesh_{idx+1}\n"]
        for v in vertices:
            part.append(f"v {v[0]} {v[1]} {v[2]}\n")
        for face in faces:
            part.append(f"f {face[0]+1+vertex_offset} {face[1]+1+vertex_offset} {face[2]+1+vertex_offset}\n")
        obj_parts.extend(part)
        vertex_offset += len(vertices)

# Write combined OBJ
with open(output_obj, "w") as f:
    f.writelines(obj_parts)
print(f"Combined OBJ with all original meshes and the simplified last mesh saved as {output_obj}")

# Optionally convert to GLB
try:
    import trimesh
    mesh = trimesh.load(output_obj)
    mesh.export(output_glb)
    print(f"Converted mesh saved as {output_glb}")
except ImportError:
    print("trimesh is not installed. To convert OBJ to GLB, run:\n  pip install trimesh\nThen use:\n  import trimesh; mesh = trimesh.load('your.obj'); mesh.export('your.glb')")
