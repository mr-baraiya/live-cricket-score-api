import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.player_image_service import get_or_fetch_player_blob_url, load_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("populate_player_blobs")

GLOBAL_CRICKETERS = [
    # Sri Lanka
    "Pathum Nissanka",
    "Kusal Mendis",
    "Dhananjaya de Silva",
    "Kamindu Mendis",
    "Asitha Fernando",
    "Dimuth Karunaratne",
    "Angelo Mathews",
    "Prabath Jayasuriya",
    "Vishwa Fernando",
    "Wanindu Hasaranga",
    "Charith Asalanka",
    "Maheesh Theekshana",
    "Matheesha Pathirana",

    # India
    "Rohit Sharma",
    "Virat Kohli",
    "Shubman Gill",
    "Yashasvi Jaiswal",
    "Rishabh Pant",
    "Ravindra Jadeja",
    "Jasprit Bumrah",
    "Mohammed Siraj",
    "Kuldeep Yadav",
    "KL Rahul",
    "Hardik Pandya",
    "Suryakumar Yadav",

    # Australia
    "Steve Smith",
    "Travis Head",
    "Marnus Labuschagne",
    "Pat Cummins",
    "Mitchell Starc",
    "Josh Hazlewood",
    "Nathan Lyon",
    "Glenn Maxwell",

    # England
    "Joe Root",
    "Ben Stokes",
    "Harry Brook",
    "Zak Crawley",
    "Ollie Pope",
    "Mark Wood",
    "Jos Buttler",

    # South Africa
    "Kagiso Rabada",
    "Heinrich Klaasen",
    "Quinton de Kock",
    "Aiden Markram",
    "Anrich Nortje",

    # Pakistan
    "Babar Azam",
    "Shaheen Afridi",
    "Mohammad Rizwan",
    "Naseem Shah",

    # New Zealand
    "Kane Williamson",
    "Daryl Mitchell",
    "Rachin Ravindra",
    "Trent Boult",

    # West Indies & Afghanistan
    "Nicholas Pooran",
    "Andre Russell",
    "Shai Hope",
    "Rashid Khan",
    "Mohammad Nabi",
    "Rahmanullah Gurbaz"
]


def run_bulk_population():
    logger.info("=== Starting Global Squad Player Portrait Pipeline ===")
    registry = load_registry()
    logger.info(f"Loaded existing registry with {len(registry)} player entries.")

    success_count = 0
    for name in GLOBAL_CRICKETERS:
        try:
            blob_url = get_or_fetch_player_blob_url(name)
            logger.info(f"✓ {name}: {blob_url}")
            success_count += 1
        except Exception as e:
            logger.error(f"✕ Failed for {name}: {e}")

    updated_registry = load_registry()
    logger.info(f"=== Bulk Population Complete: {success_count}/{len(GLOBAL_CRICKETERS)} processed ===")
    logger.info(f"Total registered players in player_registry.json: {len(updated_registry)}")


if __name__ == "__main__":
    run_bulk_population()
