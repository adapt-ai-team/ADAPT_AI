from trellis_api import run_trellis_generation

# Input from your JSON
user_id = "0f5d4414-2cc4-48f3-a873-88a7d2a37e46"
project_id = "84e1e181-379c-4c5e-9bdf-ffb63d2c0483"
image_url = "https://odhxfcinqsbsseecrlin.supabase.co/storage/v1/object/public/image-generation/0f5d4414-2cc4-48f3-a873-88a7d2a37e46/84e1e181-379c-4c5e-9bdf-ffb63d2c0483/1749138029215-generated-flux-pro-1749138029214.webp"

# Output path in Supabase
output_glb_path = f"{user_id}/{project_id}/model.glb"

# Run the pipeline
run_trellis_generation(image_url, output_glb_path)
  