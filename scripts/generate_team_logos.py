#!/usr/bin/env python3
"""
generate_team_logos.py — Generates SVG team logo placeholders for both teams
and uploads them to Vercel Blob storage.

Usage:
    python scripts/generate_team_logos.py --team-a "India" --team-b "Australia"

This is useful when no logo files are available yet — it creates a styled
SVG badge with team initials and uploads it so the broadcast frontend picks it up.
"""

import argparse
import os
import sys
import re

# Allow running from root or scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.team_logo_service import upload_team_logo


# ─── Colour Palette ───────────────────────────────────────────────────────────
PALETTE = [
    ("#1a56db", "#e8f0fe"),  # Blue
    ("#059669", "#d1fae5"),  # Green
    ("#dc2626", "#fee2e2"),  # Red
    ("#7c3aed", "#ede9fe"),  # Purple
    ("#d97706", "#fef3c7"),  # Amber
    ("#0891b2", "#e0f2fe"),  # Cyan
]


def _team_initials(name: str) -> str:
    words = name.strip().split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:3].upper()


def generate_svg_logo(team_name: str, color_idx: int = 0) -> bytes:
    """
    Generates a clean 256×256 SVG badge for a team:
    - Gradient background circle
    - Bold team initials
    - Subtle outer ring
    Returns raw SVG bytes.
    """
    initials = _team_initials(team_name)
    bg_color, text_color = PALETTE[color_idx % len(PALETTE)]

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <radialGradient id="bg" cx="40%" cy="35%" r="70%">
      <stop offset="0%" stop-color="{bg_color}" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="{bg_color}" stop-opacity="0.6"/>
    </radialGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Outer ring -->
  <circle cx="128" cy="128" r="124" fill="none" stroke="{bg_color}" stroke-opacity="0.4" stroke-width="3"/>

  <!-- Main badge circle -->
  <circle cx="128" cy="128" r="112" fill="url(#bg)" filter="url(#shadow)"/>

  <!-- Inner ring -->
  <circle cx="128" cy="128" r="108" fill="none" stroke="{text_color}" stroke-opacity="0.15" stroke-width="2"/>

  <!-- Team Initials -->
  <text
    x="128" y="128"
    text-anchor="middle"
    dominant-baseline="central"
    font-family="'Arial Black', 'Impact', sans-serif"
    font-size="80"
    font-weight="900"
    fill="{text_color}"
    letter-spacing="-4"
  >{initials}</text>

  <!-- Bottom team name strip -->
  <rect x="52" y="188" width="152" height="28" rx="6" fill="{text_color}" fill-opacity="0.12"/>
  <text
    x="128" y="206"
    text-anchor="middle"
    dominant-baseline="central"
    font-family="'Arial', sans-serif"
    font-size="11"
    font-weight="700"
    fill="{text_color}"
    fill-opacity="0.9"
    letter-spacing="1.5"
  >{team_name.upper()[:18]}</text>
</svg>"""

    return svg.encode("utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Generate SVG team logo badges and upload to Vercel Blob"
    )
    parser.add_argument("--team-a", required=True, help="Name of Team A (e.g. 'India')")
    parser.add_argument("--team-b", required=True, help="Name of Team B (e.g. 'Australia')")
    args = parser.parse_args()

    teams = [
        (args.team_a, 0),
        (args.team_b, 2),
    ]

    for team_name, color_idx in teams:
        print(f"\n📐 Generating logo for: {team_name}")
        svg_bytes = generate_svg_logo(team_name, color_idx)

        print(f"   Uploading to Vercel Blob…")
        try:
            blob_url = upload_team_logo(team_name, svg_bytes)
            print(f"   ✅ Done: {blob_url}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

    print("\n✔ Team logos generated and uploaded. Restart the frontend to see changes.")


if __name__ == "__main__":
    main()
