# Skill validacija — 2026-06-11

## Kontekst

Scope: issue #32, Phase B MCP-driven E2E validacija posle merge-a PR #64,
koji je učinio `skills/wyckoff-trader-skill/SKILL.md` i
`skills/wyckoff-trader-skill/agents/openai.yaml` MCP-aware.

Izvori promptova:

- B1 i B2: `tests/prompts/phase_b_mcp_live.md`.
- B3: instrument-specifična varijanta iz issue #32
  (`SOL/USDT 1d za poslednjih 60 dana`) umesto generičkog "thin-liquidity alt"
  prompta iz `tests/prompts/phase_b_mcp_live.md`.

Okruženje:

- Branch: `validation/issue-32-phase-b-mcp`
- Runtime: `uv run --extra mcp`
- Datum live pull-a: 2026-06-11, Europe/Belgrade

Acceptance kriterijumi za svaki prompt:

1. MCP tool-call trace je dokumentovan.
2. Vision (vizuelna analiza renderovanog chart-a) je urađen nad renderovanim
   PNG-om pre dodele Wyckoff labela.
3. Output je contract-compliant (usklađen sa ugovorom odgovora) za odabrani mod
   iz `knowledge/wiki/scenarios/output-contract.md`.
4. Wiki citacije su prisutne tamo gde se koristi Wyckoff terminologija.

Granica validacije: ovaj report validira live happy-path E2E tok za tri prompta.
MCP-unavailable, timeout, corrupt/empty PNG i prazni podaci nisu zasebno
simulirani u E2E run-u; fallback disciplina je proverena dokumentarno kroz
`SKILL.md`, a relevantni error/exception paths postoje u MCP unit testovima
navedenim u sekciji "Komande".

## Phase B (MCP)

### B1 — BTC 1d trenutna faza

Prompt:

> Pull BTC 1d for the last 200 days, render the chart, and identify the current
> Wyckoff phase.

MCP tool-call trace:

| Korak | Tool | Argumenti | Rezultat |
| --- | --- | --- | --- |
| 1 | `get_ohlcv` | `symbol="BTC"`, `timeframe="1d"`, `limit=200` | 200 BTCUSDT candles vraćeno |
| 2 | `render_chart_for_symbol` | `symbol="BTC"`, `timeframe="1d"`, `limit=200` | PNG renderovan, 1200x600, 200 candles |
| 3 | Vision | renderovani PNG iz temp chart-renderer direktorijuma | Chart pročitan pre dodele labela |

Napomena o tragu: `render_chart_for_symbol` interno ponavlja OHLCV pull i render
u jednom shortcut pozivu. Zadržan je i zaseban `get_ohlcv` korak jer acceptance
traži vidljiv data pull, dok required render alat iz prompt seta ostaje
`render_chart_for_symbol`.

Observed data:

- Latest close: `62842.01`
- 200-candle high/low: `97924.49` / `59130.91`
- Recent 40-candle high/low: `82850.00` / `59130.91`
- Latest close location in recent 40-candle range: `0.156` from low to high
- Average volume last 20 candles: `20925.48`
- Average volume prior 20 candles: `14120.68`

Vision read:

Chart pokazuje zonu vrha u januaru, oštar markdown početkom februara, recovery
rally do low-80k zone u maju, zatim novi pad u lower-60k zonu. Poslednje candles
su blizu donjeg kraja skorašnjeg range-a, sa povišenim recent volume i samo
ranom stabilizacijom. Ne vidi se čist spring confirmation zato što nema
sekvence support sweep -> uspešan test -> sign of strength.

Odabrani mod: diagnostic.

Contract-compliant output sample:

1. **What the price/volume shows.** BTC 1d je blizu donjeg kraja skorašnjeg
   40-candle range-a posle istrajnog pada iz majskog rally high-a. Volume je
   veći nego u prethodnom 20-candle prozoru, pa trenutna zona izgleda kao
   aktivan supply/demand test, ne kao mirno završena baza.
2. **Candidate label(s).** Vodeći read: late Phase B / unresolved testing range,
   ne potvrđena Phase C. Runner-up: rana stopping action posle markdown-a, ali
   chart još traži kvalitetniji test pre jače accumulation label-e.
