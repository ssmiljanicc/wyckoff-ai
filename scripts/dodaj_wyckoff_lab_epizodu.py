#!/usr/bin/env python3
"""Dodaj novu epizodu u raw/wyckoff_crypto_lab/: skini pun video sa YouTube-a i upiši je u manifest.json.

Posle ovoga, `scripts/transkribuj_wyckoff_lab.py` je pokupi automatski (status "downloaded").
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPO_ROOT / "raw/wyckoff_crypto_lab"
MANIFEST_PATH = LAB_ROOT / "manifest.json"
VIDEOS_DIR = LAB_ROOT / "videos"


def skini_video(url: str) -> Path:
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp nije instaliran. Instaliraj: brew install yt-dlp")

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    sablon = VIDEOS_DIR / "%(upload_date)s - %(title)s.%(ext)s"

    subprocess.run(
        [
            "yt-dlp",
            "-f", "bv*+ba/b",
            "--extractor-args", "youtube:player_client=android",
            "--no-overwrites",
            "-o", str(sablon),
            url,
        ],
        check=True,
    )

    kandidati = sorted(VIDEOS_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not kandidati:
        raise RuntimeError(f"Video nije skinut za: {url}")
    return kandidati[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="YouTube link nove epizode")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    print(f"Skidam: {args.url}")
    video_path = skini_video(args.url)
    name = video_path.name
    date_prefix = name[:8]
    date_iso = f"{date_prefix[:4]}-{date_prefix[4:6]}-{date_prefix[6:8]}" if date_prefix.isdigit() else datetime.now().strftime("%Y-%m-%d")
    title = name[11:-4] if name[8:11] == " - " else name[:-4]

    if any(unos["video_file"] == f"videos/{name}" for unos in manifest):
        print("Već postoji u manifestu, preskačem upis.")
        return 0

    manifest.append({
        "date": date_iso,
        "title": title,
        "youtube_url": args.url,
        "video_file": f"videos/{name}",
        "transcript_file": f"transcripts/{name[:-4]}.md",
        "status": "downloaded",
    })
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Dodato u manifest: {title} ({date_iso})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
