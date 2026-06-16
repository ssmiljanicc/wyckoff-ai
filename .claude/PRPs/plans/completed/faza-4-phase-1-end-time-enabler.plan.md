# Feature: Phase 1 — `end_time` enabler (future-blind OHLCV)

## Summary

Dodati opcioni `end_time` parametar kroz ceo market-data put (`get_ohlcv` klijent → `market_data_server` MCP tool → `render_chart_for_symbol`) tako da pozivalac može da dohvati OHLCV **do proizvoljnog trenutka T**. Backward-kompatibilno: kad je `end_time=None`, ponašanje je bajt-identično sadašnjem. Ovo je nizak nivo koji *generiše* zamrznute snapshote u Phase 2 (i blind i future_visible mod) i zamenjuje sirovi `httpx` zaobilaz iz pilota.

## User Story

As a eval-harness pripremač
I want to dohvatim sveće isključivo do (ili oko) istorijskog trenutka T
So that mogu da napravim future-blind / future-visible isečke bez ručnog `httpx` zaobilaza.

## Problem Statement

`BinanceMarketDataClient.get_ohlcv` (`scripts/mcp/market_data_client.py:136`) gradi `params = {"symbol","interval","limit"}` (linije 145-152) i nema načina da ograniči gornju granicu vremena. Pilot (`scripts/eval/pilot_blind_slice.py:51-71`) zato zaobilazi klijent sirovim `httpx.get(... "endTime": end_ms ...)`. Binance `/api/v3/klines` podržava `endTime` (ms epoch), ali on nije izložen kroz klijent/server/renderer.

## Solution Statement

Izložiti opcioni `end_time` kroz tri sloja. Klijent normalizuje ulaz na ms epoch na jednom mestu (`_normalize_end_time`), ubacuje `endTime` u Binance `params` **samo** kad nije `None`, i dodaje `end_time` u `_CacheKey` da različiti isečci ne kolidiraju u kešu. Server i renderer prosleđuju param dalje. `None` putanja ostaje identična → nula regresije.

## Metadata

- **Type:** ENHANCEMENT
- **Complexity:** LOW
- **Source PRD:** `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 1 (depends: —, parallel: with 5)
- **Build target:** Sonnet @ medium (čist plumbing) / alternativa Codex med–high
- **Affected systems:** market-data klijent, market-data MCP server, chart renderer

## UX Design

Operator/API workflow (nema ekrana):

```
PRE:   get_ohlcv("BTCUSDT","1d", limit=180)            -> poslednjih 180 sveća do SADA
       (pilot mora sirov httpx za endTime)

POSLE: get_ohlcv("BTCUSDT","1d", limit=180, end_time="2019-04-01")
       -> 180 sveća do 2019-04-01 (bez budućnosti)
       get_ohlcv(..., end_time=None)                    -> identično kao PRE
