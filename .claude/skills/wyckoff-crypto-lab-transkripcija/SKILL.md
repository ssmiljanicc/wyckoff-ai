---
name: wyckoff-crypto-lab-transkripcija
description: Upravlja epizodama Discord "Wyckoff Crypto Lab" grupe u raw/wyckoff_crypto_lab/ — dodaje novu epizodu (skida pun video sa YouTube-a, upisuje u manifest.json), pokreće lokalnu transkripciju (mlx-whisper preko globalnog skila `transkripcija`), i pravi anotirani transkript sa snimcima ekrana (uparuje tekst sa onim što je autor nacrtao na grafiku u tom trenutku). Koristi kad korisnik kaže "dodaj novu Wyckoff analizu", "transkribuj novi klip", "pokreni transkripciju za sve što nije urađeno", "napravi anotirani transkript sa snimcima ekrana", ili pošalje novi YouTube link iz te grupe.
disable-model-invocation: false
---

# Wyckoff Crypto Lab — transkripcija epizoda

Ovaj skil upravlja **sirovim izvorom** `raw/wyckoff_crypto_lab/` — nedeljne YouTube analize iz
plaćene Discord grupe. Video i transkripti su **namerno van git-a** (`.gitignore`) jer je to
plaćen, privatan sadržaj — ne diraj tu odluku bez izričitog dogovora sa korisnikom (videti
`raw/wyckoff_crypto_lab/manifest.json` napomenu i CLAUDE.md).

## Struktura

```
raw/wyckoff_crypto_lab/
  manifest.json          ← praćen u git-u (samo metapodaci: datum, naslov, link, status)
  videos/                ← puni video, van git-a
  transcripts/            ← transkripti (čist tekst, bez vremena), van git-a
  summaries/              ← sažeci (skil wyckoff-crypto-lab-sazetak), van git-a
  screenshots/<naziv>/    ← snimci ekrana na fiksnom intervalu, van git-a
  annotated/              ← transkript + snimci ekrana spojeni, van git-a
```

`manifest.json` je lista unosa:
```json
{
  "date": "2026-08-19",
  "title": "Wyckoff Crypto Discussion - August 19th 2026",
  "youtube_url": "https://youtu.be/...",
  "video_file": "videos/20260819 - ....mp4",
  "transcript_file": "transcripts/20260819 - ....md",
  "status": "downloaded"   // ili "transcribed"
}
```

## Operacija: dodaj novu epizodu

Kad korisnik pošalje novi YouTube link (npr. nedeljni Discord post):
```bash
cd ~/projekti/wyckoff-ai
python3 scripts/dodaj_wyckoff_lab_epizodu.py "<youtube-link>"
```
Ovo skine pun video (yt-dlp, android klijent zbog 403 greške) u `videos/` i doda unos u
`manifest.json` sa `status: "downloaded"`. Ne transkribuje automatski — sledeći korak je posebna
komanda (ispod), da korisnik može da odluči kada.

## Operacija: transkribuj

Pokreće lokalnu transkripciju (mlx-whisper preko `transkripcija` alata — vidi globalni skil
`transkripcija` za detalje tog CLI-ja) za sve unose sa `status: "downloaded"` i posle upisuje
`status: "transcribed"`.

Sve što čeka:
```bash
python3 scripts/transkribuj_wyckoff_lab.py
```

Samo probu (prvih N):
```bash
python3 scripts/transkribuj_wyckoff_lab.py --limit 1
```

Samo konkretan datum (npr. korisnik traži baš tu epizodu):
```bash
python3 scripts/transkribuj_wyckoff_lab.py --date 2026-08-19
```

Skripta interno zove `uv run --project ~/projekti/transkripcija transkripcija file ... --engine
lokalno` — laba veza preko fajla, ne preko Python uvoza (namerna odluka, vidi
`scripts/transkribuj_wyckoff_lab.py` docstring).

## Operacija: napravi anotirani transkript (tekst + snimci ekrana)

Čist transkript (gore) ne hvata šta je autor nacrtao na grafiku dok priča. Ova komanda spaja
transkript sa vremenskim oznakama (preko globalnog skila `transkripcija`, `--format json`) i
snimke ekrana izvučene na fiksnom intervalu (podrazumevano na 45 sekundi), u jedan Markdown fajl
gde je posle svakog dela teksta ugrađena slika onoga što se u tom trenutku videlo na ekranu:

```bash
python3 scripts/napravi_anotirani_transkript.py raw/wyckoff_crypto_lab/videos/"<naziv-fajla>.mp4"
```

Rezultat ide u `raw/wyckoff_crypto_lab/annotated/<naziv-fajla>.md`, snimci u
`raw/wyckoff_crypto_lab/screenshots/<naziv-fajla>/`. Interval je podesiv (`--interval 30`) —
fiksni interval je namerno prost izbor (ne "pametna" detekcija promene na ekranu), pošto tekst uz
sliku i dalje daje kontekst i kad slika ne pogodi tačan trenutak crtanja. Uzastopni delovi teksta
koji padaju pod isti snimak se grupišu, da se ista slika ne ponavlja iznova.

**Kad koristiti ovo umesto obične transkripcije:** kad korisnik pita nešto vizuelno ("gde je
nacrtao liniju", "kako je izgledao grafik kad je pomenuo spring") ili eksplicitno traži anotirani
transkript/snimke ekrana. Za običan tekstualni sažetak (`wyckoff-crypto-lab-sazetak`), obična
`transcripts/` verzija je dovoljna i brža — ne pravi anotiranu verziju bez potrebe, pošto pravi i
video-obradu (ffmpeg) i celu transkripciju iznova.

## Šta ovaj skil NE radi

- Ne izvlači sažetak/predviđanja iz transkripta — to je `wyckoff-crypto-lab-sazetak` skil.
- Ne commit-uje video/transkript sadržaj — to je namerno zabranjeno (.gitignore).
- Ne menja `transkripcija` alat — taj repo je nezavisan, deli se i sa drugim projektima (npr. `lakora`).
