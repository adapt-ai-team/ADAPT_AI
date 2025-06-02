import rhino3dm
import compute_rhino3d
import compute_rhino3d.Util
import requests
import os
import json
import traceback

# Rhino Compute URL
RHINO_COMPUTE_URL = "http://localhost:5000"

# File paths
GEOMETRY_PATH = r"D:\spz_analysis2\\newyork.3dm"
SCALED_GEOMETRY_PATH = r"D:\spz_analysis2\\newyork_scaled.3dm"
SCALE_FACTOR = 2.0  # Scaling factor

# Function to check if files exist
def check_files():
    print("Checking file paths:")
    if not os.path.exists(GEOMETRY_PATH):
        raise FileNotFoundError(f"Error: Geometry file '{GEOMETRY_PATH}' is missing!")
    print("✅ Geometry file found!")

# Function to test Rhino Compute connection
def test_rhino_compute():
    try:
        response = requests.get(f"{RHINO_COMPUTE_URL}/version")
        print("Rhino Compute Response:", response.text)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print("Error connecting to Rhino Compute:", e)
        return False

# Function to load .3dm file and extract geometry
def load_geometry():
    try:
        print("📂 Loading 3DM File:", GEOMETRY_PATH)
        model = rhino3dm.File3dm.Read(GEOMETRY_PATH)
        
        if not model:
            raise ValueError("❌ Failed to load the 3DM file!")

        # Extract objects (Meshes, Breps, or Curves)
        objects = [obj.Geometry for obj in model.Objects]
        if not objects:
            raise ValueError("❌ No geometry found in the 3DM file!")

        print(f"✅ Found {len(objects)} objects in the file.")
        return objects

    except Exception as e:
        print("❌ Error loading geometry:", e)
        return None

# Function to scale geometry using Rhino Compute
def scale_geometry(objects):
    try:
        print("🔹 Scaling Geometry via Rhino Compute...")

        # Define the scaling transformation
        scale_transform = rhino3dm.Transform.Scale(rhino3dm.Point3d(0, 0, 0), SCALE_FACTOR)

        # Serialize geometry using compute_rhino3d.Geometry.encode
        serialized_objects = [compute_rhino3d.Geometry.encode(obj) for obj in objects]

        # Send transformation request to Rhino Compute
        response = requests.post(
            f"{RHINO_COMPUTE_URL}/rhino/geometry/transform",
            json={
                "transforms": [scale_transform.ToFloatArray()] * len(serialized_objects),  # Correct transformation format
                "geometry": serialized_objects
            }
        )

        # Process response
        if response.status_code == 200:
            scaled_data = response.json()
            scaled_objects = [compute_rhino3d.Geometry.decode(obj) for obj in scaled_data]
            print(f"✅ Successfully scaled {len(scaled_objects)} objects.")
            return scaled_objects
        else:
            print("❌ Error:", response.status_code)
            print("🔍 Rhino Compute Response:", response.text)
            return None

    except Exception as e:
        print("❌ Error during scaling:", e)
        print(traceback.format_exc())
        return None

# Function to save the scaled geometry into a new .3dm file
def save_scaled_geometry(scaled_objects):
    try:
        print("💾 Saving Scaled Geometry...")

        # Create a new 3DM model
        model = rhino3dm.File3dm()
        for obj in scaled_objects:
            model.Objects.Add(obj)

        # Save file
        model.Write(SCALED_GEOMETRY_PATH, 6)  # Rhino 6 file format
        print(f"✅ Scaled geometry saved to {SCALED_GEOMETRY_PATH}")

    except Exception as e:
        print("❌ Error saving file:", e)
        print(traceback.format_exc())

# Run the script
if __name__ == "__main__":
    try:
        print("Requests module imported successfully.")

        # Step 1: Check files
        check_files()

        # Step 2: Test Rhino Compute
        if not test_rhino_compute():
            raise ConnectionError("Rhino Compute is not reachable. Make sure it is running.")

        # Step 3: Load geometry from .3dm file
        objects = load_geometry()
        if not objects:
            raise ValueError("No geometry found in the 3DM file.")

        # Step 4: Scale the geometry
        scaled_objects = scale_geometry(objects)
        if not scaled_objects:
            raise ValueError("Scaling failed.")

        # Step 5: Save the scaled geometry
        save_scaled_geometry(scaled_objects)

    except Exception as e:
        print("❌ Fatal Error:")
        print(traceback.format_exc())
