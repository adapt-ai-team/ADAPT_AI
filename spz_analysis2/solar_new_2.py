import rhino3dm
import numpy as np
import trimesh
import matplotlib.pyplot as plt
from ladybug.epw import EPW
from ladybug.sunpath import Sunpath
from ladybug.dt import DateTime
from ladybug_geometry.geometry3d.mesh import Mesh3D
from ladybug_geometry.geometry3d.pointvector import Point3D
import time
import multiprocessing as mp
from tqdm import tqdm

# --- Configuration ---
epw_file = r"D:\spz_analysis2\newyork.epw"  # Path to EPW weather file
mesh_file = r"D:\spz_pipeline\pipeline_outputs\merged_model.3dm"  # Path to 3DM mesh file
output_glb = r"D:\spz_pipeline\pipeline_outputs\solar_radiation_example_image.glb"  # Output .glb file
offset_dist = 0.1  # Offset for analysis points

def calculate_radiation(args):
    i, center, normal, sun_positions, solar_data = args
    total_radiation = 0
    for j, sun_pos in enumerate(sun_positions):
        sun_vector = -1 * sun_pos.sun_vector_reversed
        angle_factor = max(0, normal.dot(sun_vector))
        radiation_value = solar_data[j % len(solar_data)] * angle_factor
        total_radiation += radiation_value
    return total_radiation

def validate_solar_analysis(radiation_values, lb_mesh):
    print("\n=== VALIDATION CHECKS ===")
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
        print(f"North-facing surfaces avg radiation: {north_avg:.1f}")
        print(f"South-facing surfaces avg radiation: {south_avg:.1f}")
        print(f"North/South ratio: {north_south_ratio:.2f} (should be < 1.0)")
        print(f"Plausibility: {'✅ GOOD' if north_south_ratio < 0.8 else '❌ SUSPICIOUS'}")
    print(f"Radiation range: {min(radiation_values):.1f} - {max(radiation_values):.1f} kWh/m²")
    expected_min = 100
    expected_max = 2000
    print(f"Range check: {'✅ GOOD' if min(radiation_values) > expected_min and max(radiation_values) < expected_max else '❌ SUSPICIOUS'}")
    std_dev = np.std(radiation_values)
    mean_val = np.mean(radiation_values)
    cv = std_dev / mean_val
    print(f"Statistical variation (CV): {cv:.2f}")
    print(f"Variation check: {'✅ GOOD' if cv < 0.8 else '❌ HIGH VARIATION'}")
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

