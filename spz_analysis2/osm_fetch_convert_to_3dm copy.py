import requests
import pyproj
import shapely.geometry as sg
import trimesh
import rhino3dm
import numpy as np
import os
from flask import Flask, request, jsonify
import sys
import tempfile
import trimesh
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# Add path resolver after imports
def resolve_path(relative_path):
    """Convert relative path to absolute path based on script location"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, relative_path)

# 📂 File paths - convert to relative paths
OSM_GLB_PATH = resolve_path("../spz_pipeline/pipeline_outputs/osm_3d_environment.glb")
INPUT_GLB_PATH = resolve_path("../spz_pipeline/pipeline_outputs/example_image.glb")
FIXED_INPUT_GLB_PATH = resolve_path("../spz_pipeline/pipeline_outputs/example_image_fixed.glb")
OUTPUT_3DM_PATH = resolve_path("../spz_pipeline/pipeline_outputs/merged_model.3dm")
LATLON_FILE = resolve_path("../spz_pipeline/pipeline_outputs/latlon.txt")

# 📍 Constants
RADIUS = 250  # Max area in meters for OSM data fetch



def fetch_latlon_from_supabase(user_id: str, project_id: str):
    path = f"{user_id}/{project_id}/latlon.txt"
    try:
        data = supabase.storage.from_("location").download(path)
        latlon = data.decode("utf-8").strip()
        lat, lon = map(float, latlon.split(","))
        print(f"📍 Fetched lat/lon: {lat}, {lon}")
        return lat, lon
    except Exception as e:
        raise Exception(f"❌ Failed to fetch latlon.txt from Supabase: {e}")


def latlon_to_utm(lat, lon):
    proj = pyproj.Proj(proj="utm", zone=int((lon + 180) / 6) + 1, ellps="WGS84")
    x, y = proj(lon, lat)
    return x, y

def compute_bottom_center(bounds, up_axis=2):
    """
    Compute the bottom center point of the bounding box based on the up axis.
    
    For up_axis = 2 (Z up): returns 
        [ (min_x + max_x)/2, (min_y + max_y)/2, min_z ]
    
    For up_axis = 1 (Y up): returns 
        [ (min_x + max_x)/2, min_y, (min_z + max_z)/2 ]
    
    For up_axis = 0 (X up, rarely used): returns 
        [ min_x, (min_y + max_y)/2, (min_z + max_z)/2 ]
    """
    bmin = bounds[0]
    bmax = bounds[1]
    pivot = np.empty(3)
    for i in range(3):
        if i == up_axis:
            pivot[i] = bmin[i]
        else:
            pivot[i] = (bmin[i] + bmax[i]) / 2
    return pivot

def process_example_image(user_id: str, project_id: str, osm_scene: trimesh.Scene, up_axis=2):
    """
    Fetches a Trellis model from Supabase and aligns it to the provided OSM scene.

    Args:
        user_id (str): Supabase user ID
        project_id (str): Supabase project ID
        osm_scene (trimesh.Scene): OSM 3D model scene
        up_axis (int): Axis considered "up" (2 = Z-up)

    Returns:
        trimesh.Scene: Aligned and scaled scene
    """

    # --- Step 1: Download model.glb from Supabase ---
    input_path = f"{user_id}/{project_id}/model.glb"
    input_url = supabase.storage.from_("2d-to-3d").get_public_url(input_path)
    response = requests.get(input_url)
    if response.status_code != 200:
        raise Exception(f"❌ Failed to download model.glb from: {input_url}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp_file:
        tmp_file.write(response.content)
        tmp_file.flush()
        scene = trimesh.load(tmp_file.name)

    print(f"📦 Loaded Trellis model for {user_id}/{project_id}")
    new_scene = trimesh.Scene()

    # --- Step 2: Analyze OSM bounds ---
    osm_bounds = osm_scene.bounds
    osm_center = np.mean(osm_bounds, axis=0)
    osm_lowest_z = osm_bounds[0][2]
    print(f"📍 OSM Model Bounds: {osm_bounds}")
    print(f"📍 OSM Center Point: {osm_center}")
    print(f"📍 OSM Lowest Z: {osm_lowest_z}")

    # --- Step 3: Process Trellis geometry ---
    for mesh_name, geometry in scene.geometry.items():
        print(f"Processing mesh: {mesh_name}")
        bounds = geometry.bounds
        current_center = np.mean(bounds, axis=0)
        print(f"📏 Original Bounds: {bounds}")
        print(f"📏 Original Center: {current_center}")

        # Step 4: Uniform scaling from base
        scale_factor = 1000
        pivot_point = np.array([current_center[0], bounds[0][1], current_center[2]])

        to_origin = np.eye(4)
        to_origin[:3, 3] = -pivot_point

        scale = np.eye(4)
        scale[:3, :3] *= scale_factor

        from_origin = np.eye(4)
        from_origin[:3, 3] = pivot_point

        transform = from_origin @ scale @ to_origin
        geometry.apply_transform(transform)

        # Step 5: Translate to OSM center
        updated_bounds = geometry.bounds
        updated_center = np.mean(updated_bounds, axis=0)
        translation = np.array([
            osm_center[0] - updated_center[0],
            0,
            osm_center[2] - updated_center[2]
        ])
        T_translate = np.eye(4)
        T_translate[:3, 3] = translation
        geometry.apply_transform(T_translate)

        # Step 6: Final debug
        final_bounds = geometry.bounds
        final_center = np.mean(final_bounds, axis=0)
        print(f"📏 Final Bounds: {final_bounds}")
        print(f"📏 Final Center: {final_center}")
        center_difference_xz = np.abs(final_center[[0, 2]] - osm_center[[0, 2]])
        print(f"📏 XZ Center Difference: {center_difference_xz}")

        if np.any(center_difference_xz > 0.001):
            print(f"⚠️ Warning: Alignment offset detected: {center_difference_xz}")

        new_scene.add_geometry(geometry)

    print(f"✅ Model processed and aligned")
    return new_scene

# (The rest of your code remains unchanged)

def fetch_osm_data(lat, lon, radius):
    query = f"""
    [out:json];
    (
        way(around:{radius},{lat},{lon})[building];
    );
    out body;
    >;
    out skel qt;
    """
    api_endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]
    for endpoint in api_endpoints:
        try:
            print(f"🔍 Trying to connect to Overpass API at: {endpoint}")
            response = requests.get(endpoint, params={"data": query}, timeout=30)
            if response.status_code == 200:
                print(f"✅ Successfully fetched OSM data from {endpoint}")
                return response.json()
            else:
                print(f"⚠️ API returned status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Connection error with {endpoint}: {e}")
    print("❌ All Overpass API endpoints failed. Trying to load cached data if available...")
    cache_file = "osm_cache.json"
    if os.path.exists(cache_file):
        try:
            import json
            with open(cache_file, 'r') as f:
                print(f"✅ Loading OSM data from cache file: {cache_file}")
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load cached data: {e}")
    return None

def parse_osm_data(osm_data):
    buildings = []
    nodes = {}
    
    # Collect all nodes
    for element in osm_data["elements"]:
        if element["type"] == "node":
            x, y = latlon_to_utm(element["lat"], element["lon"])
            nodes[element["id"]] = (x, y)  # Store original UTM coordinates
    
    # Process buildings with original coordinates
    for element in osm_data["elements"]:
        if element["type"] == "way" and "building" in element.get("tags", {}):
            try:
                height = float(element["tags"].get("height", 10))
                footprint = []
                for node_id in element["nodes"]:
                    if node_id in nodes:
                        footprint.append(nodes[node_id])
                if len(footprint) >= 3:
                    buildings.append({"footprint": footprint, "height": height})
            except Exception as e:
                print(f"Error processing building: {e}")
                continue
                
    return buildings

def create_3d_model(buildings, scale_factor=1.0):
    scene = trimesh.Scene()
    
    # Create 3D models with centered coordinates
    for building in buildings:
        footprint = building["footprint"]
        height = building["height"]
        polygon = sg.Polygon(footprint)
        try:
            extruded = trimesh.creation.extrude_polygon(polygon, height, engine="triangle")
        except ValueError:
            try:
                extruded = trimesh.creation.extrude_polygon(polygon, height, engine="earcut")
            except ValueError:
                continue
                
        # Apply transformations but maintain centering
        rot_z = trimesh.transformations.rotation_matrix(-np.pi/2, [0, 0, 1])
        extruded.apply_transform(rot_z)
        rot_x = trimesh.transformations.rotation_matrix(-np.pi/2, [1, 0, 0])
        extruded.apply_transform(rot_x)
        extruded.apply_scale(scale_factor)
        
        scene.add_geometry(extruded)
    
    return scene

def export_scene_to_3dm(scene, output_path):
    model = rhino3dm.File3dm()
    for mesh_name, geometry in scene.geometry.items():
        if not isinstance(geometry, trimesh.Trimesh):
            continue
        rhino_mesh = rhino3dm.Mesh()
        for v in geometry.vertices:
            rhino_mesh.Vertices.Add(float(v[0]), float(v[1]), float(v[2]))
        for face in geometry.faces:
            if len(face) == 3:
                rhino_mesh.Faces.AddFace(int(face[0]), int(face[1]), int(face[2]))
            elif len(face) == 4:
                rhino_mesh.Faces.AddFace(int(face[0]), int(face[1]), int(face[2]), int(face[3]))
        rhino_mesh.Normals.ComputeNormals()
        rhino_mesh.Compact()
        model.Objects.AddMesh(rhino_mesh)
    model.Write(output_path, 5)
    print(f"✅ Merged model exported as `{output_path}`")


def run_osm_pipeline(user_id: str, project_id: str):
    # Set global user/project context
    LAT, LON = fetch_latlon_from_supabase(user_id, project_id)
    print(f"📍 Coordinates: {LAT}, {LON}")

    REF_X, REF_Y = latlon_to_utm(LAT, LON)
    REF_Z = 0
    print(f"📍 UTM Reference: ({REF_X}, {REF_Y})")

    # Step 1: Fetch and parse OSM data
    osm_data = fetch_osm_data(LAT, LON, RADIUS)
    if not osm_data:
        raise Exception("❌ Failed to fetch OSM data.")

    buildings = parse_osm_data(osm_data)
    if not buildings:
        raise Exception("❌ No buildings parsed from OSM.")

    # Step 2: Create 3D OSM scene
    scene_osm = create_3d_model(buildings, scale_factor=10)

    # Step 3: Process user GLB and align it to OSM
    scene_input = process_example_image(user_id, project_id, scene_osm)

    # Step 4: Merge and export
    merged_scene = trimesh.Scene()
    merged_scene.add_geometry(scene_osm)
    merged_scene.add_geometry(scene_input)

    # Export merged model to Supabase
    from supabase import create_client
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    # Export merged .glb
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as tmp_glb:
        merged_scene.export(tmp_glb.name)
        tmp_glb.flush()
        with open(tmp_glb.name, "rb") as f:
            path = f"{user_id}/{project_id}/merged_model.glb"
            supabase.storage.from_("osm-merged").upload(path, f, file_options={"content-type": "model/gltf-binary"})
        os.remove(tmp_glb.name)
        print(f"✅ Merged model uploaded to: osm-merged/{user_id}/{project_id}/merged_model.glb")
