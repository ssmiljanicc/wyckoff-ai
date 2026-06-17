# Feature: Phase 5 — Analysis Journal (append-only dnevnik živih analiza)

## Summary

Novi append-only JSONL store + FastMCP server koji beleži **ceo** scenario svake žive Wyckoff analize (narativ + strukturisan forecast + model/effort + putanja grafika), za razliku od `signal_logger`-a koji hvata samo uži trade signal. Mesečni fajlovi `data/journal/YYYY-MM.jsonl`, aktiviran u `.mcp.json`. Kasniji `review` tok popunjava šta se stvarno desilo (ocenljivost posle N meseci). Gradi se po uzoru na `scripts/mcp/signal_logger_server.py`.

## User Story

As a graditelj/evaluator Wyckoff sistema
I want to da se svaka živa analiza trajno zapiše sa modelom, effortom i forecast-om
So that posle N meseci mogu da je ocenim naspram realizovanog ishoda (a ne samo da imam ručnu sliku).

## Problem Statement

Prva produkciona analiza (BTC, jun 2026) nije nigde sačuvana osim ručne slike. Postoji `signal_logger_server.py` (`scripts/mcp/signal_logger_server.py`) ali (a) **nije u `.mcp.json`** (tamo su samo `wyckoff-market-data`, `wyckoff-chart-renderer`, `wyckoff-spread-chart`) i (b) `Signal` TypedDict (`signal_logger_server.py:17-30`) hvata samo `entry_zone/invalidation/target_zone/...` — uži izvršni signal, ne ceo narativ/forecast/dijagnostiku.

## Solution Statement

Zaseban `AnalysisJournalStore` + `FastMCP("wyckoff-analysis-journal")` po identičnom obrascu kao `SignalStore` (append-only mesečni JSONL, `log/list/get`), ali sa bogatijim zapisom (narativ, struktura, faza, `forecast{direction,trigger,invalidation,confidence}`, `model`, `effort`, `chart_path`, `review`). `review_analysis` poštuje append-only: dopiše zaseban review-record vezan `analysis_id`-jem, a `get/list` spoje najnoviji review u vraćeni zapis. Aktivacija u `.mcp.json`; `data/journal/` u `.gitignore` (živi podaci, kao `data/signals/`).

## Metadata

- **Type:** NEW_CAPABILITY
- **Complexity:** LOW–MEDIUM
- **Source PRD:** `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 5 (depends: —, parallel: with 1)
- **Build target:** Sonnet @ medium / alternativa Codex med–high
- **Affected systems:** novi MCP server, `.mcp.json`, `.gitignore`

## UX Design

Operator/MCP workflow:

```
PRE:   živa analiza -> ručna slika, nigde zapisa scenarija

POSLE: log_analysis(symbol, tf, model, effort, narrative, structure, phase,
                    forecast{direction,trigger,invalidation,confidence}, chart_path)
         -> data/journal/2026-06.jsonl  (review: null)
       ... N meseci kasnije ...
       review_analysis(analysis_id, realized_direction, hit_trigger, note)
         -> get_analysis(id).review popunjen