def main():
    # --- 1. Load Climate Data ---
    epw = EPW(epw_file)
    location = epw.location
    solar_data = [val * 0.1 for val in epw.direct_normal_radiation]
    solar_data = epw.global_horizontal_radiation

    # --- 2. Compute Solar Position ---
    sunpath = Sunpath(location.latitude, location.longitude, location.time_zone)
    solar_positions = []
    for month in range(6, 13):
        for day in [7, 14, 21]:
            for hour in range(6, 19):
                for minute in [0, 30]:
                    dt = DateTime(month, day, hour, minute)
                    sun = sunpath.calculate_sun_from_date_time(dt)
                    if sun.altitude > 0:
                        solar_positions.append(sun)
    print(f"Generated {len(solar_positions)} sun positions for analysis")

    # --- 3. Load Mesh Geometry ---
    model = rhino3dm.File3dm.Read(mesh_file)
    if not model:
        raise RuntimeError(f"Failed to read 3DM file: {mesh_file}")
    rhino_meshes = [obj.Geometry for obj in model.Objects if isinstance(obj.Geometry, rhino3dm.Mesh)]
    if not rhino_meshes:
        raise RuntimeError("No mesh found in the file.")
    print(f"Found {len(rhino_meshes)} meshes in the file")

    # Merging all meshes before analysis
    print("Merging all meshes before analysis...")
    all_vertices = []
    all_faces = []
    vertex_offset = 0
    for rhino_mesh in rhino_meshes:
        vertices = [(pt.X, pt.Y, pt.Z) for pt in rhino_mesh.Vertices]
        all_vertices.extend(vertices)
        for i in range(rhino_mesh.Faces.Count):
            face = rhino_mesh.Faces[i]
            if face[2] == face[3]:  # Triangle
                all_faces.append([face[0] + vertex_offset, face[1] + vertex_offset, face[2] + vertex_offset])
            else:  # Quad
                all_faces.append([face[0] + vertex_offset, face[1] + vertex_offset, face[2] + vertex_offset, face[3] + vertex_offset])
        vertex_offset += len(vertices)
    combined_mesh = trimesh.Trimesh(vertices=np.array(all_vertices), faces=np.array(all_faces))
    print(f"Created combined mesh with {len(combined_mesh.vertices)} vertices and {len(combined_mesh.faces)} faces")

    # Convert combined mesh to Ladybug format
    lb_vertices = [Point3D(*vertex) for vertex in combined_mesh.vertices]
    lb_faces = []
    for face in combined_mesh.faces:
        if len(face) == 3:
            lb_faces.append([lb_vertices[face[0]], lb_vertices[face[1]], lb_vertices[face[2]]])
        elif len(face) == 4:
            lb_faces.append([lb_vertices[face[0]], lb_vertices[face[1]], lb_vertices[face[2]], lb_vertices[face[3]]])
    lb_mesh = Mesh3D.from_face_vertices(lb_faces)
    print(f"Created Ladybug mesh with {len(lb_mesh.faces)} faces")

    # --- 4. Compute Solar Radiation (with multiprocessing) ---
    face_centroids = lb_mesh.face_centroids
    face_normals = lb_mesh.face_normals
    print("\nCalculating solar radiation using multiprocessing...")
    start_time = time.time()
    args_list = [(i, face_centroids[i], face_normals[i], solar_positions, solar_data) for i in range(len(lb_mesh.faces))]
    with mp.Pool(processes=max(1, mp.cpu_count()-1)) as pool:
        radiation_values = list(tqdm(pool.imap(calculate_radiation, args_list), total=len(args_list), desc="Processing faces", bar_format="{desc}: {percentage:3.1f}% |{bar}| {n_fmt}/{total_fmt} faces [ETA: {remaining}, {rate_fmt}]"))
    print(f"\nCompleted radiation analysis in {time.time() - start_time:.1f} seconds")

    # After calculating radiation_values
    validation_results = validate_solar_analysis(radiation_values, lb_mesh)
    min_radiation, max_radiation = min(radiation_values), max(radiation_values)
    norm_radiation = [(val - min_radiation) / (max_radiation - min_radiation) if max_radiation > min_radiation else 0 for val in radiation_values]
    cmap = plt.get_cmap("jet")
    colors = [cmap(val)[:3] for val in norm_radiation]
    colors = [(int(r * 255), int(g * 255), int(b * 255), 255) for r, g, b in colors]

    # --- 5. Export as .glb File ---
    import os
    output_dir = os.path.dirname(output_glb)
    main_output = os.path.join(output_dir, "solar_radiation_example_image.glb")
    lb_vertices_np = np.array([[v.x, v.y, v.z] for v in lb_mesh.vertices])
    triangulated_faces = []
    adjusted_colors = []
    for i, face in enumerate(lb_mesh.faces):
        if len(face) == 3:
            triangulated_faces.append(list(face))
            adjusted_colors.append(colors[i])
        elif len(face) == 4:
            triangulated_faces.append([face[0], face[1], face[2]])
            triangulated_faces.append([face[0], face[2], face[3]])
            adjusted_colors.append(colors[i])
            adjusted_colors.append(colors[i])
    lb_faces_np = np.array(triangulated_faces)
    mesh = trimesh.Trimesh(vertices=lb_vertices_np, faces=lb_faces_np)
    mesh.visual.face_colors = adjusted_colors
    mesh.export(main_output)
    print(f"✅ Model saved as {main_output}")

    # Create standalone legend using a different method
    print("Creating color legend...")
    legend_mesh = trimesh.creation.box(extents=[10, 1, 50])
    print("Generating 2D legend image...")
    fig, ax = plt.subplots(figsize=(2, 6))
    ax.set_visible(False)
    norm = plt.Normalize(min_radiation, max_radiation)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax)
    cbar.set_label('Radiation (kWh/m²)')
    cbar.set_ticks(np.linspace(min_radiation, max_radiation, 10))
    cbar.set_ticklabels([f"{val:.0f}" for val in np.linspace(min_radiation, max_radiation, 10)])
    plt.title('Solar Radiation\n(kWh/m²)')
    plt.figtext(0.1, 0.01, f"N/S ratio: {validation_results[0]:.2f}\nCV: {validation_results[1]:.2f}", fontsize=8)
    plt.savefig(output_glb.replace('.glb', '_legend.png'), bbox_inches='tight', dpi=300)
    print(f"✅ Legend image saved as {output_glb.replace('.glb', '_legend.png')}")
    validate_solar_analysis(radiation_values, lb_mesh)

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()