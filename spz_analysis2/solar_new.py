import rhino3dm
import numpy as np
import trimesh
import matplotlib.pyplot as plt
import math
from ladybug.epw import EPW
from ladybug.sunpath import Sunpath
from ladybug.analysisperiod import AnalysisPeriod
from ladybug.dt import DateTime
from ladybug_geometry.geometry3d.mesh import Mesh3D
from ladybug_geometry.geometry3d.pointvector import Point3D
import os
import multiprocessing as mp
from tqdm import tqdm
import tempfile
import requests
import argparse
import logging
from typing import List, Tuple, Optional
import pymeshlab

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def resolve_path(relative_path: str) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, relative_path)

def get_local_path(path_or_url: str, suffix: str) -> str:
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        logger.info(f"Downloading {path_or_url} ...")
        response = requests.get(path_or_url)
        response.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(response.content)
        tmp.close()
        logger.info(f"Downloaded to {tmp.name}")
        return tmp.name
    else:
        return path_or_url

def sample_sun_positions(sunpath: Sunpath, months, days, hours, minutes) -> List:
    positions = []
    for month in months:
        for day in days:
            for hour in hours:
                for minute in minutes:
                    dt = DateTime(month, day, hour, minute)
                    sun = sunpath.calculate_sun_from_date_time(dt)
                    if sun.altitude > 0:
                        positions.append(sun)
    return positions

def triangulate_and_color_mesh(mesh: Mesh3D, colors: Optional[List[List[int]]], default_color=[180,180,180,200]) -> trimesh.Trimesh:
    vertices_np = np.array([[v.x, v.y, v.z] for v in mesh.vertices])
    triangulated_faces = []
    adjusted_colors = []
    for i, face in enumerate(mesh.faces):
        if len(face) == 3:
            triangulated_faces.append(list(face))
            adjusted_colors.append(colors[i] if colors is not None else default_color)
        elif len(face) == 4:
            triangulated_faces.append([face[0], face[1], face[2]])
            triangulated_faces.append([face[0], face[2], face[3]])
            if colors is not None:
                adjusted_colors.append(colors[i])
                adjusted_colors.append(colors[i])
            else:
                adjusted_colors.append(default_color)
                adjusted_colors.append(default_color)
    faces_np = np.array(triangulated_faces)
    tri_mesh = trimesh.Trimesh(vertices=vertices_np, faces=faces_np)
    tri_mesh.visual.face_colors = adjusted_colors
    return tri_mesh

def process_meshes(meshes: List) -> Tuple[List[Tuple[float, float, float]], List[List[int]]]:
    all_vertices = []
    all_faces = []
    vertex_offset = 0
    for rhino_mesh in meshes:
        vertices = [(pt.X, pt.Y, pt.Z) for pt in rhino_mesh.Vertices]
        mesh_faces = []
        for face in rhino_mesh.Faces:
            if len(face) == 4:
                mesh_faces.append([face[0] + vertex_offset, face[1] + vertex_offset, face[2] + vertex_offset, face[3] + vertex_offset])
            else:
                mesh_faces.append([face[0] + vertex_offset, face[1] + vertex_offset, face[2] + vertex_offset])
        all_vertices.extend(vertices)
        all_faces.extend(mesh_faces)
        vertex_offset += len(vertices)
    return all_vertices, all_faces

def create_ladybug_mesh(vertices: List[Tuple[float, float, float]], faces: List[List[int]]) -> Mesh3D:
    lb_vertices = [Point3D(*vertex) for vertex in vertices]
    lb_faces = []
    for face in faces:
        if len(face) == 4 and face[2] != face[3]:
            lb_faces.append([lb_vertices[face[0]], lb_vertices[face[1]], lb_vertices[face[2]], lb_vertices[face[3]]])
        else:
            lb_faces.append([lb_vertices[face[0]], lb_vertices[face[1]], lb_vertices[face[2]]])
    return Mesh3D.from_face_vertices(lb_faces)

def calculate_radiation_vectorized(face_normals, sun_positions, solar_data) -> np.ndarray:
    sun_vectors = np.array([(-1 * s.sun_vector_reversed).to_array() for s in sun_positions])
    solar_data = np.array(solar_data[:len(sun_vectors)])
    normals_np = np.array([[n.x, n.y, n.z] for n in face_normals])
    dot_products = np.dot(normals_np, sun_vectors.T)
    angle_factors = np.maximum(0, dot_products)
    radiation_matrix = angle_factors * solar_data
    total_radiation = np.sum(radiation_matrix, axis=1)
    return total_radiation

