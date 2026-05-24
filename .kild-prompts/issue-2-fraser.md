# Kild prompt — Issue #2: Bruce Fraser image download

Implementiraj GitHub issue **#2** iz `ssmiljanicc/wyckoff-ai`: download Bruce Fraser slika + rebuild .md fajlova sa inline image references.

## Kontekst — pročitaj OVO PRVO (redom)

1. `gh issue view 2 --repo ssmiljanicc/wyckoff-ai` — puna spec
2. `raw/INVENTORY.md` u repo-u — trenutno stanje
3. `prds/01-knowledge-base.md` — project context (zašto se ovo radi)

## Ključne činjenice (iz inventory-ja, korigovane od HANDOFF-a)

- **855 unique slika** (NE 854 kao u handoff-u), **1565 total references** — mnoge slike se reuse-uju kroz članke
- 243 HTML fajlova lokalno na: `skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts/html/`
- 243 text-only .md na: `skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts/posts/`
- Manifest sa metapodacima: `skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts/manifest.json`

## Setup već gotov u main-u

- `pyproject.toml` sa `requests`, `beautifulsoup4`, `lxml` (samo `uv sync` i kreni)
- `.gitignore` ima Python entries
- Koristi **uv** za sve (globalna konvencija)

## Plan rada

1. `uv sync` — instalira deps
2. Napiši `scripts/download_fraser_images.py` koji:
   - Parsira svaki HTML iz `skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts/html/`
   - Ekstrahuje content image URLs — **striktan filter:** `https://d.stockcharts.com/img/articles/` prefix only (skip logos, avatars, navigation)
   - Download-uje svaku unique sliku **jednom** u `raw/bruce_fraser/images/<filename>` (deduplikuj po URL-u)
   - Regeneriše .md-ove u `raw/bruce_fraser/posts/<slug>.md` sa inline image refs umetnutim **na poziciji gde je `<img>` tag bio u HTML-u** (NE samo na kraju)
   - Idempotent: re-run preskače već skinute
   - Logs: downloaded count, skipped count, 404s, total bytes
3. **Politika prema serveru:** sekvencijalno, ~0.5s delay između download-a, deskriptivan User-Agent (npr. `wyckoff-ai-rebuild/0.1`). Na 429/403 stani i prijavi.
4. Ako total veličina slika prelazi **100MB**, dodaj `raw/bruce_fraser/images/` u `.gitignore` i objasni u commit poruci. Ispod 100MB — commit slike (radi reproducibility).

## Validacija pre commit-a

- 855 unique slika downloaded — verifikuj brojanjem
- 1565 image references inserted across .md fajlova
- Re-running scripta je no-op (drugi run downloaduje 0)
- Spot-check 3 nasumična članka: refs odgovaraju HTML pozicijama (ne samo na kraju)

## Commit + PR

- Commit script + raw/bruce_fraser/posts/ + (opciono) raw/bruce_fraser/images/ + .gitignore izmene
- Otvori PR: naslov `#2 Download Fraser images + rebuild MDs`
- PR body neka sadrži: downloaded count, total size, validation results, 3 spot-check linkova

## Bitno — šta NE diraj

- NE menjaj `skills/wyckoff-trader-skill/references/assets/...` ničim (to je sada legacy "before" stanje)
- Sve novo ide pod `raw/bruce_fraser/`

## Kad završiš

Ostavi link ka PR-u i kratak summary. Ne mergaj sam — sačekaj review.
