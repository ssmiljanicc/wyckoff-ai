# Investigation: bug: tri runtime greške u eval orkestratoru sprečavaju canary run

**Issue**: #77 (https://github.com/ssmiljanicc/wyckoff-ai/issues/77)
**Type**: BUG
**Investigated**: 2026-06-20T14:08:21+02:00

## Assessment

| Metric | Value | Reasoning |
| --- | --- | --- |
| Severity | HIGH | Issue dokumentuje da sva tri uzastopna kvara blokiraju prvi naplativi Claude canary i zato ceo Phase 4 benchmark ne može da proizvede validan rezultat. |
| Complexity | HIGH | Plan zahvata sedam fajlova i više integracionih tačaka: provider argv/auth izolaciju, parser, prompt/schema ugovor, testove i operator runbook. |
| Confidence | HIGH | Issue sadrži konkretne runtime izlaze, lokalni Claude Code 2.1.183 help potvrđuje inline schema i OAuth ograničenje `--bare`, a trenutni kod, testovi i skoring ugovor su pregledani sa tačnim referencama. |

## Problem Statement

Claude adapter trenutno prosleđuje putanju tamo gde CLI očekuje inline JSON schema sadržaj, a `--bare` režim na instaliranom Claude Code 2.1.183 ne koristi OAuth/keychain autentifikaciju, pa canary ne stiže do pouzdanog strukturisanog odgovora. Radni diff popravlja oba neposredna kvara i dodaje JSON-only prompt/parser fallback, ali još nema testove za inline schema-u i fenced JSON, a nova prompt formulacija uklanja eksplicitni analitički narativ koji nosi 10% skora (`scripts/eval/scoring.py:53-61`, `scripts/eval/scoring.py:82-87`).

## Analysis

### Codebase Explorer — šta postoji

| Area | File:Lines | Notes |
| --- | --- | --- |
| Claude argv | `scripts/eval/runtime_adapters.py:110-131` | Gradi headless poziv, radi capability/auth preflight; radni diff već inline-uje schema-u i uklanja `--bare`. |
| Claude parser | `scripts/eval/runtime_adapters.py:133-154` | Preferira `structured_output`, zatim `result`; radni diff uklanja standardni markdown fence pre `json.loads`. |
| Analyst prompt | `scripts/eval/orchestrator.py:212-238` | Ugrađuje `candles.json` u prompt; radni diff zahteva JSON-only i navodi sedam obaveznih polja. |
| Runtime ulaz | `scripts/eval/orchestrator.py:288-306` | I analyst i judge koriste isti Claude adapter; output se naknadno validira JSON schema-om. |
| Analyst schema | `scripts/eval/schemas/analysis_output.schema.json:1-24` | Sedam obaveznih polja; `narrative`, `evidence`, `rationale` i srodna polja su dozvoljena, ali opciona. |
| Skoring ugovor | `scripts/eval/scoring.py:17-61` | `narrative_quality` je judge dimenzija težine 0.10. |
| Judge rubrika | `scripts/eval/scoring.py:64-93` | Ocenjuje kvalitet rezonovanja, redosled dokaza i odsustvo hindsight tvrdnji. |
| Judge payload | `scripts/eval/scoring.py:362-389` | Prosleđuje dozvoljena analitička polja, uključujući `narrative`, `thesis`, `evidence` i `rationale`. |
| Unit testovi | `tests/test_runtime_adapters.py:12-60` | Proveravaju osnovni argv i `structured_output`, ali ne proveravaju vrednost `--json-schema`, `result` string, fenced JSON niti malformed fence. |
| Prompt test | `tests/test_eval_orchestrator.py:97-105` | Proverava samo inline candles i `NO tools`; ne zaključava JSON ni label-last/narativni ugovor. |
| Operator runbook | `runbooks/faza-4-eval-orchestrator.md:7-43` | Još traži `--bare` capability i definiše preview pre naplativog canary-ja. |
| Izvorni plan | `PRPs/plans/completed/faza-4-end-to-end-eval-orchestrator.plan.md:123-132,197-205` | `--bare` je izabran da isključi CLAUDE.md, MCP, hooks i memoriju; plan takođe zahteva kontrolisan env allowlist. |
| Sličan provider obrazac | `scripts/eval/runtime_adapters.py:157-204` | Codex koristi `--ignore-user-config`, read-only sandbox, output schema putanju i JSONL parser. |

