"""
import os
import json
import numpy as np
import rhino3dm
import matplotlib.pyplot as plt
from ladybug.epw import EPW
from ladybug.sunpath import Sunpath
from pygltflib import GLTF2, Buffer, Accessor, BufferView, Mesh, Asset, Primitive, Material, Scene, Node

# 📂 Define file paths
PIPELINE_OUTPUT_DIR = r"D:\spz_pipeline\pipeline_outputs"
EPW_FILE_PATH = os.path.join(PIPELINE_OUTPUT_DIR, "newyork.epw")
RESULTS_FILE = os.path.join(PIPELINE_OUTPUT_DIR, "solar_results_example_image.json")
GLB_FILE_PATH = os.path.join(PIPELINE_OUTPUT_DIR, "example_image.glb")  # Ensure this is correct
SOLAR_OUTPUT_GLB = os.path.join(PIPELINE_OUTPUT_DIR, "solar_radiation_example_image.glb")

# ✅ Load EPW weather data
def load_epw(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ EPW file not found: {file_path}")
    return EPW(file_path)

# ☀️ Generate sun vectors
def get_sun_vectors(epw):
    sunpath = Sunpath.from_location(epw.location)
    return [sunpath.calculate_sun(6, 21, h).sun_vector for h in range(8, 15, 1)]

# 📂 Extract surfaces from GLB file
def extract_surfaces_from_glb(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ GLB file not found: {file_path}")

    # Load the GLB file
    gltf = GLTF2().load_binary(file_path)

    # Ensure GLB file has meshes
    if not gltf.meshes or len(gltf.meshes) == 0:
        raise ValueError("❌ No meshes found in the GLB file.")

    binary_blob = gltf.binary_blob()
    surfaces = []
    for mesh_index, mesh in enumerate(gltf.meshes):
        print(f"📌 Processing mesh {mesh_index + 1}/{len(gltf.meshes)}")
        for prim_index, primitive in enumerate(mesh.primitives):
            print(f"   🔹 Processing primitive {prim_index + 1}/{len(mesh.primitives)}")
            if not hasattr(primitive.attributes, "POSITION"):
                print(f"⚠️ Warning: No POSITION attribute in primitive {prim_index}, skipping.")
                continue
            pos_accessor_index = primitive.attributes.POSITION
            pos_accessor = gltf.accessors[pos_accessor_index]
            buffer_view = gltf.bufferViews[pos_accessor.bufferView]
            vertex_start = buffer_view.byteOffset
            vertex_end = vertex_start + buffer_view.byteLength
            vertices = np.frombuffer(binary_blob[vertex_start:vertex_end], dtype=np.float32).reshape(-1, 3)
            print(f"   ✅ Extracted {len(vertices)} vertices for primitive {prim_index}.")
            if primitive.indices is None:
                print(f"⚠️ Warning: No face index data found in primitive {prim_index}. Creating default faces.")
                faces = np.array([], dtype=np.uint32).reshape(0, 3)
            else:
                index_accessor = gltf.accessors[primitive.indices]
                index_buffer_view = gltf.bufferViews[index_accessor.bufferView]
                index_start = index_buffer_view.byteOffset
                index_end = index_start + index_buffer_view.byteLength
                faces = np.frombuffer(binary_blob[index_start:index_end], dtype=np.uint32).reshape(-1, 3)
                print(f"   ✅ Extracted {len(faces)} faces for primitive {prim_index}.")
            rhino_mesh = rhino3dm.Mesh()
            for v in vertices:
                rhino_mesh.Vertices.Add(v[0], v[1], v[2])
            for f in faces:
                if len(f) == 3:
                    rhino_mesh.Faces.AddFace(int(f[0]), int(f[1]), int(f[2]))
            surfaces.append(rhino_mesh)
    if not surfaces:
        raise ValueError("❌ No valid geometry extracted from the GLB file.")
    print(f"✅ Final: Extracted {len(surfaces)} mesh surfaces.")
    return surfaces

# 🔆 Compute Solar Radiation
def compute_solar_radiation(epw, surfaces):
    sun_vectors = get_sun_vectors(epw)
    all_radiation_values = []
    for i, surface in enumerate(surfaces):
        normals = [surface.Normals[j] for j in range(len(surface.Vertices))] if len(surface.Normals) > 0 else [rhino3dm.Vector3d(0, 0, 1)]
        print(f"   🔹 Processing surface {i + 1}/{len(surfaces)} with {len(normals)} normals.")
        solar_exposure = [
            max(0, np.dot([normals[0].X, normals[0].Y, normals[0].Z], [sun_vec.x, sun_vec.y, sun_vec.z]))
            for sun_vec in sun_vectors
        ]
        direct_radiation = [epw.direct_normal_radiation[hour % 24] for hour in range(6, 18)]
        max_radiation = max(direct_radiation) if max(direct_radiation) > 0 else 1
        normalized_exposure = [(solar / max_radiation) * rad for solar, rad in zip(solar_exposure, direct_radiation)]
        all_radiation_values.append(normalized_exposure)
    min_value = min(map(min, all_radiation_values))
    max_value = max(map(max, all_radiation_values))
    normalized_radiation_values = [[(value - min_value) / (max_value - min_value) if max_value != min_value else 1.0 for value in radiation] for radiation in all_radiation_values]
    with open(RESULTS_FILE, "w") as f:
        json.dump(normalized_radiation_values, f, indent=4)
    save_mesh_to_glb(surfaces, normalized_radiation_values, SOLAR_OUTPUT_GLB)
    print(f"✅ solar_radiation.glb saved to {SOLAR_OUTPUT_GLB}")

# 🎭 Save a Mesh with Solar Radiation Data to GLB
def save_mesh_to_glb(meshes, radiation_values, filename):
    gltf = GLTF2(asset=Asset(version="2.0"))
    all_vertices, all_faces = [], []
    vertex_offset = 0
    for mesh in meshes:
        vertices = np.array([[v.X, v.Y, v.Z] for v in mesh.Vertices], dtype=np.float32)
        faces = np.array([[f[0], f[1], f[2]] for f in mesh.Faces], dtype=np.uint32)
        all_vertices.append(vertices)
        all_faces.append(faces + vertex_offset)
        vertex_offset += len(vertices)
    final_vertices = np.vstack(all_vertices)
    final_faces = np.vstack(all_faces)
    vertex_buffer = Buffer(uri=None, byteLength=final_vertices.nbytes)
    face_buffer = Buffer(uri=None, byteLength=final_faces.nbytes)
    gltf.buffers.extend([vertex_buffer, face_buffer])
    buffer_view_vertices = BufferView(buffer=0, byteOffset=0, byteLength=final_vertices.nbytes, target=34962)
    buffer_view_faces = BufferView(buffer=1, byteOffset=0, byteLength=final_faces.nbytes, target=34963)
    gltf.bufferViews.extend([buffer_view_vertices, buffer_view_faces])
    accessor_vertices = Accessor(bufferView=0, byteOffset=0, componentType=5126, count=len(final_vertices), type="VEC3")
    accessor_faces = Accessor(bufferView=1, byteOffset=0, componentType=5125, count=len(final_faces) * 3, type="SCALAR")
    gltf.accessors.extend([accessor_vertices, accessor_faces])
    primitive = Primitive(attributes={"POSITION": 0}, indices=1)
    mesh = Mesh(primitives=[primitive])
    gltf.meshes.append(mesh)
    node = Node(mesh=0)
    gltf.nodes.append(node)
    scene = Scene(nodes=[0])
    gltf.scenes.append(scene)
    gltf.scene = 0
    gltf.set_binary_blob(final_vertices.tobytes() + final_faces.tobytes())
    gltf.save_binary(filename)
    print(f"✅ Successfully saved {filename} as a proper GLB file.")

# 🚀 Run Analysis
if __name__ == "__main__":
    try:
        epw_data = load_epw(EPW_FILE_PATH)
        surfaces = extract_surfaces_from_glb(GLB_FILE_PATH)
        compute_solar_radiation(epw_data, surfaces)
    except Exception as e:
        print(f"❌ Error: {e}")
"""