```

| Lokacija | Before | After | Impact |
| --- | --- | --- | --- |
| `get_ohlcv` | samo do sada | opciono do T | future-blind dohvat bez zaobilaza |
| `market_data_server.get_ohlcv` tool | bez `end_time` | `end_time: int\|str\|None` | MCP pozivaocu dostupan cutoff |
| `render_chart_for_symbol` | bez `end_time` | prosleđuje `end_time` | render isečka do T |

## Mandatory Reading

- `scripts/mcp/market_data_client.py:136-161` — `get_ohlcv` telo, `params`, keš tok.
- `scripts/mcp/market_data_client.py:68-73` — `_CacheKey` frozen dataclass.
- `scripts/mcp/market_data_client.py:254-276` — `_normalize_limit`, `parse_kline` (obrazac validacije/parsiranja).
- `scripts/mcp/signal_logger_server.py:43-54` — `_now`, `_parse_iso`, `_to_aware_utc` (obrazac za datetime → UTC → ISO/ms).
- `scripts/mcp/market_data_server.py` — MCP tool `get_ohlcv` potpis i prosleđivanje.
- `scripts/mcp/chart_renderer.py` — `render_chart_for_symbol` potpis i poziv klijenta.
- `tests/test_market_data_client.py` — `FakeHttpClient` beleži `params`; postojeći `test_get_ohlcv_fetches_and_caches_identical_request` tvrdi tačan `params` dict.
- `tests/test_market_data_server.py` — obrazac za server-tool test.

## Patterns to Mirror

- **Datetime normalizacija:** `signal_logger_server._parse_iso` (`fromisoformat`, zamena `Z`) + `_to_aware_utc` (naive → UTC). Reuse istu logiku za `_normalize_end_time` (ali izlaz je ms `int`, ne `datetime`).
- **Validacija ulaza:** `_normalize_limit` (`scripts/mcp/market_data_client.py:254-260`) — `ValueError` sa jasnom porukom.
- **Keš ključ:** postojeći `_CacheKey(symbol, timeframe, limit)` — proširiti aditivno.

## Files to Change

| File | Action | Notes |
| --- | --- | --- |
| `scripts/mcp/market_data_client.py` | edit | `_CacheKey` + `_normalize_end_time` + `get_ohlcv` potpis/telo + import `datetime` |
| `scripts/mcp/market_data_server.py` | edit | tool `get_ohlcv` dobija `end_time` i prosleđuje |
| `scripts/mcp/chart_renderer.py` | edit | `render_chart_for_symbol` dobija `end_time` i prosleđuje |
| `tests/test_market_data_client.py` | edit | +5 test slučajeva |
| `tests/test_market_data_server.py` | edit | +1 test slučaj (forwarding) |

## NOT Building

- Sekundni ulaz za `end_time` (samo ms i ISO/`datetime`) — izbegava dvosmislenost; ako ikad zatreba, dodati eksplicitan `unit` param.
- `datetime` tip na MCP/renderer granici — JSON schema ne voli `datetime`; granica drži `int | str | None`.
- „cutoff u budućnosti" validaciju — Binance prosto vrati do sada; legalno.
- Izmenu pilota (`scripts/eval/pilot_blind_slice.py`) — refaktoriše ga Phase 2.

## Step-by-Step Tasks

1. **`_CacheKey` proširenje** — `scripts/mcp/market_data_client.py`
   - Action: dodati polje `end_time: int | None = None` u frozen dataclass (linije 68-73).
   - Gotcha: default `None` čuva sve postojeće pozicione konstrukcije (sve trenutno koriste 3 polja).
   - Validate: `uv run python -c "from scripts.mcp.market_data_client import _CacheKey; _CacheKey('BTCUSDT','1d',200)"`

2. **`_normalize_end_time` helper** — `scripts/mcp/market_data_client.py`
   - Action: dodati funkciju `_normalize_end_time(value: int | str | datetime | None) -> int | None`:
     - `None` → `None`.
     - `int` → ms epoch; ako `<= 0` → `ValueError`.
     - `str` → `datetime.fromisoformat(value.replace("Z","+00:00"))`; naive → UTC; → `int(ts*1000)`. Neparsabilan → `ValueError` (poruka sadrži vrednost).
     - `datetime` → naive → UTC; → ms.
   - Pattern: `signal_logger_server._parse_iso` + `_to_aware_utc`.
   - Import: dodati `from datetime import datetime, timezone`.
   - Validate: `uv run pytest tests/test_market_data_client.py -q`

3. **`get_ohlcv` potpis + telo** — `scripts/mcp/market_data_client.py`
   - Action: dodati `end_time: int | str | datetime | None = None`; `normalized_end = _normalize_end_time(end_time)`; `cache_key = _CacheKey(normalized_symbol, normalized_timeframe, normalized_limit, normalized_end)`; u `params` dodati `"endTime": normalized_end` **samo ako** `normalized_end is not None`.
   - Gotcha: kad je `None`, `params` MORA ostati `{"symbol","interval","limit"}` (postojeći test tvrdi tačan dict).
   - Validate: `uv run pytest tests/test_market_data_client.py -q`

4. **Server tool prosleđivanje** — `scripts/mcp/market_data_server.py`
   - Action: tool `get_ohlcv(symbol, timeframe, limit=DEFAULT_LIMIT, end_time: int | str | None = None)` → `client.get_ohlcv(symbol, timeframe, limit, end_time=end_time)`.
   - Gotcha: tip na granici `int | str | None` (bez `datetime`) zbog JSON scheme.
   - Validate: `uv run pytest tests/test_market_data_server.py -q`

5. **Renderer prosleđivanje** — `scripts/mcp/chart_renderer.py`
   - Action: `render_chart_for_symbol(..., end_time: int | str | None = None)` → `market_data_client.get_ohlcv(..., end_time=end_time)`.
   - Validate: `uv run pytest -q`

6. **Testovi** — `tests/test_market_data_client.py` + `tests/test_market_data_server.py` (vidi Testing Strategy).
   - Validate: `uv run pytest tests/test_market_data_client.py tests/test_market_data_server.py -q`

## Testing Strategy

`tests/test_market_data_client.py`:
1. `test_get_ohlcv_passes_end_time_to_binance` — `end_time` (ms int) → zabeleženi `params` sadrži `"endTime": <ms>` uz `symbol/interval/limit`.
2. `test_get_ohlcv_accepts_iso_end_time` — `end_time="2019-04-01"` → `endTime == 1554076800000` (UTC ponoć).
3. `test_get_ohlcv_without_end_time_omits_param` — `params == {"symbol","interval","limit"}` (backward-compat regresija; ogledalo postojeće tvrdnje).
4. `test_end_time_cache_does_not_collide` — isti `symbol/tf/limit`, dva različita `end_time` → dva upstream poziva; ponovljen isti `end_time` → keš hit (bez novog poziva).
5. `test_get_ohlcv_rejects_invalid_end_time` — negativan ms i neparsabilan string → `ValueError`.

`tests/test_market_data_server.py`:
6. `test_server_get_ohlcv_forwards_end_time` — server tool prosleđuje `end_time` klijentu (stub/monkeypatch beleži kwarg).

## Validation Commands

```bash
# CLAUDE.md: koristiti uv, ne pip
uv run pytest tests/test_market_data_client.py tests/test_market_data_server.py -q   # ciljani
uv run pytest -q                                                                      # pun set — postojeći ostaju zeleni
uv run ruff check scripts/mcp/ tests/                                                 # ako je ruff u projektu; inače preskoči
```

## Acceptance Criteria

- `get_ohlcv(symbol, tf, end_time=T)` vraća isključivo sveće ≤ T (preko `endTime`).
- `end_time=None` → `params` i ponašanje bajt-identični pre-izmeni; `test_get_ohlcv_fetches_and_caches_identical_request` ostaje zelen bez izmene.
- ISO string i ms int daju isti `endTime`; nevalidan ulaz → `ValueError`.
- Različit `end_time` ne deli keš; isti `end_time` se kešira.
- Server tool i `render_chart_for_symbol` prosleđuju `end_time`.
- Svi postojeći testovi zeleni.

## Completion Checklist

- [ ] `_CacheKey.end_time` dodato (default `None`).
- [ ] `_normalize_end_time` (int/str/datetime/None → ms/None) + validacija.
- [ ] `get_ohlcv` potpis/telo + `endTime` samo kad nije None.
- [ ] `market_data_server.get_ohlcv` prosleđuje.
- [ ] `render_chart_for_symbol` prosleđuje.
- [ ] 6 novih testova prolaze.
- [ ] `uv run pytest -q` ceo zelen.
- [ ] Pilot netaknut.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Dodatak polja u `_CacheKey` lomi postojeće konstrukcije | default `None` pokriva sve trenutne pozicione (3-polja) pozive |
| `datetime` na MCP granici lomi JSON schema | granica drži `int \| str \| None`; `datetime` je interna pogodnost klijenta |
| Backward-compat regresija u `params` | `endTime` se dodaje samo kad nije None; namenski regresioni test |

## Notes

`end_time` služi **oba moda** Phase 2: `blind` (`end_time=T`) i `future_visible` (`end_time=T+N`, „as-of T" marker dodaje render u Phase 2). Phase 1 ne radi marker/render logiku — samo cutoff primitiv. ISO ponoć UTC za `"2019-04-01"` = `1554076800000` ms.