Aktuelni radni diff koji je eksplicitno naveden u issue-u menja `CLAUDE.md`, `scripts/eval/orchestrator.py`, `scripts/eval/runtime_adapters.py` i `tests/test_runtime_adapters.py`. Ostale zatečene izmene i untracked fajlovi nisu deo ove istrage.

### Codebase Analyst — trenutni tok

1. `execute_run()` kreira izolovani privremeni root i poziva adapter sa promptom i kopijom schema-e (`scripts/eval/orchestrator.py:288-295`).
2. `ClaudeRuntimeAdapter.build_argv()` prosleđuje prompt kroz stdin, a schema-u kroz `--json-schema` (`scripts/eval/runtime_adapters.py:113-118`).
3. `_exec()` pokreće proces sa PIPE stdin/stdout/stderr i nasleđenim procesnim okruženjem (`scripts/eval/runtime_adapters.py:72-86`).
4. Claude parser čita outer JSON envelope i bira `structured_output`, pa `result`, pa sam envelope (`scripts/eval/runtime_adapters.py:139-152`).
5. Orkestrator ponovo validira dobijeni objekat prema lokalnoj schema-i pre checkpoint-a (`scripts/eval/orchestrator.py:290-297`).
6. `prepare_judge_input()` šalje dozvoljena polja izolovanom sudiji (`scripts/eval/scoring.py:362-389`), koji ocenjuje i `narrative_quality` (`scripts/eval/scoring.py:64-87`).

Posledica: transportni JSON i analitički sadržaj su dva različita ugovora. JSON-only instrukcija je potrebna za transport, ali ne sme da svede sadržaj na sedam labela jer bi sudija ostao bez eksplicitnog rezonovanja i dokaza.

### Root Cause / Change Rationale

#### Greška 1 — schema putanja umesto sadržaja (5 Whys)

1. Canary pada sa `--json-schema is not valid JSON` jer argv sadrži filesystem putanju; dokaz: issue #77 i originalni kod u commit-u `a41bde5`, `scripts/eval/runtime_adapters.py:113-117`.
2. Putanja se šalje zato što je Claude flag tretiran kao Codex `--output-schema`, koji zaista prima putanju (`scripts/eval/runtime_adapters.py:163-169`).
3. Provider ugovori nisu razdvojeni testom vrednosti flag-a; postojeći test proverava samo prisustvo opštih argv osobina (`tests/test_runtime_adapters.py:18-24`).
4. Bez tog testa pogrešna pretpostavka je prošla offline suite.
5. Fixable root cause: Claude adapter mora da pročita schema fajl i pošalje njegov JSON tekst, uz test koji eksplicitno zabranjuje putanju kao vrednost flag-a.

Lokalni dokaz iz `claude --help` na verziji 2.1.183 prikazuje `--json-schema <schema>` sa inline primerom `{"type":"object",...}`, ne putanjom.

#### Greška 2 — `--bare` i OAuth subprocess auth (5 Whys)

