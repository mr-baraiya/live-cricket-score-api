import os
import io
import json
import logging
import re
import httpx
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("team_logo_service")

BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
BLOB_API_URL = "https://blob.vercel-storage.com"

# Team logo standards: square PNG/WebP 256x256
LOGO_SIZE = 256

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "team_logo_registry.json"
)


def _normalize_team_key(team_name: str) -> str:
    """Converts team name to a clean snake_case slug key."""
    if not team_name:
        return "unknown_team"
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", team_name.strip())
    slug = re.sub(r"\s+", "_", cleaned.lower())
    return slug or "unknown_team"


def load_logo_registry() -> dict:
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading team logo registry: {e}")
    return {}


def save_logo_registry(registry: dict):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving team logo registry: {e}")


def process_team_logo(image_bytes: bytes) -> bytes:
    """
    Process team logo: resize to 256x256 square PNG with transparent background
    (or white bg if no alpha), export as WebP.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Preserve transparency if available, otherwise convert to RGBA
    if img.mode not in ("RGBA", "LA", "PA"):
        img = img.convert("RGBA")

    # Square crop from center
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

    img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.Resampling.LANCZOS)

    output_buffer = io.BytesIO()
    img.save(output_buffer, format="WEBP", quality=90, method=6)
    return output_buffer.getvalue()


def upload_to_vercel_blob(filename: str, file_bytes: bytes, content_type: str = "image/webp") -> str:
    if not BLOB_TOKEN:
        raise ValueError("BLOB_READ_WRITE_TOKEN environment variable is missing!")

    url = f"{BLOB_API_URL}/{filename}"
    headers = {
        "Authorization": f"Bearer {BLOB_TOKEN}",
        "x-api-version": "7",
        "content-type": content_type,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.put(url, headers=headers, content=file_bytes)
        if response.status_code != 200:
            logger.error(f"Vercel Blob Upload Failed ({response.status_code}): {response.text}")
            response.raise_for_status()
        data = response.json()
        return data.get("url")


def upload_team_logo(team_name: str, file_bytes: bytes) -> str:
    """
    Uploads a team logo to Vercel Blob storage, saves to registry.
    Returns the public blob URL.
    """
    if not team_name:
        raise ValueError("Team name is required.")

    key = _normalize_team_key(team_name)
    processed_webp = process_team_logo(file_bytes)
    filename = f"team_logos/{key}.webp"
    blob_url = upload_to_vercel_blob(filename, processed_webp)

    registry = load_logo_registry()
    registry[key] = {
        "name": team_name,
        "filename": filename,
        "blob_url": blob_url,
    }
    save_logo_registry(registry)
    logger.info(f"Team logo uploaded for '{team_name}': {blob_url}")
    return blob_url


def process_stadium_background(image_bytes: bytes) -> bytes:
    """
    Processes stadium backdrop image: 1920x1080 WebP broadcast resolution.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    target_aspect = 16.0 / 9.0
    aspect = w / float(h)

    if aspect > target_aspect:
        new_w = int(h * target_aspect)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_aspect)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
    output_buffer = io.BytesIO()
    img.save(output_buffer, format="WEBP", quality=85, method=6)
    return output_buffer.getvalue()


STADIUM_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "stadium_registry.json"
)


def load_stadium_registry() -> dict:
    if os.path.exists(STADIUM_REGISTRY_PATH):
        try:
            with open(STADIUM_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading stadium registry: {e}")
    return {}


def save_stadium_registry(registry: dict):
    os.makedirs(os.path.dirname(STADIUM_REGISTRY_PATH), exist_ok=True)
    try:
        with open(STADIUM_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving stadium registry: {e}")


def upload_stadium_background(file_bytes: bytes) -> str:
    processed_webp = process_stadium_background(file_bytes)
    filename = "stadium_bg/current_stadium.webp"
    blob_url = upload_to_vercel_blob(filename, processed_webp)

    registry = {"blob_url": blob_url, "filename": filename}
    save_stadium_registry(registry)
    logger.info(f"Stadium background uploaded: {blob_url}")
    return blob_url


def get_stadium_background_url() -> str:
    registry = load_stadium_registry()
    if registry.get("blob_url"):
        return registry["blob_url"]
    return "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?auto=format&fit=crop&w=1920&q=80"
