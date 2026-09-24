# Wyckoff strategy eligibility i post-T replay — development pilot

**Povezano:** #101 — Proveriti wiki-assisted analizu grafikona prema ekspertu i budućem ishodu

**Datum:** 2026-09-24

**Skup:** 20 ranije analiziranih crypto grafikona, Arm A / theory-only, Luna xhigh

**Presuda:** četiri stroge strategije nisu još operativan trading sloj; postojeći slobodni analyst output nije dao nijedan setup koji prolazi sve evidence, readiness, numeric-anchor i stvarni ≥3R gate.

## Šta je provereno

Nad zamrznutim pre-T Luna analizama proverene su četiri unapred definisane Wyckoff strategije:

1. `phase_c_shake_direct` — direktan Spring #3 long ili UTAD/SOW short;
2. `phase_c_test` — Spring/Test long ili UTAD/Test short;
3. `phase_d_break_test` — BUEC/LPS long ili FTI/LPSY short;
4. `phase_e_continuation` — potvrđen Phase E nastavak na reakciji/testu, bez jurenja breakouta.

Pravila su izvedena iz postojećeg teorijskog wikija (`accumulation-phase-c-entry`, `distribution-phase-c-entry`, `phase-d-breakout-test`, BUEC i FTI stranice) i Fraserovog zahteva za najmanje 3:1 reward:risk. Prag 3R je filter nad stvarnim nivoima, ne generator izmišljenog targeta.

Za svaki grafikon izolovani `gpt-5.6-luna xhigh` normalizer video je samo:

- već zamrznutu Arm A analyst analizu;
- anonimne pre-T OHLCV sveće;
- četiri zamrznuta pravila, prompt i strogu JSON schemu.

Nije video case identitet, ekspertski odgovor, expert wiki, Git, post-T sveće niti ostatak repozitorijuma. Posle modelskog koraka planovi su hashovani, a odvojeni proces bez modela dobio je post-T podatke i postojeći `evaluate_trade()`.

## Glavni rezultat

| Metrika | Rezultat |
|---|---:|
| Grafikona | 20 |
| Strategy assessment-a | 80 |
| Modelski prihvaćenih case sidecar-a | 19 |
| Konzervativnih validation fallback-a | 1 |
| Eligible strategija | **0 / 80** |
| Ineligible | 75 / 80 |
| Insufficient evidence | 5 / 80 |
| Strategy entry / trade | **0 / 0** |

Razlozi preskakanja:

| Razlog | Broj |
|---|---:|
| `not_ready` | 41 |
| `setup_absent` | 29 |
| `insufficient_numeric_anchors` | 5 |
| `below_3r` | 4 |
| `contradictory_evidence` | 1 |

Nulta coverage nije dokaz da Wyckoff setupi ne postoje. Ona dokazuje užu stvar: iz postojećeg analyst output contract-a ne možemo pošteno i reproduktivno izvući ove četiri trade strategije bez dopisivanja činjenica, izmišljanja targeta ili popuštanja evidence/readiness pravila.

## Existing-plan baseline

Radi poređenja je replay-ovan originalni `trade_plan` iz svake Luna analize. To nije jedna od četiri strategije i nije korišćen za njihovu eligibility odluku.

| Metrika | Rezultat |
|---|---:|
| Actionable planovi | 10 / 20 |
| Stvarni entry | 7 |
| Target / stop | 2 / 5 |
| Expired bez entry-ja | 2 |
| Intrabar neodređeno pre entry-ja | 1 |
| Win rate među uđenim i scorable trejdovima | 2 / 7 = **28,57%** |
| Svi razrešeni planovi, uključujući no-trade/expiry 0R | 19 |
| Zbir net R uz 10 bps fee + 5 bps slippage po strani | **+0,05036R** |
| Prosečan net R po razrešenom planu | **+0,00265R** |
| Fixed-risk zbir pri 1% rizika po nezavisnom planu | **+0,05036%** |

Rezultat je praktično break-even i veoma nestabilan: dva targeta nose dobit, pet ulazaka završava stopom. Ovo nije portfolio backtest; pozicije nisu vremenski chain-ovane, kapital se ne reinvestira i preklapanje nije modelovano.

## Po grafikonu

`Gate` sažima dominantan ishod četiri strategije. Svi redovi imaju 0 eligible strategija.