1. Non-TTY subprocess vraća `Not logged in` samo sa `--bare`; dokaz: izolovani eksperiment opisan u issue #77.
2. Instalirani CLI definiše `--bare` kao režim u kome su auth opcije striktno `ANTHROPIC_API_KEY` ili `apiKeyHelper`, dok OAuth i keychain nisu učitani; dokaz: lokalni `claude --help`, Claude Code 2.1.183.
3. Lokalni auth je `claude.ai` OAuth (`claude auth status` tokom istrage), pa `--bare` namerno ne vidi aktivnu prijavu.
4. Prvobitni plan je koristio `--bare` i zbog izolacije od CLAUDE.md/MCP/hooks/memorije (`PRPs/plans/completed/faza-4-end-to-end-eval-orchestrator.plan.md:123-132`), pa prosto uklanjanje rešava auth, ali slabi originalnu determinističku granicu.
5. Fixable root cause: adapter mora da podrži OAuth-kompatibilan non-bare poziv uz eksplicitno gašenje user/project settings, MCP/plugin/skill površine i bez alata/session persistence; runbook mora jasno da zabeleži preostalu granicu i canary proveru.

#### Greška 3 — narativ ili fenced JSON umesto parsabilnog objekta (5 Whys)

1. Parser očekuje da je `result` čist JSON string (`scripts/eval/runtime_adapters.py:141-149`), dok issue beleži prose ili markdown fence output.
2. Originalni prompt traži sadržaj scenarija, ali ne kaže da ceo odgovor mora biti JSON (`git show a41bde5:scripts/eval/orchestrator.py`, odgovarajuće linije 215-219).
3. Schema nije pouzdana kao jedina prompt instrukcija u zabeleženom realnom pozivu; orkestrator tek posle poziva validira objekat (`scripts/eval/orchestrator.py:290-295`).
4. Ne postoji test za `result` fallback ni fenced JSON (`tests/test_runtime_adapters.py:35-42`).
5. Fixable root cause: prompt mora eksplicitno zahtevati jedan JSON objekat i opisati analitička polja, dok parser treba usko da prihvati samo kompletan standardni JSON fence kao kompatibilni fallback.

Radni prompt rešava format, ali uvodi regresioni rizik: navodi samo sedam obaveznih polja (`scripts/eval/orchestrator.py:229-236`), dok skoring izričito meri reasoning/evidence kvalitet (`scripts/eval/scoring.py:53-61,82-87`). Implementacija zato treba da zadrži `narrative` i `evidence` unutar JSON-a i eksplicitno kaže „price/volume behavior before labels”.

### Evidence Chain

**Aktuelni Claude argv kod:**

```python
# SOURCE: scripts/eval/runtime_adapters.py:113-118
def build_argv(self, request: RuntimeRequest) -> list[str]:
    return [
        self.binary, "-p", "--model", request.model, "--effort", request.effort,
        "--json-schema", request.schema_path.read_text().strip(), "--output-format", "json",
        "--tools", "", "--permission-mode", "dontAsk", "--no-session-persistence",
    ]
```

**Aktuelni parser fallback:**

```python
# SOURCE: scripts/eval/runtime_adapters.py:140-151
envelope = json.loads(stdout)
output = envelope.get("structured_output", envelope.get("result", envelope))
if isinstance(output, str):
    stripped = output.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = lines[1:-1] if len(lines) > 2 and lines[-1].strip() == "```" else lines[1:]
        stripped = "\n".join(inner)
    output = json.loads(stripped)
if not isinstance(output, dict):
    raise ValueError("structured output is not an object")
```

**Konflikt sadržajnog ugovora:**

```python
# SOURCE: scripts/eval/scoring.py:53-61
DIMENSION_WEIGHTS: dict[str, float] = {
    "structure": 0.15,
    "phase": 0.15,
    "event": 0.15,
    "direction": 0.15,
    "trigger": 0.10,
    "invalidation": 0.10,
    "narrative_quality": 0.10,
    "calibration": 0.10,
}
```

Komande izvršene tokom istrage:

```text
claude --version
=> 2.1.183 (Claude Code)

claude auth status
=> loggedIn=true, authMethod=claude.ai, apiProvider=firstParty

