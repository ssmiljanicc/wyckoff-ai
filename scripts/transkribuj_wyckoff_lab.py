#!/usr/bin/env python3
"""Transkribuj video iz raw/wyckoff_crypto_lab/ preko spoljnog `transkripcija` alata.

Ne uvozi `transkripcija` kao Python zavisnost — poziva njen CLI preko `uv run`
u njenom sopstvenom repou i samo prihvata izlazni .md fajl. Laba veza, bez
mešanja ML zavisnosti (mlx, torch...) u wyckoff-ai.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPO_ROOT / "raw/wyckoff_crypto_lab"
MANIFEST_PATH = LAB_ROOT / "manifest.json"
TRANSKRIPCIJA_REPO = Path.home() / "projekti/transkripcija"


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: list[dict]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def transkribuj(video_path: Path, transkript_path: Path) -> None:
    transkript_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uv", "run", "--project", str(TRANSKRIPCIJA_REPO),
            "transkripcija", "file", str(video_path),
            "--engine", "lokalno",
            "-o", str(transkript_path),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Transkribuj najviše N unosa (za probu)")
    parser.add_argument("--date", default=None, help="Transkribuj samo unos za dati datum (YYYY-MM-DD)")
    args = parser.parse_args()

    manifest = load_manifest()
    stavke = [unos for unos in manifest if unos["status"] == "downloaded"]
    if args.date:
        stavke = [unos for unos in stavke if unos["date"] == args.date]
    if args.limit:
        stavke = stavke[: args.limit]

    if not stavke:
        print("Nema stavki za transkripciju (sve su već transkribovane ili nedostaje status 'downloaded').")
        return 0

    for i, unos in enumerate(stavke, 1):
        video_path = LAB_ROOT / unos["video_file"]
        transkript_path = LAB_ROOT / unos["transcript_file"]
        print(f"[{i}/{len(stavke)}] {unos['title']}")

        if not video_path.exists():
            print(f"  GREŠKA: video ne postoji: {video_path}", file=sys.stderr)
            continue

        try:
            transkribuj(video_path, transkript_path)
        except subprocess.CalledProcessError as e:
            print(f"  GREŠKA: {e}", file=sys.stderr)
            continue

        unos["status"] = "transcribed"
        save_manifest(manifest)
        print(f"  Sačuvano u: {transkript_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
