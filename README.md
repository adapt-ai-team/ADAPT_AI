# ADAPT-AI: End-to-End Pipeline for 3D Urban Modeling and Solar Analysis

This repository provides a FastAPI backend that handles the full workflow for generating 3D models from 2D images, aligning them with OpenStreetMap (OSM) context, and performing solar radiation analysis using Ladybug Tools. All inputs and outputs are managed via Supabase storage.

## 🔧 Features

- 📷 Generate 3D buildings from a single image (via Trellis API)
- 🌍 Align and merge generated models with surrounding OSM data
- ☀️ Run solar radiation analysis using EPW weather files
- 🗂 Upload and manage all assets via Supabase storage
- 🌐 RESTful API with FastAPI for integration in web UIs

## 📁 Project Structure

.
├── api_server.py # Main FastAPI server with endpoints
├── create_button.py # Script to handle 3D model creation and OSM merging
├── run_button.py # Script to run solar analysis and upload results
├── trellis_api.py # Interface to Trellis model generation (via Replicate API)
├── osm_fetch_convert_to_3dm.py # Fetch OSM buildings, convert & align, upload merged models
├── solar_new.py # Solar radiation analysis using Ladybug and Rhino3DM
└── spz_analysis2/ # Folder expected to hold solar_new.py and support files


## 🔑 Requirements

- Python 3.9+
- Supabase account with the following buckets:
  - `2d-to-3d`
  - `context-merged`
  - `solar-radiation`
  - `pipeline_outputs`
  - `location`
- Replicate API key (for Trellis model)
- `.env` file configured with:
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
REPLICATE_API=your_replicate_api_token


## ⚙️ Installation

1. **Clone the repository**

git clone https://github.com/your-username/adapt-ai.git
cd adapt-ai


2. **Install Python dependencies**

pip install -r requirements.txt


3. **Set up your `.env` file** with Supabase and Replicate credentials

## 🚀 Running the API Server

Start the FastAPI server locally:

python api_server.py


## 📡 API Endpoints

### `/create` - Generate 3D model and align with OSM

**POST** `/create`

```json
{
  "user_id": "user123",
  "project_id": "proj001",
  "image_url": "https://your-bucket/image.jpg"
}


{
  "user_id": "user123",
  "project_id": "proj001",
  "epw_url": "https://your-climate-bucket/weather.epw",
  "mesh_url": "https://your-solar-bucket/user123/proj001/merged_model.3dm"
}

/save - Upload results from local pipeline_outputs to Supabase
POST /save

```

🖥️ Manual Usage (CLI)
Generate and Align Model

python create_button.py --user_id user123 --project_id proj001 --image_url https://example.com/image.jpg

Run Solar Radiation Analysis

python run_button.py '{"user_id":"user123", "project_id":"proj001", "epw_url":"https://...epw", "mesh_url":"https://...3dm"}'


📤 Output Files
model.glb – Raw output from Trellis

model_fixed.glb – Rescaled + positioned

merged_model.glb – Combined Trellis + OSM model

merged_model.3dm – Rhino-native version

solar_radiation.glb – Colored model with radiation results

solar_radiation_legend.png – Legend image showing scale

🛠 Tech Stack
FastAPI

Supabase Storage

Replicate API (Trellis)

Rhino3DM

Ladybug Tools

Trimesh & PyMeshLab

OpenStreetMap + Overpass API

🧪 Test
Test if the server is live:

curl http://localhost:10000/test