uv run --extra mcp pytest tests/test_runtime_adapters.py tests/test_eval_orchestrator.py tests/test_scoring.py -q
=> 25 passed in 0.97s

uv run --extra mcp pytest -q
=> 246 passed in 4.55s
```

Zeleni testovi potvrđuju da radni diff nije polomio postojeća očekivanja; ne potvrđuju nove runtime ugovore koji još nemaju testove.

### Affected Files

| File | Lines | Action | Description |
| --- | --- | --- | --- |
| `scripts/eval/runtime_adapters.py` | `72-86,110-154` | UPDATE | Inline Claude schema, OAuth-kompatibilan ali očvrsnut non-bare argv, uski fenced-JSON fallback i jasne greške. |
| `scripts/eval/orchestrator.py` | `212-238` | UPDATE | JSON-only transport uz očuvan behavior-before-labels narativ i dokaze. |
| `scripts/eval/schemas/analysis_output.schema.json` | `1-24` | UPDATE | Uskladiti schema-u sa sadržajem koji `narrative_quality` zaista ocenjuje; zahtevati najmanje `narrative` i `evidence` pored postojećih sedam polja. |
| `tests/test_runtime_adapters.py` | `12-60` | UPDATE | Zaključati inline schema, non-bare izolacione flagove, raw/fenced `result` i negativne parser slučajeve. |
| `tests/test_eval_orchestrator.py` | `97-105` | UPDATE | Zaključati JSON-only, price/volume-before-labels, `narrative`/`evidence` i polja scenarija. |
| `runbooks/faza-4-eval-orchestrator.md` | `7-43,78-88` | UPDATE | Ukloniti zastareli `--bare` capability zahtev, opisati OAuth razlog, očvrsnut profil i obavezni canary. |
| `CLAUDE.md` | `54-57` | UPDATE (već zatečeno) | Nezavisna konvencija naslova issue-a koju #77 eksplicitno dopušta u istom PR-u; nema runtime uticaj. |

Nema fajlova za brisanje. Nema potrebe za novim produkcionim modulom.

### Integration Points

- `scripts/eval/orchestrator.py:290-305` koristi isti adapter za analyst i judge, pa argv/parser izmena mora raditi sa obe schema-e.
- `scripts/eval/orchestrator.py:294-295,306` radi konačnu JSON Schema validaciju i ostaje autoritativna granica posle parsera.
- `scripts/eval/scoring.py:362-389` prosleđuje `narrative` i `evidence` sudiji; prompt/schema moraju osigurati da ta polja postoje.
- `scripts/eval/benchmark.py:106-118` dokumentuje minimalna scenario polja i ne zahteva promenu ako se dodatna analitička polja samo prošire unutar postojeće schema-e.
- `runbooks/faza-4-eval-orchestrator.md:32-43` je jedino odobreno mesto za naplativi canary posle preview-a.

### Git History

- **Introduced**: `a41bde5` — 2026-06-19 — `feat: dodaj end-to-end eval orkestrator`; uveo Claude argv, parser, prompt i schema-u zajedno.
- **Last relevant committed change**: `820073d` — 2026-06-20 — `fix: analyst dobija OHLCV inline + in-process retry za max_attempts`; promenio analyst prompt/input tok.
- **Runbook follow-up**: `06dfc75` — 2026-06-20 — `docs: ispravi evaluacioni ugovor i izolacione garancije u runbook-u`.
- **Implication**: greške 1 i 2 su originalne pretpostavke nove integracije, ne kasnija regresija. Greška 3 je integraciona praznina između transportnog formata, prompta i postojećeg judge ugovora.

## Implementation Plan

### Step 1: Prvo zaključati runtime ugovore regresionim testovima

**File**: `tests/test_runtime_adapters.py`
**Lines**: `12-60`
**Action**: UPDATE

**Current code:**

```python
# SOURCE: tests/test_runtime_adapters.py:18-24
argv = runtime.ClaudeRuntimeAdapter().build_argv(request(tmp_path))
assert argv[0:2] == ["claude", "-p"]
assert "--bare" not in argv
assert argv[argv.index("--tools") + 1] == ""
assert "--no-session-persistence" in argv
```

**Required change:**

- U test helper upisati prepoznatljivu schema-u, ne samo `{}`.
- Asertovati da je vrednost posle `--json-schema` tačan sadržaj fajla i da nije `str(schema_path)`.
- Asertovati odsustvo `--bare` i prisustvo svih eksplicitnih non-bare izolacionih flagova iz Step 2.
- Dodati parametrizovane parser testove za:
  - `structured_output` objekat;
  - `result` kao čist JSON string;
  - `result` kao kompletan ```` ```json ... ``` ```` fence;
  - `result` kao kompletan neutralni ```` ``` ... ``` ```` fence.
- Dodati negativne testove za prose prefix/suffix, nezatvoren fence, JSON listu i invalid JSON; svi moraju dati `RuntimeExecutionError("invalid Claude structured output")`.

**Why**: postojeći suite ne bi uhvatio nijednu od tri runtime greške iz issue-a.

### Step 2: Završiti Claude argv popravku bez tihog odustajanja od izolacije

**File**: `scripts/eval/runtime_adapters.py`
**Lines**: `72-86,110-154`
**Action**: UPDATE

**Current code:** vidi Evidence Chain.

**Required change:**

1. Zadržati `request.schema_path.read_text().strip()` za `--json-schema`.
2. Zadržati uklanjanje `--bare` za OAuth/keychain profil potvrđen u issue-u i lokalnom CLI help-u.
3. Dodati eksplicitne CLI granice dostupne u Claude Code 2.1.183:
   - `--setting-sources ""` da se ne učitavaju user/project/local settings;
   - `--strict-mcp-config --mcp-config "{}"` da se ne naslede MCP serveri;
   - `--disable-slash-commands` da se isključe skills/commands;
   - zadržati `--tools ""`, `--permission-mode dontAsk` i `--no-session-persistence`.
4. Proširiti preflight listu istim korišćenim capability flagovima; ne proveravati uklonjeni `--bare` kao zahtev.
5. Ako CLI odbija prazan `--setting-sources`, tretirati to kao `RuntimeUnavailable`, ne vraćati se automatski na nasleđena podešavanja. Ovo se proverava besplatnim capability/argv smoke-om pre canary-ja.
6. Izdvojiti usko parsiranje string rezultata: trim whitespace; ukloniti samo kompletan fence čiji je prvi red tačno ` ``` ` ili ` ```json `, a poslednji red tačno ` ``` `; zatim `json.loads`; odbiti sav prose oko JSON-a i sve non-object vrednosti.

