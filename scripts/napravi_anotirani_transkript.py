#!/usr/bin/env python3
"""Spoji timestamp-ovan transkript sa snimcima ekrana u jedan anotirani Markdown fajl.

Lanac: `transkripcija file --format json` (segmenti sa vremenom) + `izvuci_snimke_ekrana.py`
(snimci na fiksnom intervalu) → svaki segment dobija poslednji snimak pre/na tom trenutku;
uzastopni segmenti pod istim snimkom se grupišu u jedan blok, da se ista slika ne ponavlja.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from izvuci_snimke_ekrana import format_timestamp, izvuci_snimke

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPO_ROOT / "raw/wyckoff_crypto_lab"
TRANSKRIPCIJA_REPO = Path.home() / "projekti/transkripcija"


def dobij_segmente(video_path: Path, model: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        izlaz = Path(tmp) / "segmenti.json"
        subprocess.run(
            [
                "uv", "run", "--project", str(TRANSKRIPCIJA_REPO),
                "transkripcija", "file", str(video_path),
                "--engine", "lokalno", "--format", "json",
                "--model", model,
                "-o", str(izlaz),
            ],
            check=True,
        )
        return json.loads(izlaz.read_text(encoding="utf-8"))


def najblizi_frame(vreme_s: float, frameovi: list[tuple[int, Path]]) -> Path | None:
    """Nađi poslednji snimak čije vreme je <= vreme_s ("kako je grafik izgledao tad")."""
    kandidati = [put for t, put in frameovi if t <= vreme_s]
    if kandidati:
        return kandidati[-1]
    return frameovi[0][1] if frameovi else None


def grupisi(segmenti: list[dict], frameovi: list[tuple[int, Path]]) -> list[dict]:
    grupe: list[dict] = []
    for seg in segmenti:
        frame = najblizi_frame(seg["start"], frameovi)
        if grupe and grupe[-1]["frame"] == frame:
            grupe[-1]["kraj"] = seg["end"]
            grupe[-1]["tekst"].append(seg["text"])
        else:
            grupe.append({"frame": frame, "pocetak": seg["start"], "kraj": seg["end"], "tekst": [seg["text"]]})
    return grupe


def sastavi_markdown(grupe: list[dict], slike_prefiks: str) -> str:
    delovi = []
    for grupa in grupe:
        naslov = f"## [{format_timestamp(int(grupa['pocetak']))} – {format_timestamp(int(grupa['kraj']))}]"
        deo = [naslov]
        if grupa["frame"] is not None:
            deo.append(f"![snimak ekrana]({slike_prefiks}/{grupa['frame'].name})")
        deo.append(" ".join(grupa["tekst"]))
        delovi.append("\n\n".join(deo))
    return "\n\n".join(delovi)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Putanja do video fajla")
    parser.add_argument("--interval", type=int, default=45, help="Interval snimaka u sekundama")
    parser.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    parser.add_argument(
        "--izlaz", type=Path, default=None,
        help="Ciljni .md fajl (podrazumevano raw/wyckoff_crypto_lab/annotated/<naziv-videa>.md)",
    )
    args = parser.parse_args()

    naziv = args.video.stem
    izlazni_md = args.izlaz or (LAB_ROOT / "annotated" / f"{naziv}.md")
    slike_dir = LAB_ROOT / "screenshots" / naziv

    print("Izvlačim snimke ekrana...")
    snimci = izvuci_snimke(args.video, slike_dir, args.interval)
    frameovi = [(i * args.interval, put) for i, put in enumerate(snimci)]

    print("Transkribujem sa vremenskim oznakama...")
    segmenti = dobij_segmente(args.video, args.model)

    grupe = grupisi(segmenti, frameovi)
    slike_prefiks = f"../screenshots/{naziv}"
    md = sastavi_markdown(grupe, slike_prefiks)

    izlazni_md.parent.mkdir(parents=True, exist_ok=True)
    izlazni_md.write_text(md, encoding="utf-8")
    print(f"Sačuvano: {izlazni_md} ({len(grupe)} blokova, {len(snimci)} snimaka)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
