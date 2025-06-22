import os
import requests
import tempfile
from dotenv import load_dotenv
import replicate
from supabase import create_client, Client
import time

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

def run_trellis_generation(input_image, output_glb_path: str):
    """
    Runs Trellis model on an image and uploads the output .glb.
    
    Args:
        input_image (str): Either a Supabase path or a full image URL
        output_glb_path (str): Path for output like 'user_id/project_id/model.glb'
    """
    print(f"📥 Starting Trellis generation: {input_image} → {output_glb_path}")
    
    # Handle both paths and URLs
    if input_image.startswith("http"):
        public_url = input_image
        print(f"🌐 Using provided image URL directly")
    else:
        # If it's a path, get the URL
        public_url = supabase.storage.from_("image-generation").get_public_url(input_image)
        if not public_url:
            raise Exception(f"❌ Failed to get public URL for image: {input_image}")
        print(f"🌐 Generated public URL: {public_url}")

    # If input_image is a path, ensure it is in the format user_id/project_id/image_filename
    if not input_image.startswith("http"):
        # Enforce folder structure for output to match input
        # input_image: user_id/project_id/image_filename
        # output_glb_path: user_id/project_id/model.glb
        input_parts = input_image.split("/")
        if len(input_parts) >= 3:
            user_id, project_id = input_parts[0], input_parts[1]
            output_glb_path = f"{user_id}/{project_id}/model.glb"
        else:
            raise Exception(f"❌ input_image path must be user_id/project_id/image_filename, got: {input_image}")

    # 2. Run Trellis model via Replicate
    max_retries = 3
    for attempt in range(max_retries):
        try:
            output = client.run(
                "firtoz/trellis:e8f6c45206993f297372f5436b90350817bd9b4a0d52d2a76df50c1c8afa2b3c",
                input={"images": [public_url], "generate_model": True},
                timeout=600  # if supported
            )
            print("🔁 Replicate output:", output)
            break  # Exit the retry loop on success
        except Exception as e:
            if "timed out" in str(e) and attempt < max_retries - 1:
                print(f"⏳ Timeout occurred, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(5)  # Wait before retrying
                continue
            raise Exception(f"❌ Replicate call failed: {e}")

    # 3. Parse returned model file URL
    model_url = None
    
    print(f"🔍 Inspecting output type: {type(output)}")
    
    if isinstance(output, dict):
        model_file = output.get("model_file")
        print(f"🔍 Model file type: {type(model_file)}")
        
        # Handle FileOutput object from replicate
        if hasattr(model_file, 'url'):  # Check if it has .url attribute
            model_url = model_file.url
            print(f"📄 Found URL from FileOutput: {model_url}")
        elif model_file and isinstance(model_file, dict):
            model_url = model_file.get("url")
    elif isinstance(output, list) and len(output) > 0:
        model_url = output[0]
    elif isinstance(output, str):
        model_url = output
        
    if not model_url:
        print(f"❌ DEBUG - Full output: {output}")
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

    # Ensure the folder structure exists in Supabase (Supabase auto-creates folders on upload, but we can check)
    folder_path = os.path.dirname(output_glb_path)
    if folder_path:
        try:
            supabase.storage.from_("2d-to-3d").list(folder_path)
        except Exception:
            pass  # Supabase auto-creates folders on upload

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

    # After upload completes
    try:
        # List files in directory to verify upload
        files = supabase.storage.from_("2d-to-3d").list(os.path.dirname(output_glb_path))
        print(f"📋 Files in directory after upload: {files}")
    except Exception as e:
        print(f"⚠️ Error checking files: {e}")

    print(f"✅ Trellis model uploaded successfully: 2d-to-3d/{output_glb_path}")