**Why**: uklanjanje `--bare` je neophodno za trenutno OAuth okruženje, ali bez eksplicitnog očvršćavanja krši prvobitni benchmark zahtev da hidden user/project config ne utiče na rezultat (`PRPs/plans/completed/faza-4-end-to-end-eval-orchestrator.plan.md:197-205`).

Besplatni CLI parse smoke tokom istrage potvrdio je da Claude Code 2.1.183 prihvata kombinaciju `--setting-sources "" --strict-mcp-config --mcp-config '{}' --disable-slash-commands --tools '' --no-session-persistence` i vraća verziju sa exit statusom 0. To ne dokazuje ponašanje tokom realnog model poziva; naplativi canary ostaje obavezna integraciona provera.

### Step 3: Očuvati Wyckoff analizu unutar strogog JSON objekta

**File**: `scripts/eval/orchestrator.py`
**Lines**: `212-238`
**Action**: UPDATE

**Current code:**

```python
# SOURCE: scripts/eval/orchestrator.py:229-236
"Your ENTIRE response must be a single valid JSON object — no markdown, no text, no explanation outside the JSON. "
"Analyze ONLY the anonymized OHLCV data embedded below. Reason about price/volume "
"behavior (supply/demand, effort/result, cause/effect) and return exactly one scenario "
"as a JSON object with these fields: "
"direction (\"up\"/\"down\"/\"none\"), "
"trigger (number or null), invalidation (number or null), "
"confidence (float 0..1), structure (string), phase (string), event (string). "
```

