from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from subprocess import run, CalledProcessError
import subprocess
import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("❌ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in environment variables.")

# Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Constants
OUTPUT_DIR = "spz_pipeline/pipeline_outputs"
BUCKET_NAME = "pipeline_outputs"

# FastAPI app setup
app = FastAPI()

# Allow all origins for now (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Server is running!"}


@app.post("/create")
def create_pipeline(request: Request):
    """Run create_button.py to perform 3D model + OSM alignment"""
    try:
        result = subprocess.run(
            ["python", "spz_analysis2/create_button.py"],
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "status": "create step completed",
            "stdout": result.stdout
        }
    except CalledProcessError as e:
        return {
            "error": "Subprocess failed",
            "stdout": e.stdout,
            "stderr": e.stderr,
            "code": e.returncode
        }
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


@app.post("/run")
def run_pipeline():
    """Run solar analysis step."""
    try:
        result = subprocess.run(
            ["python", "spz_analysis2/solar_new.py"],
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "status": "solar analysis completed",
            "stdout": result.stdout
        }
    except CalledProcessError as e:
        return {
            "error": "Subprocess failed",
            "stdout": e.stdout,
            "stderr": e.stderr,
            "code": e.returncode
        }
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


@app.post("/save")
def save_outputs():
    """Upload pipeline outputs to Supabase storage."""
    uploaded = 0
    try:
        for root_dir, _, files in os.walk(OUTPUT_DIR):
            for file in files:
                local_path = os.path.join(root_dir, file)
                rel_path = os.path.relpath(local_path, OUTPUT_DIR)
                with open(local_path, "rb") as f:
                    supabase.storage.from_(BUCKET_NAME).upload(
                        path=rel_path,
                        file=f,
                        file_options={"upsert": True}
                    )
                    uploaded += 1
        return {"status": f"✅ Uploaded {uploaded} files to Supabase."}
    except Exception as e:
        return {"error": f"❌ Upload failed: {e}"}
