from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import traceback
import logging
from fastapi.middleware.cors import CORSMiddleware
import argparse

# --- Setup environment path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "spz_analysis2"))

# --- Import pipeline functions ---
from trellis_api import run_trellis_generation
from osm_fetch_convert_to_3dm import run_osm_pipeline
# You'll later import: from solar_new import run_solar_analysis

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --- Validate Environment Variables at Startup ---
REQUIRED_ENV_VARS = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
missing_vars = [var for var in REQUIRED_ENV_VARS if var not in os.environ]
if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

# --- Supabase Client Singleton ---
from supabase import create_client
SUPABASE_CLIENT = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"]
)

# --- FastAPI App ---
app = FastAPI(
    title="ADAPT AI API",
    description="API for 3D model generation and analysis",
    version="1.0.0"
)

# --- CORS Middleware (allow all origins for now, restrict in prod) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        logger.info(f"🚀 Starting pipeline for user: {user_id}, project: {project_id}")

        # Step 1: Trellis Model Generation
        output_glb_path = f"{user_id}/{project_id}/model.glb"
        try:
            trellis_result = run_trellis_generation(image_url, output_glb_path)
            logger.info(f"Trellis generation result: {trellis_result}")
        except Exception as e:
            logger.error(f"Trellis generation failed: {e}")
            logger.error(traceback.format_exc())
            return {"status": "error", "message": f"Trellis generation failed: {e}"}
        logger.info("✅ Trellis model generated and uploaded.")

        # Step 2: OSM Alignment + Merge
        try:
            osm_result = run_osm_pipeline(user_id, project_id)
            logger.info(f"OSM pipeline result: {osm_result}")
        except Exception as e:
            logger.error(f"OSM pipeline failed: {e}")
            logger.error(traceback.format_exc())
            return {"status": "error", "message": f"OSM pipeline failed: {e}"}
        logger.info("✅ OSM alignment and merge complete.")

        # --- Improved Supabase file listing and logging ---
        try:
            files = SUPABASE_CLIENT.storage.from_("2d-to-3d").list(f"{user_id}/{project_id}")
            logger.info(f"Files in 2d-to-3d bucket for {user_id}/{project_id}: {files}")
        except Exception as e:
            logger.error(f"Failed to list files in Supabase: {e}")

        return {
            "status": "success",
            "message": f"Pipeline completed for user {user_id}, project {project_id}.",
            "trellis_result": str(trellis_result),
            "osm_result": str(osm_result),
            "files": str(files) if 'files' in locals() else None
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        logger.error(traceback.format_exc())  # Print full stack trace
        return {"status": "error", "message": str(e)}

# --- Solar Analysis Route (for future use) ---
@app.post("/save", tags=["Solar Analysis"])
def solar_analysis(data: SaveRequest):
    """Run solar analysis on the 3D model"""
    user_id = data.user_id
    project_id = data.project_id

    try:
        logger.info(f"☀️ Starting solar analysis for user: {user_id}, project: {project_id}")
        
        # This will be implemented later with solar_new.py
        # run_solar_analysis(user_id, project_id)
        
        # For now, return a placeholder response
        return {
            "status": "not_implemented",
            "message": "Solar analysis will be implemented soon."
        }

    except Exception as e:
        logger.error(f"❌ Solar analysis failed: {e}")
        logger.error(traceback.format_exc())
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

def run_pipeline(user_id, project_id, image_url):
    # This is the core logic from trigger_pipeline, but as a function
    try:
        logger.info(f"🚀 Starting pipeline for user: {user_id}, project: {project_id}")

        output_glb_path = f"{user_id}/{project_id}/model.glb"
        trellis_result = run_trellis_generation(image_url, output_glb_path)
        logger.info(f"Trellis generation result: {trellis_result}")

        osm_result = run_osm_pipeline(user_id, project_id)
        logger.info(f"OSM pipeline result: {osm_result}")

        files = SUPABASE_CLIENT.storage.from_("2d-to-3d").list(f"{user_id}/{project_id}")
        logger.info(f"Files in 2d-to-3d bucket for {user_id}/{project_id}: {files}")

        return {
            "status": "success",
            "message": f"Pipeline completed for user {user_id}, project {project_id}.",
            "trellis_result": str(trellis_result),
            "osm_result": str(osm_result),
            "files": str(files) if files else None
        }
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Run the 3D generation pipeline")
    parser.add_argument("--user_id", type=str, help="User ID")
    parser.add_argument("--project_id", type=str, help="Project ID")
    parser.add_argument("--image_url", type=str, help="Image URL")
    args = parser.parse_args()

    result = run_pipeline(args.user_id, args.project_id, args.image_url)
    print(result)

if __name__ == "__main__":
    main()

