import sys
import json
import requests
import os
from supabase import create_client
from dotenv import load_dotenv
import subprocess

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def upload_to_supabase(bucket, supabase_path, local_path):
    with open(local_path, "rb") as f:
        supabase.storage.from_(bucket).upload(
            path=supabase_path,
            file=f,
            file_options={"upsert": "true"}  # String, not Boolean
        )

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_button.py '{\"user_id\":..., \"project_id\":..., \"epw_url\":..., \"mesh_url\":...}'")
        sys.exit(1)

    # Accept JSON string or path to JSON file
    arg = sys.argv[1]
    try:
        if os.path.isfile(arg):
            with open(arg, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(arg)
    except Exception as e:
        print(f" Failed to parse input JSON: {e}")
        sys.exit(1)

    user_id = data["user_id"]
    project_id = data["project_id"]
    epw_url = data["epw_url"]  # Public URL
    mesh_url = data["mesh_url"]  # Public URL

    local_output = "solar_radiation.glb"
    output_supabase_path = f"{user_id}/{project_id}/solar_radiation.glb"

    try:
        print(" Running solar analysis...")
        subprocess.run([
            sys.executable, "spz_analysis2/solar_new.py",
            "--user_id", user_id,
            "--project_id", project_id,
            "--epw_url", epw_url,
            "--mesh_url", mesh_url
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f" Solar analysis failed:\n{e}")
        sys.exit(1)

    try:
        print(" Uploading result to Supabase...")
        upload_to_supabase("solar-radiation", output_supabase_path, local_output)
        print(" Done.")
    except Exception as e:
        print(f" Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