def validate_solar_analysis(radiation_values: List[float], lb_mesh: Mesh3D):
    logger.info("\n=== VALIDATION CHECKS ===")
    north_facing = []
    south_facing = []
    for i, normal in enumerate(lb_mesh.face_normals):
        if normal.y < -0.7:
            north_facing.append(radiation_values[i])
        elif normal.y > 0.7:
            south_facing.append(radiation_values[i])
    if north_facing and south_facing:
        north_avg = sum(north_facing) / len(north_facing)
        south_avg = sum(south_facing) / len(south_facing)
        north_south_ratio = north_avg / south_avg if south_avg > 0 else 0
        logger.info(f"North-facing surfaces avg radiation: {north_avg:.1f}")
        logger.info(f"South-facing surfaces avg radiation: {south_avg:.1f}")
        logger.info(f"North/South ratio: {north_south_ratio:.2f} (should be < 1.0)")
        logger.info(f"Plausibility: {'GOOD' if north_south_ratio < 0.8 else ' SUSPICIOUS'}")
    logger.info(f"Radiation range: {min(radiation_values):.1f} - {max(radiation_values):.1f} kWh/m²")
    expected_min_val = 100
    expected_max_val = 2000
    logger.info(f"Range check: {'GOOD' if min(radiation_values) > expected_min_val and max(radiation_values) < expected_max_val else 'SUSPICIOUS'}")
    std_dev = np.std(radiation_values)
    mean_val = np.mean(radiation_values)
    cv = std_dev / mean_val if mean_val != 0 else float('nan')
    logger.info(f"Statistical variation (CV): {cv:.2f}")
    logger.info(f"Variation check: {' GOOD' if cv < 0.8 else ' HIGH VARIATION'}")
    return north_south_ratio, cv

def create_solar_path_visualization(sunpath: Sunpath, scale=500) -> List[trimesh.Trimesh]:
    paths = []
    dates = [ (6, 21), (12, 21), (3, 21), (9, 21) ]
    path_colors = [ [255, 128, 0, 255], [0, 128, 255, 255], [0, 255, 0, 255], [255, 255, 0, 255] ]
    for (month, day), color in zip(dates, path_colors):
        day_points = []
        for hour in range(24):
            for minute in [0, 30]:
                dt = DateTime(month, day, hour, minute)
                sun = sunpath.calculate_sun_from_date_time(dt)
                if sun.altitude > 0:
                    alt_rad = math.radians(sun.altitude)
                    azm_rad = math.radians(sun.azimuth - 180)
                    x = scale * math.cos(alt_rad) * math.sin(azm_rad)
                    y = scale * math.cos(alt_rad) * math.cos(azm_rad)
                    z = scale * math.sin(alt_rad)
                    day_points.append([x, y, z])
        for i in range(len(day_points) - 1):
            direction = np.array(day_points[i+1]) - np.array(day_points[i])
            length = np.linalg.norm(direction)
            cylinder = trimesh.creation.cylinder(radius=2.0, height=length, sections=8)
            direction = direction / length
            rot = trimesh.geometry.align_vectors([0, 0, 1], direction)
            cylinder.apply_transform(rot)
            trans = trimesh.transformations.translation_matrix(day_points[i])
            cylinder.apply_transform(trans)
            cylinder.visual.face_colors = color
            paths.append(cylinder)
    return paths

# --- Main Execution ---
parser = argparse.ArgumentParser()
parser.add_argument("--user_id", required=True)
parser.add_argument("--project_id", required=True)
parser.add_argument("--epw_url", required=True)
parser.add_argument("--mesh_url", required=True)
parser.add_argument("--processes", type=int, default=max(1, mp.cpu_count()-1), help="Number of parallel processes for radiation calculation")
args = parser.parse_args()

local_epw = get_local_path(args.epw_url, ".epw")
local_mesh = get_local_path(args.mesh_url, ".3dm")
output_glb = "solar_radiation.glb"
if not local_epw or not local_mesh or not output_glb:
    raise RuntimeError("Missing required file paths: epw, mesh, or output")

# --- 1. Load Climate Data ---
epw = EPW(local_epw)
location = epw.location
solar_data = epw.global_horizontal_radiation
logger.info(f"np.minimum type: {type(np.minimum)}, np.maximum type: {type(np.maximum)}")
logger.info(f"Solar data min: {min(solar_data)}, max: {max(solar_data)}")