**Required change:**

- Zadržati prvu JSON-only rečenicu.
- Vratiti eksplicitni redosled „describe price/volume behavior before labels”.
- Zahtevati `narrative` string koji opisuje observations pre etiketa i `evidence` kao niz kratkih price/volume dokaza, pored postojećih sedam polja.
- Naglasiti da su Wyckoff labels (`structure`, `phase`, `event`) zaključak iz prethodnih opservacija, ne zamena za njih.
- Ne tražiti chain-of-thought; `narrative` i `evidence` treba da budu sažet, proverljiv izlaz koji judge već ocenjuje.
- Zadržati zabranu identiteta/datuma i operatorovu per-spec instrukciju.

**Why**: transport ostaje parsabilan, a sadržaj ostaje usklađen sa `narrative_quality` rubrikom i „labeling is last step” metodologijom.

### Step 4: Uskladiti schema-u sa stvarnim skoring ugovorom

**File**: `scripts/eval/schemas/analysis_output.schema.json`
**Lines**: `1-24`
**Action**: UPDATE

**Current code:**

```json
"required": ["direction", "trigger", "invalidation", "confidence", "structure", "phase", "event"]
```

**Required change:**

Dodati `narrative` i `evidence` u `required`; zadržati `narrative` kao neprazan string, a `evidence` ograničiti na niz nepraznih stringova (ne slobodan string) kako bi output bio uporediv između modela. Ostala opciona kompatibilna polja mogu ostati dozvoljena; `additionalProperties: false` ostaje.

**Why**: bez obaveznih analitičkih polja model može validno vratiti samo labele, dok sudija ipak pokušava da oceni kvalitet rezonovanja.

### Step 5: Zaključati prompt/schema vezu testom

**File**: `tests/test_eval_orchestrator.py`
**Lines**: `97-105`
**Action**: UPDATE

**Current code:**

```python
assert "333.33" in prompt
assert "NO tools" in prompt
```

**Required change:**

Asertovati JSON-only zabranu markdown/prose izlaza, frazu behavior-before-labels, `narrative`, `evidence` i svih sedam scenario polja. U zasebnom testu učitati `analysis_output.schema.json` i proveriti da promptom tražena obavezna polja odgovaraju `required` skupu.

**Why**: sprečava da buduća prompt optimizacija ponovo razdvoji sadržaj od schema/skoring ugovora.

### Step 6: Ažurirati operator runbook i izvršiti preview → canary sekvencu

**File**: `runbooks/faza-4-eval-orchestrator.md`
**Lines**: `7-43,78-88`
**Action**: UPDATE

**Required change:**

- U capability komandi zameniti `--bare` novim stvarno korišćenim non-bare izolacionim flagovima.
- Dokumentovati da Claude Code 2.1.183 `--bare` ne koristi OAuth/keychain i zato se u ovom lokalnom subscription profilu ne koristi.
- Dokumentovati da tool/filesystem izolacija ostaje `--tools ""` + temp cwd, dok config/MCP/skills izolaciju daju eksplicitni flagovi iz Step 2.
- Zadržati postojeći obavezni `--dry-run` pre realnog canary-ja.
- Posle merge-a pokrenuti samo jedan `case_01 × claude-opus-4-8 × high` canary i ručno proveriti:
  - `analysis_output` je objekat sa svih devet obaveznih polja;
  - `narrative` prvo opisuje price/volume, pa tek onda labels;
  - nema markdown fence-a u sačuvanom rezultatu;
  - usage, analyst checkpoint, judge verdict i report postoje;
  - spoljašnji canary fajl nije dostupan analyst-u.