3. **Confidence and what is missing.** Confidence: medium-low. Prema
   `knowledge/wiki/concepts/labeling-is-last-step.md`, label-e su provisional
   dok ih struktura ne potvrdi. Spring label bi tražio ponašanje opisano u
   `knowledge/wiki/events/spring.md`: false break, re-entry, test i kasniju
   snagu. Ta potvrda se ne vidi na ovom chart-u.
4. **Optional escalation.** Scenario mode bi tražio forward plan sa triggerom i
   invalidation-om; iz ovog chart-a samog zaključak je watch/diagnose, ne trade
   call.

Evaluacija:

- MCP trace: PASS.
- Vision nad renderovanim chart-om: PASS.
- Mode contract: PASS, diagnostic četvorodelna struktura je prisutna.
- Wyckoff wiki citacije: PASS via `labeling-is-last-step.md` i
  `events/spring.md`.
- Contract reference: `output-contract.md` korišćen je za proveru moda, ne kao
  in-output Wyckoff citacija.

Failure/fallback check:

- Ako `get_ohlcv` ili `render_chart_for_symbol` padnu, validan skill odgovor ne
  sme izmišljati live state; treba da prijavi failure i traži chart observations
  ili ispravljene inpute, prema `SKILL.md` fallback disciplini.
- Vision guard: ako render ne vrati postojeći, čitljiv PNG, korak "Vision" ne
  sme biti označen kao PASS.

### B2 — ETHBTC 4h spread leadership

Prompt:

> Pull ETHBTC 4h, render the spread, and tell me whether altcoins are leading.

MCP tool-call trace:

| Korak | Tool | Argumenti | Rezultat |
| --- | --- | --- | --- |
| 1 | `get_spread` | `base_symbol="ETH"`, `quote_symbol="BTC"`, `timeframe="4h"`, `limit=200` | 200 ETH/BTC ratio candles vraćeno |
| 2 | `render_spread_chart` | `base="ETH"`, `quote="BTC"`, `timeframe="4h"`, `limit=200` | PNG renderovan, 1200x600, 200 ratio candles |
| 3 | Vision | renderovani PNG iz temp chart-renderer direktorijuma | Spread chart pročitan pre rotation zaključka |

Observed data:

- Latest ETH/BTC ratio close: `0.02634925686642691`
- 200-candle high/low: `0.029047188511776404` / `0.02563841105631293`
- Recent 40-candle high/low: `0.027926407580900522` / `0.02563841105631293`
- Latest close location in recent 40-candle range: `0.311` from low to high
- Average ratio-volume proxy last 20 candles: `58407.54`
- Average ratio-volume proxy prior 20 candles: `120003.04`

Vision read:

Spread počinje u downtrend-u, pokušava oštar rally početkom juna, zatim fail-uje
i probija naniže u novu nižu zonu. Rebound sa low-a je parcijalan i staje ispod
prethodne baze. To ne podržava trenutni altcoin-leadership read za ETH u odnosu
na BTC.

Odabrani mod: diagnostic.

Contract-compliant output sample:

1. **What the price/volume shows.** ETH/BTC trenutno ne vodi. Spread je fail-ovao
   posle kratkog upside pokušaja, probio niže na oštrom move-u i oporavlja se
   slabo ispod prethodnog range-a.
2. **Candidate label(s).** Vodeći read: failed relative-strength attempt / weak
   spread. Runner-up: moguć rani repair attempt, ali ne potvrđeno leadership.
3. **Confidence and what is missing.** Confidence: medium. Crypto spread charts
   se koriste kao leadership i rotation evidence, ali actual entry ostaje na
   USD pair-u prema `knowledge/wiki/crypto/spread-charts.md`. Upgrade u
   leadership bi tražio da ETH/BTC reclaim-uje failed range i pokaže bolji
   comparative slope, u skladu sa `knowledge/wiki/crypto/comparative-strength.md`
   i `knowledge/wiki/crypto/rotation-hierarchy.md`.
4. **Optional escalation.** Scenario mode treba da doda ETHUSDT i BTCUSDT context
   pre forward path-a.

