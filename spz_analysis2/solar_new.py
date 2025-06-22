import rhino3dm
import numpy as np
import trimesh
import matplotlib.pyplot as plt
import math  # Add this import
from ladybug.epw import EPW
from ladybug.sunpath import Sunpath
from ladybug.analysisperiod import AnalysisPeriod
from ladybug.dt import DateTime
from ladybug_geometry.geometry3d.mesh import Mesh3D
from ladybug_geometry.geometry3d.pointvector import Point3D
from ladybug_geometry.geometry3d.arc import Arc3D
from ladybug_geometry.geometry3d.line import LineSegment3D
import os
import multiprocessing as mp
from tqdm import tqdm  # Also make sure tqdm is imported for the progress bar
import tempfile
import requests

# Add path resolver helper at the top after imports
def resolve_path(relative_path):
    """Convert relative path to absolute path based on script location"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, relative_path)

# Helper to download a file if given a URL
def get_local_path(path_or_url, suffix):
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        print(f"Downloading {path_or_url} ...")
        response = requests.get(path_or_url)
        response.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(response.content)
        tmp.close()
        print(f"Downloaded to {tmp.name}")
        return tmp.name
    else:
        return path_or_url

import argparse
import os

# Setup argparse
parser = argparse.ArgumentParser()
parser.add_argument("--user_id", required=True)
parser.add_argument("--project_id", required=True)
parser.add_argument("--epw_url", required=True)
parser.add_argument("--mesh_url", required=True)
args = parser.parse_args()

# Download files if URLs, else use as-is
local_epw = get_local_path(args.epw_url, ".epw")
local_mesh = get_local_path(args.mesh_url, ".3dm")
output_glb = "solar_radiation.glb"  # Always save as this name in CWD

if not local_epw or not local_mesh or not output_glb:
    raise RuntimeError("Missing required file paths: epw, mesh, or output")
offset_dist = 0.1  # Offset for analysis points

# Move this function outside main(), at the module level
def calculate_radiation(args):
    i, center, normal, sun_positions, solar_data = args
    total_radiation = 0
    for j, sun_pos in enumerate(sun_positions):
        # Fix the vector direction by negating sun_vector_reversed
        sun_vector = -1 * sun_pos.sun_vector_reversed
        # Alternative: use correct property if available
        # sun_vector = sun_pos.sun_vector  # Try this if available
        
        angle_factor = max(0, normal.dot(sun_vector))
        radiation_value = solar_data[j % len(solar_data)] * angle_factor
        total_radiation += radiation_value
    return total_radiation

def validate_solar_analysis(radiation_values, lb_mesh):
    # 1. Check for physical plausibility
    print("\n=== VALIDATION CHECKS ===")
    
    
    # North/South facing surfaces check (Northern Hemisphere)
    north_facing = []
    south_facing = []
    
    for i, normal in enumerate(lb_mesh.face_normals):
        # Simple check - if y component is strongly negative, it's north-facing
        if normal.y < -0.7:
            north_facing.append(radiation_values[i])
        elif normal.y > 0.7:
            south_facing.append(radiation_values[i])
    
    if north_facing and south_facing:
        north_avg = sum(north_facing) / len(north_facing)
        south_avg = sum(south_facing) / len(south_facing)
        north_south_ratio = north_avg / south_avg if south_avg > 0 else 0
        
        print(f"North-facing surfaces avg radiation: {north_avg:.1f}")
        print(f"South-facing surfaces avg radiation: {south_avg:.1f}")
        print(f"North/South ratio: {north_south_ratio:.2f} (should be < 1.0)")
        print(f"Plausibility: {'✅ GOOD' if north_south_ratio < 0.8 else ' SUSPICIOUS'}")
    
    # Check radiation range
    print(f"Radiation range: {min(radiation_values):.1f} - {max(radiation_values):.1f} kWh/m²")
    expected_min = 100  # Adjust based on your climate
    expected_max = 2000  # Adjust based on your climate
    print(f"Range check: {' GOOD' if min(radiation_values) > expected_min and max(radiation_values) < expected_max else '❌ SUSPICIOUS'}")
    
    # Check for outliers (standard deviation)
    std_dev = np.std(radiation_values)
    mean_val = np.mean(radiation_values)
    cv = std_dev / mean_val  # Coefficient of variation
    print(f"Statistical variation (CV): {cv:.2f}")
    print(f"Variation check: {' GOOD' if cv < 0.8 else ' HIGH VARIATION'}")
    
    return north_south_ratio, cv

def add_color_legend(mesh, min_val, max_val, colors, position=None):
    """Add a color legend to the 3D scene"""
    # Default position (adjust based on your model bounds)
    if position is None:
        bounds = mesh.bounds
        position = [bounds[1][0] + 100, bounds[0][1], bounds[0][2]]  # Right side of model
    
    # Create legend dimensions
    legend_height = 50
    legend_width = 10
    legend_depth = 1
    text_height = 10
    
    # Create legend base geometry
    legend_vertices = []
    legend_faces = []
    legend_colors = []
    
    # Create the color bar with gradient
    segments = 20
    for i in range(segments):
        # Calculate corners of this segment
        z_bottom = i * (legend_height / segments)
        z_top = (i + 1) * (legend_height / segments)
        
        # Add vertices
        base_idx = len(legend_vertices)
        legend_vertices.extend([
            [position[0], position[1], position[2] + z_bottom],              # front bottom left
            [position[0] + legend_width, position[1], position[2] + z_bottom], # front bottom right
            [position[0] + legend_width, position[1], position[2] + z_top],    # front top right
            [position[0], position[1], position[2] + z_top]                  # front top left
        ])
        
        # Add face
        legend_faces.append([base_idx, base_idx + 1, base_idx + 2, base_idx + 3])
        
        # Add color (reverse order to have high values at top)
        color_idx = segments - i - 1
        color = colors[int(color_idx / segments * (len(colors)-1))]
        legend_colors.append(color)
    
    # Create text labels (in separate rendering step)
    # For GLB, we can't easily add text, so we'll create markers at min, mid, max
    
    # Create a trimesh for the legend
    legend_mesh = trimesh.Trimesh(
        vertices=np.array(legend_vertices),
        faces=np.array(legend_faces),
        face_colors=legend_colors,
        process=False
    )
    
    # Combine with main mesh
    combined = trimesh.util.concatenate([mesh, legend_mesh])
    
    # Create text values for separate display
    text_values = {
        "min": f"{min_val:.1f} kWh/m²",
        "max": f"{max_val:.1f} kWh/m²",
        "position": [position[0] + legend_width + 5, position[1], position[2]]
    }
    
    return combined, text_values

def create_color_legend(min_val, max_val, cmap_name="jet", size=None):
    """Create a standalone color legend mesh"""
    if size is None:
        size = (10, 50, 1)  # width, height, depth
    
    # Position at origin
    position = [0, 0, 0]
    
    # Create legend dimensions
    legend_width, legend_height, legend_depth = size
    
    # Create legend base geometry
    vertices = []
    faces = []
    colors = []
    
    # Get colormap
    cmap = plt.get_cmap(cmap_name)
    
    # Create the color bar with gradient
    segments = 20
    for i in range(segments):
        # Calculate corners of this segment
        z_bottom = i * (legend_height / segments)
        z_top = (i + 1) * (legend_height / segments)
        
        # Add vertices
        base_idx = len(vertices)
        vertices.extend([
            [position[0], position[1], position[2] + z_bottom],
            [position[0] + legend_width, position[1], position[2] + z_bottom],
            [position[0] + legend_width, position[1], position[2] + z_top],
            [position[0], position[1], position[2] + z_top]
        ])
        
        # Add face
        faces.append([base_idx, base_idx + 1, base_idx + 2, base_idx + 3])
        
        # Add color (reverse order to have high values at top)
        color_idx = segments - i - 1
        color_value = color_idx / (segments - 1)
        color_rgb = cmap(color_value)[:3]  # Get RGB (ignore alpha)
        color_rgba = [int(c * 255) for c in color_rgb] + [255]  # Add alpha channel
        colors.append(color_rgba)
    
    # Create a trimesh for the legend
    legend_mesh = trimesh.Trimesh(
        vertices=np.array(vertices),
        faces=np.array(faces),
        face_colors=np.array(colors)
    )
    
    return legend_mesh, min_val, max_val

def triangulate_and_color_mesh(mesh, colors):
    """Triangulate a mesh and apply colors to each face"""
    vertices_np = np.array([[v.x, v.y, v.z] for v in mesh.vertices])
    
    # Triangulate the mesh - convert quads to triangles
    triangulated_faces = []
    adjusted_colors = []
    
    for i, face in enumerate(mesh.faces):
        if len(face) == 3:
            triangulated_faces.append(list(face))
            adjusted_colors.append(colors[i])
        elif len(face) == 4:
            # Convert quad to two triangles
            triangulated_faces.append([face[0], face[1], face[2]])
            triangulated_faces.append([face[0], face[2], face[3]])
            # Duplicate this face's color for both triangles
            adjusted_colors.append(colors[i])
            adjusted_colors.append(colors[i])
    
    faces_np = np.array(triangulated_faces)
    
    # Create trimesh with colors
    tri_mesh = trimesh.Trimesh(vertices=vertices_np, faces=faces_np)
    tri_mesh.visual.face_colors = adjusted_colors
    
    return tri_mesh

def process_meshes(meshes):
    """Process a list of Rhino meshes into vertices and faces"""
    all_vertices = []
    all_faces = []
    vertex_offset = 0
    
    for rhino_mesh in meshes:
        vertices = [(pt.X, pt.Y, pt.Z) for pt in rhino_mesh.Vertices]
        
        mesh_faces = []
        for face in rhino_mesh.Faces:
            if len(face) == 4:  # Quad
                mesh_faces.append([face[0] + vertex_offset, 
                                 face[1] + vertex_offset, 
                                 face[2] + vertex_offset, 
                                 face[3] + vertex_offset])
            else:  # Triangle
                mesh_faces.append([face[0] + vertex_offset, 
                                 face[1] + vertex_offset, 
                                 face[2] + vertex_offset])
        
        all_vertices.extend(vertices)
        all_faces.extend(mesh_faces)
        vertex_offset += len(vertices)
    
    return all_vertices, all_faces

def create_ladybug_mesh(vertices, faces):
    """Convert vertices and faces to a Ladybug mesh"""
    lb_vertices = [Point3D(*vertex) for vertex in vertices]
    lb_faces = []
    
    for face in faces:
        if len(face) == 4 and face[2] != face[3]:  # Valid quad
            lb_faces.append([lb_vertices[face[0]], lb_vertices[face[1]], 
                           lb_vertices[face[2]], lb_vertices[face[3]]])
        else:  # Triangle or degenerate quad
            lb_faces.append([lb_vertices[face[0]], lb_vertices[face[1]], 
                           lb_vertices[face[2]]])
    
    return Mesh3D.from_face_vertices(lb_faces)

def create_context_mesh(vertices_np, lb_mesh):
    """Create a plain gray mesh for context buildings"""
    # Triangulate the mesh for context
    triangulated_faces = []
    
    for face in lb_mesh.faces:
        if len(face) == 3:
            triangulated_faces.append(list(face))
        elif len(face) == 4:
            # Convert quad to two triangles
            triangulated_faces.append([face[0], face[1], face[2]])
            triangulated_faces.append([face[0], face[2], face[3]])
    
    faces_np = np.array(triangulated_faces)
    
    # Create gray context mesh
    context_mesh = trimesh.Trimesh(vertices=vertices_np, faces=faces_np)
    # Set all faces to light gray with some transparency
    gray_color = [180, 180, 180, 200]  # Light gray with some transparency
    context_mesh.visual.face_colors = np.tile(gray_color, (len(context_mesh.faces), 1))
    
    return context_mesh

def create_solar_path_visualization(sunpath, scale=500):
    """Create visualization geometry for annual solar paths"""
    paths = []
    
    # Key dates for solar path visualization
    dates = [
        (6, 21),  # Summer solstice (orange)
        (12, 21), # Winter solstice (blue)
        (3, 21),  # Spring equinox (green)
        (9, 21)   # Fall equinox (yellow)
    ]
    
    path_colors = [
        [255, 128, 0, 255],  # Orange
        [0, 128, 255, 255],  # Blue
        [0, 255, 0, 255],    # Green
        [255, 255, 0, 255]   # Yellow
    ]
    
    for (month, day), color in zip(dates, path_colors):
        day_points = []
        # Sample sun positions throughout the day
        for hour in range(24):
            for minute in [0, 30]:
                dt = DateTime(month, day, hour, minute)
                sun = sunpath.calculate_sun_from_date_time(dt)
                if sun.altitude > 0:  # Only include daytime positions
                    # Convert altitude/azimuth to 3D position
                    alt_rad = math.radians(sun.altitude)
                    azm_rad = math.radians(sun.azimuth - 180)  # Align with south
                    
                    # Coordinate system aligned with solar analysis:
                    # X is East(+) to West(-)
                    # Y is South(+) to North(-)
                    # Z is Up(+)
                    x = scale * math.cos(alt_rad) * math.sin(azm_rad)
                    y = scale * math.cos(alt_rad) * math.cos(azm_rad)
                    z = scale * math.sin(alt_rad)
                    day_points.append([x, y, z])
        
        # Create path segments
        for i in range(len(day_points) - 1):
            # Create cylinder along path segment
            direction = np.array(day_points[i+1]) - np.array(day_points[i])
            length = np.linalg.norm(direction)
            
            # Create cylinder mesh
            cylinder = trimesh.creation.cylinder(
                radius=2.0,  # Increased radius from 0.5 to 2.0 for better visibility
                height=length,
                sections=8
            )
            
            # Orient cylinder along path
            direction = direction / length
            rot = trimesh.geometry.align_vectors([0, 0, 1], direction)
            cylinder.apply_transform(rot)
            
            # Position cylinder
            trans = trimesh.transformations.translation_matrix(day_points[i])
            cylinder.apply_transform(trans)
            
            # Apply color
            cylinder.visual.face_colors = color
            paths.append(cylinder)
    
    return paths

def main():
    # --- 1. Load Climate Data ---
    epw = EPW(local_epw)
    location = epw.location
    # Adjust direct_normal_radiation to annual values
    # Current values are hourly, multiply by hours or average
    solar_data = [val * 0.1 for val in epw.direct_normal_radiation]  # Scale down values

    # Alternative: Use global horizontal radiation
    solar_data = epw.global_horizontal_radiation

    # --- 2. Compute Solar Position ---
    sunpath = Sunpath(location.latitude, location.longitude, location.time_zone)

    # Get sun positions for each hour of the year (only when sun is up)
    solar_positions = []
    for month in range(6, 13):
        for day in [7, 14, 21]:  # Sample days throughout the month
            for hour in range(6, 19):  # Daylight hours
                for minute in [0, 30]:  # Half-hour samples
                    dt = DateTime(month, day, hour, minute)
                    sun = sunpath.calculate_sun_from_date_time(dt)
                    if sun.altitude > 0:  # Only include daytime positions
                        solar_positions.append(sun)

    print(f"Generated {len(solar_positions)} sun positions for analysis")

    # Add this debug check
    if hasattr(solar_positions[0], 'sun_vector_reversed'):
        print("Using sun_vector_reversed")
    else:
        print("WARNING: sun_vector_reversed not found, using altitude/azimuth")
        # Alternative approach if needed

    # Add a check for data length
    print(f"Sun positions: {len(solar_positions)}, Solar data points: {len(solar_data)}")

    # --- 3. Load Mesh Geometry ---
    model = rhino3dm.File3dm.Read(local_mesh)
    if not model:
        raise RuntimeError(f"Failed to read 3DM file: {local_mesh}")

    # Get all meshes from the model
    all_meshes = []
    for obj in model.Objects:
        geom = obj.Geometry
        if isinstance(geom, rhino3dm.Mesh):
            name = obj.Attributes.Name if obj.Attributes.Name else "unnamed"
            all_meshes.append((geom, name))
    
    if not all_meshes:
        raise RuntimeError("No meshes found in the model file")
    
    # Process the LAST mesh as the target (example_image) and the rest as context
    target_meshes = [all_meshes[-1][0]]  # Get the last mesh
    context_meshes = [mesh[0] for mesh in all_meshes[:-1]]  # All except the last mesh
    
    print(f"Using the last mesh '{all_meshes[-1][1]}' as target, and {len(context_meshes)} other meshes as context")
    print(f"Found {len(target_meshes)} target meshes and {len(context_meshes)} context meshes")
    
    # Process target meshes for analysis
    target_vertices, target_faces = process_meshes(target_meshes)
    
    # Process context meshes (only needed for shadow casting)
    context_vertices, context_faces = process_meshes(context_meshes)
    
    # Create Ladybug meshes for analysis
    target_lb_mesh = create_ladybug_mesh(target_vertices, target_faces)
    context_lb_mesh = create_ladybug_mesh(context_vertices, context_faces)
    
    # --- 4. Compute Solar Radiation (with multiprocessing) ---
    # Calculate face centroids and normals for target mesh
    face_centroids = target_lb_mesh.face_centroids
    face_normals = target_lb_mesh.face_normals
    
    # Prepare arguments for parallel processing
    args_list = [(i, face_centroids[i], face_normals[i], solar_positions, solar_data) 
                for i in range(len(target_lb_mesh.faces))]
    
    # Calculate radiation for target mesh only
    with mp.Pool(processes=max(1, mp.cpu_count()-1)) as pool:
        radiation_values = list(tqdm(
            pool.imap(calculate_radiation, args_list),
            total=len(args_list),
            desc="Processing target faces"
        ))
    
    # After calculating radiation values for target mesh
    validation_results = validate_solar_analysis(radiation_values, target_lb_mesh)
    
    # Generate colors for target mesh
    min_radiation, max_radiation = min(radiation_values), max(radiation_values)
    norm_radiation = [(val - min_radiation) / (max_radiation - min_radiation) 
                     if max_radiation > min_radiation else 0 for val in radiation_values]
    
    cmap = plt.get_cmap("jet")
    target_colors = [(int(r * 255), int(g * 255), int(b * 255), 255) 
                    for r, g, b in [cmap(val)[:3] for val in norm_radiation]]
    
    # --- After calculating radiation values, BEFORE creating meshes ---
    # Find the faces with high radiation (top 10%)
    sorted_radiation = sorted(radiation_values, reverse=True)
    high_threshold = sorted_radiation[int(len(sorted_radiation) * 0.1)]  # Top 10% threshold
    
    # Find average position and normal of high-radiation faces
    high_rad_positions = []
    high_rad_normals = []
    for i, rad in enumerate(radiation_values):
        if rad >= high_threshold:
            high_rad_positions.append([face_centroids[i].x, face_centroids[i].y, face_centroids[i].z])
            high_rad_normals.append([face_normals[i].x, face_normals[i].y, face_normals[i].z])
    
    # --- NOW create colored target mesh and context mesh ---
    target_trimesh = triangulate_and_color_mesh(target_lb_mesh, target_colors)
    context_vertices_np = np.array([[v.x, v.y, v.z] for v in context_lb_mesh.vertices])
    context_trimesh = create_context_mesh(context_vertices_np, context_lb_mesh)
    
    # --- Now you can use target_trimesh.bounds ---
    bounds = target_trimesh.bounds
    model_center = np.mean(bounds, axis=0)
    model_height = bounds[1][2]  # Highest Z coordinate
    clearance = 20  # Add some space above model

    # Calculate average position and normal of high radiation faces
    high_rad_center = np.mean(high_rad_positions, axis=0) if high_rad_positions else model_center
    high_rad_normal = np.mean(high_rad_normals, axis=0) if high_rad_normals else [0, 1, 0]
    high_rad_normal = high_rad_normal / np.linalg.norm(high_rad_normal)  # Normalize

    # Position for solar path above the high radiation area
    high_rad_point = [
        high_rad_center[0],      # X at high radiation center
        high_rad_center[1],      # Y at high radiation center
        model_height + clearance # Z above the model
    ]
    
    # Mirror the high radiation center across the model center
    # opposite_point = [
    #     2 * model_center[0] - high_rad_center[0],
    #     2 * model_center[1] - high_rad_center[1],
    #     model_height + clearance
    # ]
    
    # Vector from model center to high radiation center
    vec = np.array(high_rad_center[:2]) - np.array(model_center[:2])

    # Move to the other side by adding this vector to the model center
    other_side_point = [
        model_center[0] - vec[0],
        model_center[1] - vec[1],
        model_height + clearance
    ]
    
    # Generate solar paths
    print("Generating solar path visualization...")
    solar_paths = create_solar_path_visualization(sunpath, scale=500)
    
    # First, position paths on opposite side of the model from high radiation area
    for path in solar_paths:
        # Use other_side_point instead of high_rad_point
        translation = trimesh.transformations.translation_matrix(other_side_point)
        path.apply_transform(translation)

    # Then, rotate all paths 180 degrees around the Z-axis at model center
    rotation_matrix = trimesh.transformations.rotation_matrix(
        angle=np.pi,  # 180 degrees in radians
        direction=[0, 1, 0],  # Z-axis
        point=model_center  # Rotate around model center
    )

    # Apply rotation to all paths
    for path in solar_paths:
        path.apply_transform(rotation_matrix)
    
    # Now combine all meshes with correctly positioned solar paths
    all_meshes = [target_trimesh, context_trimesh]
    all_meshes.extend(solar_paths)
    combined_mesh = trimesh.util.concatenate(all_meshes)
    
    # Export combined model
    combined_mesh.export(output_glb)
    print(f"✅ Model with solar paths saved as {output_glb}")
    
    # --- 5. Export Legend Image ---
    # Create a 2D legend image using matplotlib
    print("Generating 2D legend image...")
    
    # Generate a color legend image using matplotlib
    fig, ax = plt.subplots(figsize=(2, 6))
    ax.set_visible(False)  # Hide the main axes, we just want the colorbar
    
    norm = plt.Normalize(min_radiation, max_radiation)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    
    # Pass the axes to the colorbar
    cbar = plt.colorbar(sm, ax=ax)  
    cbar.set_label('Radiation (kWh/m²)')
    
    # Add more ticks for better readability
    cbar.set_ticks(np.linspace(min_radiation, max_radiation, 10))
    cbar.set_ticklabels([f"{val:.0f}" for val in np.linspace(min_radiation, max_radiation, 10)])
    
    # Add a title with statistics
    plt.title('Solar Radiation\n(kWh/m²)')
    plt.figtext(0.1, 0.01, f"N/S ratio: {validation_results[0]:.2f}\nCV: {validation_results[1]:.2f}", fontsize=8)
    
    # Add solar path legend
    plt.figtext(0.1, 0.2, 'Solar Paths:', fontsize=8)
    plt.figtext(0.1, 0.17, '■ Summer Solstice', color='orange', fontsize=8)
    plt.figtext(0.1, 0.14, '■ Winter Solstice', color='blue', fontsize=8)
    plt.figtext(0.1, 0.11, '■ Spring Equinox', color='green', fontsize=8)
    plt.figtext(0.1, 0.08, '■ Fall Equinox', color='yellow', fontsize=8)
    
    # Save the image with better resolution
    legend_image = output_glb.replace('.glb', '_legend.png')
    plt.savefig(legend_image, bbox_inches='tight', dpi=300)
    print(f"✅ Legend image saved as {legend_image}")

if __name__ == "__main__":
    main()