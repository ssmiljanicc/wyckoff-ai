# Faza 4 — Eval & Journal Harness za kvalitet Wyckoff analize

> Izvor: GitHub issue [#66](https://github.com/ssmiljanicc/wyckoff-ai/issues/66) · Milestone **M7: Analysis Evaluation & Model Benchmarking** · Labele: `phase:4`, `infrastructure`, `skill`, `idea`, `model:opus`
> Jezik per `CLAUDE.md` §0.1 (srpski + engleski tehnički termini objašnjeni pri prvom pomenu).

## Problem Statement

Sistem (skill + MCP serveri) sada **može** da uradi živu Wyckoff analizu, ali **niko ne zna koliko je ta analiza pouzdana**, ni gde radi dobro a gde loše. Dva merljiva jaza: (1) ne možemo da pokrenemo analizu na istorijskim trenucima i uporedimo je sa onim što se *stvarno* desilo posle — a da agent pritom **ne vidi budućnost** (lookahead / data-leakage — curenje budućih informacija u analizu); (2) žive analize se nigde ne beleže (journal — dnevnik), pa posle 3 meseca nema čime da se proveri šta je analiza pogodila. Cena nerešavanja: gradimo i otpremamo analizu na osnovu subjektivnog utiska „deluje korektno", bez ijednog merljivog dokaza pouzdanosti, i bez osnova da kažemo *koji model i koji effort* (nivo uloženog rezonovanja) vredi koristiti.

## Evidence

- **Pilot je izveden pre ovog PRD-a** (`scripts/eval/pilot_blind_slice.py` + `pilot_out/`): povučene realne BTC 1d sveće do `2019-04-01` (markup breakout krenuo `2019-04-02`, dakle van isečka), anonimizovane (cena × `7.31`, volume × `0.043`, lažni datumi, naslov `ASSET-X 1D`), renderovane, i pušten **slepi** general-purpose subagent (bez konteksta razgovora, bez pristupa answer key-u). Slepa analiza je pogodila svih 6 dimenzija (struktura, SC, faza, vodeći scenario, trigger nivo, kalibracija) — scorecard u issue-u #66.
- **Najvažniji nalaz pilota (iskrena ograda):** jedan pogodak ne dokazuje pouzdanost, i baš taj primer je opasan — BTC 2018–2019 akumulacija je verovatno **najčešće citiran Wyckoff primer u kripto edukaciji**, pa je model mogao da *prepozna oblik iz pretreninga* umesto da ga razreši rezonovanjem. Pilot **ne ume da razdvoji „dobar Wyckoff" od „setio se poznatog setapa".** Ovo direktno diktira dizajn (anonimizacija + anon-vs-revealed kontrola).
- **`market_data_client.get_ohlcv`** (`scripts/mcp/market_data_client.py:136-161`) nema `end_time` param — `params` šalje samo `symbol/interval/limit`. Pilot to zaobilazi sirovim `httpx`-om sa Binance `endTime` (`pilot_blind_slice.py:51-71`). Potvrđen enabler-jaz.
- **`signal_logger_server.py`** postoji (append-only mesečni JSONL pod `data/signals/`, već ima deterministički `replay_signal` → `hit_tp`/`hit_sl`/`open`), ali (a) **nije u `.mcp.json`** (potvrđeno — tamo su samo `wyckoff-market-data`, `wyckoff-chart-renderer`, `wyckoff-spread-chart`) i (b) hvata samo *uži trade signal* (entry/sl/tp/phase/evidence), ne ceo scenario/narativ/dijagnostiku.
- **`chart_renderer.render_chart_image`** prima proizvoljan OHLCV (`pilot_blind_slice.py:29,95`) → anonimizovani render radi bez izmena renderera.

## Proposed Solution

Gradimo dvonamenski **slepi istorijski eval + journal harness** sa fizičkom (ne „časna reč") garancijom protiv leakage-a. Pripremač (zna odgovor) pre-izvozi **zamrznute snapshote** (statični, već anonimizovani fajlovi pod `data/eval/case_XX/`) gde answer key fizički stoji **van** foldera koji analitičar čita; `end_time` je nizak nivo koji *generiše* te snapshote. Slepi agent-analitičar čita **isključivo** snapshot → ne može da procuri budućnost ni iz razgovora ni iz živog MCP-a. Anonimizacija (cena/volume × koeficijent guran u *neuobičajen* opseg, neutralisani datumi i mplfinance volume-stil) brani od pretraining-prepoznavanja; isti slučaj se pušta i **anonimizovan i revealed** kao A/B kontrola koja *kvantifikuje* leakage. Izolovani **LLM-sudija** (Opus) skoruje po rubrici videći **samo agentov output + answer key, nikad grafik**. Svaka živa analiza ide u **novi analysis-journal** (`data/journal/YYYY-MM.jsonl`) sa modelom/effortom i strukturisanim forecast-om, ocenljiva posle N meseci. Kad sve to postoji, isti slepi ulaz se pušta kroz **matricu model × effort** → empirijski benchmark sa token-cost-om.

Biramo snapshot (a ne živi `end_time`) jer je reproducibilan (isti bajtovi → fer poređenje modela), fizički bez budućnosti, i ugrađuje anonimizaciju u prep korak. Biramo novi journal (a ne proširenje `signal_logger`-a) radi čiste separacije: signal_logger ostaje uži izvršni trade signal, journal hvata ceo analitički scenario.

## Key Hypothesis

Verujemo da će **slepi istorijski eval harness + journal** pretvoriti subjektivni utisak „deluje korektno" u **merljivu pouzdanost po Wyckoff fazi/eventu i po modelu/effortu**.
Znaćemo da smo u pravu kada: (a) možemo da pokrenemo N slepih istorijskih tačaka i dobijemo skorovan izveštaj po dimenzijama; (b) anonimizovan-vs-revealed kontrola **kvantifikuje** pretraining-leakage kao Δskor; (c) svaka živa analiza je trajno zabeležena i ocenljiva posle N meseci; (d) imamo tabelu **model × effort × skor × token-cost**; (e) **lookahead-honesty probe** (slep vs vidljiva budućnost) nam empirijski kaže **da li blinding kompleksnost uopšte treba** — ako agent ne „vara" gledanjem budućnosti, deo mašinerije za sečenje budućnosti se može odbaciti.

## What We're NOT Building

- **Real-money trading / order placement** — trajni non-goal projekta (per `CLAUDE.md` §10 i issue #66).
- **ML klasifikator faza** — to je Faza 3 / M6 (#25–#28); ovde se ground truth *koristi*, ne trenira model.
- **Trening / fine-tuning modela** — samo evaluacija postojećih modela.
- **Tick-level / intraday mikrostruktura** — eval radi na bar-nivou (1h/4h/1d/1w kao postojeći timeframe-ovi).
- **Pakovanje u Fazu 3** — drugačiji cilj (evaluacija + observability + benchmark), zato zaseban milestone M7. Reuse postojeće infra (`signal_logger.replay_signal`, `chart_renderer`) gde ima smisla.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Skorovan slepi izveštaj | ≥ 10 tačaka × 6 dimenzija, jednom komandom | Pokretanje eval runner-a daje per-dimenziju skor + agregat |
| Kvantifikovan pretraining-leakage | Δskor(anon → revealed) izmeren na istom setu | Anon-vs-revealed A/B na ≥ 5 zajedničkih tačaka |
| Lookahead-honesty probe | Δskor(slep → vidljiva budućnost) izmeren → odluka o blinding-u | Slepi-vs-vidljiva-budućnost na 2–3 (rana provera) pa ≥ 5 tačaka |
| Journal pokrivenost | 100% živih analiza zabeleženo | `data/journal/*.jsonl` zapis po analizi (model, effort, forecast, chart_path) |
| Ocenljivost unazad | „review" tok radi na zapisu starijem od N meseci | `replay`/review popunjava `review` polje naspram realizovanog ishoda |
| Benchmark tabela | model × effort × skor × token-cost popunjena | Benchmark batch report nad identičnim slepim ulazom |
| Sudija ne curi | Sudija nikad ne vidi anon grafik | Harness fizički ne prosleđuje grafik sudiji (verifikovano u kodu/testu) |

## Open Questions

- [ ] Definicija „N meseci" za review tok — fiksno (npr. 3 mes.) ili po realizaciji ground-truth prozora po tački?
- [ ] Da li benchmark batch uključuje Codex (`.agents/` wrapper) u v1 ili tek pošto Claude matrica radi? (Fable 5 čeka dostupnost — uključiti čim bude.)
- [ ] Tačan format „neuobičajenog" cenovnog opsega za anonimizaciju (kako garantovati da koeficijent ne padne slučajno u poznat opseg kao u pilotu ~25–55k).
- [ ] Potvrditi tačan gornji effort tier za Claude u Claude Code (`extra-high` vs `max`) iz `/effort` opcija — pre benchmark batch-a.
- [ ] Lookahead probe: koliko tačaka i koji prag Δskor-a znači „agent vara" (i koliko blinding kompleksnosti tada graditi u Phase 2). Kako future-visible mod tačno označava „as-of T" (vertikalna linija + instrukcija) da bude pošteno poređenje.

---

## Users & Context

**Primary User**
- **Who**: Sam vlasnik projekta (Stefan) kao **graditelj/evaluator** Wyckoff sistema — ne krajnji trgovac, nego osoba koja odlučuje da li sistemu i kom modelu/effortu da veruje.
- **Current behavior**: Pušta živu analizu, gleda render i narativ, formira subjektivan utisak; jedina trajna evidencija prve produkcione upotrebe (BTC, jun 2026) je ručno generisana slika.
- **Trigger**: „Hoću da znam koliko je ova analiza dobra, i koji model/effort da koristim za koji tip zadatka" — pre nego što se sistem dalje gradi ili pre nego što mu se veruje na živom tržištu.
- **Success state**: Postoji skorovan izveštaj po dimenzijama, leakage je kvantifikovan, žive analize se beleže i mogu se oceniti unazad, i tabela model × effort × skor × token-cost vodi izbor `model:*` labela na budućim issue-ima.

**Job to Be Done**
Kada uradim Wyckoff analizu (živu ili eksperimentalnu), želim da je objektivno izmerim naspram onoga što se stvarno desilo — bez da agent vidi budućnost — da bih znao kome (kom modelu i effortu) i koliko da verujem.

**Non-Users**
Krajnji trgovci koji traže signal za izvršenje (wiki/skill nisu signal feed); ML pipeline koji trenira klasifikator (Faza 3); bilo koji potrošač koji očekuje real-money izvršenje.

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | `end_time`/`as_of` u `get_ohlcv` (+ provući kroz `render_chart_for_symbol`) | Čist enabler — generiše future-blind snapshote |
| Must | Zamrznut snapshot prep + anonimizacija (`data/eval/case_XX/`, answer key van foldera) | Fizička garancija protiv leakage-a + reproducibilnost |
| Must | Dual-mode render: `blind` (budućnost odsečena) vs `future_visible` (cela kriva + „as-of T" marker) | Toggle nije skup; omogućava lookahead-honesty probe |
| Should | Lookahead-honesty probe (slep vs vidljiva budućnost), kao prvi korak Phase 2 | Meri da li agent zaista „vara" gledanjem budućnosti; ako ne — blinding kompleksnost se odbacuje pre nego što se izgradi |
| Must | Ground-truth test set v1 (~10 kuriranih tačaka, miks event-tipova, uklj. post-cutoff) | Bez kuriranog seta nema šta da se skoruje; post-cutoff brani od pretreninga |
| Must | Skoring rubrika + izolovani LLM-sudija (Opus, vidi samo output + answer key) | Suština vrednosti; sprečava da sudija sam „prepozna" grafik |
| Must | Analysis-journal (`data/journal/*.jsonl`) + aktivacija u `.mcp.json` | Trajni zapis žive analize, ocenljiv unazad |
| Should | Anon-vs-revealed A/B kontrola | Kvantifikuje pretraining-leakage kao Δskor |
| Should | Benchmark batch runner (model × effort) + token-cost + report | Dvonamenski cilj: empirijski izbor modela/efforta |
| Should | Review tok („oceni prošlu analizu naspram realizovanog") | Zatvara petlju observability-ja posle N meseci |
| Could | Codex (`.agents/` wrapper) u benchmark matrici | Vredi proveriti (jak na strukturisanom, sumnjiv na vizuelnom) |
| Could | Fable 5 u matrici | Čim bude dostupan — sumnja se da pravi razliku na vizuelno-strukturnom čitanju |
| Won't | Real-money izvršenje, ML trening, tick-level | Van opsega projekta / faze |

### MVP Scope

Najmanje da se validira hipoteza (a)+(c): **Phase 1 → 2 → 3 → 4** daju jednu komandu koja nad ~10 zamrznutih anon snapshota pušta slepog analitičara i vraća skorovan izveštaj po 6 dimenzija, plus **Phase 5** journal koji beleži živu analizu. Anon-vs-revealed (b) i benchmark matrica (d) dolaze u Phase 6 kao dovršenje dvonamenskog cilja. **Phase 2 počinje lookahead-honesty probe-om (e):** ako probe pokaže da agent ne vara gledanjem budućnosti, ostatak blinding mašinerije se gradi „tanje" (ili se svodi na živi `end_time` umesto punog snapshot sečenja) — dokaz pre kompleksnosti.

### User Flow

Kritični put (eval): `prep (zna odgovor)` generiše `data/eval/case_XX/{candles.json, chart.png}` sa `end_time`, answer key se piše **van** foldera → `slepi analitičar` (subagent bez konteksta) čita samo snapshot i vraća strukturisan output → `izolovani sudija (Opus)` vidi output + answer key (nikad grafik) i skoruje po rubrici → `report` agregira po dimenziji/modelu/effortu.

Kritični put (journal): `živa analiza` → zapis u `data/journal/YYYY-MM.jsonl` (model, effort, narativ, forecast{direction, trigger, invalidation, confidence}, chart_path, `review: null`) → posle N meseci `review` popunjava `review` naspram realizovanog ishoda (reuse `replay`-logike).

---

## Technical Approach

**Feasibility**: **HIGH** — pilot je već dokazao celu mehaniku; gradnja je formalizacija throwaway scaffolding-a u reproducibilan harness uz reuse postojećih komponenti.

**Architecture Notes**
- `end_time` se dodaje kao opcioni param u `BinanceMarketDataClient.get_ohlcv` (Binance `/klines` podržava `endTime`); ulazi u `_CacheKey` da keš ne pomeša isečke. Provlači se kroz `market_data_server` i `render_chart_for_symbol`.
- Snapshot prep je **odvojen sloj** koji zove `get_ohlcv(end_time=...)`, anonimizuje, renderuje, i piše answer key van analitičarevog foldera. Anonimizacija mora da popravi pilot-curenja: koeficijent koji gura cenu u neuobičajen opseg, neutralisani datumi (ne „2009"), neutralisan mplfinance volume-stil.
- **Dual-mode render** (isti `end_time` primitiv, dva izlaza): `blind` = sveće samo do T; `future_visible` = sveće i posle T (npr. `end_time = T + N`) sa vertikalnim „as-of T" markerom + instrukcijom „analiziraj kao da je sada T". Lookahead-honesty probe poredi slepu analizu sa future-visible analizom; ako se skor bitno ne menja → agent ne vara → blinding (fizičko sečenje) je suvišan, dovoljan je živi `end_time` + as-of instrukcija. Probe se izvodi **prvo** (Phase 2) da ne gradimo skupu mašineriju bez dokaza.
- Journal = **novi mali MCP server/store** po uzoru na `signal_logger` (append-only mesečni JSONL, `data/journal/`), aktiviran u `.mcp.json`. Review reuse-uje deterministički obrazac iz `signal_logger.replay_signal`.
- Sudija je izolovan agent: harness mu prosleđuje samo agentov output + answer key; grafik fizički nije u promptu.
- Benchmark batch parametrizuje (model, effort) nad **identičnim** snapshotima; beleži token-cost uz skor (ROI = skor/token).

**Granica agenta (disciplina protiv leakage-a — dve osovine):** pripremač ≠ analitičar (subagent bez konteksta štiti od curenja iz *razgovora*); anonimizacija štiti od *pretraining* prepoznavanja; answer key fizički van vidokruga. Trebaju **obe**.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Anonimizacija nedovoljna → model i dalje prepozna setup | M | Anon-vs-revealed A/B meri zaostali leakage; koeficijent u neuobičajen opseg; uključiti post-cutoff tačke |
| Sudija (LLM) sam „prepozna" grafik i procuri | M | Sudija fizički ne vidi grafik — samo output + answer key; verifikovano testom |
| Test set premali → skor statistički nestabilan | M | v1 ~10 kao signal, ne dokaz; dizajn dozvoljava rast do ~20–30; izveštaj jasno označava n |
| Binance revidira istorijske podatke → snapshot „mrdne" | L | Snapshot je zamrznut u fajl; jednom izvezen, nezavisan od upstream-a |
| „Wait/no-trade" ispravan odgovor kažnjen u skoringu | M | Rubrika: ne kažnjavati opravdan oprez; ako ground truth nije dao trigger u prozoru, ispravan low-confidence „wait" je tačan; kalibracija se skoruje odvojeno |
| Skladište (PNG snapshoti) raste | L | `.gitignore` politika za `data/eval/` artefakte; čuvati answer key + manifest, regenerisati slike po potrebi |
| Gradimo skupu blinding mašineriju bez dokaza da je potrebna | M | Phase 2 počinje lookahead-honesty probe-om (slep vs vidljiva budućnost); ako agent ne vara, blinding se svodi na živi `end_time` + as-of instrukciju (manje koda/skladišta) |

---

## Implementation Phases

<!--
  STATUS: pending | in-progress | complete
  PARALLEL: phases that can run concurrently
  DEPENDS: phases that must complete first
  PRP: link to generated plan file once created
-->

| # | Phase | Description | Status | Parallel | Depends | PRP Plan |
|---|-------|-------------|--------|----------|---------|----------|
| 1 | `end_time` enabler | `end_time`/`as_of` u `get_ohlcv` + provlačenje kroz server i `render_chart_for_symbol` | complete | with 5 | - | [plan](../plans/completed/faza-4-phase-1-end-time-enabler.plan.md) · [report](../reports/faza-4-phase-1-end-time-enabler-report.md) · PR #68 |
| 2 | Lookahead probe + dual-mode prep + anonimizacija | Prvo probe (slep vs vidljiva budućnost) → odluka o blinding-u; pa dual-mode render i prep `data/eval/case_XX/`, answer key van foldera, popravke pilot-curenja | complete | - | 1 | [plan](../plans/completed/faza-4-phase-2-lookahead-probe-prep.plan.md) · [report](../reports/faza-4-phase-2-lookahead-probe-prep-report.md) · PR #69 |
| 3 | Ground-truth test set v1 | ~10 kuriranih tačaka (miks event-tipova, multi-symbol, ≥2 post-cutoff) | complete | with 4 | 2 | [plan](../plans/completed/faza-4-phase-3-ground-truth-set.plan.md) · [report](../reports/faza-4-phase-3-ground-truth-set-report.md) · PR #70 |
| 4 | Skoring rubrika + izolovani sudija | Rubrika (6 dimenzija + kalibracija + wait-pravilo) i izolovani Opus-sudija | complete | with 3 | 2 | [plan](../plans/completed/faza-4-phase-4-scoring-judge.plan.md) · [report](../reports/faza-4-phase-4-scoring-judge-report.md) · PR #71 |
| 5 | Analysis-journal | Novi JSONL store/MCP + aktivacija u `.mcp.json` + review tok | complete | with 1 | - | [plan](../plans/completed/faza-4-phase-5-analysis-journal.plan.md) · [report](../reports/faza-4-phase-5-analysis-journal-report.md) · PR #67 |
| 6 | Benchmark batch + report | Matrica model × effort nad identičnim ulazom, token-cost, obe kontrole (anon-vs-revealed + slep-vs-vidljiva-budućnost), report | complete | - | 3, 4 | [plan](../plans/completed/faza-4-phase-6-benchmark-report.plan.md) · PR #72 |

### Phase Details

**Phase 1: `end_time` enabler**
- **Goal**: Čist, niskorizičan param koji omogućava future-blind dohват podataka.
- **Scope**: `end_time` u `BinanceMarketDataClient.get_ohlcv` (+ `_CacheKey`), prosleđivanje kroz `market_data_server` i `render_chart_for_symbol`; testovi za odsustvo budućih sveća.
- **Success signal**: `get_ohlcv(symbol, tf, end_time=T)` vraća isključivo sveće ≤ T; postojeći testovi zeleni.
- **Build model/effort**: Sonnet @ medium (plumbing, jasna izmena) **/ Codex med–high** kao alternativa (čist kod, malo tokena).

**Phase 2: Lookahead probe + dual-mode prep + anonimizacija**
- **Goal**: Prvo *dokazati* da li blinding uopšte treba (lookahead-honesty probe), pa izgraditi reproducibilan, anonimizovan ulaz do opravdane dubine.
- **Scope (redom):**
  1. **Probe** — minimalni dual-mode render za 2–3 poznata slučaja (npr. pilot BTC): `blind` (do T) i `future_visible` (posle T + vertikalni „as-of T" marker + instrukcija „analiziraj kao da je sada T"). Pusti slepog analitičara na oba; uporedi da li future-visible analiza „curi" budućnost (referencira događaje posle T) i da li joj skor skače.
  2. **Odluka (gate):** ako Δskor ≈ 0 → agent ne vara → blinding se svodi na živi `end_time` + as-of instrukciju (tanji prep). Ako Δskor velik → pun snapshot blinding kako je planiran.
  3. **Prep** — `data/eval/case_XX/{candles.json, chart.png}` + answer key **van** foldera; `mode: blind | future_visible` toggle; anonimizacija sa popravkama (neuobičajen cenovni opseg, neutralisani datumi i volume-stil); manifest slučajeva.
- **Success signal**: Probe rezultat zapisan (Δskor + odluka); dual-mode toggle radi; dva poziva sa istim parametrima → isti bajtovi snapshota; answer key nedostupan analitičaru; vizuelno se ne prepoznaje BTC/datum.
- **Build model/effort**: Opus @ high za probe-analizu i anonimizacijske odluke (vizuelno-judgment, **ne Codex**); Sonnet @ medium za render/prep I/O (**/ Codex med** alternativa).

**Phase 3: Ground-truth test set v1**
- **Goal**: Kurirani skup „odlučujućih tačaka" koji nije samo poznati BTC vrhovi/dna.
- **Scope**: ~10 tačaka — 2 spring, 2 UTAD/UT, 2 SOS/SOW, 1 redistribucija prerušena u akumulaciju, 1 čista Phase-B buka, 2 failed signala; simboli BTC + 2–3 mid-cap alta + 1 akcija; **≥2 post-knowledge-cutoff**; svaka sa answer key-em (šta se desilo posle T).
- **Success signal**: Snapshoti generisani za svih ~10; svaka tačka ima verifikovan ground truth i event-tip oznaku.
- **Build model/effort**: Opus @ high→extra-high/max za teže tačke (Wyckoff domen + vizuelno čitanje — suština). **Ne Codex** (slab na čisto vizuelnom).

**Phase 4: Skoring rubrika + izolovani sudija**
- **Goal**: Objektivno skorovanje *verovatnosnog* outputa, otporno na sudija-leakage.
- **Scope**: rubrika (tačnost strukture/faze/eventa, ispravnost vodećeg smera, razumnost trigger/invalidacije, **kalibracija confidence-a**, wait-pravilo); semi-automatika (deterministički: smer-match, trigger-u-opsegu; LLM: narativ/kalibracija); izolovani Opus-sudija koji vidi samo output + answer key.
- **Success signal**: Skorovanje pilot-outputa reprodukuje scorecard iz #66; test dokazuje da grafik nikad ne stiže do sudije.
- **Build model/effort**: Opus @ high→extra-high/max za dizajn rubrike (glavni izvor vrednosti); **Codex med–high** za deterministički skoring kod (smer-match, trigger-u-opsegu).

**Phase 5: Analysis-journal**
- **Goal**: Trajni, ocenljivi zapis svake žive analize.
- **Scope**: novi append-only JSONL store (`data/journal/YYYY-MM.jsonl`) sa poljima `analysis_id, logged_at, symbol, timeframe, model, effort, narrative, structure, phase, forecast{direction, trigger, invalidation, confidence}, chart_path, review`; MCP tool-ovi (log/list/get/review); aktivacija u `.mcp.json`; review tok (reuse `replay`-obrasca).
- **Success signal**: Živa analiza upiše zapis; `review` se može popuniti naspram kasnijeg OHLCV-a; server vidljiv u `.mcp.json`.
- **Build model/effort**: Sonnet @ medium (paralela `signal_logger` obrasca) **/ Codex med–high** alternativa (čist store/MCP kod).

**Phase 6: Benchmark batch + report**
- **Goal**: Empirijski odgovor „koji model + effort za koji tip zadatka" + kvantifikovan leakage.
- **Scope**: batch runner nad identičnim snapshotima preko **matrice model × effort** (vidi sekciju „Model × Effort" dole — pun effort raspon, Codex uključen); beleženje token-cost-a uz skor (ROI); **obe kontrole** (anon-vs-revealed za pretraining-leakage + slep-vs-vidljiva-budućnost za lookahead-honesty); report tabela model × effort × skor × token-cost po dimenziji/event-tipu.
- **Success signal**: Jedan report koji rangira model×effort i prikazuje oba Δskor-a (anon→revealed i slep→vidljiva budućnost); izlaz hrani `model:*` preporuke na budućim issue-ima.
- **Build model/effort**: Opus @ high→extra-high/max za sintezu/izveštaj; **Codex med–high** za batch-runner plumbing. **Pokreće** ceo matrični benchmark.

### Parallelism Notes

- **Phase 5 (journal)** je nezavisan od eval isečaka (drugi domen — observability žive analize) → može teći paralelno sa 1–4 u zasebnom worktree-u.
- **Phase 3 (test set)** i **Phase 4 (sudija/rubrika)** dele samo zavisnost od Phase 2; međusobno su različiti domeni (domenska kuracija vs. skoring infrastruktura) → paralelno.
- **Phase 6** je integracioni vrh — čeka i 3 i 4.

---

## Model × Effort (build i benchmark)

> **Napomena o Claude effort nivoima:** prvobitna matrica iz #66 navela je samo `medium/high` za Claude — to sam preuzeo iz seme, **nije bila namerna isključivost** `extra-high`/`max`. Ovde proširujem na **pun raspon**, jer je effort **merena varijabla** harness-a, ne pretpostavka. Tačan gornji naziv tiera (`extra-high` vs `max`) potvrditi iz Claude Code `/effort` opcija pre benchmark batch-a (vidi Open Questions).

**A) Build — koji model gradi koju fazu (+ da li je Codex alternativa):**

| Faza | Primarni build | Codex alternativa? | Zašto |
|---|---|---|---|
| 1 `end_time` | Sonnet @ medium | **Da** (med–high) | Čist plumbing, malo tokena — Codex jak |
| 2 probe + prep + anon | Opus @ high (probe-analiza + anon odluke) + Sonnet @ medium (render/I/O) | **Delom** (render/I/O da; probe + anon ne) | Probe i anonimizacija su vizuelno-judgment |
| 3 test set v1 | Opus @ high→extra-high/max | **Ne** | Wyckoff domen + vizuelno čitanje — Codex slab |
| 4 rubrika + sudija | Opus @ high→extra-high/max (rubrika) + Codex (det. kod) | **Delom** (det. skoring da; rubrika ne) | Dizajn rubrike = judgment |
| 5 journal | Sonnet @ medium | **Da** (med–high) | Čist store/MCP kod (paralela `signal_logger`) |
| 6 benchmark + report | Opus @ high→extra-high/max (sinteza) + Codex (runner) | **Delom** (runner da; sinteza ne) | Izveštaj = sinteza |

**B) Benchmark run — matrica koju harness pušta nad identičnim slepim ulazom** (analitičar; effort = merena varijabla, token-cost se beleži uz skor):

| Model | Effort nivoi za test | Napomena |
|---|---|---|
| Claude Sonnet 4.x | medium, high, extra-high/max | jeftina baza |
| Claude Opus 4.x | medium, high, extra-high/max | trenutni default za sintezu |
| Claude Fable 5 | medium, high, extra-high/max | uključiti čim bude dostupan (sumnja se da pravi razliku na vizuelno-strukturnom čitanju) |
| Codex (GPT-5.x-codex) | low, medium, high, extra-high | jak na strukturisanom, sumnjiv na čisto vizuelnom; jeftiniji po tokenu |

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Primarni izvor za analitičara | Zamrznut snapshot (`end_time` kao generator) | Živi `end_time` direktno | Reproducibilno (fer poređenje modela), fizički bez budućnosti, anonimizacija ugrađena u prep |
| Journal mehanizam | Novi analysis-journal | Proširiti `signal_logger`; hibrid | Čista separacija: signal_logger = uži trade signal, journal = ceo analitički scenario |
| Test set v1 | Mali kurirani (~8–12) | Srednji (~20–30); minimalno ~5 | Dovoljno za signal, brzo za izgradnju; miks event-tipova + post-cutoff |
| Skoring | Izolovani LLM-sudija (Opus) + semi-automatika | Ručna ocena; čisto polu-automatska | Skalira na model×effort batch; izolacija (bez grafika) sprečava sudija-leakage |
| Milestone | Novi M7 / „Faza 4" | Pakovati u Fazu 3 | Drugačiji cilj (eval + observability + benchmark) uz reuse Faza-3 infra |
| „Wait/no-trade" u skoringu | Ne kažnjavati opravdan oprez; kalibracija odvojeno | Tretirati kao promašaj | Ispravan low-confidence „wait" bez trigera u prozoru je tačan |
| Anon-vs-revealed izvođenje | Dvostruko puštanje (double run) — različit agent po prolazu | Jedan slučaj viđen oba puta od istog agenta | Otvoreni (revealed) prolaz ne sme da zagadi slepi (anon) prolaz istog modela |
| `data/eval/` + `pilot_out/` artefakti | Idu u `.gitignore` | Komitовати snapshote/PNG-ove | Snapshoti se regenerišu iz answer key-a + manifesta; repo ostaje lak |
| Da li blinding (sečenje budućnosti) uopšte treba | **Probe pre gradnje**: dual-mode (slep vs vidljiva budućnost) + gate u Phase 2 | Pretpostaviti da treba i graditi pun snapshot blinding odmah | Ako agent ne vara gledanjem budućnosti, skupa mašinerija je suvišna — dokaz pre kompleksnosti |

---

## Research Summary

**Market Context**
Domen je „blind backtest" + „LLM-as-judge eval" + „data-leakage/contamination kontrola" — ustaljeni obrasci u evaluaciji modela (held-out/post-cutoff skupovi, anonimizacija ulaza, izolovani sudija koji ne vidi sirovi stimulus). Nije rađeno tržišno istraživanje konkurenata (interni harness, niska vrednost eksternog benchmark-a); relevantni obrasci već su utelovljeni u dizajnu (post-cutoff tačke, anon-vs-revealed A/B, judge-bez-stimulusa).

**Technical Context**
- `scripts/mcp/market_data_client.py:136-161` — `get_ohlcv` bez `end_time`; `endTime` postoji na Binance `/klines` (pilot ga koristi sirovo).
- `scripts/mcp/signal_logger_server.py` — uzor za append-only JSONL store; `replay_signal` (linije 210-271) je reuse-abilan obrazac za review tok; **nije u `.mcp.json`**.
- `scripts/mcp/chart_renderer.py` — `render_chart_image` prima proizvoljan OHLCV (anon render bez izmena).
- `scripts/eval/pilot_blind_slice.py` + `pilot_out/{blind_chart.png, blind_candles.json, ANSWER_KEY.json}` — referentna implementacija mehanike (throwaway).
- `.mcp.json` — trenutno 3 servera; journal i (po potrebi) signal_logger se aktiviraju ovde.

---

*Generated: 2026-06-16*
*Status: DRAFT — needs validation*
