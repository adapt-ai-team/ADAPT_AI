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
import base64
from supabase import create_client, Client

# Get the current directory and project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

# Supabase configuration
SUPABASE_URL = "https://odhxfcinqsbsseecrlin.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9kaHhmY2lucXNic3NlZWNybGluIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODA3Njk0NiwiZXhwIjoyMDYzNjUyOTQ2fQ.uDa54g3CeYrmoNG9wT4ViurCoBVgt2fQXLi0wztvlA0"
BUCKET = "pipeline-outputs"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Define Directories using relative paths
PIPELINE_FOLDER = CURRENT_DIR
SPZ_FOLDER = os.path.join(PROJECT_ROOT, "spz")
ANALYSIS_FOLDER = os.path.join(PROJECT_ROOT, "spz_analysis2")

# Define Script Paths using relative paths
EXAMPLE_SCRIPT = os.path.join(PROJECT_ROOT, "trellis_api", "trellis_api.py")
CONVERT_SCRIPT = os.path.join(ANALYSIS_FOLDER, "osm_fetch_convert_to_3dm.py")
SOLAR_SCRIPT = os.path.join(ANALYSIS_FOLDER, "solar_new.py")

app = Flask(__name__, 
            static_folder=os.path.join(PIPELINE_FOLDER, 'static'),
            template_folder=os.path.join(PIPELINE_FOLDER, 'templates'))
CORS(app)

def download_from_supabase(bucket: str, path_in_bucket: str, local_path: str) -> bool:
    try:
        response = supabase.storage.from_(bucket).download(path_in_bucket)
        with open(local_path, 'wb') as f:
            f.write(response)
        return True
    except Exception as e:
        print(f"Download error: {str(e)}")
        return False

def upload_to_supabase(bucket: str, local_path: str, path_in_bucket: str) -> bool:
    try:
        with open(local_path, 'rb') as f:
            supabase.storage.from_(bucket).upload(path_in_bucket, f)
        return True
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return False

def generate_public_url(bucket: str, path_in_bucket: str) -> str:
    try:
        return supabase.storage.from_(bucket).get_public_url(path_in_bucket)
    except Exception as e:
        print(f"URL generation error: {str(e)}")
        return ""

def verify_and_create_directories():
    os.makedirs(PIPELINE_FOLDER, exist_ok=True)
    print(f"📁 Pipeline folder path: {PIPELINE_FOLDER}")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/create_step', methods=['POST'])
def create_step():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        image_path = data.get("image_path")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if not all([user_id, image_path, latitude, longitude]):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        verify_and_create_directories()
        local_image_path = os.path.join(PIPELINE_FOLDER, f"{user_id}_input.jpg")
        local_latlon_path = os.path.join(PIPELINE_FOLDER, f"{user_id}_latlon.txt")

        # Download from image-generation bucket
        if not download_from_supabase("image-generation", image_path, local_image_path):
            return jsonify({'status': 'error', 'message': 'Failed to download image'}), 500

        with open(local_latlon_path, "w") as f:
            f.write(f"{latitude},{longitude}")

        print(f"📸 Image downloaded to: {local_image_path}")
        print(f"📍 Coordinates saved to: {local_latlon_path}")

        # Run Trellis API
        subprocess.run(
            ['conda', 'run', '-n', 'trellis', 'python', EXAMPLE_SCRIPT, '--input', local_image_path],
            check=True,
            cwd=PIPELINE_FOLDER
        )

        # Run OSM conversion
        subprocess.run(
            ['conda', 'run', '-n', 'ladybug_env', 'python', CONVERT_SCRIPT, latitude, longitude],
            check=True,
            cwd=PIPELINE_FOLDER
        )

        # Upload output to pipeline-outputs bucket
        local_glb = os.path.join(PIPELINE_FOLDER, "merged_model.glb")
        remote_glb = f"{user_id}/merged_model.glb"

        if not upload_to_supabase(BUCKET, local_glb, remote_glb):
            return jsonify({'status': 'error', 'message': 'Failed to upload GLB'}), 500

        model_url = generate_public_url(BUCKET, remote_glb)
        if not model_url:
            return jsonify({'status': 'error', 'message': 'Failed to generate public URL'}), 500

        return jsonify({
            'status': 'success',
            'modelUrl': model_url
        })

    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'error', 'message': f"Pipeline failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    verify_and_create_directories()
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    app.run(debug=False, host='0.0.0.0', port=5000)