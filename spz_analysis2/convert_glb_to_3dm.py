import rhino3dm
import trimesh
import numpy as np
import os

# 📂 Define file paths
INPUT_GLB_PATH = r"D:\spz_pipeline\pipeline_outputs\example_image.glb"  # ✅ Ensure correct input file
OUTPUT_3DM_PATH = r"D:\spz_pipeline\pipeline_outputs\example_image.3dm"  # ✅ Ensure correct output file

def convert_glb_to_3dm(glb_path, output_3dm_path):
    # 🔍 Check if input file exists
    if not os.path.exists(glb_path):
        print(f"❌ Error: Input file `{glb_path}` not found!")
        return
    
    print(f"🔄 Converting `{glb_path}` → `{output_3dm_path}`...")
    
    try:
        # Load the .glb file
        scene = trimesh.load(glb_path)

        # Create a new Rhino 3DM file
        model = rhino3dm.File3dm()

        # Process each mesh in the scene
        for mesh_name, geometry in scene.geometry.items():
            print(f"Processing mesh: {mesh_name}")

            # Convert trimesh mesh to Rhino mesh
            rhino_mesh = rhino3dm.Mesh()

            # Add vertices with Y-Z axis swap
            vertices = geometry.vertices.copy()
            vertices[:, [1, 2]] = vertices[:, [2, 1]]  # Swap Y and Z coordinates (GLB Y-up → Rhino Z-up)

            # Add transformed vertices to Rhino mesh
            for vertex in vertices:
                rhino_mesh.Vertices.Add(float(vertex[0]), float(vertex[1]), float(vertex[2]))

            # Add faces
            for face in geometry.faces:
                if len(face) == 3:
                    rhino_mesh.Faces.AddFace(int(face[0]), int(face[2]), int(face[1]))  # Reverse orientation
                elif len(face) == 4:
                    rhino_mesh.Faces.AddFace(int(face[0]), int(face[3]), int(face[2]), int(face[1]))  # Reverse orientation for quads

            # Compute mesh normals
            rhino_mesh.Normals.ComputeNormals()
            rhino_mesh.Compact()

            # Add the mesh to the Rhino 3DM model
            model.Objects.AddMesh(rhino_mesh)
            print(f"✅ Added mesh with {len(rhino_mesh.Vertices)} vertices and {len(rhino_mesh.Faces)} faces")

        # Save the file
        model.Write(output_3dm_path, 5)
        print(f"✅ Conversion successful! Saved as `{output_3dm_path}`")

    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}")

# 🚀 Run the conversion process
if __name__ == "__main__":
    convert_glb_to_3dm(INPUT_GLB_PATH, OUTPUT_3DM_PATH)
