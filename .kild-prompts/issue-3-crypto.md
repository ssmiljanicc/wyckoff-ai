# Kild prompt — Issue #3: Crypto archive re-scrape

Implementiraj GitHub issue **#3** iz `ssmiljanicc/wyckoff-ai`: re-scrape crypto archive postova sa slikama.

## Kontekst — pročitaj OVO PRVO (redom)

1. `gh issue view 3 --repo ssmiljanicc/wyckoff-ai` — puna spec, paywall politika već definisana
2. `raw/INVENTORY.md` — sekcija "Source 2 — Crypto Archive" ima listu 12 verovatno paywalled postova
3. `prds/01-knowledge-base.md` — project context

## Ključne činjenice

- 46 URL-ova u manifestu: `skills/wyckoff-trader-skill/references/assets/crypto_archive/manifest.json`
- Stari text-only .md fajlovi: `skills/wyckoff-trader-skill/references/assets/crypto_archive/posts/`
- **HTML nikad nije sačuvan** u prošlom scrape-u — sad mora da se sačuva
- **12 postova verovatno paywalled** (već identifikovani u inventory-ju, char_count < 1500). Uključuje neočekivano vol 26.

## Setup već gotov u main-u

- `pyproject.toml` sa `requests`, `beautifulsoup4`, `lxml`
- Koristi **uv** za sve

## Plan rada

1. `uv sync`
2. Napiši `scripts/scrape_crypto_archive.py` koji:
   - Učita URL-ove iz `skills/wyckoff-trader-skill/references/assets/crypto_archive/manifest.json`
   - Za svaki URL:
     - Fetch (sa rate limit-om ~1s)
     - Sačuvaj **full HTML** u `raw/crypto_archive/html/<slug>.html`
     - Ekstrahuj tekst → `raw/crypto_archive/posts/<slug>.md`
     - Download content slike u `raw/crypto_archive/images/<slug>/`
     - Inline image refs u .md na ispravnim pozicijama (gde je `<img>` tag bio u HTML-u)
   - Build novi manifest u `raw/crypto_archive/manifest.json` sa poljima: `slug, url, date, char_count, html_file, image_count, status` (`status` može biti `ok | paywalled | error`)
3. **Paywall politika — NE bypass-uj:**
   - Detektuj paywall (content < 1000 chars ILI klasični "subscribe to read" UI element)
   - Mark u manifestu `status: "paywalled"`
   - Sačuvaj public excerpt (šta god je dostupno)
4. **Rate limit i etiketa:**
   - ~1s delay između requests-a
   - Deskriptivan User-Agent: `wyckoff-ai-rebuild/0.1 (contact: ssmiljanic3@gmail.com)`
   - Na 429/403 — stani, prijavi, ne pokušavaj agresivnije
5. **Idempotent** — re-run preskoči što već postoji u `raw/crypto_archive/`
6. Logs: downloaded posts, paywalled posts, errors, total images, total bytes

## Validacija pre commit-a

- Svih 46 URL-ova obrađeno — ni jedan ne sme tiho da nestane. Svaki ima status u manifestu.
- HTML sačuvan za svih 46 (čak i za paywalled — kao dokaz)
- Spot-check: vol 14 (full content) treba da ima više slika i 7000+ chars; vol 58 (paywalled) treba da ima `status: paywalled` u manifestu
- Re-run je no-op

## Commit + PR

- Commit script + raw/crypto_archive/ + .gitignore (ako treba za images)
- Otvori PR: `#3 Re-scrape crypto archive with images`
- PR body: total posts processed, paywalled count, total images, validation results

## Šta NE diraj

- Legacy `skills/wyckoff-trader-skill/references/assets/crypto_archive/...` ostaje netaknut
- Sve novo pod `raw/crypto_archive/`

## Kad završiš

PR link + summary. Bez self-merge — sačekaj review.
