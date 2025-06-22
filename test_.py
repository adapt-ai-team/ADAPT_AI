import requests
resp = requests.post(
    "http://localhost:8000/create",
    json={
        "user_id": "0f5d4414-2cc4-48f3-a873-88a7d2a37e46",
        "project_id": "84e1e181-379c-4c5e-9bdf-ffb63d2c0483",
        "image_url": "https://odhxfcinqsbsseecrlin.supabase.co/storage/v1/object/public/image-generation/0f5d4414-2cc4-48f3-a873-88a7d2a37e46/84e1e181-379c-4c5e-9bdf-ffb63d2c0483/1749138029215-generated-flux-pro-1749138029214.webp"
    },
    timeout=300  # 5 minutes
)
print(resp.json())