import requests
import pyproj
import shapely.geometry as sg
import trimesh
import numpy as np
# OSM Overpass API URL
OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# Function to convert latitude/longitude to UTM (meters)
def latlon_to_utm(lat, lon):
    """Convert WGS84 (lat/lon in degrees) to UTM (meters)."""
    proj = pyproj.Proj(proj="utm", zone=int((lon + 180) / 6) + 1, ellps="WGS84")
    x, y = proj(lon, lat)  # Note: pyproj uses (lon, lat) order
    return x, y

# Function to fetch OSM data
def fetch_osm_data(lat, lon, radius=500):
    """Fetch OSM data for buildings within a given radius of a coordinate."""
    query = f"""
    [out:json];
    (
        way(around:{radius},{lat},{lon})[building];
    );
    out body;
    >;
    out skel qt;
    """
    response = requests.get(OVERPASS_URL, params={"data": query})
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Error fetching OSM data:", response.status_code)
        return None

# Function to parse OSM data
def parse_osm_data(osm_data):
    """Extract building footprints and heights from OSM data."""
    buildings = []
    nodes = {}

    # Store node locations
    for element in osm_data["elements"]:
        if element["type"] == "node":
            lon, lat = element["lon"], element["lat"]
            x, y = latlon_to_utm(lat, lon)  # Convert to meters
            nodes[element["id"]] = (x, y)

    # Extract building footprints
    for element in osm_data["elements"]:
        if element["type"] == "way" and "tags" in element and "building" in element["tags"]:
            try:
                height = float(element["tags"].get("height", 10))  # Default height if missing
                footprint = [nodes[node_id] for node_id in element["nodes"] if node_id in nodes]
                if footprint:
                    buildings.append({"footprint": footprint, "height": height})
            except Exception as e:
                print(f"Error processing building: {e}")

    return buildings

# Function to create a 3D model (with fixed Y/Z orientation)
def create_3d_model(buildings):
    """Create a 3D model using trimesh with proper Y/Z axis adjustment."""
    scene = trimesh.Scene()

    for building in buildings:
        footprint = building["footprint"]
        height = building.get("height", 10)  # Ensure height is valid

        # Ensure height is greater than zero
        if height <= 0:
            print(f"Skipping building with zero height: {footprint}")
            continue  # Skip this building

        # Convert footprint to a 2D polygon
        polygon = sg.Polygon(footprint)

        # Try different triangulation engines
        try:
            extruded = trimesh.creation.extrude_polygon(polygon, height, engine="triangle")
        except ValueError:
            print("Triangle engine failed, trying earcut...")
            try:
                extruded = trimesh.creation.extrude_polygon(polygon, height, engine="earcut")
            except ValueError:
                print(f"Skipping building due to triangulation error: {footprint}")
                continue  # Skip this building if triangulation fails
        
        # **Fix Y/Z Axis Issue**: Rotate 90 degrees to swap Y and Z
        extruded.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))

        # Add to scene
        scene.add_geometry(extruded)

    return scene

# Function to save as GLTF
def save_3d_model(scene, filename="osm_3d_environment.glb"):
    """Export the 3D scene to a GLB file."""
    scene.export(filename)
    print(f"3D model saved as {filename}")

# Main Execution
if __name__ == "__main__":
    # 🔹 Replace with your own coordinates
    lat, lon = 40.748817, -73.985428  # Example: New York (Empire State Building)
    radius = 500  # Max area in meters

    # Fetch and process OSM data
    osm_data = fetch_osm_data(lat, lon, radius)
    if osm_data:
        buildings = parse_osm_data(osm_data)
        scene = create_3d_model(buildings)
        save_3d_model(scene)
