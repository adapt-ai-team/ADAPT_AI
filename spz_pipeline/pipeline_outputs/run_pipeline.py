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
import shutil
import time
import base64

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

# Add/update the static folder configuration
app = Flask(__name__, 
            static_folder=os.path.join(PIPELINE_FOLDER, 'static'),
            template_folder=os.path.join(PIPELINE_FOLDER, 'templates'))
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Allow all origins for development
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

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

# Add these new route handlers after the existing routes
@app.route('/create_step', methods=['POST', 'OPTIONS'])
def create_step():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response

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

        # Save uploaded image and coordinates
        image_file.save(image_path)
        with open(latlon_path, "w") as f:
            f.write(f"{latitude},{longitude}")

        print(f"📸 Saved image to: {image_path}")

        try:
            # Run example.py
            example_cmd = [
                'conda', 'run', '-n', 'trellis',
                'python', EXAMPLE_SCRIPT,
                '--input', image_path
            ]
            print("🚀 Running example script...")
            subprocess.run(example_cmd, shell=False, check=True, cwd=PIPELINE_FOLDER)

            # Run OSM conversion
            print("🌍 Running OSM conversion...")
            subprocess.run(
                ['conda', 'run', '-n', 'ladybug_env', 'python', CONVERT_SCRIPT, latitude, longitude],
                shell=False,
                check=True,
                cwd=PIPELINE_FOLDER
            )

            return jsonify({
                'status': 'success',
                'message': 'Create step completed',
                'modelUrl': 'http://localhost:5000/merged_model.glb'
            })

        except subprocess.CalledProcessError as e:
            print(f"❌ Create step error: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    except Exception as e:
        print(f"❌ Unexpected error in create step: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_step', methods=['POST'])
def save_step():
    try:
        data = request.json
        model_state = data.get('modelState', {})
        
        # Check if modelState has the expected structure
        if 'meshes' not in model_state:
            return jsonify({
                'status': 'error', 
                'message': 'Invalid model state format'
            }), 400
            
        # Load the GLB file
        model_path = os.path.join(PIPELINE_FOLDER, "merged_model.glb")
        if not os.path.exists(model_path):
            return jsonify({
                'status': 'error',
                'message': 'Model file not found'
            }), 404
            
        gltf = GLTF2().load(model_path)
        
        # Apply transformations from modelState
        for mesh_name, transform in model_state['meshes'].items():
            # Update mesh transformations in the GLB file
            node = next((n for n in gltf.nodes if n.name == mesh_name), None)
            if node:
                print(f"Updating node {mesh_name} with transform: {transform}")
                if 'position' in transform:
                    node.translation = transform['position']
                if 'rotation' in transform:
                    node.rotation = transform['rotation']
                if 'scale' in transform:
                    node.scale = transform['scale']
        
        # Save the modified model
        gltf.save(model_path)
        
        print(f"✅ Model saved with transformations to: {model_path}")
        
        return jsonify({
            'status': 'success',
            'message': 'Model saved with transformations',
            'modelUrl': f'http://localhost:5000/merged_model.glb?t={int(time.time())}'
        })

    except Exception as e:
        print(f"❌ Error in save step: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/run_step', methods=['POST'])
def run_step():
    try:
        merged_model_path = os.path.join(PIPELINE_FOLDER, "merged_model.glb")
        if not os.path.exists(merged_model_path):
            return jsonify({
                'status': 'error',
                'message': 'Merged model not found'
            }), 400

        print("🔆 Running Solar Radiation Analysis...")
        subprocess.run(
            ['conda', 'run', '-n', 'ladybug_env', 'python', SOLAR_SCRIPT],
            shell=False,
            check=True,
            cwd=PIPELINE_FOLDER
        )

        # Check if solar analysis output exists
        solar_model_path = os.path.join(PIPELINE_FOLDER, "solar_radiation_example_image.glb")
        if not os.path.exists(solar_model_path):
            return jsonify({
                'status': 'error',
                'message': 'Solar analysis model not generated'
            }), 500

        return jsonify({
            'status': 'success',
            'message': 'Solar analysis completed',
            'modelUrl': f'http://localhost:5000/solar_radiation_example_image.glb?t={int(time.time())}'
        })

    except subprocess.CalledProcessError as e:
        print(f"❌ Run step error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    except Exception as e:
        print(f"❌ Unexpected error in run step: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/merged_model.glb')
def serve_merged_model():
    try:
        response = send_from_directory(PIPELINE_FOLDER, 'merged_model.glb', 
                                     mimetype='model/gltf-binary')
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404

# Add a route for static files including the log

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

@app.route('/save_screenshot', methods=['POST'])
def save_screenshot():
    try:
        data = request.json
        image_data = data['imageData']
        filename = data['filename']
        
        # Remove the data URL prefix (e.g., "data:image/png;base64,")
        image_data = image_data.split(',')[1]
        
        # Decode base64 data
        image_binary = base64.b64decode(image_data)
        
        # Save to pipeline_outputs folder
        output_path = os.path.join('pipeline_outputs', filename)
        
        with open(output_path, 'wb') as f:
            f.write(image_binary)
            
        return jsonify({'success': True, 'path': output_path})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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