from fastapi import FastAPI
from subprocess import run
import os
from supabase import create_client
from dotenv import load_dotenv

app = FastAPI()

# Load env variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

OUTPUT_DIR = "spz_pipeline/pipeline_outputs"
BUCKET_NAME = "pipeline_outputs"

@app.get("/")
def root():
    return {"status": "Server is running!"}

@app.post("/create")
def create_pipeline():
    try:
        run(["python", "example.py"], check=True)
        run(["python", "osm_fetch_convert_to_3dm.py"], check=True)
        return {"status": "example.py and osm_fetch_convert_to_3dm.py completed"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/run")
def run_pipeline():
    try:
        run(["python", "solar_new.py"], check=True)
        return {"status": "solar_new.py completed"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/save")
def save_outputs():
    uploaded = 0
    for root_dir, _, files in os.walk(OUTPUT_DIR):
        for file in files:
            local_path = os.path.join(root_dir, file)
            rel_path = os.path.relpath(local_path, OUTPUT_DIR)
            with open(local_path, "rb") as f:
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=rel_path, file=f, file_options={"upsert": True}
                )
                uploaded += 1
    return {"status": f"Uploaded {uploaded} files to Supabase."}
