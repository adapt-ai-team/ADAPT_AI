#05.05.2025


from flask import Flask, render_template, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import subprocess
import threading
import os
import time
from pathlib import Path
import json
import math
from pygltflib import GLTF2
from werkzeug.serving import WSGIRequestHandler

# Get the current directory and project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))  # Go up two levels

# 📂 Define Directories using relative paths
PIPELINE_FOLDER = CURRENT_DIR
SPZ_FOLDER = os.path.join(PROJECT_ROOT, "spz")
ANALYSIS_FOLDER = os.path.join(PROJECT_ROOT, "spz_analysis2")

# 📌 Define Script Paths using relative paths
EXAMPLE_SCRIPT = os.path.join(PROJECT_ROOT, "spz", "trellis-spz", "code", "example.py")
CONVERT_SCRIPT = os.path.join(ANALYSIS_FOLDER, "osm_fetch_convert_to_3dm.py")
SOLAR_SCRIPT = os.path.join(ANALYSIS_FOLDER, "solar_new.py")

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})  # Enable CORS for all routes

# Add this helper function at the top level of the file, after the imports
def verify_and_create_directories():
    """Verify directories exist and create if necessary"""
    os.makedirs(PIPELINE_FOLDER, exist_ok=True)
    print(f"📁 Pipeline folder path: {PIPELINE_FOLDER}")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/run_pipeline', methods=['POST'])
def run_pipeline_endpoint():
    try:
        if 'image' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image file uploaded'}), 400
        
        image_file = request.files['image']
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not latitude or not longitude:
            return jsonify({'status': 'error', 'message': 'Missing latitude or longitude'}), 400

        # Ensure directory exists
        verify_and_create_directories()

        # Create absolute paths
        image_path = os.path.abspath(os.path.join(PIPELINE_FOLDER, "input_image.jpg"))
        latlon_path = os.path.abspath(os.path.join(PIPELINE_FOLDER, "latlon.txt"))

        # Save coordinates to file with comma separator
        with open(latlon_path, "w") as f:
            f.write(f"{latitude},{longitude}")

        # Save uploaded image
        image_file.save(image_path)
        print(f"📸 Saved image to: {image_path}")

        def execute_pipeline():
            try:
                print(f"🔄 Running pipeline with image path: {image_path}")
                
                # Build commands without timeout
                example_cmd = [
                    'conda', 'run', '-n', 'trellis',
                    'python', EXAMPLE_SCRIPT,
                    '--input', image_path
                ]
                print(f"🚀 Running example script...")
                
                # Run processes without timeout
                subprocess.run(
                    example_cmd,
                    shell=False,
                    check=True,
                    cwd=PIPELINE_FOLDER
                )

                print("✅ Example Script Finished. Running OSM Conversion...")
                subprocess.run(
                    ['conda', 'run', '-n', 'ladybug_env', 'python', CONVERT_SCRIPT, latitude, longitude],
                    shell=False,
                    check=True,
                    cwd=PIPELINE_FOLDER
                )

                print("🔆 Running Solar Radiation Analysis...")
                subprocess.run(
                    ['conda', 'run', '-n', 'ladybug_env', 'python', SOLAR_SCRIPT],
                    shell=False,
                    check=True,
                    cwd=PIPELINE_FOLDER
                )
                return True

            except subprocess.CalledProcessError as e:
                print(f"❌ Pipeline Error: {e}")
                return False
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                return False

        success = execute_pipeline()
        
        if success:
            return jsonify({'status': 'success', 'message': 'Pipeline completed successfully!'})
        else:
            return jsonify({'status': 'error', 'message': 'Pipeline execution failed'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/solar_radiation_example_image.glb')
def serve_glb():
    try:
        response = send_from_directory(PIPELINE_FOLDER, 'solar_radiation_example_image.glb', 
                                     mimetype='model/gltf-binary')
        # Add CORS and cache control headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404

def fix_model_orientation():
    """Fix the orientation of the GLB file by swapping Y and Z axes"""
    glb_path = os.path.join(PIPELINE_FOLDER, "solar_radiation_example_image.glb")
    
    try:
        # Load the GLB file
        gltf = GLTF2.load(glb_path)
        
        # Iterate through all nodes and apply rotation
        for node in gltf.nodes:
            if hasattr(node, 'matrix'):
                continue
            
            # Initialize rotation if it doesn't exist
            if not hasattr(node, 'rotation'):
                node.rotation = [0, 0, 0, 1]
            
            # Apply 90-degree rotation around X-axis
            x, y, z, w = node.rotation
            new_w = w * math.cos(math.pi/4) - x * math.sin(math.pi/4)
            new_x = w * math.sin(math.pi/4) + x * math.cos(math.pi/4)
            node.rotation = [new_x, y, z, new_w]
        
        # Save the modified GLB
        gltf.save(glb_path)
        return True
        
    except Exception as e:
        print(f"Error fixing model orientation: {e}")
        return False

@app.errorhandler(500)
def handle_500(e):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error occurred'
    }), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({
        'status': 'error',
        'message': 'Resource not found'
    }), 404

if __name__ == '__main__':
    # Print paths for debugging
    print(f"Current Directory: {CURRENT_DIR}")
    print(f"Pipeline Folder: {PIPELINE_FOLDER}")
    print(f"Analysis Folder: {ANALYSIS_FOLDER}")
    print(f"Example Script: {EXAMPLE_SCRIPT}")
    print(f"Convert Script: {CONVERT_SCRIPT}")
    print(f"Solar Script: {SOLAR_SCRIPT}")
    
    # Enable longer timeout
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    app.run(debug=False, host='0.0.0.0', port=5000)