# --- 2. Compute Solar Position ---
sunpath = Sunpath(location.latitude, location.longitude, location.time_zone)
# Use a much larger and more varied set of sun positions
sun_positions = []
for month in [6, 12, 3, 9]:
    for day in [7, 14, 21]:
        for hour in range(6, 19):
            dt = DateTime(month, day, hour, 0)
            sun = sunpath.calculate_sun_from_date_time(dt)
            if sun.altitude > 0:
                sun_positions.append(sun)
logger.info(f"Using {len(sun_positions)} sun positions for analysis.")

# --- 3. Load Mesh Geometry and Simplify Last Mesh ---
model = rhino3dm.File3dm.Read(local_mesh)  # type: ignore
if not model:
    raise RuntimeError(f"Failed to read 3DM file: {local_mesh}")
all_meshes = []
for obj in model.Objects:
    geom = obj.Geometry
    if type(geom).__name__ == "Mesh":
        name = obj.Attributes.Name if obj.Attributes.Name else "unnamed"
        all_meshes.append((geom, name))
if not all_meshes:
    raise RuntimeError("No meshes found in the model file")

logger.info("Mesh face counts in the .3dm file:")
for idx, (m, n) in enumerate(all_meshes):
    logger.info(f"  Mesh {idx+1}: {len(m.Faces)} faces")

# Simplify only the last mesh
mesh = all_meshes[-1][0]
original_face_count = len(mesh.Faces)
simplification_ratio = 0.2  # 20% of original
calculated_target = max(2000, min(8000, int(original_face_count * simplification_ratio)))
target_faces = calculated_target
logger.info(f"\nSimplifying the last mesh (Mesh {len(all_meshes)}) with {original_face_count} faces.")
logger.info(f"Target face count for simplification: {target_faces}")

vertices = [(v.X, v.Y, v.Z) for v in mesh.Vertices]
faces = []
for f in mesh.Faces:
    if len(f) == 4:
        faces.append([f[0], f[1], f[2]])
        faces.append([f[0], f[2], f[3]])
    elif len(f) == 3:
        faces.append([f[0], f[1], f[2]])

temp_obj = "temp_solar_mesh.obj"
with open(temp_obj, "w") as f:
    for v in vertices:
        f.write(f"v {v[0]} {v[1]} {v[2]}\n")
    for face in faces:
        f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

ms = pymeshlab.MeshSet()  # type: ignore
ms.load_new_mesh(temp_obj)
ms.meshing_decimation_quadric_edge_collapse(
    targetfacenum=target_faces,
    preservenormal=True,
    preserveboundary=True,
    preservetopology=True,
    planarquadric=True
)
logger.info("Decimation complete.")
ms.meshing_remove_duplicate_faces()
ms.meshing_remove_unreferenced_vertices()
if hasattr(ms, 'meshing_remove_isolated_pieces'):
    ms.meshing_remove_isolated_pieces(mincomponentsize=10)
logger.info("Cleaning complete.")
if hasattr(ms, 'compute_normals_for_faces'):
    ms.compute_normals_for_faces()
    logger.info("Normals recomputed.")

simplified_obj = "temp_solar_mesh_simplified.obj"
ms.save_current_mesh(simplified_obj)
with open(simplified_obj, "r") as f:
    lines = f.readlines()

simple_vertices = []
simple_faces = []
for line in lines:
    if line.startswith("v "):
        parts = line.strip().split()
        simple_vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    elif line.startswith("f "):
        nums = [int(n.split('/')[0]) - 1 for n in line.strip().split()[1:]]
        simple_faces.append(nums)

class DummyPt:
    def __init__(self, x, y, z):
        self.X = x
        self.Y = y
        self.Z = z
class DummyMesh:
    pass
simple_mesh = DummyMesh()
simple_mesh.Vertices = [DummyPt(*v) for v in simple_vertices]
simple_mesh.Faces = simple_faces
all_meshes[-1] = (simple_mesh, all_meshes[-1][1])
target_meshes = [all_meshes[-1][0]]
context_meshes = [mesh[0] for mesh in all_meshes[:-1]]
logger.info(f"Using the last mesh '{all_meshes[-1][1]}' as target (simplified), and {len(context_meshes)} other meshes as context")

# --- 4. Process Meshes ---
target_vertices, target_faces = process_meshes(target_meshes)
target_lb_mesh = create_ladybug_mesh(target_vertices, target_faces)
context_vertices, context_faces = process_meshes(context_meshes)
context_lb_mesh = create_ladybug_mesh(context_vertices, context_faces)