- Codex sandbox ostaje zasebno `UNVERIFIED`, kako issue već nalaže.

**Why**: runtime problem je eksperimentalno pronađen; offline testovi sami ne dokazuju auth, hidden-config ni real provider envelope.

### Step 7: Pregledati i uključiti nezavisnu CLAUDE.md izmenu

**File**: `CLAUDE.md`
**Lines**: `54-57`
**Action**: UPDATE (već zatečeno)

**Required change:** Zadržati postojeću promenu naslova issue-a na srpski, jer je #77 eksplicitno odobrava. Ne vezivati je za runtime logiku niti širiti schema pravila.

**Why**: operator je izričito naveo da je izmena ispravna i može u isti PR; ona nema uticaj na validaciju runtime popravke.

## Patterns to Follow

```python
# SOURCE: scripts/eval/runtime_adapters.py:163-170
# Provider-specific schema semantika mora ostati odvojena:
# Claude --json-schema prima sadržaj; Codex --output-schema prima putanju.
return [
    self.binary, "exec", "-", "--model", model, "--cd", str(request.cwd),
    "--sandbox", "read-only", "--ephemeral", "--ignore-user-config",
    "--output-schema", str(request.schema_path), "--json",
    "-c", f'model_reasoning_effort="{request.effort}"',
]
```

```python
# SOURCE: scripts/eval/orchestrator.py:290-295
# Parser transporta ne zamenjuje autoritativnu schema validaciju.
response = await adapters[spec["model"]].run(RuntimeRequest(...))
validate_json(response.output, json.loads(ANALYSIS_SCHEMA.read_text()))
```

```python
# SOURCE: tests/test_runtime_adapters.py:35-42
# Runtime se testira preko monkeypatch-ovanog _exec bez mreže i troška.
monkeypatch.setattr(runtime, "_exec", fake_exec)
response = asyncio.run(runtime.ClaudeRuntimeAdapter().run(request(tmp_path)))
```

## Edge Cases & Risks

| Risk/Edge Case | Mitigation |
| --- | --- |
| Non-bare Claude učita hidden settings, MCP, skills ili memoriju i kontaminira benchmark | Eksplicitni settings/MCP/skills flagovi, temp cwd, `--tools ""`, no-session; dokumentovati preostali memory rizik i zaustaviti canary ako granica nije dokaziva. |
| Prazan `--setting-sources` nije validan u verziji 2.1.183 | Besplatni CLI parse/capability smoke pre naplativog canary-ja; neuspeh je `RuntimeUnavailable`, bez silent fallback-a. |
| Schema fajl ne postoji ili nije čitljiv | `build_argv()` treba da pusti jasnu `OSError`/konfiguracionu grešku pre model poziva; testirati missing path. |
| Schema sadržaj je sintaksno nevalidan JSON | Lokalno `json.loads(schema_text)` validirati pre subprocess-a radi rane, jeftine greške. |
| Model vrati prose oko JSON-a | Odbiti; ne izvlačiti prvi `{...}` heuristikom jer to može sakriti dodatni neželjeni sadržaj. |
| Model vrati nezatvoren markdown fence | Odbiti; fallback prihvata samo kompletan standardni fence. |
| JSON je parsabilan ali ne zadovoljava schema-u | Postojeći `validate_json()` u `orchestrator.py:294,306` ostaje konačna provera. |
| Minimalni JSON smanji kvalitet Wyckoff analize | Obavezni `narrative` + `evidence`, behavior-before-labels prompt i prompt/schema regresioni test. |
| `evidence` sadrži pune OHLCV candles i procuri judge-u | Schema dozvoljava samo niz string sažetaka; postojeći sanitizer i testovi ostaju defense-in-depth. |
| Promena analyst schema-e utiče i na Codex benchmark | To je namerno provider-neutralno usklađivanje; pokrenuti postojeći offline suite i kasnije zaseban Codex canary tek posle sandbox verifikacije. |
| Real canary košta i menja rezultate na disku | Pokrenuti samo posle runbook dry-run preview-a i merge-a, tačno jedan slučaj/model/effort. |
| Zatečeni dirty worktree sadrži tuđe izmene | Implementator menja samo navedene fajlove, pregleda `git diff`, ne resetuje niti uključuje ostale untracked artefakte. |

