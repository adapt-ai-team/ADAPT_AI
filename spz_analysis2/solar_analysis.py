import os
import sys
import json
import numpy as np

# Import required packages after dependency check
import trimesh
from ladybug.epw import EPW
from ladybug_radiance.sky.cumulative import CumulativeSkyMatrix
from ladybug_geometry.geometry3d.pointvector import Point3D
from ladybug_radiance.visualize.raddome import RadiationDome
from ladybug_rhino.fromgeometry import from_point3d

### USER INPUTS ###
EPW_FILE_PATH = "D:\spz_analysis2\\newyork.epw"  # Modify this path
OUTPUT_GLB_PATH = "D:\spz_analysis2\solar_radiation_mesh.glb"  # Modify this path

### 1️⃣ Load EPW File ###
print("Loading EPW file...")
epw = EPW(EPW_FILE_PATH)

### 2️⃣ Generate Cumulative Sky Matrix ###
print("Generating Sky Matrix...")
sky_mtx = CumulativeSkyMatrix.from_epw(epw, north=0)

### 3️⃣ Define Radiation Dome Parameters ###
print("Setting up Radiation Dome parameters...")
az_count = 36  # Horizontal divisions (lower for faster computation)
alt_count = 12  # Vertical divisions
scale = 1  # Scale factor
center_pt = Point3D(0, 0, 0)  # Center point of the dome

# Create Radiation Dome object
rad_dome = RadiationDome(sky_mtx, None, az_count, alt_count, None, False, center_pt, 100, None)

### 4️⃣ Extract Radiation Data ###
print("Extracting radiation data...")
radiation_values = np.array(rad_dome.total_values)  # Convert list to NumPy array
max_radiation = np.max(radiation_values)
min_radiation = np.min(radiation_values)

# Normalize radiation values (0 to 1 for coloring)
normalized_values = (radiation_values - min_radiation) / (max_radiation - min_radiation)

### 5️⃣ Generate 3D Mesh ###
print("Generating 3D radiation mesh...")
vertices = []
faces = []
colors = []

for i, vec in enumerate(rad_dome.dome_vectors(az_count, alt_count)):
    pt = from_point3d(vec)
    vertices.append([pt.x, pt.y, pt.z])

    # Assign color based on radiation value (red = high, blue = low)
    value = normalized_values[i]
    colors.append([value, 0, 1 - value, 1])  # RGBA format (Gradient: Blue → Red)

# Create faces by connecting neighboring points
for i in range(len(vertices) - az_count - 1):
    if (i + 1) % az_count == 0:
        continue  # Skip connecting edges
    faces.append([i, i + 1, i + az_count])
    faces.append([i + 1, i + az_count, i + az_count + 1])

# Convert to Trimesh object
mesh = trimesh.Trimesh(vertices=vertices, faces=faces, vertex_colors=colors)

### 6️⃣ Export Mesh to GLB ###
print(f"Exporting mesh to {OUTPUT_GLB_PATH}...")
mesh.export(OUTPUT_GLB_PATH, file_type="glb")
print("✅ GLB file created successfully!")

