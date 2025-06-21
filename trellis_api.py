import os
import requests
import tempfile
from dotenv import load_dotenv
import replicate
from supabase import create_client, Client

# --- Load environment variables ---
load_dotenv()

# --- Replicate Configuration ---
api_token = os.getenv("REPLICATE_API")
if not api_token:
    raise ValueError("❌ REPLICATE_API not set in environment variables.")
client = replicate.Client(api_token=api_token)

# --- Supabase Configuration ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("❌ Supabase environment variables not set.")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def run_trellis_generation(input_image_path: str, output_glb_path: str):
    """
    Given a Supabase path to an input image, runs Trellis via Replicate and uploads the output .glb to Supabase.

    Args:
        input_image_path (str): e.g., 'user_id/project_id/input.jpg'
        output_glb_path (str): e.g., 'user_id/project_id/model.glb'
    """
    print(f"📥 Starting Trellis generation: {input_image_path} → {output_glb_path}")

    # 1. Get public URL of the image
    public_url = supabase.storage.from_("image-generation").get_public_url(input_image_path)
    if not public_url:
        raise Exception(f"❌ Failed to get public URL for image: {input_image_path}")
    print(f"🌐 Image public URL: {public_url}")

    # 2. Run Trellis model via Replicate
    try:
        output = client.run(
            "firtoz/trellis:e8f6c45206993f297372f5436b90350817bd9b4a0d52d2a76df50c1c8afa2b3c",
            input={"images": [public_url], "generate_model": True}
        )
        print("🔁 Replicate output:", output)
    except Exception as e:
        raise Exception(f"❌ Replicate call failed: {e}")

    # 3. Parse returned model file URL
    model_url = None
    if isinstance(output, dict):
        model_file = output.get("model_file")
        if model_file and isinstance(model_file, dict):
            model_url = model_file.get("url")
    elif isinstance(output, list) and len(output) > 0:
        model_url = output[0]
    elif isinstance(output, str):
        model_url = output

    if not model_url:
        raise Exception("❌ No valid model_file URL returned from Trellis")

    # 4. Download the .glb file
    print(f"⬇️ Downloading model file from: {model_url}")
    response = requests.get(model_url)
    if response.status_code != 200:
        raise Exception(f"❌ Failed to download .glb from {model_url} (status code: {response.status_code})")

    # 5. Upload to Supabase
    with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp_file:
        tmp_file.write(response.content)
        tmp_file.flush()
        tmp_path = tmp_file.name

    print(f"📦 Uploading to Supabase at 2d-to-3d/{output_glb_path}")
    try:
        with open(tmp_path, "rb") as f:
            # Remove existing file if present
            try:
                supabase.storage.from_("2d-to-3d").remove([output_glb_path])
            except Exception:
                pass  # Safe to ignore if file doesn't exist
            supabase.storage.from_("2d-to-3d").upload(
                output_glb_path,
                f,
                file_options={"content-type": "model/gltf-binary"}
            )
    finally:
        os.unlink(tmp_path)

    print(f"✅ Trellis model uploaded successfully: 2d-to-3d/{output_glb_path}")