Evaluacija:

- MCP trace: PASS.
- Vision nad renderovanim chart-om: PASS.
- Mode contract: PASS, diagnostic četvorodelna struktura je prisutna.
- Wyckoff/crypto wiki citacije: PASS via `crypto/spread-charts.md`,
  `crypto/comparative-strength.md` i `crypto/rotation-hierarchy.md`.
- Contract reference: `output-contract.md` korišćen je za proveru moda, ne kao
  in-output Wyckoff citacija.

Failure/fallback check:

- Ako `get_spread` ili `render_spread_chart` padnu, validan skill odgovor treba
  da prijavi da spread evidence nije dostupno i da ne tvrdi altcoin leadership.
- Vision guard: ako spread render ne vrati čitljiv PNG, rotation zaključak ne
  sme biti označen kao Vision-backed.

### B3 — SOL/USDT 1d spring / upthrust scan

Prompt:

> Pull SOL/USDT 1d for the last 60 days -- scan for spring or upthrust setups.

MCP tool-call trace:

| Korak | Tool | Argumenti | Rezultat |
| --- | --- | --- | --- |
| 1 | `get_ohlcv` | `symbol="SOL"`, `timeframe="1d"`, `limit=60` | 60 SOLUSDT candles vraćeno |
| 2 | `render_chart_for_symbol` | `symbol="SOL"`, `timeframe="1d"`, `limit=60` | PNG renderovan, 1200x600, 60 candles |
| 3 | Vision | renderovani PNG iz temp chart-renderer direktorijuma | Chart skeniran za spring/upthrust ponašanje |

Napomena o tragu: kao i u B1, `render_chart_for_symbol` interno radi fetch +
render. Zaseban `get_ohlcv` korak ostaje u report-u zato što acceptance traži
vidljiv OHLCV pull.

Observed data:

- Latest close: `65.44`
- 60-candle high/low: `98.41` / `60.13`
- Recent 40-candle high/low: `98.41` / `60.13`
- Latest close location in recent 40-candle range: `0.139` from low to high
- Average volume last 20 candles: `2791436.56`
- Average volume prior 20 candles: `2538788.90`

Vision read:

SOL 1d pokazuje majski rally u high-90s zonu, zatim controlled roll-over koji
ubrzava početkom juna. Poslednji bars su blizu donjeg kraja 60-day window-a
posle high-volume downside leg-a. Chart sada ne pokazuje upthrust setup jer cena
nije kod upper boundary-ja. Takođe još ne pokazuje confirmed spring jer move
ispod/blizu support-a nije praćen odlučnim re-entryjem, quiet testom i upward
resolution-om.

Odabrani mod: diagnostic.

Contract-compliant output sample:

1. **What the price/volume shows.** SOL testira donji kraj 60-day range-a posle
   oštrog markdown-a iz majskog high-a. Recent volume je malo viši nego u
   prethodnom 20-candle prozoru, pa je supply bio aktivan na padu.
2. **Candidate label(s).** Vodeći read: lower-boundary test after markdown, ne
   confirmed spring. Runner-up: early spring candidate samo ako cena re-enteruje
   prethodni range i kasnije održi low-volume test. Upthrust nije podržan jer
   chart nije blizu upper boundary-ja.
3. **Confidence and what is missing.** Confidence: medium. Spring kriterijumi u
   `knowledge/wiki/events/spring.md` traže false break/re-entry i test; upthrust
   kriterijumi u `knowledge/wiki/events/upthrust.md` traže upper-boundary probe
   i re-entry. Prema `knowledge/wiki/concepts/labeling-is-last-step.md`, ovo
   treba da ostane provisional lower-boundary test dok follow-through ne razreši
   strukturu.
4. **Optional escalation.** Scenario mode može definisati trigger tek posle
   reclaim/test sekvence ili vidljivog breakdown continuation-a.

Evaluacija:

- MCP trace: PASS.
- Vision nad renderovanim chart-om: PASS.
- Mode contract: PASS, diagnostic četvorodelna struktura je prisutna.
- Wyckoff wiki citacije: PASS via `events/spring.md`, `events/upthrust.md` i
  `concepts/labeling-is-last-step.md`.
