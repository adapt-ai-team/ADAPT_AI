# supabase_utils.py

import os
from supabase import create_client, Client

# Load credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def download_from_supabase(bucket: str, path_in_bucket: str, local_path: str) -> bool:
    """Download a file from Supabase Storage."""
    try:
        print(f"⬇️  Downloading {bucket}/{path_in_bucket} → {local_path}")
        data = supabase.storage.from_(bucket).download(path_in_bucket)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"❌ Failed to download from Supabase: {e}")
        return False

def upload_to_supabase(bucket: str, local_path: str, path_in_bucket: str) -> bool:
    """Upload a file to Supabase Storage."""
    try:
        print(f"⬆️  Uploading {local_path} → {bucket}/{path_in_bucket}")
        with open(local_path, "rb") as f:
            supabase.storage.from_(bucket).upload(path_in_bucket, f, upsert=True)
        return True
    except Exception as e:
        print(f"❌ Failed to upload to Supabase: {e}")
        return False

def generate_public_url(bucket: str, path_in_bucket: str) -> str:
    """Generate public URL for a Supabase file."""
    try:
        return supabase.storage.from_(bucket).get_public_url(path_in_bucket)
    except Exception as e:
        print(f"⚠️  Could not generate public URL: {e}")
        return None
