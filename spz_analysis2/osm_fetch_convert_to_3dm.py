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
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Bucket names
LATLON_BUCKET = "location"
INPUT_BUCKET = "2d-to-3d"
MERGED_BUCKET = "context-merged"  # Use the existing bucket name

# 📍 Constants
RADIUS = 250  # Max area in meters for OSM data fetch

# Initialize Flask app
app = Flask(__name__)

@app.route('/save_latlon', methods=['POST'])
def save_latlon():
    try:
        data = request.json
        user_id = data.get("user_id")
        project_id = data.get("project_id")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if not all([user_id, project_id, latitude, longitude]):
            return jsonify({"status": "error", "message": "Missing required parameters"}), 400

        path = f"{user_id}/{project_id}/latlon.txt"
        content = f"{latitude},{longitude}"
        
        try:
            # Remove existing file if present
            supabase.storage.from_(LATLON_BUCKET).remove([path])
        except Exception:
            pass  # Safe to ignore if file doesn't exist
            
        # Upload new coordinates
        supabase.storage.from_(LATLON_BUCKET).upload(
            path,
            content.encode(),
            file_options={"content-type": "text/plain"}
        )
        
        return jsonify({"status": "success", "message": "Lat/lon saved successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def fetch_latlon_from_supabase(user_id: str, project_id: str):
    path = f"{user_id}/{project_id}/latlon.txt"
    try:
        data = supabase.storage.from_(LATLON_BUCKET).download(path)
        lat, lon = map(float, data.decode("utf-8").strip().split(","))
        print(f"📍 Fetched lat/lon: {lat}, {lon}")
        return lat, lon
    except Exception as e:
        raise Exception(f"❌ Failed to fetch latlon.txt: {e}")

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

def fetch_model_from_supabase(user_id: str, project_id: str):
    path = f"{user_id}/{project_id}/model.glb"
    url = supabase.storage.from_(INPUT_BUCKET).get_public_url(path)
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"❌ Failed to download model.glb from: {url}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp:
        tmp.write(response.content)
        tmp.flush()
        return trimesh.load(tmp.name)

def upload_fixed_model(scene: trimesh.Scene, user_id: str, project_id: str):
    path = f"{user_id}/{project_id}/model_fixed.glb"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp_file:
        scene.export(tmp_file.name)
        tmp_file.flush()
        try:
            # Remove existing file if present
            supabase.storage.from_(INPUT_BUCKET).remove([path])
        except Exception:
            pass  # Safe to ignore if file doesn't exist

        # Upload the new model
        supabase.storage.from_(INPUT_BUCKET).upload(
            path,
            tmp_file.name,
            file_options={"content-type": "model/gltf-binary"}
        )
        print(f"✅ Uploaded model_fixed.glb to {INPUT_BUCKET}/{path}")

def upload_merged_model(scene: trimesh.Scene, user_id: str, project_id: str):
    path = f"{user_id}/{project_id}/merged_model.glb"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp_file:
        scene.export(tmp_file.name)
        tmp_file.flush()
        
        try:
            # Remove existing file if present
            supabase.storage.from_(MERGED_BUCKET).remove([path])
        except Exception:
            pass  # Safe to ignore if file doesn't exist
        
        # Upload the new model
        supabase.storage.from_(MERGED_BUCKET).upload(
            path,
            tmp_file.name,
            file_options={"content-type": "model/gltf-binary"}
        )
        print(f"✅ Uploaded merged_model.glb to {MERGED_BUCKET}/{path}")

def export_scene_to_3dm_and_upload(scene, user_id: str, project_id: str):
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
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".3dm") as tmp_file:
        model.Write(tmp_file.name, 5)
        path = f"{user_id}/{project_id}/merged_model.3dm"
        
        try:
            # Remove existing file if present
            supabase.storage.from_("solar-radiation").remove([path])
        except Exception:
            pass  # Safe to ignore if file doesn't exist
            
        # Upload the new model
        supabase.storage.from_("solar-radiation").upload(
            path,
            tmp_file.name,
            file_options={"content-type": "application/octet-stream"}
        )
        print(f"✅ Uploaded merged_model.3dm to solar-radiation/{path}")

def process_example_image(user_id: str, project_id: str, osm_scene: trimesh.Scene, up_axis=2):
    """Process example_image.glb to match OSM model position and scale."""
    scene = fetch_model_from_supabase(user_id, project_id)
    new_scene = trimesh.Scene()
    
    # Get OSM bounds and center
    osm_bounds = osm_scene.bounds
    osm_center = np.mean(osm_bounds, axis=0)
    osm_lowest_z = osm_bounds[0][2]
    print(f"📍 OSM Model Bounds: {osm_bounds}")
    print(f"📍 OSM Center Point: {osm_center}")
    print(f"📍 OSM Lowest Z: {osm_lowest_z}")

    for mesh_name, geometry in scene.geometry.items():
        print(f"Processing mesh: {mesh_name}")

        # 1. Get original bounds and center
        bounds = geometry.bounds
        current_center = np.mean(bounds, axis=0)
        current_lowest_z = bounds[0][2]
        print(f"📏 Original Bounds: {bounds}")
        print(f"📏 Original Center: {current_center}")
        
        # 2. Scale by 1000 uniformly from current position
        scale_factor = 1000
        
        # Use bottom center as pivot point
        pivot_point = np.array([
            current_center[0],  # X center
            bounds[0][1],      # Y bottom
            current_center[2]   # Z center
        ])
        
        # Create scaling transformation
        to_origin = np.eye(4)
        to_origin[:3, 3] = -pivot_point
        
        scale = np.eye(4)
        scale[:3, :3] *= scale_factor
        
        from_origin = np.eye(4)
        from_origin[:3, 3] = pivot_point
        
        # Apply scaling transformation
        transform = from_origin @ scale @ to_origin
        geometry.apply_transform(transform)
        
        # 3. Get updated bounds after scaling
        updated_bounds = geometry.bounds
        updated_center = np.mean(updated_bounds, axis=0)
        
        # 4. Calculate translation to match centers on XZ plane
        translation = np.array([
            osm_center[0] - updated_center[0],  # X alignment
            0,                                  # Keep Y unchanged
            osm_center[2] - updated_center[2]   # Z alignment
        ])
        
        # 5. Apply translation
        T_translate = np.eye(4)
        T_translate[:3, 3] = translation
        geometry.apply_transform(T_translate)
        
        # 6. Verify final position
        final_bounds = geometry.bounds
        final_center = np.mean(final_bounds, axis=0)
        print(f"📏 Final Bounds: {final_bounds}")
        print(f"📏 Final Center: {final_center}")
        
        # Verify center alignment on XZ plane
        center_difference_xz = np.array([
            abs(final_center[0] - osm_center[0]),
            abs(final_center[2] - osm_center[2])
        ])
        print(f"📏 XZ Center Difference: {center_difference_xz}")
        
        if np.any(center_difference_xz > 0.001):
            print(f"⚠️ Warning: XZ center alignment offset detected: {center_difference_xz}")

        new_scene.add_geometry(geometry)

    # Upload the fixed model
    upload_fixed_model(new_scene, user_id, project_id)
    return new_scene

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
    print("❌ All Overpass API endpoints failed.")
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

def run_osm_pipeline(user_id: str, project_id: str):
    # Check if required buckets exist
    try:
        buckets = [bucket["name"] for bucket in supabase.storage.list_buckets()]
        required_buckets = [LATLON_BUCKET, INPUT_BUCKET, MERGED_BUCKET, "solar-radiation"]
        
        for bucket in required_buckets:
            if bucket not in buckets:
                print(f"⚠️ Warning: Bucket '{bucket}' doesn't exist in Supabase. Some operations may fail.")
    except Exception as e:
        print(f"⚠️ Warning: Couldn't verify buckets: {e}")
    
    lat, lon = fetch_latlon_from_supabase(user_id, project_id)
    print(f"🔹 Using Lat/Lon: {lat}, {lon}")
    
    REF_X, REF_Y = latlon_to_utm(lat, lon)
    REF_Z = 0
    print(f"🔹 Reference UTM Coordinates: ({REF_X}, {REF_Y})")
    
    osm_data = fetch_osm_data(lat, lon, RADIUS)
    if osm_data:
        print(f"📍 Found {len(osm_data['elements'])} OSM elements")
        buildings = parse_osm_data(osm_data)
        print(f"🏢 Parsed {len(buildings)} buildings")
        if not buildings:
            print("⚠️ No buildings found. Try increasing RADIUS or verifying coordinates.")
            return
            
        scene_osm = create_3d_model(buildings, scale_factor=10)
        if len(scene_osm.geometry) == 0:
            print("❌ No valid geometry created from buildings")
            return
            
        # Process and align the input model
        scene_fixed = process_example_image(user_id, project_id, scene_osm)
        
        # Create merged scene
        merged_scene = trimesh.Scene()
        for g in scene_osm.geometry.values():
            merged_scene.add_geometry(g)
        for g in scene_fixed.geometry.values():
            merged_scene.add_geometry(g)
            
        # Upload merged model in GLB format
        upload_merged_model(merged_scene, user_id, project_id)
        
        # Export and upload Rhino 3DM format
        export_scene_to_3dm_and_upload(merged_scene, user_id, project_id)
        
    else:
        print("❌ Failed to fetch OSM data")
        return

if __name__ == "__main__":
    # Run as a CLI tool or as a service
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", required=True)
    parser.add_argument("--project_id", required=True)
    args = parser.parse_args()
    
    # Start Flask in a background thread
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(port=5000, debug=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run the pipeline with arguments
    run_osm_pipeline(args.user_id, args.project_id)