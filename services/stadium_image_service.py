import os
import io
import json
import logging
import httpx
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("stadium_image_service")

BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
BLOB_API_URL = "https://blob.vercel-storage.com"

TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_MAX_SIZE_KB = 250
INITIAL_QUALITY = 85

STADIUM_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stadium_background.json")
DEFAULT_STADIUM_URL = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1920&auto=format&fit=crop"


def load_stadium_data() -> dict:
    if os.path.exists(STADIUM_DATA_PATH):
        try:
            with open(STADIUM_DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading stadium background data: {e}")
    return {"url": DEFAULT_STADIUM_URL, "overlay_opacity": 0.55, "blur": 4}


def save_stadium_data(data: dict):
    os.makedirs(os.path.dirname(STADIUM_DATA_PATH), exist_ok=True)
    try:
        with open(STADIUM_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving stadium background data: {e}")


def resize_stadium_image(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")

    resized_img = img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    quality = INITIAL_QUALITY
    output_buffer = io.BytesIO()
    resized_img.save(output_buffer, format="WEBP", quality=quality, method=6)
    webp_bytes = output_buffer.getvalue()
    size_kb = len(webp_bytes) / 1024.0

    while size_kb > TARGET_MAX_SIZE_KB and quality > 65:
        quality -= 5
        output_buffer = io.BytesIO()
        resized_img.save(output_buffer, format="WEBP", quality=quality, method=6)
        webp_bytes = output_buffer.getvalue()
        size_kb = len(webp_bytes) / 1024.0

    logger.info(f"Processed 1920x1080 WebP stadium background: {size_kb:.2f} KB (Quality={quality}%)")
    return webp_bytes


def upload_stadium_photo(file_bytes: bytes, overlay_opacity: float = 0.55, blur: int = 4) -> str:
    processed_webp = resize_stadium_image(file_bytes)

    # 1. Attempt Vercel Blob Upload if Token exists
    if BLOB_TOKEN:
        try:
            filename = "stadium_background.webp"
            url = f"{BLOB_API_URL}/{filename}"
            headers = {
                "Authorization": f"Bearer {BLOB_TOKEN}",
                "x-api-version": "7",
                "content-type": "image/webp"
            }
            with httpx.Client(timeout=15.0) as client:
                response = client.put(url, headers=headers, content=processed_webp)
                if response.status_code == 200:
                    data = response.json()
                    public_url = data.get("url")
                    stadium_info = {
                        "url": public_url,
                        "overlay_opacity": overlay_opacity,
                        "blur": blur
                    }
                    save_stadium_data(stadium_info)
                    logger.info(f"Stadium background uploaded to Vercel Blob CDN: {public_url}")
                    return public_url
                else:
                    logger.warning(f"Vercel Blob status {response.status_code}, falling back to local static storage")
        except Exception as e:
            logger.warning(f"Vercel Blob upload failed, falling back to local static storage: {e}")

    # 2. Local Static File Storage Fallback
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    local_file_path = os.path.join(static_dir, "stadium_background.webp")
    with open(local_file_path, "wb") as f:
        f.write(processed_webp)

    local_url = "http://localhost:6020/static/stadium_background.webp"
    stadium_info = {
        "url": local_url,
        "overlay_opacity": overlay_opacity,
        "blur": blur
    }
    save_stadium_data(stadium_info)
    logger.info(f"Stadium background saved locally to: {local_url}")
    return local_url


def get_stadium_background() -> dict:
    return load_stadium_data()