```

| Lokacija | Before | After | Impact |
| --- | --- | --- | --- |
| živa analiza | efemerna | trajni JSONL zapis | ocenljivost unazad |
| `.mcp.json` | 3 servera | + `wyckoff-analysis-journal` | tool dostupan agentu |

## Mandatory Reading

- `scripts/mcp/signal_logger_server.py:43-54` — `_now`, `_parse_iso`, `_to_aware_utc` (kopirati obrazac).
- `scripts/mcp/signal_logger_server.py:57-125` — `SignalStore.__init__`, `_month_file`, `log_signal` (append-only upis).
- `scripts/mcp/signal_logger_server.py:127-208` — `list_signals` (filteri + `_month_files_in_range`), `get_signal`.
- `scripts/mcp/signal_logger_server.py:274-333` — `FastMCP` instanca + `@mcp.tool()` definicije + `main()`.
- `.mcp.json` — oblik postojećih server unosa (`type stdio`, `command "uv"`, `args ["run","python","-m","scripts.mcp.<modul>"]`, `cwd`).
- `tests/test_signal_logger_server.py` — obrazac testova za store + tools.
- `.gitignore` — sekcija `data/signals/` (živi podaci se ne komituju).

## Patterns to Mirror

- **Store:** `SignalStore` — `base_dir`, `_month_file(when) -> base_dir/<YYYY-MM>.jsonl`, append-only upis (`open("a")`), `list_*` sa filterима i sortiranjem po `logged_at`, `get_*` skeniranjem.
- **Vreme:** `_now`/`_parse_iso`/`_to_aware_utc` + `logged_at` kao ISO sa `Z`.
- **MCP:** `FastMCP("...")`, modul-level `store`, `@mcp.tool()` funkcije, `main(): mcp.run()`.
- **`.mcp.json` unos:** preslikati `wyckoff-market-data` blok (stdio/uv/-m modul/cwd).

## Files to Change

| File | Action | Notes |
| --- | --- | --- |
| `scripts/mcp/analysis_journal_server.py` | create | store + TypedDict + FastMCP tools |
| `.mcp.json` | edit | + `wyckoff-analysis-journal` server |
| `.gitignore` | edit | + `data/journal/` |
| `tests/test_analysis_journal_server.py` | create | store + tools testovi |

## NOT Building

- Izmenu/zamenu `signal_logger`-a — ostaje nepromenjen za uži trade signal.
- `replay`/skoring rubriku — to je Phase 4/6; ovde samo zapis + jednostavan `review`.
- Brisanje/uređivanje zapisa u mestu — store je append-only (review = dopisan record).

## Step-by-Step Tasks

1. **Skelet store-a** — `scripts/mcp/analysis_journal_server.py`
   - Action: `DEFAULT_JOURNAL_DIR = Path("data/journal")`; kopirati `_now/_parse_iso/_to_aware_utc`; `AnalysisRecord` TypedDict polja: `analysis_id, logged_at, symbol, timeframe, model, effort, narrative, structure, phase, forecast (dict), chart_path, review (dict | None)`.
   - Pattern: `signal_logger_server.py:17-54`.
   - Validate: `uv run python -c "import scripts.mcp.analysis_journal_server"`

2. **`log_analysis` + `_month_file`** — store
   - Action: `AnalysisJournalStore(base_dir=DEFAULT_JOURNAL_DIR)`; `_month_file` kao kod SignalStore; `log_analysis(...)` generiše `analysis_id=uuid4`, `logged_at` (ISO Z), `review=None`, validira `symbol` i `forecast` ključeve (`direction,trigger,invalidation,confidence`), append u mesečni fajl.
   - Pattern: `log_signal` (`:70-125`).
   - Validate: `uv run pytest tests/test_analysis_journal_server.py -q`

3. **`list_analyses` + `get_analysis`** — store
   - Action: `list_analyses(symbol=None, start=None, end=None, model=None)` (filteri + sort po `logged_at`, `_month_files_in_range` obrazac); `get_analysis(analysis_id)`.
   - Pattern: `list_signals`/`get_signal` (`:127-208`).
   - Validate: `uv run pytest tests/test_analysis_journal_server.py -q`

4. **`review_analysis` (append-only merge)** — store
   - Action: `review_analysis(analysis_id, realized_direction, hit_trigger: bool, note, reviewed_at=None)` dopiše zaseban record `{"type":"review","analysis_id":...,"review":{...}}`; `get_analysis`/`list_analyses` spoje **najnoviji** review u vraćeni `AnalysisRecord.review`. Nepostojeći id → `None`/no-op.
   - Gotcha: zadržati append-only (ne editovati postojeći red).
   - Validate: `uv run pytest tests/test_analysis_journal_server.py -q`

5. **FastMCP tools + main** — server
   - Action: `mcp = FastMCP("wyckoff-analysis-journal")`; modul-level `store`; `@mcp.tool()` za `log_analysis/list_analyses/get_analysis/review_analysis`; `main(): mcp.run()`.
   - Pattern: `signal_logger_server.py:274-340`.
   - Validate: `uv run python -c "import scripts.mcp.analysis_journal_server as m; assert m.mcp"`

6. **Aktivacija + gitignore**
   - Action: `.mcp.json` → dodati `"wyckoff-analysis-journal"` (stdio/uv/`-m scripts.mcp.analysis_journal_server`/cwd repo root, po uzoru na `wyckoff-market-data`). `.gitignore` → dodati `data/journal/`.
   - Validate: `uv run python -c "import json; json.load(open('.mcp.json'))"`

7. **Testovi** — `tests/test_analysis_journal_server.py` (vidi Testing Strategy).
   - Validate: `uv run pytest tests/test_analysis_journal_server.py -q`

## Testing Strategy

`tests/test_analysis_journal_server.py` (preslikati `tests/test_signal_logger_server.py`), `tmp_path` za `base_dir`:
1. log + `get_analysis` round-trip (polja sačuvana, `review is None`).
2. `_month_file` putanja po `logged_at` mesecu.
3. `list_analyses` filteri: `symbol`, `model`, `start/end` opseg; sort po `logged_at`.
4. append-only: dva `log_analysis` → dva reda u fajlu.
5. `review_analysis` → `get_analysis(id).review` popunjen; `list_analyses` takođe spaja review.
6. nepostojeći `analysis_id` → `get_analysis` vraća `None`.
7. nevalidan `forecast` (fali ključ) ili prazan `symbol` → `ValueError`.

## Validation Commands

```bash
# CLAUDE.md: koristiti uv, ne pip
uv run pytest tests/test_analysis_journal_server.py -q   # ciljani
uv run pytest -q                                          # pun set — postojeći ostaju zeleni
uv run python -c "import json; json.load(open('.mcp.json'))"   # .mcp.json validan JSON
```

## Acceptance Criteria

- `log_analysis` upiše ceo zapis u `data/journal/<YYYY-MM>.jsonl` sa `review=None`.
- `list_analyses`/`get_analysis` rade sa filterима i vraćaju spojene review-e.
- `review_analysis` popuni `review` zadržavajući append-only store.
- `wyckoff-analysis-journal` je u `.mcp.json` i `.mcp.json` ostaje validan JSON.
- `data/journal/` u `.gitignore`.
- `signal_logger` netaknut; svi postojeći testovi zeleni.

## Completion Checklist

- [ ] `analysis_journal_server.py` (store + TypedDict + tools + main).
- [ ] `log_analysis` / `list_analyses` / `get_analysis` / `review_analysis`.
- [ ] append-only review merge radi.
- [ ] `.mcp.json` + `wyckoff-analysis-journal` (validan JSON).
- [ ] `.gitignore` + `data/journal/`.
- [ ] 7 testova prolaze.
- [ ] `uv run pytest -q` ceo zelen.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Append-only vs „popuni review" konflikt | review = dopisan record; `get/list` spaja najnoviji (ne edituje red) |
| `.mcp.json` se pokvari (nevalidan JSON) | validacioni korak `json.load` posle izmene |
| Slučajan commit živih podataka | `data/journal/` u `.gitignore` (kao `data/signals/`) |

## Notes

Polja `model`/`effort` u zapisu su upravo ono što benchmark (Phase 6) kasnije agregira (model × effort × skor × token-cost). `forecast.confidence` hrani kalibracioni deo skoringa (Phase 4). Ne uvoditi privatne importe iz `signal_logger`-a — kopirati helpere radi nezavisnosti modula.