import os
import json
import numpy as np
import rhino3dm
import matplotlib.pyplot as plt
from matplotlib import cm
from ladybug.epw import EPW
from ladybug.sunpath import Sunpath
from pygltflib import GLTF2, Scene, Node, Mesh, Buffer, BufferView, Accessor, Asset, Primitive, Material

# 📂 Define file paths (Updated)
PIPELINE_FOLDER = r"D:\spz_pipeline\pipeline_outputs"

EPW_FILE_PATH = os.path.join(PIPELINE_FOLDER, "newyork.epw")  # Assuming EPW file is here
THREEDM_FILE_PATH = os.path.join(PIPELINE_FOLDER, "merged_model.3dm")  # ✅ Updated input file
RESULTS_FILE = os.path.join(PIPELINE_FOLDER, "solar_results_example_image.json")  # ✅ Updated JSON output
GLB_FILE_PATH = os.path.join(PIPELINE_FOLDER, "solar_radiation_example_image.glb")  # ✅ Corrected output file

# ✅ Load EPW weather data
def load_epw(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ EPW file not found: {file_path}")
    return EPW(file_path)

# ☀️ Generate sun vectors
def get_sun_vectors(epw):
    sunpath = Sunpath.from_location(epw.location)
    return [sunpath.calculate_sun(6, 21, h).sun_vector for h in range(8, 15, 1)]

# 🏢 Extract surfaces from 3DM file
def extract_surfaces_from_3dm(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ 3DM file not found: {file_path}")

    model = rhino3dm.File3dm.Read(file_path)
    return [obj.Geometry for obj in model.Objects if isinstance(obj.Geometry, rhino3dm.Mesh)]

# 🔆 Compute Solar Radiation
def compute_solar_radiation(epw, surfaces):
    sun_vectors = get_sun_vectors(epw)
    all_radiation_values = []
    
    for i, surface in enumerate(surfaces):
        normals = [surface.Normals[j] for j in range(len(surface.Vertices))] if len(surface.Normals) > 0 else [rhino3dm.Vector3d(0, 0, 1)]

        solar_exposure = [
            max(0, np.dot([normals[0].X, normals[0].Y, normals[0].Z], [sun_vec.x, sun_vec.y, sun_vec.z]))
            for sun_vec in sun_vectors
        ]
        direct_radiation = [epw.direct_normal_radiation[hour % 24] for hour in range(6, 18)]
        max_radiation = max(direct_radiation) if max(direct_radiation) > 0 else 1

        normalized_exposure = [(solar / max_radiation) * rad for solar, rad in zip(solar_exposure, direct_radiation)]
        all_radiation_values.append(normalized_exposure)

    min_value = min(map(min, all_radiation_values))
    max_value = max(map(max, all_radiation_values))

    normalized_radiation_values = [[(value - min_value) / (max_value - min_value) if max_value != min_value else 1.0 for value in radiation] for radiation in all_radiation_values]

    with open(RESULTS_FILE, "w") as f:
        json.dump(normalized_radiation_values, f, indent=4)

    save_multiple_meshes_to_glb(surfaces, normalized_radiation_values, GLB_FILE_PATH)

# 🎭 Save a Mesh with Color Data to GLB
def save_multiple_meshes_to_glb(surfaces, radiation_values, filename):
    all_vertices, all_faces, all_colors = [], [], []
    vertex_offset = 0
    colormap = plt.colormaps.get_cmap('viridis')

    for i, surface in enumerate(surfaces):
        vertices = np.array([[pt.X, pt.Y, pt.Z] for pt in surface.Vertices], dtype=np.float32)
        faces = np.array([[f[0], f[1], f[2]] for f in surface.Faces], dtype=np.uint32) + vertex_offset
        vertex_offset += len(vertices)

        # Calculate face-based colors (instead of per-vertex)
        face_colors = np.zeros((len(faces), 4), dtype=np.float32)
        for j, face in enumerate(faces):
            face_avg_radiation = np.mean([radiation_values[i][v % len(radiation_values[i])] for v in face])  # Compute avg radiation for face
            mapped_color = colormap(face_avg_radiation)  # Map to colormap
            face_colors[j] = mapped_color  # Assign color

        all_vertices.append(vertices)
        all_faces.append(faces)
        all_colors.append(face_colors)

    save_mesh_to_glb(np.vstack(all_vertices), np.vstack(all_faces), np.vstack(all_colors), filename)

# 🎭 Save a Mesh to GLB
def save_mesh_to_glb(vertices, faces, colors, filename):
    gltf = GLTF2(asset=Asset(version="2.0"))
    buffer_data = vertices.tobytes() + faces.tobytes() + colors.tobytes()
    
    gltf.buffers.append(Buffer(uri=None, byteLength=len(buffer_data)))

    buffer_views = [
        BufferView(buffer=0, byteOffset=0, byteLength=vertices.nbytes, target=34962),
        BufferView(buffer=0, byteOffset=vertices.nbytes, byteLength=faces.nbytes, target=34963),
        BufferView(buffer=0, byteOffset=vertices.nbytes + faces.nbytes, byteLength=colors.nbytes, target=34962),
    ]
    
    gltf.bufferViews.extend(buffer_views)

    gltf.accessors.extend([
        Accessor(bufferView=0, componentType=5126, count=len(vertices), type="VEC3"),
        Accessor(bufferView=1, componentType=5125, count=len(faces) * 3, type="SCALAR"),
        Accessor(bufferView=2, componentType=5126, count=len(colors), type="VEC4"),
    ])

    gltf.materials.append(Material(
        pbrMetallicRoughness={"baseColorFactor": [1.0, 1.0, 1.0, 1.0]},
        doubleSided=True
    ))

    gltf.meshes.append(Mesh(primitives=[Primitive(attributes={"POSITION": 0, "COLOR_0": 2}, indices=1, material=0)]))
    gltf.nodes.append(Node(mesh=0))
    gltf.scenes.append(Scene(nodes=[0]))
    gltf.scene = 0

    gltf.set_binary_blob(buffer_data)
    gltf.save_binary(filename)

    print(f"✅ Successfully saved `{filename}`")

# 🚀 Run Analysis
if __name__ == "__main__":
    try:
        epw_data = load_epw(EPW_FILE_PATH)
        surfaces = extract_surfaces_from_3dm(THREEDM_FILE_PATH)
        compute_solar_radiation(epw_data, surfaces)
    except Exception as e:
        print(f"❌ Error: {e}")