## Validation

### Automated Checks

```bash
uv run --extra mcp pytest tests/test_runtime_adapters.py -q
uv run --extra mcp pytest tests/test_eval_orchestrator.py -q
uv run --extra mcp pytest tests/test_scoring.py -q
uv run --extra mcp python -c 'import json; from pathlib import Path; [json.loads(p.read_text()) for p in Path("scripts/eval/schemas").glob("*.json")]'
uv run --extra mcp pytest -q
```

Besplatni CLI preflight posle implementacije:

```bash
claude --version
claude --help | rg -- '--model|--effort|--json-schema|--no-session-persistence|--setting-sources|--strict-mcp-config|--disable-slash-commands|--tools'
claude auth status
```

### Manual Verification

1. Pregledati `git diff --check` i kompletan diff samo navedenih fajlova; potvrditi da schema JSON nije putanja u Claude argv testu.
2. Pokrenuti runbook `--dry-run` za `case_01`, `claude-opus-4-8`, `high`; proveriti `scope`, `planned`, `unavailable` i da nisu nastali state/result fajlovi.
3. Tek posle review-a/merge-a pokrenuti jedan naplativi canary iz runbook §2.
4. Ručno otvoriti `data/eval/benchmark/_benchmark/results/<run_id>.json` i potvrditi devet obaveznih analyst polja, parsabilan objekat bez fence-a, usage i judge output.
5. Potvrditi da narativ opisuje price/volume dokaze pre `structure`/`phase`/`event` zaključka.
6. Ponoviti isolation canary sa sentinel fajlom van privremenog root-a; ako analyst pokaže sadržaj sentinela, prekinuti dalji benchmark.

## Scope Boundaries

**In scope:**

- Review i dovršavanje četiri zatečene runtime/prompt/test izmene iz #77.
- Provider-specific schema semantika i Claude OAuth auth kompatibilnost.
- Očuvanje postojećeg Wyckoff narrative-quality ugovora u JSON outputu.
- Minimalno potrebni testovi, analyst schema i operator runbook ažuriranje.
- Zatečena `CLAUDE.md` konvencija koju issue eksplicitno odobrava.

**Out of scope:**

- Implementacija popravke u ovoj investigation operaciji.
- Pokretanje naplativog canary-ja pre merge-a.
- Pun benchmark batch.
- Promena skoring težina ili judge rubrike.
- Redizajn Codex adaptera; njegova sandbox izolacija ostaje `UNVERIFIED`.
- Bilo kakav reset, commit ili uključivanje drugih zatečenih untracked/modified fajlova.

## Metadata

- **Investigated by**: Codex (GPT-5)
- **Timestamp**: 2026-06-20T14:08:21+02:00
- **Branch**: `main`
- **Artifact**: `PRPs/issues/issue-77.md`
- **GitHub comment**: nije postavljen; operator nije eksplicitno odobrio eksterno slanje.
- **Linked PRs**: nijedan pronađen (`closedByPullRequestsReferences=[]`; `gh pr list --state all --search '77'` prazan).
- **Issue state**: OPEN.
- **Pre-implementation sanity check**: 2026-06-20 su dva odvojena Codex subagenta paralelno ponovila `codebase-explorer` i `codebase-analyst` prolaze; oba su potvrdila da artefakt odgovara trenutnom stablu, uz jedino beznačajno pomeranje `CLAUDE.md` linije.