# --- 5. Compute Solar Radiation (vectorized, all faces) ---
face_centroids = target_lb_mesh.face_centroids
face_normals = target_lb_mesh.face_normals
num_faces = len(target_lb_mesh.faces)
logger.info(f"Calculating solar radiation for {num_faces} faces using single-threaded mode...")
logger.info(f"Sample normals: {[str(n) for n in face_normals[:5]]}")
radiation_values = calculate_radiation_vectorized(face_normals, sun_positions, solar_data)
min_val = np.amin(radiation_values)
max_val = np.amax(radiation_values)
logger.info(f"Radiation min: {min_val}, max: {max_val}")
if max_val > min_val:
    norm_radiation = (radiation_values - min_val) / (max_val - min_val)
else:
    norm_radiation = np.zeros_like(radiation_values)

validation_results = validate_solar_analysis(radiation_values, target_lb_mesh)
cmap = plt.get_cmap("jet")
target_colors = [(int(r * 255), int(g * 255), int(b * 255), 255) for r, g, b in [cmap(val)[:3] for val in norm_radiation]]

# --- 6. High Radiation Face Analysis ---
sorted_radiation = np.sort(radiation_values)[::-1]
high_threshold = sorted_radiation[int(len(sorted_radiation) * 0.1)]
high_rad_positions = []
high_rad_normals = []
for i, rad in enumerate(radiation_values):
    if rad >= high_threshold:
        high_rad_positions.append([face_centroids[i].x, face_centroids[i].y, face_centroids[i].z])
        high_rad_normals.append([face_normals[i].x, face_normals[i].y, face_normals[i].z])

target_trimesh = triangulate_and_color_mesh(target_lb_mesh, target_colors)
context_vertices_np = np.array([[v.x, v.y, v.z] for v in context_lb_mesh.vertices])
context_trimesh = triangulate_and_color_mesh(context_lb_mesh, None)

bounds = target_trimesh.bounds
model_center = np.mean(bounds, axis=0)
model_height = bounds[1][2]
clearance = 20
high_rad_center = np.mean(high_rad_positions, axis=0) if high_rad_positions else model_center
high_rad_normal = np.mean(high_rad_normals, axis=0) if high_rad_normals else [0, 1, 0]
high_rad_normal = high_rad_normal / np.linalg.norm(high_rad_normal)
vec = np.array(high_rad_center[:2]) - np.array(model_center[:2])
other_side_point = [model_center[0] - vec[0], model_center[1] - vec[1], model_height + clearance]

# --- 7. Solar Path Visualization ---
logger.info("Generating solar path visualization...")
solar_paths = create_solar_path_visualization(sunpath, scale=500)
for path in solar_paths:
    translation = trimesh.transformations.translation_matrix(other_side_point)
    path.apply_transform(translation)
rotation_matrix = trimesh.transformations.rotation_matrix(angle=np.pi, direction=[0, 1, 0], point=model_center)
for path in solar_paths:
    path.apply_transform(rotation_matrix)

all_meshes = [target_trimesh, context_trimesh]
all_meshes.extend(solar_paths)
combined_mesh = trimesh.util.concatenate(all_meshes)
combined_mesh.export(output_glb)
logger.info(f"Model with solar paths saved as {output_glb}")

# --- 8. Export 2D Legend Image ---
logger.info("Generating 2D legend image...")
fig, ax = plt.subplots(figsize=(2, 6))
ax.set_visible(False)
norm = plt.Normalize(min_val, max_val)
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax)
cbar.set_label('Radiation (kWh/m²)')
cbar.set_ticks(np.linspace(min_val, max_val, 10))
cbar.set_ticklabels([f"{val:.0f}" for val in np.linspace(min_val, max_val, 10)])
plt.title('Solar Radiation\n(kWh/m²)')
plt.figtext(0.1, 0.01, f"N/S ratio: {validation_results[0]:.2f}\nCV: {validation_results[1]:.2f}", fontsize=8)
plt.figtext(0.1, 0.2, 'Solar Paths:', fontsize=8)
plt.figtext(0.1, 0.17, 'Summer Solstice', color='orange', fontsize=8)
plt.figtext(0.1, 0.14, 'Winter Solstice', color='blue', fontsize=8)
plt.figtext(0.1, 0.11, 'Spring Equinox', color='green', fontsize=8)
plt.figtext(0.1, 0.08, 'Fall Equinox', color='yellow', fontsize=8)
legend_image = output_glb.replace('.glb', '_legend.png')
plt.savefig(legend_image, bbox_inches='tight', dpi=300)
logger.info(f"Legend image saved as {legend_image}")