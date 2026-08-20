#!/usr/bin/env python3
"""Izvuci snimke ekrana iz videa na fiksnom intervalu (ffmpeg, ne "pametna" detekcija).

Nazivi fajlova nose vreme (MM-SS ili H-MM-SS) da ih `napravi_anotirani_transkript.py`
može uparivati sa segmentima transkripta bez čitanja slika.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPO_ROOT / "raw/wyckoff_crypto_lab"


def format_timestamp(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}-{m:02d}-{s:02d}" if h else f"{m:02d}-{s:02d}"


def izvuci_snimke(video_path: Path, izlazni_dir: Path, interval_s: int = 45) -> list[Path]:
    izlazni_dir.mkdir(parents=True, exist_ok=True)
    sablon = izlazni_dir / "tmp_%04d.jpg"

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"fps=1/{interval_s}",
            "-q:v", "2",
            str(sablon),
        ],
        check=True,
        capture_output=True,
    )

    privremeni = sorted(izlazni_dir.glob("tmp_*.jpg"))
    rezultat = []
    for i, fajl in enumerate(privremeni):
        vreme_s = i * interval_s
        novo_ime = izlazni_dir / f"frame_{format_timestamp(vreme_s)}.jpg"
        fajl.rename(novo_ime)
        rezultat.append(novo_ime)
    return rezultat


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Putanja do video fajla")
    parser.add_argument("--interval", type=int, default=45, help="Interval u sekundama (podrazumevano 45)")
    parser.add_argument(
        "--izlaz", type=Path, default=None,
        help="Ciljni folder (podrazumevano raw/wyckoff_crypto_lab/screenshots/<naziv-videa>/)",
    )
    args = parser.parse_args()

    izlazni_dir = args.izlaz or (LAB_ROOT / "screenshots" / args.video.stem)
    snimci = izvuci_snimke(args.video, izlazni_dir, args.interval)
    print(f"Izvučeno {len(snimci)} snimaka u {izlazni_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
