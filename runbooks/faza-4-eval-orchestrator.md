# Faza 4 eval orkestrator — operator runbook

Ovaj tok izvršava benchmark matricu kroz izolovane analyst i judge procese, čuva atomske checkpoint-e i završava postojećim `benchmark.ingest` izveštajem. Ground truth (referentni tačan odgovor) se nikada ne generiše u ovom toku.

## Preduslovi

- Privatni answer key, na primer `data/eval/_answers/ground_truth_answers.json`; fajl ne sme biti commit-ovan.
- Autentifikovani lokalni Claude Code 2.1.183 i Codex CLI 0.141.0 za modele koje birate.
- Capability preflight (provera podržanih mogućnosti CLI-ja):

```bash
claude --version
claude --help | rg -- '--bare|--model|--effort|--json-schema|--no-session-persistence'
codex --version
codex exec --help | rg -- '--model|--cd|--sandbox|--output-schema|--ephemeral|--ignore-user-config'
```

Orkestrator ponavlja proveru pre izvršavanja i označava nepodržan provider/model kao `unavailable`. `claude-fable-5` nema mapiranje u v1 i zato se eksplicitno preskače.

## 1. Obavezni preview

`--dry-run` validira privatni odgovor i selektore, ali ne pravi snapshot, manifest, state ili result fajlove i ne poziva modele/mrežu:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case case_01 --model claude-opus-4-8 --effort high --dry-run
```

Opcije `--case`, `--model` i `--effort` mogu da se ponove ili prime CSV listu. Pregledajte `scope`, `planned` i `unavailable` pre realnog poziva.

## 2. Mali real canary

Ovo pravi naplative pozive. Pokrenite tek posle pregleda preview-a:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case case_01 --model claude-opus-4-8 --effort high \
  --max-concurrency 1 --min-start-interval 2
```

Pre prvog punog batch-a ručno proverite da canary fajl postavljen izvan privremenog runtime root-a nije dostupan analyst-u. Ako instalirana CLI/sandbox kombinacija ne garantuje granicu, real run mora da se prekine; ne prelazite na prompt-only izolaciju.

## 3. Pun run i nastavak

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --max-concurrency 2 --min-start-interval 2 --max-attempts 2 --timeout 900

uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json --resume
```

`--resume` preskače kompletne rezultate. Ako je analyst checkpoint kompletan, ponavlja samo judge fazu. `--no-ingest` preskače završni report, ali ne menja checkpoint semantiku. `--reset-state` koristite samo posle pregleda manifest fingerprint mismatch-a; postojeće validne rezultate ne briše i reconciliation (usklađivanje) će ih ponovo označiti kao uspešne.

## Status i izlazi

- State: `<base-dir>/_benchmark/orchestrator_state.json`
- Rezultati: `<base-dir>/_benchmark/results/<run_id>.json`
- Izveštaji: `<base-dir>/_benchmark/report.md` i `report.json`

`failed` znači da je run iscrpeo `max_attempts`; `pending` ostaje za bezbedan nastavak; `skipped` znači eksplicitno nedostupan provider/model. Exit status je `0` samo kada selektovani scope nema `failed` ili `pending`; konfiguracija/preflight koristi `2`, parcijalni batch `3`, a prekid `130`.

## Anti-leakage granica

Analyst dobija samo kopiju case fajlova i analyst schema-u u sistemskom temp direktorijumu. Symlink i path escape se odbijaju; answer key i repo root se ne kopiraju; provider nema alate, MCP ni trajnu sesiju. Judge radi u drugom praznom root-u i dobija samo payload iz `scoring.prepare_judge_input`, bez grafikona, candles, identiteta i putanja. Prompt i privatni judge payload se ne upisuju u state ili stderr dijagnostiku.

## Opt-in manual smoke

Posle promene Claude/Codex verzije ponovite jedan canary po provider-u. Proverite structured JSON, usage zbir, `result` checkpoint i report. Ovaj smoke nije deo podrazumevanog `pytest` paketa zbog autentifikacije, mreže i troška.
