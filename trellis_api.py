import os
from dotenv import load_dotenv
import replicate

# Load environment variables
load_dotenv()

# Get API token from environment
api_token = os.getenv("REPLICATE_API")
if not api_token:
    raise ValueError("REPLICATE_API is not set")

# Initialize client
client = replicate.Client(api_token=api_token)

# --- Supabase Configuration (from environment variables on Render) ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def run_trellis_generation(input_image_path: str, output_glb_path: str):
    """
    Given a Supabase image path, runs Trellis model and uploads the .glb output.

    Args:
        input_image_path (str): Supabase path like 'image-generation/user_id/project_id/input.jpg'
        output_glb_path (str): Supabase path like '2d-to-3d/user_id/project_id/model.glb'
    """
    print(f"📥 Starting Trellis generation: {input_image_path} → {output_glb_path}")

    # 1. Get public URL of input image
    public_url = supabase.storage.from_("image-generation").get_public_url(input_image_path)
    if not public_url:
        raise Exception(f"❌ Failed to get public URL for {input_image_path}")

    print(f"🌐 Input image public URL: {public_url}")

    # 2. Call Trellis model via Replicate
    output = replicate_client.run(
        "firtoz/trellis:e8f6c45206993f297372f5436b90350817bd9b4a0d52d2a76df50c1c8afa2b3c",
        input={"images": [public_url], "generate_model": True}
    )

    model_file = output.get("model_file")
    if not model_file or not model_file.url:
        raise Exception("❌ Trellis did not return a valid model_file URL")

    print("⬇️ Downloading Trellis .glb file...")
    response = requests.get(model_file.url)
    if response.status_code != 200:
        raise Exception(f"❌ Failed to download model: {response.status_code}")

    # 3. Upload .glb to Supabase
    with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp_file:
        tmp_file.write(response.content)
        tmp_file.flush()

        with open(tmp_file.name, "rb") as f:
            try:
                supabase.storage.from_("2d-to-3d").remove([output_glb_path])
            except Exception:
                pass  # File may not exist yet

            supabase.storage.from_("2d-to-3d").upload(
                output_glb_path,
                f,
                file_options={"content-type": "model/gltf-binary"}
            )

    os.unlink(tmp_file.name)
    print(f"✅ Trellis .glb model uploaded to Supabase: 2d-to-3d/{output_glb_path}")
