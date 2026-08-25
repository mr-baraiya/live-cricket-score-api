import os
import io
import json
import logging
import re
import httpx
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("player_image_service")

BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
BLOB_API_URL = "https://blob.vercel-storage.com"

# BROADCAST PLAYER IMAGE STANDARDS
TARGET_WIDTH = 600
TARGET_HEIGHT = 800
TARGET_ASPECT_RATIO = 3.0 / 4.0  # 0.75
TARGET_MAX_SIZE_KB = 150
INITIAL_QUALITY = 85

HEADERS = {
    "User-Agent": "CricketBroadcastApp/1.0 (admin@cricketbroadcast.com)",
    "Accept": "application/json, image/webp, image/apng, image/*, */*"
}

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "player_registry.json")


def _normalize_key(name: str) -> str:
    """
    Converts player name to clean snake_case slug:
    e.g. "Virat Kohli" -> "virat_kohli"
         "Pathum Nissanka" -> "pathum_nissanka"
         "Steve Smith" -> "steve_smith"
    """
    if not name:
        return "unknown"
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", name.strip())
    slug = re.sub(r"\s+", "_", cleaned.lower())
    return slug or "unknown"


def load_registry() -> dict:
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading player registry: {e}")
    return {}


def save_registry(registry: dict):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving player registry: {e}")


def _match_abbreviated_player_name(player_name: str, registry: dict) -> str:
    """
    Matches live scorecard abbreviated names (e.g., "R Sharma", "R Jadeja", "W Hasaranga")
    to full registered player entries in player_registry.json.
    """
    if not player_name or not registry:
        return None

    clean_parts = [p.lower() for p in re.sub(r"[^a-zA-Z0-9\s]", "", player_name).split() if p]
    if not clean_parts:
        return None

    # Exact key match
    exact_key = "_".join(clean_parts)
    if exact_key in registry and registry[exact_key].get("blob_url"):
        return registry[exact_key]["blob_url"]

    # Abbreviation matching (e.g. initial 'r' + last name 'sharma')
    if len(clean_parts) >= 2:
        initial = clean_parts[0][0]  # 'r'
        last_name = clean_parts[-1] # 'sharma' or 'hasaranga'

        # Candidate search
        for reg_key, data in registry.items():
            reg_parts = reg_key.split("_")
            if len(reg_parts) >= 2:
                reg_first = reg_parts[0]
                reg_last = reg_parts[-1]
                if reg_last == last_name and reg_first.startswith(initial):
                    if data.get("blob_url"):
                        return data["blob_url"]

        # Last name fallback search
        for reg_key, data in registry.items():
            if reg_key.endswith(f"_{last_name}") or reg_key == last_name:
                if data.get("blob_url"):
                    return data["blob_url"]

    return None


def search_real_player_photo_url(player_name: str) -> str:
    """
    Searches Wikipedia MediaWiki API for a real high-resolution photograph of the cricketer.
    Uses non-blocking 2.0s timeout to prevent event loop stalls.
    """
    if not player_name:
        return None

    clean_name = player_name.strip()

    try:
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={clean_name}&prop=pageimages&format=json&pithumbsize=1000"
        with httpx.Client(headers=HEADERS, timeout=2.0, follow_redirects=True) as client:
            resp = client.get(wiki_url)
            if resp.status_code == 200:
                pages = resp.json().get("query", {}).get("pages", {})
                for page_id, page_info in pages.items():
                    if page_id != "-1":
                        thumbnail = page_info.get("thumbnail", {}).get("source")
                        if thumbnail and thumbnail.startswith("http"):
                            return thumbnail
    except Exception:
        pass

    return None


