---
name: wyckoff-crypto-lab-sazetak
description: Čita transkript nedeljne Wyckoff Crypto Lab Discord analize (raw/wyckoff_crypto_lab/transcripts/) i izvlači sažetak — Wyckoff faza i predviđanja za BTC, ETH i pomenute altcoin-e (glavni fokus, puni detalji), kraće za S&P 500/zlato/šire tržište (manje bitno). Koristi kad korisnik kaže "izvuci suštinu iz [datum] analize", "šta se predviđa za BTC/ETH", "sažmi poslednju Wyckoff analizu", ili posle transkripcije nove epizode.
disable-model-invocation: false
---

# Wyckoff Crypto Lab — sažetak analize

Cilj: korisnik umesto da gleda ceo YouTube klip od pola sata, na brzinu vidi šta eksterni
analitičar predviđa. Ovo **NIJE** wiki-kanonsko znanje niti naš trading signal — vidi napomenu u
šablonu ispod. Za razliku od `knowledge/wiki/`, ovo je lični digest tuđe (plaćene) analize.

## Ulaz

Transkript iz `raw/wyckoff_crypto_lab/transcripts/<naziv>.md` (napravljen skilom
`wyckoff-crypto-lab-transkripcija`). Ako transkript za traženi datum ne postoji, prvo pokreni taj
skil, ne izmišljaj sadržaj.

**Pročitaj CEO transkript pre pisanja sažetka** — ne samo prvih par pasusa. Analitičar često menja
mišljenje ili dodaje nijansu kasnije u snimku (npr. "ali ako probije X, onda...").

## Izlaz

Sačuvaj u `raw/wyckoff_crypto_lab/summaries/<isti-naziv-kao-transkript>.md` (van git-a, kao i
transkript — isti razlog: izvedeno iz plaćenog sadržaja).

### Šablon

```markdown
# Sažetak: <naslov epizode> (<datum>)

> Sažetak stavova eksternog analitičara (Wyckoff Crypto Lab, plaćena Discord grupa) — nije naš
> signal niti wiki-kanonsko znanje. Izvor: <youtube_url iz manifest.json>. Pun transkript:
> `raw/wyckoff_crypto_lab/transcripts/<naziv>.md`.

## Bitcoin (BTC)
- **Trenutna Wyckoff faza/struktura:** ...
- **Predviđanje za naredni period:** ...
- **Ključni nivoi pomenuti (support/resistance):** ...

## Ethereum (ETH)
(isti format kao BTC)

## Ostali kriptovaluta pomenuti
Za svaki pomenuti altcoin — kratko, isti format. Ako nijedan nije pomenut, napiši "Nije pomenuto
u ovoj epizodi", ne izostavljaj sekciju ćutke.

## Šira tržišta (kraće — sekundarni fokus)
- **S&P 500 / opšta berza:** 1-2 rečenice.
- **Zlato:** 1 rečenica, samo ako je pomenuto.
- **Ostalo pomenuto (DXY, obveznice, itd.):** 1 rečenica po stavci, samo ako je pomenuto.
```

## Pravila

- **Ne izmišljaj.** Ako nešto nije pomenuto u transkriptu, napiši "nije pomenuto" — ne popunjavaj
  praznine iz opšteg znanja o tržištu.
- **Razlikuj tvrdnju od nagoveštaja.** Ako analitičar kaže "verovatno" ili "ako se desi X", prenesi
  tu uslovnost — ne pretvaraj nagoveštaj u siguran zaključak.
- **BTC/ETH/altcoin dobijaju puni detalj; S&P/zlato kratko** — ovo je eksplicitan prioritet
  korisnika, ne podrazumevana težina.
- **Precizno, ne cvetno** — isti stil kao wiki (CLAUDE.md §9): "brže od prethodnog impulsa" umesto
  "brzo". Poredi kad analitičar poredi.

## Šta ovaj skil NE radi

- Ne poredi sa našom sopstvenom Wyckoff analizom istog perioda — to je budući, poseban korak
  (eval/poređenje tačnosti), još nije izgrađen.
- Ne piše u `knowledge/wiki/` — sažetak je lični digest, ne wiki znanje.