- Contract reference: `output-contract.md` korišćen je za proveru moda, ne kao
  in-output Wyckoff citacija.

Failure/fallback check:

- Ako SOL nije podržan ili render padne, validan skill odgovor treba da prijavi
  failure i traži drugi symbol/timeframe ili user-provided observations.
- Vision guard: ako render ne vrati čitljiv PNG, spring/upthrust scan ne sme
  biti označen kao PASS.

## Failure i fallback scope

Ovaj E2E run nije pokušao da namerno sruši MCP servers. To je svesna granica:
issue #32 acceptance traži tri live MCP prompta sa tool-call trace-om, Vision
read-om, contract-compliant output-om i wiki citacijama. Negativni putevi su
zabeleženi kao očekivano ponašanje skill-a:

- MCP unavailable: odgovor mora reći da live pull nije dostupan i tražiti chart
  observations ili image.
- MCP fetch error, timeout ili unsupported symbol/timeframe: odgovor mora
  prijaviti konkretan failure i ne sme tvrdити live phase/leadership/setup.
- Empty OHLCV: odgovor mora tretirati rezultat kao failure, ne kao validan
  chart.
- Render failure ili corrupt/nonexistent PNG: Vision korak ne sme biti PASS;
  odgovor mora tražiti ponovni render ili user chart input.

Postojeći unit testovi pokrivaju deo ovih failure surfaces:

- `tests/test_market_data_client.py` pokriva invalid limit i Binance
  rate-limit/legal error propagaciju.
- `tests/test_chart_renderer.py` pokriva invalid chart dimensions, bad
  annotations i missing market-data fallback za `render_chart_for_symbol`.
- `tests/test_spread_chart_server.py` pokriva spread wrapper/render ponašanje i
  zavisi od istih OHLCV validation path-ova.

## Scenario mode coverage

Sva tri live prompta su validno završila u diagnostic mode-u jer pitanja traže
klasifikaciju trenutnog chart/spread stanja, ne forward scenario tree sa
triggerom i invalidation-om. Scenario mode nije predmet ovog #32 acceptance
run-a. Poseban scenario-mode E2E bi trebalo da koristi prompt tipa "Build a
Wyckoff scenario for BTC 1d with trigger and invalidation".

## Komande

Live MCP run:

```bash
uv run --extra mcp python - <<'PY'
from scripts.mcp.market_data_server import get_ohlcv
from scripts.mcp.chart_renderer import render_chart, render_chart_for_symbol
from scripts.mcp.spread_chart_server import get_spread, render_spread_chart

btc = get_ohlcv("BTC", "1d", 200)
btc_render = render_chart_for_symbol("BTC", "1d", 200)
ethbtc = get_spread("ETH", "BTC", "4h", 200)
ethbtc_render = render_spread_chart("ETH", "BTC", "4h", 200)
sol = get_ohlcv("SOL", "1d", 60)
sol_render = render_chart_for_symbol("SOL", "1d", 60)
PY
```

Regression subset:

```bash
uv run pytest tests/test_market_data_server.py tests/test_chart_renderer.py tests/test_spread_chart_server.py
```

Rezultat: `36 passed`.

Report checks:

```bash
rg -n "Phase B \\(MCP\\)|MCP tool-call trace|Vision|Contract-compliant|wiki citacije|PASS" tests/skill_validation_2026-06-11.md
git diff --check
```

## Sažetak

Sva tri Phase B prompta su prošla acceptance signal:

- MCP tool-call trace: PASS za B1, B2, B3.
- Vision nad renderovanim chart-om: PASS za B1, B2, B3.
- Contract-compliant output: PASS za B1, B2, B3.
- Wiki citacije za Wyckoff terminologiju: PASS za B1, B2, B3.

Residual risk: ovo je live-data validacija, pa su konkretne cene i chart read
vremenski zavisni. Stabilni invariant je workflow: pull podataka kroz MCP,
render chart-a, Vision pregled renderovanog chart-a, zatim odgovor po postojećem
mode contract-u sa wiki citacijama.
