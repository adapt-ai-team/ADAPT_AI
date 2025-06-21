from fastapi import FastAPI
from pydantic import BaseModel
import sys
import os

# --- Setup environment path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "spz_analysis2"))

# --- Import pipeline functions ---
from trellis_api import run_trellis_generation
from osm_fetch_convert_to_3dm import run_osm_pipeline

# --- FastAPI App ---
app = FastAPI()

# --- Request Schema ---
class CreateRequest(BaseModel):
    user_id: str
    project_id: str
    image_url: str  # Optional, if you want to pass the image URL directly
# --- API Route ---
@app.post("/create")
def trigger_pipeline(data: CreateRequest):
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

        return {
            "status": "success",
            "message": f"Pipeline completed for user {user_id}, project {project_id}."
        }

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        return {"status": "error", "message": str(e)}


# Optional: local dev entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10001)  # Change to any unused port