def crop_and_resize_portrait(image_bytes: bytes) -> bytes:
    """
    Processes image according to Broadcast Standards:
    - 600 x 800 px (3:4 ratio)
    - WebP format, quality 85% (< 150 KB)
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")

    orig_width, orig_height = img.size
    orig_aspect = orig_width / float(orig_height)

    if orig_aspect > TARGET_ASPECT_RATIO:
        new_width = int(orig_height * TARGET_ASPECT_RATIO)
        left = (orig_width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = orig_height
    else:
        new_height = int(orig_width / TARGET_ASPECT_RATIO)
        left = 0
        top = int((orig_height - new_height) * 0.15)
        right = orig_width
        bottom = top + new_height

    cropped_img = img.crop((left, top, right, bottom))
    resized_img = cropped_img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)

    quality = INITIAL_QUALITY
    output_buffer = io.BytesIO()
    resized_img.save(output_buffer, format="WEBP", quality=quality, method=6)
    webp_bytes = output_buffer.getvalue()
    size_kb = len(webp_bytes) / 1024.0

    while size_kb > TARGET_MAX_SIZE_KB and quality > 70:
        quality -= 5
        output_buffer = io.BytesIO()
        resized_img.save(output_buffer, format="WEBP", quality=quality, method=6)
        webp_bytes = output_buffer.getvalue()
        size_kb = len(webp_bytes) / 1024.0

    return webp_bytes


def upload_to_vercel_blob(filename: str, file_bytes: bytes) -> str:
    """
    Uploads raw WebP image binary directly to Vercel Blob Storage REST API.
    """
    if not BLOB_TOKEN:
        raise ValueError("BLOB_READ_WRITE_TOKEN environment variable is missing!")

    url = f"{BLOB_API_URL}/{filename}"
    headers = {
        "Authorization": f"Bearer {BLOB_TOKEN}",
        "x-api-version": "7",
        "content-type": "image/webp"
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.put(url, headers=headers, content=file_bytes)
        if response.status_code != 200:
            logger.error(f"Vercel Blob Binary Upload Failed ({response.status_code}): {response.text}")
            response.raise_for_status()

        data = response.json()
        public_url = data.get("url")
        return public_url


def upload_custom_player_photo(player_name: str, file_bytes: bytes, role_key: str = None) -> str:
    if not player_name:
        raise ValueError("Player name is required.")

    key = _normalize_key(player_name)
    processed_webp = crop_and_resize_portrait(file_bytes)
    filename = f"{key}.webp"
    blob_url = upload_to_vercel_blob(filename, processed_webp)

    registry = load_registry()
    entry = {
        "name": player_name,
        "filename": filename,
        "source_url": "Control Panel Upload",
        "blob_url": blob_url
    }
    registry[key] = entry

    if role_key:
        r_key = _normalize_key(role_key)
        registry[r_key] = entry

    save_registry(registry)
    return blob_url


def get_or_fetch_player_blob_url(player_name: str, fallback_image_url: str = None) -> str:
    """
    Main Manager:
    1. Checks persistent player_registry.json (including smart abbreviation matching e.g. R Sharma -> rohit_sharma).
    2. Returns Vercel Blob URL instantly if cached.
    """
    if not player_name or player_name == "Unknown Player":
        return "https://api.dicebear.com/7.x/avataaars/svg?seed=Player"

    registry = load_registry()
    matched_blob_url = _match_abbreviated_player_name(player_name, registry)
    if matched_blob_url:
        return matched_blob_url

    key = _normalize_key(player_name)
    source_url = fallback_image_url or search_real_player_photo_url(player_name)
    if not source_url:
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed={key}"

    try:
        with httpx.Client(headers=HEADERS, timeout=3.0, follow_redirects=True) as client:
            resp = client.get(source_url)
            resp.raise_for_status()
            raw_bytes = resp.content

        processed_webp = crop_and_resize_portrait(raw_bytes)
        filename = f"{key}.webp"
        blob_url = upload_to_vercel_blob(filename, processed_webp)

        registry[key] = {
            "name": player_name,
            "filename": filename,
            "source_url": source_url,
            "blob_url": blob_url
        }
        save_registry(registry)
        return blob_url
    except Exception:
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed={key}"
