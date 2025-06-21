from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import traceback

# --- Setup environment path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "spz_analysis2"))

# --- Import pipeline functions ---
from trellis_api import run_trellis_generation
from osm_fetch_convert_to_3dm import run_osm_pipeline
# You'll later import: from solar_new import run_solar_analysis

# --- FastAPI App ---
app = FastAPI(
    title="ADAPT AI API",
    description="API for 3D model generation and analysis",
    version="1.0.0"
)

# --- Request Schemas ---
class CreateRequest(BaseModel):
    user_id: str
    project_id: str
    image_url: str

class SaveRequest(BaseModel):
    user_id: str
    project_id: str
    # Add other fields needed for solar analysis

# --- API Routes ---
@app.post("/create", tags=["3D Generation"])
def trigger_pipeline(data: CreateRequest):
    """Generate 3D model from image and align with OSM data"""
    user_id = data.user_id
    project_id = data.project_id
    image_url = data.image_url

    try:
        print(f"🚀 Starting pipeline for user: {user_id}, project: {project_id}")

        # Step 1: Trellis Model Generation
        output_glb_path = f"{user_id}/{project_id}/model.glb"
        run_trellis_generation(image_url, output_glb_path)
        print("✅ Trellis model generated and uploaded.")

        # Step 2: OSM Alignment + Merge
        run_osm_pipeline(user_id, project_id)
        print("✅ OSM alignment and merge complete.")

        # Add debugging to check for files in Supabase
        try:
            from supabase import create_client
            supabase = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            )
            files = supabase.storage.from_("2d-to-3d").list(f"{user_id}/{project_id}")
            print(f"📋 Files in 2d-to-3d bucket: {files}")
        except Exception as e:
            print(f"⚠️ Failed to list files: {e}")

        return {
            "status": "success",
            "message": f"Pipeline completed for user {user_id}, project {project_id}."
        }

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        print(traceback.format_exc())  # Print full stack trace
        return {"status": "error", "message": str(e)}

# --- Solar Analysis Route (for future use) ---
@app.post("/save", tags=["Solar Analysis"])
def solar_analysis(data: SaveRequest):
    """Run solar analysis on the 3D model"""
    user_id = data.user_id
    project_id = data.project_id

    try:
        print(f"☀️ Starting solar analysis for user: {user_id}, project: {project_id}")
        
        # This will be implemented later with solar_new.py
        # run_solar_analysis(user_id, project_id)
        
        # For now, return a placeholder response
        return {
            "status": "not_implemented",
            "message": "Solar analysis will be implemented soon."
        }

    except Exception as e:
        print(f"❌ Solar analysis failed: {e}")
        print(traceback.format_exc())
        return {"status": "error", "message": str(e)}

# --- Home Route ---
@app.get("/", tags=["Status"])
def root():
    """API Status check"""
    return {
        "status": "online",
        "endpoints": ["/create", "/save"],
        "version": "1.0.0"
    }

