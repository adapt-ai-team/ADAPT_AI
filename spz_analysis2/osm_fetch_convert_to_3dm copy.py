import requests
import pyproj
import shapely.geometry as sg
import trimesh
import rhino3dm
import numpy as np
import os
from flask import Flask, request, jsonify
import sys

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

# Initialize Flask app
app = Flask(__name__)

@app.route('/save_latlon', methods=['POST'])
def save_latlon():
    try:
        data = request.json
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if latitude is None or longitude is None:
            return jsonify({"status": "error", "message": "Invalid lat/lon values"}), 400

        with open(LATLON_FILE, "w") as file:
            file.write(f"{latitude},{longitude}")
        
        return jsonify({"status": "success", "message": "Lat/lon saved successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def get_saved_latlon():
    try:
        if not os.path.exists(LATLON_FILE):
            print(f"⚠️ Warning: Lat/lon file not found at {LATLON_FILE}")
            return None, None
        with open(LATLON_FILE, "r") as file:
            latlon = file.read().strip()
            if "," not in latlon:
                print(f"⚠️ Warning: Invalid format in {LATLON_FILE}. Expected 'lat,lon'")
                return None, None
            lat, lon = map(float, latlon.split(","))
            print(f"✅ Successfully read coordinates from {LATLON_FILE}")
            return lat, lon
    except Exception as e:
        print(f"❌ Error reading lat/lon file: {e}")
        return None, None

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

def process_example_image(up_axis=2):
    """Process example_image.glb to match OSM model position and scale."""
    scene = trimesh.load(INPUT_GLB_PATH)
    new_scene = trimesh.Scene()

    # Load OSM model and get its bounds and center
    osm_scene = trimesh.load(OSM_GLB_PATH)
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

    new_scene.export(FIXED_INPUT_GLB_PATH)
    print(f"✅ Model processed and saved as `{FIXED_INPUT_GLB_PATH}`")
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

if __name__ == "__main__":
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(port=5000, debug=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    if len(sys.argv) == 3:
        lon, lat = float(sys.argv[1]), float(sys.argv[2])
        with open(LATLON_FILE, "w") as file:
            file.write(f"{lat},{lon}")
        LAT, LON = lat, lon
        print(f"📍 Using coordinates from command line: {LAT}, {LON}")
    else:
        LAT, LON = get_saved_latlon()
        if LAT is None or LON is None:
            print("❌ Could not read coordinates from file. Ensure:")
            print(f"1. File exists at {LATLON_FILE}")
            print("2. File contains coordinates in format: latitude,longitude")
            print("3. File has correct permissions")
            exit(1)
    
    print(f"🔹 Using Lat/Lon: {LAT}, {LON}")
    
    REF_X, REF_Y = latlon_to_utm(LAT, LON)
    REF_Z = 0
    print(f"🔹 Reference UTM Coordinates: ({REF_X}, {REF_Y})")
    
    osm_data = fetch_osm_data(LAT, LON, RADIUS)
    if osm_data:
        print(f"📍 Found {len(osm_data['elements'])} OSM elements")
        buildings = parse_osm_data(osm_data)
        print(f"🏢 Parsed {len(buildings)} buildings")
        if not buildings:
            print("⚠️ No buildings found. Try increasing RADIUS or verifying coordinates.")
            exit(1)
        scene_osm = create_3d_model(buildings, scale_factor=10)
        if len(scene_osm.geometry) > 0:
            scene_osm.export(OSM_GLB_PATH)
            print("✅ OSM model exported")
        else:
            print("❌ No valid geometry created from buildings")
            exit(1)
    else:
        print("❌ Failed to fetch OSM data")
        exit(1)
    
    scene_osm = trimesh.load(OSM_GLB_PATH)
    # Set up_axis=1 if you suspect Y is up; otherwise use up_axis=2.
    scene_input = process_example_image(up_axis=2)
    
    if scene_osm and scene_input:
        osm_bounds = scene_osm.bounds
        osm_center = np.mean(osm_bounds, axis=0)
        print(f"📍 Final OSM Center: {osm_center}")
        input_bounds = scene_input.bounds
        input_center = np.mean(input_bounds, axis=0)
        print(f"📍 Final Input Center: {input_center}")
        
        # Create merged scene
        merged_scene = trimesh.Scene()
        merged_scene.add_geometry(scene_osm)
        merged_scene.add_geometry(scene_input)
        
        # Export as 3DM
        export_scene_to_3dm(merged_scene, OUTPUT_3DM_PATH)
        
        # Export as GLB
        glb_output_path = OUTPUT_3DM_PATH.replace('.3dm', '.glb')
        try:
            merged_scene.export(glb_output_path)
            print(f"✅ Merged model also exported as GLB: {glb_output_path}")
        except Exception as e:
            print(f"❌ Failed to export GLB: {e}")