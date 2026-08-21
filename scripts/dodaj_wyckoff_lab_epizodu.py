#!/usr/bin/env python3
"""Dodaj novu epizodu u raw/wyckoff_crypto_lab/: skini pun video sa YouTube-a i upiši je u manifest.json.

Posle ovoga, `scripts/transkribuj_wyckoff_lab.py` je pokupi automatski (status "downloaded").
Skidanje ide preko globalnog `transkripcija skini` (deljena logika sa frontend-saveti, ne
duplira se yt-dlp poziv ovde).
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
DESCRIPTIONS_DIR = LAB_ROOT / "descriptions"
TRANSKRIPCIJA_REPO = Path.home() / "projekti/transkripcija"


def skini_video(url: str) -> Path:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    rezultat = subprocess.run(
        [
            "uv", "run", "--project", str(TRANSKRIPCIJA_REPO),
            "transkripcija", "skini", url,
            "--izlaz", str(VIDEOS_DIR),
            "--opis",
        ],
        check=True, capture_output=True, text=True,
    )
    linije = [red for red in rezultat.stdout.strip().splitlines() if red.strip()]
    if not linije:
        raise RuntimeError(f"`transkripcija skini` nije vratio putanju za: {url}")
    return Path(linije[-1])


def sacuvaj_opis(video_path: Path) -> str | None:
    opis_fajl = video_path.with_suffix(".description")
    if not opis_fajl.exists():
        return None
    DESCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    cilj = DESCRIPTIONS_DIR / f"{video_path.stem}.txt"
    shutil.move(str(opis_fajl), cilj)
    return f"descriptions/{cilj.name}"


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

    description_file = sacuvaj_opis(video_path)

    manifest.append({
        "date": date_iso,
        "title": title,
        "youtube_url": args.url,
        "video_file": f"videos/{name}",
        "transcript_file": f"transcripts/{name[:-4]}.md",
        "description_file": description_file,
        "status": "downloaded",
    })
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Dodato u manifest: {title} ({date_iso})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
