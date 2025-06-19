from fastapi import FastAPI, Request
from pydantic import BaseModel
from trellis_api import run_trellis_generation
from osm_fetch_convert_to_3dm import run_osm_pipeline  # You’ll define this in that file
import uvicorn
import sys
import os

app = FastAPI()

# Add the folder containing trellis_api.py to sys.path
TRELLIS_PATH = os.path.join(os.path.dirname(__file__), "spz_pipeline", "pipeline_outputs")
sys.path.append(TRELLIS_PATH)

from trellis_api import run_trellis_generation

class CreateRequest(BaseModel):
    user_id: str
    project_id: str

@app.post("/create")
def trigger_pipeline(data: CreateRequest):
    user_id = data.user_id
    project_id = data.project_id

    try:
        # Step 1: Run Trellis generation
        input_image_path = f"{user_id}/{project_id}/input.jpg"
        output_glb_path = f"{user_id}/{project_id}/model.glb"
        run_trellis_generation(input_image_path, output_glb_path)
        print("✅ Trellis generation complete.")

        # Step 2: Run OSM + alignment + merging
        run_osm_pipeline(user_id, project_id)
        print("✅ OSM pipeline complete.")

        return {"status": "success", "message": "Pipeline completed."}
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        return {"status": "error", "message": str(e)}
