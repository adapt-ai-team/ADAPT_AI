from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from subprocess import run, CalledProcessError
import subprocess
import os
from supabase import create_client
from dotenv import load_dotenv

app = FastAPI()

# Optional CORS (useful if your frontend calls this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("❌ SUPABASE_URL or SUPABASE_SERVICE_KEY not set in environment variables.")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Constants
OUTPUT_DIR = "spz_pipeline/pipeline_outputs"
BUCKET_NAME = "pipeline_outputs"

@app.get("/")
def root():
    return {"status": "Server is running!"}

@app.post("/create")
def create_pipeline():
    """Run initial model generation and OSM alignment steps."""
    try:
        # Step 1: Run example.py
        result1 = subprocess.run(
            ["python", "example.py"],
            capture_output=True,
            text=True,
            check=True
        )

        # Step 2: Run osm_fetch_convert_to_3dm.py
        result2 = subprocess.run(
            ["python", "osm_fetch_convert_to_3dm.py"],
            capture_output=True,
            text=True,
            check=True
        )

        return {
            "status": "Pipeline create step completed.",
            "example_stdout": result1.stdout,
            "osm_stdout": result2.stdout
        }

    except CalledProcessError as e:
        return {
            "error": f"Subprocess failed: {e}",
            "stdout": e.stdout,
            "stderr": e.stderr
        }
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


@app.post("/run")
def run_pipeline():
    """Run solar radiation analysis."""
    try:
        result = subprocess.run(
            ["python", "solar_new.py"],
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "status": "Solar analysis completed.",
            "stdout": result.stdout
        }
    except CalledProcessError as e:
        return {
            "error": f"Subprocess failed: {e}",
            "stdout": e.stdout,
            "stderr": e.stderr
        }
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


@app.post("/save")
def save_outputs():
    """Upload all pipeline outputs to Supabase storage."""
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
