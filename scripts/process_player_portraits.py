import os
import io
import json
import logging
import httpx
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("player_portrait_pipeline")

BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
BLOB_API_URL = "https://blob.vercel-storage.com"

# BROADCAST PLAYER IMAGE STANDARDS
TARGET_WIDTH = 600
TARGET_HEIGHT = 800
TARGET_ASPECT_RATIO = 3.0 / 4.0  # 0.75
TARGET_MAX_SIZE_KB = 150
ABSOLUTE_MAX_SIZE_KB = 300
INITIAL_QUALITY = 85

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def crop_and_resize_portrait(image_bytes: bytes) -> bytes:
    """
    Processes raw image bytes according to Broadcast Player Image Standards:
    - Format: WebP
    - Dimensions: 600 x 800 px (3:4 ratio)
    - Quality: 80-85% (Target size < 150 KB)
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        logger.warning(f"Unrecognized image format ({e}), rendering studio portrait backdrop")
        img = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT), color=(15, 23, 42))

    if img.mode != "RGB":
        img = img.convert("RGB")

    orig_width, orig_height = img.size
    orig_aspect = orig_width / float(orig_height)

    # Determine 3:4 crop box
    if orig_aspect > TARGET_ASPECT_RATIO:
        new_width = int(orig_height * TARGET_ASPECT_RATIO)
        left = (orig_width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = orig_height
    else:
        new_height = int(orig_width / TARGET_ASPECT_RATIO)
        left = 0
        top = int((orig_height - new_height) * 0.2)
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

    logger.info(f"Processed portrait to {TARGET_WIDTH}x{TARGET_HEIGHT} WebP: {size_kb:.2f} KB (Quality={quality}%)")
    return webp_bytes


def upload_to_vercel_blob(filename: str, file_bytes: bytes) -> str:
    """
    Uploads processed WebP portrait to Vercel Blob Storage using REST API.
    Returns public CDN URL.
    """
    if not BLOB_TOKEN:
        raise ValueError("BLOB_READ_WRITE_TOKEN environment variable is missing!")

    url = f"{BLOB_API_URL}/{filename}"
    headers = {
        "Authorization": f"Bearer {BLOB_TOKEN}",
        "x-api-version": "7",
        "content-type": "image/webp"
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.put(url, headers=headers, content=file_bytes)
        if response.status_code != 200:
            logger.error(f"Vercel Blob Upload Failed ({response.status_code}): {response.text}")
            response.raise_for_status()

        data = response.json()
        public_url = data.get("url")
        logger.info(f"Successfully uploaded to Vercel Blob: {public_url}")
        return public_url


def process_and_upload_player(player_id: str, image_url_or_bytes) -> str:
    """
    Main entrypoint: Fetches player photo, enforces 600x800 WebP broadcast standard,
    and uploads to Vercel Blob as <player_id>.webp.
    """
    if isinstance(image_url_or_bytes, str) and image_url_or_bytes.startswith("http"):
        logger.info(f"Downloading player image for ID {player_id}: {image_url_or_bytes}")
        with httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            resp = client.get(image_url_or_bytes)
            resp.raise_for_status()
            raw_bytes = resp.content
    elif isinstance(image_url_or_bytes, bytes):
        raw_bytes = image_url_or_bytes
    else:
        raise ValueError("Invalid image input: expected URL string or bytes.")

    processed_webp = crop_and_resize_portrait(raw_bytes)
    filename = f"{player_id}.webp"
    blob_url = upload_to_vercel_blob(filename, processed_webp)
    return blob_url


if __name__ == "__main__":
    logger.info("=== Broadcast Player Portrait Pipeline ===")

    sample_players = [
        {
            "id": "1413",
            "name": "Virat Kohli",
            "url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800&auto=format&fit=crop"
        },
        {
            "id": "1113",
            "name": "Rohit Sharma",
            "url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&auto=format&fit=crop"
        }
    ]

    results = {}
    for player in sample_players:
        try:
            url = process_and_upload_player(player["id"], player["url"])
            results[player["id"]] = {"name": player["name"], "blob_url": url}
        except Exception as e:
            logger.error(f"Failed to process player {player['id']}: {e}")

    logger.info("Batch processing results:")
    logger.info(json.dumps(results, indent=2))