| Case | Strategy gate | Existing baseline post-T |
|---|---|---|
| `btc_vol14_2020_03` | 4× not ready | no trade, 0R |
| `btc_vol16_2020_04` | 4× not ready | no trade, 0R |
| `btc_vol17_weekly_2020_04` | 4× setup absent | no trade, 0R |
| `btc_vol18_2020_04` | 2× not ready, 2× absent | no trade, 0R |
| `btc_vol19_2020_04` | absent/contradictory/not ready | target, **+3,3101R** |
| `btc_vol21_2020_05` | Phase D ispod 3R; ostalo skip | intrabar ambiguous, N/A |
| `btc_vol22_2020_05` | 4× not ready | no trade, 0R |
| `btc_vol27f_2020_07` | 2× not ready, 2× absent | no trade, 0R |
| `btc_vol35_2020_09` | Phase E ispod 3R; ostalo skip | stop, **−1,1284R** |
| `btc_vol37_2020_10` | Phase E ispod 3R; ostalo skip | stop, **−1,1024R** |
| `btc_vol43_2020_11` | Phase E ispod 3R; ostalo skip | stop, **−1,1161R** |
| `btc_vol44_2020_11` | 4× not ready | no trade, 0R |
| `btc_vol45_2020_11` | 4× not ready | no trade, 0R |
| `ethbtc_vol20_2020_05` | absent/not ready | expired bez entry-ja, 0R |
| `link_vol25_2020_06` | absent/not ready | stop, **−1,0304R** |
| `link_vol40_2020_10` | validation fallback, 4× insufficient evidence | target, **+2,1559R** |
| `linkbtc_vol17_2020_04` | not ready/absent | expired bez entry-ja, 0R |
| `trx_vol23_2020_05` | absent/not ready | no trade, 0R |
| `xtz_vol30_2020_08` | 4× setup absent | no trade, 0R |
| `yfi_vol32_2020_08` | 4× not ready | stop, **−1,0383R** |

`link_vol40_2020_10` je transparentno označen fallback: dva model outputa su spojila delove dve različite rečenice u navodno verbatim evidence. Oba su odbijena; kod je konzervativno napravio no-trade/insufficient-evidence plan i hashovao oba failure traga. Baseline u tom redu potiče iz originalne, ranije zamrznute Luna analize i zato se i dalje može odvojeno replay-ovati.

## Odnos prema ekspertu

Prethodni blind evaluator je na istih 20 Luna grafikona izmerio prosečan expert-claim alignment od 58,89% za Arm A i 60,49% za Arm B. Ovaj experiment meri drugo: da li se iz analize može dobiti izvršiv trade sa strogim pravilima.

Na slučajevima gde je ekspert eksplicitno dao smer i baseline je dao smer, baseline smer je uglavnom kompatibilan sa ekspertom, ali praktičan rezultat nije dobar: `btc_vol43`, `btc_vol37` i `yfi_vol32` imaju kompatibilan smer, a ipak završavaju stopom; `ethbtc_vol20` i `linkbtc_vol17` ne dobijaju entry. To direktno pokazuje da slaganje oko smera nije isto što i profitabilan entry/stop/target plan.

Ne postoji pošten expert-vs-LLM trade P&L poređenje za ovaj skup: ekspertski pasusi uglavnom nemaju sva tri eksplicitna numerička nivoa entry/stop/target. Zato ekspertov tekst nije pretvoren u izmišljeni executable trade.

## Tokeni, trajanje i trošak

Finalni v5 run:

| Metrika | Vrednost |
|---|---:|
| Pozivi / prihvaćeni | 24 / 19 |
| Input / cached input / output tokeni | 2.350.693 / 1.550.848 / 153.073 |
| Zbir prijavljenog call trajanja | 3.595,103 s |
| API-ekvivalentna procena | **$0,374674** |

Sa contract probe-ovima i odbačenim v1–v4 pokušajima: 43 poziva, 3.900.227 input, 2.582.784 cached input i 281.381 output tokena, približno **$0,652801** API-ekvivalentno. To nije izmerena Codex CLI naplata. Jedan runtime proces je ručno prekinut kada je ostao zaglavljen preko timeouta; njegov stvarni wall-clock nije pouzdano predstavljen zbirom prijavljenih trajanja.

## Reproduktivnost i artefakti

Root artefakata:

`/Users/ssmiljanic/.prp/wyckoff-ai-472026b6/spikes/wyckoff-strategy-eligibility-replay-v1/`

- `run-v5-final/` — 20 fizički izolovanih paketa, 24 attempt traga i 19 accepted outputa;
- `frozen-plans-v1/` — 20 hashovanih case zapisa, 80 strategy planova i baseline;
- `replay-v1/` — per-case replay, `summary.json` i manifest;
- `final-usage-cost.json` — per-call token/duration/cost ledger;
- `private-replay-inputs/` — privatne transformacije i post-T sveće.

Package verify, frozen byte-identical rebuild i replay byte-identical verify prolaze. Produkcioni wiki nije menjan.

## Slabosti i sledeći korak

- Ovo je development skup koji je već korišćen za istraživanje, ne nov holdout dokaz.
- Četiri pravila su namerno stroga i single-entry; ne pokrivaju staged entry, trailing stop ili scenario bez stvarnog targeta.
- Nulta eligibility znači da ne možemo rangirati četiri strategije po profitu na ovom skupu.
- Baseline ima samo sedam ulazaka; jedan ili dva ishoda potpuno menjaju zbir.

Najmanji sledeći korak nije još deset skupih chart analiza. Prvo treba napraviti mali, unapred zamrznut **trade-decision output contract** u samom analyst promptu: setup enum, readiness, entry, stop, stvarni target, expiry i evidence leaf za svaki nivo. Zatim isti theory-only analyst pokrenuti na približno 10 novih holdout grafikona. Ako taj contract proizvede razumnu coverage bez popuštanja 3R/evidence pravila, tek tada ima smisla birati jednu ili dve strategije i meriti out-of-sample trading rezultat.
