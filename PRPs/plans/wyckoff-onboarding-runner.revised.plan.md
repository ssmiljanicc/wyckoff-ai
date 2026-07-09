# Feature: Wyckoff onboarding na poligon ingest runner (`research/expert-analyses/` kao konzument)

## Izmene od pregled-plana

Re-pakovano nakon `/pregled-plana` (izveštaj: `.claude/pregled-plana/wyckoff-onboarding-runner.md`).
Utkana PLAN DEFECT popravka:

1. **`by-event`/`by-structure` NISU prazni foldere (KRITIČNO)** — plan je tvrdio "folderi su
   trenutno prazni" (Zadatak 1), ali oba foldera već sadrže 28 taksonomijskih skeleton fajlova
   (23 event + 5 structure, Faza A) BEZ IJEDNOG frontmatter polja (goli `# Naslov`, bez `---`
   bloka). Pošto `check_frontmatter`/`check_index_complete` u core-u rade BEZUSLOVNO nad svim
   stranicama pod `page_dirs`, prvi validator poziv posle restrukturiranja bi vratio `fail≈196`
   (168 F-FRONTMATTER + 28 F-INDEX-COMPLETE), ne `fail=0` kako je plan tvrdio kao Acceptance
   kriterijum — i, ozbiljnije, runner-ov deterministički gate bi mogao ostati TRAJNO crven kroz
   ceo sweep (nijedan pojedinačan batch prompt ne dotiče svih 28 taksonomijskih stranica odjednom).
   Popravka: Zadatak 1 sada uključuje backfill minimalnog validnog frontmatter-a na svih 28
   postojećih stranica + eksplicitno linkovanje svih u `wiki/index.md` (Zadatak 2), PRE nego što
   se bilo koji batch izvrši. Zadatak 1 Instruction/Gotchas i Zadatak 2 Gotchas ispravljeni da
   uklone netačnu "prazno" tvrdnju. Zadatak 5 Acceptance/Validation ispravljeni da `fail=0`
   očekivanje važi POSLE backfill koraka, ne na sirovom `git mv` rezultatu.
2. **`--delta` raw-backlog detekcija (informativno, VALIDATION GAP)** — dokumentovano kao poznato
   ograničenje u Risks: `compute_delta_sources` (`ingest_runner.py:1095`) pretpostavlja
   `raw/` POD `kb_root`, dok plan D2 namerno drži `raw/` na repo-root nivou — grana "nov raw bez
   wiki stranice" u delta detekciji neće okinuti za wyckoff. Nizak rizik (raw korpus je istorijska
   literatura, ne raste), ali implementator treba da zna unapred, ne da otkrije posle prvog
   "praznog" delta poziva koji izgleda kao "sve ažurno" a zapravo je strukturno tih.

## Summary

`research/expert-analyses/` (ekspertske Wyckoff analize grafikona — Faza A skela već postoji, wyckoff#89) treba da postane KONZUMENT poligonovog `scripts/ingest_runner.py` (auto batch ingest runner + FAIL/WARN validator gate + PR-tok), po dokazanom obrascu aerodrom ADR-KB (aerodrom#142/#144, E2E dokazano). Ovaj plan gradi KOD-infrastrukturu: `batches.md` skelet, domenski validator (`scripts/validate_expert_analyses.py`), i seam wrapper (`scripts/kb_ingest.py` + `config/kb_ingest.yaml`) sa PR-tokom. SKIL deo (puni promptovi B02+, wyckoff disciplina) je van obima ovog plana.

**Ključan arhitektonski nalaz (menja premisu iz naloga)**: `validate_kb_core.py` i sam `ingest_runner.py` **tvrdo pretpostavljaju** da `kb_root` sadrži doslovan `wiki/` poddirektorijum (`discover_pages`, `check_index_complete`, `check_index_descriptions` u core-u; `snapshot_wiki_pages`, `try_autofix_index_desc`, `try_autofix_local_links`, handoff log-tail u runneru — svi rade `kb_root / "wiki"` bez ijednog CorpusProfile parametra koji to preimenuje). Postojeća Faza A skela (`research/expert-analyses/{extracts,by-event,by-structure}/`) NEMA taj `wiki/` sloj — postavljena je pre nego što je runner-konzumacija bila u planu. Ovaj plan zato uključuje **restrukturiranje** (Zadatak 1) — pomeranje tri foldera pod `wiki/`, PLUS backfill minimalnog frontmatter-a na 28 postojećih `by-event`/`by-structure` skeleton stranica (pregled-plana nalaz — te stranice NISU prazne, samo nemaju frontmatter) — kao preduslov, ne kao opcionu kozmetiku.

Drugi ključan nalaz: core-ov `check_frontmatter` ima TVRDO KODIRANE `REQUIRED_FRONTMATTER`/`VALID_TYPES`/`VALID_STATUSES` (nisu `CorpusProfile` polja) — i `check_complete_coverage`/`check_dup_identity` pretpostavljaju **bijektivan** odnos raw-jedinica ↔ wiki-stranica (1 issue → 1 stranica, 1 skill → 1 stranica). Wyckoff-ov model je **N raw dokumenata → 0..M filtriranih extract kartica** (većina Fraser postova se odbacuje) — fundamentalno nebijektivan. Ova dva nalaza vode direktno na Odluke D3/D4/D5 ispod.

## User Story

```text
Kao agent koji izvršava sweep ekspertskog Wyckoff korpusa (book/crypto/Fraser)
želim da `research/expert-analyses/` bude pravi konzument poligonovog `ingest_runner.py`
da bih dobio: fresh-context batch po batch izvršenje, deterministički FAIL/WARN gate posle svakog batch-a,
i automatski PR-tok — umesto ručnog `prp-implement` task-resume bez gate-a.
```

## Problem Statement

Stari plan (`PRPs/plans/research-expert-analyses-index.plan.md`, Zadaci 3-8) predviđa RUČNI sweep preko `prp-implement`-a: task-resume, serije ≤20, stop na 50% konteksta — bez determinističkog gate-a posle svake serije i bez PR-toka. Poligon (mini-PRD `visekorpusni-validirani-ingest.mini-prd.md`, Faza 1/2/4 već `complete`) je u međuvremenu izgradio deljivo jezgro (`validate_kb_core.py`) + deklarativne kapije (`batches.md` kolona "Posebna kapija") + generalizovanu `--delta` detekciju — dokazano nad aerodrom ADR-KB (aerodrom#142/#144, E2E fail=0). Wyckoff treba da nasledi tu infrastrukturu umesto da ponavlja ručni tok, ALI postojeća Faza A skela nije rođena kompatibilna sa runner-ovim `wiki/`-pretpostavkama, niti sa core-ovim frontmatter šablonom — ovaj plan razrešava oba jaza.

## Solution Statement

1. **Restrukturiraj** `research/expert-analyses/` da doda `wiki/` sloj (Zadatak 1) — `extracts/`, `by-event/`, `by-structure/` sele se pod `wiki/`; `_progress.md`/`_gaps.md`/`EXTRACT_TEMPLATE.md` ostaju na kb-root nivou (kao `batches.md`/`README.md`/`run-log.md` u skills-kb uzorku); `raw/` OSTAJE na repo-root nivou (nije pod kb-root — namerna devijacija, D2). Zadatak 1 TAKOĐE backfill-uje minimalan frontmatter na 28 postojećih `by-event`/`by-structure` skeleton stranica (pregled-plana nalaz, vidi §Izmene od pregled-plana).
2. **Podeli sadržajni model** (Zadatak 2/3): `by-event/`+`by-structure/` postaju llm-wiki-šablonske stranice (title/description/type/status/updated/sources) — core-ove generičke provere (frontmatter/index/linkovi) rade nad njima BEZ IZMENE. `extracts/` OSTAJU domenske strukturirane kartice sa postojećim (Faza A) frontmatter šablonom — NE prolaze kroz core-ov `check_frontmatter` (isključene iz `page_dirs`); dobijaju SOPSTVENE domenske provere u wrapperu (10 obaveznih polja, `image_path` postojanje, ≤400 reči heuristika, by-event/by-structure parity — direktan port starog plana Validation #3/#5/#6/#7 u `Finding`-producing Python).
3. **Napiši `batches.md`** (Zadatak 4) — parse-kompatibilan skelet, 29 redova (B01-B29: 13 book + 3 crypto + 13 fraser), B01 = identičan opseg staroj seriji 3.1 (page_001-020, deljeni merni uzorak #92), pun prompt tekst za B01, TODO placeholder za B02-B29 (SKIL prolaz), semantic-lint marker na poslednjem batch-u svakog izvora.
4. **Napiši `scripts/validate_expert_analyses.py`** (Zadatak 5) — TANAK wrapper, ali NE `core.run_cli()` delegacija (kao skills-kb) zbog D3/D4 — sopstveni `collect_findings()` koji komponuje primenljive core provere + domenske ekstenzije, sopstveni CLI koji replicira `core.build_parser`/`run_cli` UGOVOR (identičan `--kb-root/--json/--skip-git` + JSON šema + exit semantika) da `--delta` mod i runner subprocess pozivi rade nepromenjeno. Izlaže modul-level `PROFILE` (runner-consumed ugovor #220).
5. **Napiši `scripts/kb_ingest.py` + `config/kb_ingest.yaml`** (Zadatak 6) — PO UZORU na aerodrom, plus PR-tok wrapper (grana + `gh pr create --body-file`) koji aerodrom exemplar NEMA (issue #219 nalaz 2).
6. **Dopiši napomenu** na vrh starog plana (Zadatak 7) — istorijski dokument, Zadaci 3-8 zamenjeni ovim planom.

## Metadata

| Polje | Vrednost |
|---|---|
| Feature type | `NEW_CAPABILITY` (runner-konzumacija) + `REFACTOR` (restrukturiranje Faza A skele) |
| Complexity | `HIGH` — dva tvrda strukturna jaza (wiki/ sloj, frontmatter šablon) otkrivena čitanjem core/runner koda, ne trivijalna kopija aerodrom obrasca |
| Affected systems | Novo: `research/expert-analyses/wiki/`, `scripts/validate_expert_analyses.py`, `scripts/kb_ingest.py`, `config/kb_ingest.yaml`. Pomereno (git mv): `research/expert-analyses/{extracts,by-event,by-structure}/` → `wiki/{...}`. Izmenjeno (frontmatter backfill): 28 postojećih `wiki/by-event/*.md` + `wiki/by-structure/*.md` fajlova. Nedirano: `raw/`, poligon repo (poziva se apsolutnom putanjom, ADR 0006). |
| Izvor inputa | Orkestrator brief ove sesije (poligon#221 grupa, presuda SIMPLIFY #219, mini-PRD Faza 3 `visekorpusni-validirani-ingest.mini-prd.md`) |
| Model preporuka | Sonnet (mehanički kod + parametrizacija po dokazanom obrascu — ne domenska sinteza) |
| Implementacija | Kod pod `scripts/`/`config/` + strukturne izmene `research/`; PR obavezan (CLAUDE.md §0.2 — infrastruktura, lagani review) |

## UX Design

```
PRE (stari plan, ručni tok):
  prp-implement research-expert-analyses-index.plan.md
    → task-resume kroz Zadatke 3.1...5.3, ručna serija ≤20, ručni stop na 50% konteksta
    → NEMA determinističkog gate-a posle serije (samo ljudska "Validation Commands" provera na kraju)
    → NEMA PR-a (CLAUDE.md §0.2: "čista dokumentacija, može direktno na main")

POSLE (ovaj plan, runner-konzumacija):
  uv run python scripts/kb_ingest.py --kb expert-analyses -- --max-batches 1
    → kb_ingest.py: subprocess poziv na poligon ingest_runner.py --kb-root research/expert-analyses
        --validator-script scripts/validate_expert_analyses.py
    → runner: pročita batches.md B01 (pending) → spawn agent (svež kontekst) sa B01 promptom
        → agent piše extracts/by-event/by-structure pod wiki/, ažurira _progress.md/_gaps.md, wiki/log.md dopis
    → runner: validate_expert_analyses.py --json (FAIL blokira complete)
    → runner: upiše SAMO polja napretka u batches.md (status/datum/wiki stranice/preostalo/log)
    → wrapper: grana wiki-ingest/<kb>-<batch>, gh pr create --body-file (#89 Wiki ingest research/expert-analyses B01)
    → operator: review + merge PR
```

| Lokacija | Pre | Posle | Vrednost |
|---|---|---|---|
| Izvršenje | ručni `prp-implement` resume | runner batch-po-batch, svež agent kontekst po batch-u | manje context-degradacije, konzistentan sa skills-kb/aerodrom iskustvom |
| Gate | ljudska provera na kraju svih zadataka | deterministički FAIL/WARN posle SVAKOG batch-a | rani stop na grešci, ne na kraju 29 batch-eva |
| PR-tok | nema (direktno na main) | grana + PR po batch-u | review pre merge-a, konzistentno sa CLAUDE.md §0.2 infrastruktura pravilom |

## Mandatory Reading

Implementacioni agent (TI, u sledećem pozivu) MORA pročitati pre rada:

- `PRPs/prds/visekorpusni-validirani-ingest.mini-prd.md` (poligon repo) — pun fazni kontekst, Decisions Log
- `~/projekti/poligon/scripts/validate_kb_core.py` — CEO fajl (posebno `CorpusProfile` L124-138, `discover_pages` L205-220 — hardkodovan `wiki/`, `check_frontmatter` L402-456 — hardkodovan REQUIRED_FRONTMATTER/VALID_TYPES/VALID_STATUSES, `check_dup_identity` L562-582, `check_complete_coverage` L603-626, `parse_batches` L289-357, `run_cli` L944-965)
- `~/projekti/poligon/scripts/ingest_runner.py` — posebno `extract_batch_prompt` L136-167, `update_batch_progress` L201-261, `snapshot_wiki_pages` L267-289 (hardkodovan `kb_root/wiki`), `extract_batch_gate`/`resolve_gate_type` L436-497, `_load_profile_from_validator_script` L806-848 (PROFILE ugovor + `sys.modules` gotcha), `try_autofix_index_desc`/`try_autofix_local_links` L883-960+ (takođe hardkoduju `wiki/`), `_append_run_log` L~395-416, `compute_delta_sources` L1052-1114 (`raw_dir = kb_root / "raw"` — NAPOMENA: pretpostavlja raw POD kb_root, wyckoff D2 devijacija čini "nov raw bez wiki stranice" granu neaktivnom, vidi Risks)
- `~/projekti/poligon/scripts/validate_skills_kb.py` — CEO fajl, uzorak za wrapper OBLIK (ali ne za `collect_findings` sadržaj — vidi D5)
- `~/projekti/poligon/knowledge/skills-kb/batches.md` — CEO fajl, tačan tabelarni/prompt format
- `~/projekti/aerodrom/scripts/kb_ingest.py` + `~/projekti/aerodrom/config/kb_ingest.yaml` — CEO oba fajla, seam obrazac (ADR 0006)
- `research/expert-analyses/EXTRACT_TEMPLATE.md`, `_progress.md` (ovaj repo) — postojeći domenski frontmatter šablon, NE MENJATI polja
- `research/expert-analyses/by-event/*.md`, `research/expert-analyses/by-structure/*.md` (ovaj repo) — SVIH 28 postojećih skeleton fajlova, PRE Zadatka 1 — potvrdi da nijedan trenutno nema frontmatter (pregled-plana nalaz, backfill je deo Zadatka 1)
- `PRPs/plans/research-expert-analyses-index.plan.md` — ceo fajl, posebno Notes (Batch protokol: serije ≤20, stop na 50%) — ta disciplina PRELAZI u batches.md B01 prompt tekst
- `runbooks/wyckoff-wiki-ingest.md:372` — PR title template `#<issue> Wiki ingest (source, scope)`
- `CLAUDE.md:1-60` (ovaj repo) — §0.1 srpski default, §0.2 code review tabela

## Patterns to Mirror

| Category | File:Lines | Pattern | Snippet/Napomena |
|---|---|---|---|
| WIKI HARDCODE (core) | `poligon/scripts/validate_kb_core.py:205-220` | `discover_pages` traži `kb_root/wiki/{page_dirs}` | `wiki = kb_root / "wiki"` — nema CorpusProfile parametra za preimenovanje |
| WIKI HARDCODE (runner) | `poligon/scripts/ingest_runner.py:267-289` | `snapshot_wiki_pages` broji "Wiki stranice" isključivo pod `kb_root/wiki` | ako `wiki/` ne postoji, vraća `{}` → batch uvek izgleda kao 0 stranica → W-BATCH-SUSPECT |
| FRONTMATTER HARDCODE | `poligon/scripts/validate_kb_core.py:68,69-78` | `REQUIRED_FRONTMATTER`/`VALID_TYPES`/`VALID_STATUSES` su MODUL-nivo konstante, ne CorpusProfile polja | extract šablon (`type: forward\|retrospective\|schematic`, `status: candidate\|validated\|eval-used`) se KOSI sa ovim enumima — extracts NE SME proći kroz `check_frontmatter` |
| COVERAGE BIJEKCIJA | `poligon/scripts/validate_kb_core.py:603-626` | `check_complete_coverage` očekuje content-page PO SVAKOJ batch jedinici | wyckoff: N raw → 0..M extract (filtrirano) — NE bijektivno; provera bi lažno FAIL-ovala svaki batch sa bar jednim odbačenim dokumentom |
| BEZUSLOVNA FRONTMATTER/INDEX PROVERA | `poligon/scripts/validate_kb_core.py:402-456,478-511` | `check_frontmatter`/`check_index_complete` rade nad SVIM stranicama pod `page_dirs`, ne samo nad batch-om koji ih je doneo | pregled-plana nalaz: 28 postojećih `by-event`/`by-structure` stranica BEZ frontmatter-a bi trajno FAIL-ovale gate dok se ručno ne backfill-uju (Zadatak 1) |
| TANAK WRAPPER (delimično uzor) | `poligon/scripts/validate_skills_kb.py:88-146` | `PROFILE = core.CorpusProfile(...)` + `core.run_cli(PROFILE, argv, ...)` u `main()` | wyckoff NE MOŽE kopirati `main()` 1:1 (D5) — CorpusProfile definicija DA, `run_cli` delegacija NE |
| PROFILE UGOVOR | `poligon/scripts/ingest_runner.py:806-848` | `_load_profile_from_validator_script` dinamički učitava modul, čita `PROFILE` | `sys.modules[spec.name] = module` MORA ići PRE `exec_module` (dataclass anotacije) |
| BATCHES.MD ŠEMA | `poligon/knowledge/skills-kb/batches.md:16-33` | kolone mapirane po imenu zaglavlja, "Jedinice" (ne "Issue-i"), CSV stem imena | `batch_column_prefix="jedinic"`, `identity_mode="stem"` — POTVRĐENO precedentno: skills-kb koristi identičan obrazac, runner-ova sopstvena `parse_batches` (uvezena iz `validate_issues_kb`) ostaje slepa za tu kolonu i bira sledeći batch samo po statusu — dokumentovano ponašanje, ne defekt |
| BATCHES.MD PROMPT | `poligon/knowledge/skills-kb/batches.md:58-62` | code-block prompt posle `### B01` | `extract_batch_prompt` (ingest_runner.py:136) čita code-block PRVO, inline drugo |
| SEAM WRAPPER | `aerodrom/scripts/kb_ingest.py:57-121` | subprocess poziv apsolutnom putanjom, env override, cwd tvrda provera | `AERODROM_INGEST_RUNNER` → `WYCKOFF_INGEST_RUNNER` |
| SEAM CONFIG | `aerodrom/config/kb_ingest.yaml:1-12` | `runner.putanja`/`runner.transport` + `kb.<key>.{kb_root,validator_script}` | dodati `kb.expert-analyses` unos |
| PR TITLE | `runbooks/wyckoff-wiki-ingest.md:372` | `#<issue> Wiki ingest (source, scope)` | npr. `#89 Wiki ingest (research/expert-analyses, B01 book page_001-020)` |
| RAW REGEX | (novi kod, D6) | jedan capture-grupa preko alternacije | `re.compile(r"raw/(?:book/pages\|crypto_archive/posts\|bruce_fraser/posts)/([^/]+)\.md")` |

## Files to Change

| Putanja | Akcija | Sadržaj |
|---|---|---|
| `research/expert-analyses/wiki/extracts/` | git mv (od `research/expert-analyses/extracts/`) | prazan folder, isti sadržaj (trenutno prazan) |
| `research/expert-analyses/wiki/by-event/` | git mv (od `research/expert-analyses/by-event/`) | 23 postojeća skeleton fajla, MOVE + frontmatter backfill (pregled-plana popravka) |
| `research/expert-analyses/wiki/by-structure/` | git mv (od `research/expert-analyses/by-structure/`) | 5 postojećih skeleton fajlova, MOVE + frontmatter backfill (pregled-plana popravka) |
| `research/expert-analyses/wiki/index.md` | create | master index (stari plan Zadatak 7 sadržaj, novi PATH pod `wiki/`), linkuje SVIH 28 backfill-ovanih stranica |
| `research/expert-analyses/wiki/log.md` | create | prazan seed (runner dopisuje ingest log unose, mirror `llm-wiki.md:155-165`) |
| `research/expert-analyses/batches.md` | create | 29-red skelet + B01 pun prompt + B02-B29 TODO placeholderi |
| `scripts/validate_expert_analyses.py` | create | domenski validator, `PROFILE` + sopstveni `collect_findings`/CLI |
| `scripts/kb_ingest.py` | create | seam wrapper + PR-tok (grana + `gh pr create`) |
| `config/kb_ingest.yaml` | create | `kb.expert-analyses: {kb_root, validator_script}` |
| `pyproject.toml` | edit | dodaj `pyyaml>=6.0` u `[project] dependencies` (nema ga trenutno — `kb_ingest.py` uvozi `yaml`) |
| `PRPs/plans/research-expert-analyses-index.plan.md` | edit (dopis na vrh) | napomena: "izvršenje Zadataka 3-8 zamenjeno runner batches.md arhitekturom, vidi wyckoff-onboarding-runner.plan.md"; Zadaci 3-8 NISU prepisani/brisani |

## NOT Building

- Sadržaj SVIH batch promptova B02-B29 (SKIL prolaz, van ovog plana) — samo TODO placeholder + strukturna validnost.
- Bilo kakva izmena poligon repoa (`~/projekti/poligon`) — apsolutna putanja poziv, ADR 0006, ne dira se.
- Stari `knowledge/wiki` korpus / `runbooks/wyckoff-wiki-ingest.md` — van obima (ostaje ručni, druga validaciona loza).
- Sam sweep (popunjavanje `extracts/`) — izvršenje batch-eva PO ovom planu, ne deo plana; ovaj plan gradi infrastrukturu.
- Test-sloj za `scripts/validate_expert_analyses.py`/`kb_ingest.py` (odluka D9 — obrazloženo u Testing Strategy).
- Migracija `raw/` pod `kb_root` (D2 — namerna devijacija, raw ostaje na repo-root nivou).
- `README.md` za `research/expert-analyses/` (odluka: EXTRACT_TEMPLATE.md + batches.md Protokol sekcija pokrivaju istu svrhu; izbegnuta duplikacija).
- Popunjavanje SADRŽAJA `by-event`/`by-structure` "Primeri" sekcija (pointeri na extracts) — backfill u Zadatku 1 dodaje SAMO frontmatter (title/description/type/status/updated/sources), ne sadržajne pointere; te popunjava B01+ sweep.

## Step-by-Step Tasks

### Zadatak 1 — Restrukturiraj Faza A skelu pod `wiki/` + backfill frontmatter na postojećim 28 taksonomijskim stranicama

- **Action:** `git mv` tri foldera pod novi `wiki/` poddirektorijum, ZATIM dodaj minimalan frontmatter na 28 postojećih `by-event`/`by-structure` fajlova
- **Files:** `research/expert-analyses/{extracts,by-event,by-structure}/` → `research/expert-analyses/wiki/{extracts,by-event,by-structure}/`; sve 23 `wiki/by-event/*.md` + 5 `wiki/by-structure/*.md` fajlova (edit, dodaj frontmatter)
- **Instruction:**
  1. `mkdir -p research/expert-analyses/wiki && git mv research/expert-analyses/extracts research/expert-analyses/wiki/extracts && git mv research/expert-analyses/by-event research/expert-analyses/wiki/by-event && git mv research/expert-analyses/by-structure research/expert-analyses/wiki/by-structure`. **NAPOMENA (pregled-plana ispravka)**: `extracts/` JESTE trenutno prazan folder (čist mv, nema sadržaja), ALI `by-event/` (23 fajla) i `by-structure/` (5 fajla) NISU prazni — sadrže postojeće taksonomijske skeleton stranice iz Faze A (goli `# Naslov`, bez frontmatter-a). `git mv` na ne-praznim folderima radi normalno (standardan `git mv`, nema potrebe za `.gitkeep` workaround-om — taj workaround ostaje relevantan SAMO za `extracts/` ako `git status` ne pokaže prazan folder posle mv-a).
  2. `EXTRACT_TEMPLATE.md`, `_progress.md`, `_gaps.md` OSTAJU na `research/expert-analyses/` nivou (ne pod `wiki/`) — mirror skills-kb gde `README.md`/`batches.md`/`run-log.md` sede pored `wiki/`, ne unutra.
  3. **Backfill frontmatter (nova pod-tačka, pregled-plana KRITIČNO nalaz)**: za SVIH 23 `wiki/by-event/*.md` + 5 `wiki/by-structure/*.md` fajlova, dodaj YAML frontmatter blok na vrh (PRE postojećeg `# Naslov` sadržaja, sadržaj ispod ostaje netaknut):
     ```yaml
     ---
     title: <Naslov iz H1, npr. "Spring">
     description: "Wyckoff <event|struktura> — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a."
     type: topic
     status: draft
     updated: 2026-07-09
     sources: []
     ---
     ```
     Ovo je MINIMALAN validan frontmatter (prolazi `check_frontmatter`: sve 6 obaveznih polja prisutna, `type: topic` ∈ `VALID_TYPES`, `status: draft` ∈ `VALID_STATUSES`, `updated` je validan YYYY-MM-DD, `description` neprazan). `sources: []` je legitimno prazna lista (nijedan raw fajl još nije ekstraktovan za ovu temu) — `check_sources_exist` prolazi trivijalno nad praznom listom.
  4. **Linkuj svih 28 backfill-ovanih stranica iz `wiki/index.md`** — vidi Zadatak 2 (nužno da `check_index_complete` ne FAIL-uje).
- **Pattern:** `poligon/knowledge/skills-kb/` layout (`batches.md`, `README.md`, `run-log.md` pored `wiki/`); minimalan `type: topic`/`status: draft` frontmatter mirror poligon konvencije za rane/nepotpune wiki stranice
- **Gotchas:** `.gitkeep` workaround relevantan SAMO za `extracts/` (jedini istinski prazan folder). `by-event`/`by-structure` mv radi normalno jer imaju sadržaj. Frontmatter backfill MORA prethoditi Zadatku 5 validaciji — bez njega, `fail=0` acceptance kriterijum je nedostižan (pregled-plana nalaz).
- **Validation:** `test -d research/expert-analyses/wiki/extracts && test -d research/expert-analyses/wiki/by-event && test -d research/expert-analyses/wiki/by-structure && ! test -d research/expert-analyses/extracts && for f in research/expert-analyses/wiki/by-event/*.md research/expert-analyses/wiki/by-structure/*.md; do head -1 "$f" | grep -q '^---$' || echo "MISSING FRONTMATTER: $f"; done` (poslednja linija ne sme ispisati ništa — svih 28 fajlova mora imati `---` kao prvi red)

### Zadatak 2 — `wiki/index.md` (master index, llm-wiki šablon)

- **Action:** create master index stranicu pod novom putanjom, linkuj SVE postojeće `by-event`/`by-structure` stranice
- **Files:** `research/expert-analyses/wiki/index.md`
- **Instruction:** Sadržaj = stari plan Zadatak 7 opis (corpus-count tabela iz `_progress.md`, navigacija ka `by-event/`, `by-structure/`, linkovi ka `../EXTRACT_TEMPLATE.md`, `../_gaps.md` — relativne putanje su sad JEDAN NIVO DUBLJE nego u starom planu jer je index pod `wiki/`). Pošto core-ov `check_index_complete`/`check_index_descriptions` OVU stranicu NE proverava (index.md je uvek isključen, `EXCLUDED_NAMES`), frontmatter za `index.md` samog sebe nije obavezan po core-u, ali dodaj ga za konzistentnost (title/description/type=`system`/status/updated/sources prazno ili sa referencom na `_progress.md`). Popuni ranim skeletom (tabela sa `Ukupno pregledano=0` po sva tri izvora, jer sweep još nije počeo) — B01+ izvršenje će ga ažurirati. **DODATNO (pregled-plana ispravka)**: eksplicitno linkuj svih 28 `by-event`/`by-structure` stranica (backfill-ovanih u Zadatku 1) — npr. sekcija "## Taksonomija (events)" sa 23 linka i "## Taksonomija (structures)" sa 5 linkova, svaki oblika `- [Naziv](by-event/naziv.md)`.
- **Pattern:** `poligon/knowledge/skills-kb/wiki/index.md` (struktura), stari plan Zadatak 7 (sadržajni ugovor)
- **Gotchas:** **(pregled-plana ispravka — uklonjena netačna tvrdnja)** `by-event`/`by-structure` folderi NISU prazni (28 postojećih skeleton stranica, Zadatak 1) — `check_index_complete` NE prolazi trivijalno, MORA imati eksplicitan link ka svih 28 stranica ili FAIL-uje za svaku nelinkovanu. Ovo je razlog za novu "Taksonomija" sekciju iznad.
- **Validation:** `test -f research/expert-analyses/wiki/index.md && for f in research/expert-analyses/wiki/by-event/*.md research/expert-analyses/wiki/by-structure/*.md; do rel="$(basename $(dirname $f))/$(basename $f)"; grep -q "$rel" research/expert-analyses/wiki/index.md || echo "NOT LINKED: $rel"; done` (ne sme ispisati ništa)

### Zadatak 3 — Domenski frontmatter split: potvrdi `EXTRACT_TEMPLATE.md` ostaje netaknut, dokumentuj by-event/by-structure šablon

- **Action:** ne menjati `EXTRACT_TEMPLATE.md` (Faza A, zaštićen); dodati kratku napomenu u `wiki/index.md` ili `README`-ekvivalent koja eksplicira DVA frontmatter režima
- **Files:** `research/expert-analyses/wiki/index.md` (dopuna), NEMA izmene `EXTRACT_TEMPLATE.md`
- **Instruction:** U `wiki/index.md` dodaj sekciju "## Dva frontmatter režima" koja objašnjava: (1) `wiki/extracts/*.md` — domenska struktura (source/page|post_url/asset/timeframe/wyckoff_event/structure/phase/image_path/type/status po `EXTRACT_TEMPLATE.md`), validira ih `validate_expert_analyses.py` DOMENSKIM proverama, NE core `check_frontmatter`; (2) `wiki/by-event/*.md` i `wiki/by-structure/*.md` — llm-wiki šablon (title/description/type∈{topic,system,...}/status∈{draft,active,needs-review}/updated/sources), validira ih core `check_frontmatter` NEPROMENJEN — trenutno svih 28 nosi minimalan `type: topic`/`status: draft` backfill (Zadatak 1); B01+ sweep dopunjava `sources`/`description`/`status` kako pointeri pristižu. Ovo je dokumentacija ARHITEKTONSKE odluke D3 za budućeg čitaoca (Zadatak 5 je implementacija).
- **Pattern:** ovaj plan §Solution Statement tačka 2
- **Gotchas:** ne menjati postojeći `EXTRACT_TEMPLATE.md` frontmatter (Faza A, ne diraj bez razloga — razlog bi bio SAMO ako bi trebalo da extract prođe kroz core check_frontmatter, a odluka D3 je suprotna)
- **Validation:** `grep -q "Dva frontmatter režima" research/expert-analyses/wiki/index.md`

### Zadatak 4 — `research/expert-analyses/batches.md`

- **Action:** create parse-kompatibilan batch raspored
- **Files:** `research/expert-analyses/batches.md`
- **Instruction:**
  - Kopiraj strukturu iz `poligon/knowledge/skills-kb/batches.md` §Protokol + §Šema rasporeda (adaptiraj brojeve tačaka za wyckoff — runner je i dalje "izvršni pisac polja napretka", metod/ovaj-plan autoriše strukturu).
  - Tabela "Raspored": kolone `Batch | Izvor | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log`.
  - **Book** (248 strana, `raw/book/pages/page_NNN.md`): B01-B13, serije od 20 (12×20=240 + poslednja B13=8). **B01 = `page_001-020` MORA ostati identičan opseg** kao stari Zadatak 3.1 (deljeni merni uzorak za wyckoff#92) — ne pomerati granicu.
  - **Crypto** (46 postova, `raw/crypto_archive/posts/*.md`, slug imena npr. `wyckoff-crypto-report-53.md`): B14-B16, 3 serije (~16 svaka). Pošto imena NISU sekvencijalna po broju, "Jedinice" ćelija za B02+ (crypto/fraser) je OPISNA ("crypto serija 2/3 — sledećih ~16 po `_progress.md last_reviewed` redosledu"), ne CSV lista stema — resume ide preko ledgera, ne preko batches.md.
  - **Fraser** (243 posta, `raw/bruce_fraser/posts/*.md`, slug imena): B17-B29, 13 serija od 20 (12×20=240 + poslednja B29=3, mirror stari 5.3 "poslednja 3").
  - Status kolona: `pending` za svih 29 redova (sweep još nije počeo).
  - "Posebna kapija" kolona: `semantic-lint` marker na B13 (poslednji book batch), B16 (poslednji crypto), B29 (poslednji fraser + korpus-DoD) — po analogiji skills-kb B09 "završni batch; zatim semantic-lint". Ostali redovi: `standardna`.
  - **Copy/paste prompt za B01 — PUN TEKST** (ne placeholder): mora instruisati agenta da (a) pročita `research/expert-analyses/EXTRACT_TEMPLATE.md`, `_progress.md`, `wiki/index.md`, poslednjih 50 linija `wiki/log.md`, `CLAUDE.md` §5/§7 pre pisanja; (b) obradi TAČNO `raw/book/pages/page_001.md` do `page_020.md`; (c) primeni kriterijume validnog para iz starog plana Zadatak 3 (postoji grafikon/referenca preko `raw/book/image_manifest.json` + konkretna Wyckoff interpretacija, ne gola definicija); (d) piše extract kartice u `research/expert-analyses/wiki/extracts/book_*.md` po `EXTRACT_TEMPLATE.md` (verbatim citat, `status: candidate`); (e) dopuni odgovarajuće `wiki/by-event/*.md`/`wiki/by-structure/*.md` pointerima U POSTOJEĆE (backfill-ovane, Zadatak 1) stranice — ažurira `description`/`sources`/`status` polja tih stranica kako pointeri pristižu, NE kreira nove; (f) ažurira `_progress.md` red `book` (`reviewed`, `valid`, `rejected`, `last_reviewed`); (g) dopiše `wiki/log.md`; (h) **Batch protokol iz starog plana Notes**: serija ≤20 je već ceo batch (nema dalje deljenje), ali ako proceni ≥50% konteksta pre završetka svih 20, stani i ostavi `_progress.md last_reviewed` na poslednjoj završenoj stranici (partial resume); (i) NE piše u `batches.md` (runner piše napredak).
  - Copy/paste prompt za B02-B29: kratak TODO blok — `"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."` — u `### Bxx` code-block obliku (parser ga i dalje čita kao validan prompt string, samo semantički nekompletan).
- **Pattern:** `poligon/knowledge/skills-kb/batches.md:1-110` (ceo fajl, format)
- **Gotchas:** `parse_batches` (core) traži zaglavlje koje SADRŽI `profile.batch_column_prefix` ("jedinic") — kolona MORA se zvati nešto što počinje na "Jedinic" (npr. "Jedinice"), ne "Izvor" kao primarno ime (može biti dodatna "Izvor" kolona ODVOJENO, core je ignoriše jer nije prepoznat prefiks — dozvoljeno, "dodatne kolone... parse_batches ih ignoriše"). Svaka `### Bxx` sekcija MORA postojati za svaki red u tabeli (strukturna parse-validnost) — čak i za TODO placeholdere. Runner-ova SOPSTVENA `parse_batches` (uvezena iz `validate_issues_kb`, koristi se za izbor sledećeg batch-a) ostaje slepa za "Jedinice" kolonu i bira samo po statusu — precedentno ponašanje (skills-kb isti obrazac), nije problem.
- **Validation:** ```cd research/expert-analyses && python3 -c "
import sys; sys.path.insert(0, '../../scripts')
sys.path.insert(0, '$(cd ../../ && pwd)/../poligon/scripts')  # prilagodi apsolutnoj putanji
"``` (praktično: pokreni Zadatak 5 validator sa `--json` i proveri da `parse_batches`-ekvivalent vrati 29 batch-eva bez greške — vidi Validation Commands blok dole)

### Zadatak 5 — `scripts/validate_expert_analyses.py`

- **Action:** create domenski validator (core-parametrizovan, ALI sopstvena `collect_findings`/CLI — vidi D5)
- **Files:** `scripts/validate_expert_analyses.py`
- **Instruction:**
  1. `sys.path.insert(0, ...)` na apsolutnu putanju `~/projekti/poligon/scripts` (isti obrazac kao `ingest_runner.py:69`, ALI kroz apsolutnu putanju jer je poligon DRUGI repo — ne `Path(__file__).parent`; koristi env override `POLIGON_SCRIPTS_DIR` sa default `~/projekti/poligon/scripts` da ostane premestivo). `import validate_kb_core as core`.
  2. Definiši `Batch` dataclass (mirror `validate_skills_kb.py:72-85`), `_make_batch` factory.
  3. Definiši `PAGE_DIRS = ("by-event", "by-structure")`, `RAW_UNIT_RE = re.compile(r"raw/(?:book/pages|crypto_archive/posts|bruce_fraser/posts)/([^/]+)\.md")` — JEDNA capture grupa preko alternacije (D6, potvrđeno da core koristi `m.group(1)` — regex SA tri odvojene grupe bi pukao).
  4. `PROFILE = core.CorpusProfile(name="expert-analyses", unit_word="event", page_dirs=PAGE_DIRS, content_dir="by-event", raw_unit_re=RAW_UNIT_RE, file_unit_re=None, identity_key="unit", identity_mode="stem", batch_column_prefix="jedinic", make_batch=_make_batch, batch_units=lambda b: b.units)`. Modul-level, runner-consumed ugovor (#220) — NE preskočiti.
  5. **`collect_findings(kb_root, repo_root, skip_git)`** — SOPSTVENA implementacija (NE `core.collect_findings`), komponuje:
     - `core.check_sources_exist(pages, repo_root)`
     - `core.check_frontmatter(pages)` — radi SAMO nad učitanim `pages` = by-event/by-structure/index (extracts nikad ne uđu u `pages` jer nisu u `page_dirs`); posle Zadatka 1 backfill-a, svih 28 postojećih stranica ima minimalan validan frontmatter, pa ova provera vraća `fail=0` na praznoj skeli (pregled-plana popravka)
     - `core.check_local_links(pages)`
     - `core.check_index_complete(pages, kb_root)` — posle Zadatka 2 (linkovanje svih 28), vraća `fail=0`
     - `core.check_index_descriptions(pages, kb_root)`
     - `core.check_dup_identity(pages, PROFILE)` — inertno/bezopasno zadržati (event-imena su prirodno jedinstvena po fajlu)
     - `core.check_batch_status(batches)`
     - **NE `core.check_complete_coverage`** (D4 — bijekcija ne važi za wyckoff; eksplicitno IZOSTAVITI uz komentar zašto)
     - `check_raw_integrity_multi(repo_root, skip_git)` — NOVA funkcija, poziva `core.check_raw_integrity` TRI PUTA (jednom po `repo_root / "raw/book"`, `raw/crypto_archive`, `raw/bruce_fraser` — NE `kb_root/raw` jer ne postoji, D2), agregira `Finding` liste; napravi malu wrapper-funkciju koja privremeno konstruiše lažni "kb_root" = `repo_root / f"raw/{sub}"`.parent za svaki poziv ILI direktno reimplementiraj 15-linijsku `git status --porcelain -- <path>` proveru lokalno (jednostavnije — ne forsirati reuse gde signatura ne odgovara)
     - `core.check_orphans(pages)`, `core.check_dup_title(pages)`, `core.check_anchors(pages)`, `core.check_wiki_gap(pages)`, `core.check_batch_suspect(batches)`, `core.check_stale_reingest(pages, repo_root, PROFILE)`
     - **Domenske ekstenzije (NOVE funkcije, portuju stari plan Validation #3/#5/#6/#7 u `Finding` oblik):**
       - `check_extract_frontmatter(extract_paths)` — FAIL po nedostajućem od 10 obaveznih ključeva (`source, asset, timeframe, wyckoff_event, structure, phase, image_path, type, status` + either/or `page`/`post_url`); `status` mora biti `candidate|validated|eval-used`; `type` mora biti `forward|retrospective|schematic` (SVOJI enumi, ne core-ovi)
       - `check_extract_image_path(extract_paths, repo_root)` — FAIL ako `image_path` nije `(remote...)`/`bez slike`/prazno i fajl ne postoji
       - `check_extract_not_full_copy(extract_paths)` — WARN ako extract > 400 reči (heuristika kopije celog dokumenta)
       - `check_extract_parity(extract_paths, by_event_dir, by_structure_dir)` — WARN ako extract fajl nije referenciran ni u jednom `by-event/*.md`
       - `check_progress_ledger_sane(kb_root)` — FAIL ako `_progress.md` nedostaje red za `book/crypto/fraser`, ili `reviewed > total_files`, ili kolone nisu non-negativni brojevi (STRUKTURNA sanost, NE potpuna pokrivenost — ta ostaje ručna/LLM procena kao u starom planu Validation #10, van dosega determinističkog gate-a)
  6. **CLI** — `build_parser`-ekvivalent (reuse `core.build_parser(default_kb_root=Path("research/expert-analyses"), description=..., require_kb_root=False)` DIREKTNO — ovaj deo NEMA D3/D4 sukob, samo `--kb-root/--json/--skip-git/--version` flagovi), `main()` poziva SOPSTVENI `collect_findings` pa `core.format_report`/`core.format_json` (reuse — nema profile-zavisnosti) + identičnu exit semantiku (`1` ako bar jedan FAIL/`ValidationError`/`OSError`, inače `0`).
  7. Eksplicitan komentar na vrhu modula (docstring) koji objašnjava D3/D4/D5 devijaciju od `validate_skills_kb.py` obrasca — sledeći čitalac NE SME misliti da je ovo nemarna divergencija.
- **Pattern:** `poligon/scripts/validate_skills_kb.py` (OBLIK wrappera — CorpusProfile definicija, re-exports gde primenjivo), `poligon/scripts/validate_kb_core.py:854-877` (`collect_findings` KAO REFERENCA ZA KOJE funkcije postoje, ne za copy-paste poziva)
- **Gotchas:**
  - `sys.modules[spec.name] = module` PRE `exec_module` (dinamički loader gotcha, `tests/test_validate_skills_kb.py:19` u poligonu, `ingest_runner.py:830-834`) — relevantno AKO se piše bilo kakav loader/test za ovaj modul; sam wrapper `main()` nema ovaj problem (statičan `import`), samo `_load_profile_from_validator_script` u runneru (koji već postoji, nema izmene) i eventualni test bi ga imali.
  - `raw_unit_re` MORA imati TAČNO jednu capture grupu (core radi `m.group(1)` bez provere broja grupa) — validiraj sa `python3 -c "import re; m = re.compile(r'...').search('raw/book/pages/page_001.md'); print(m.group(1))"` pre commit-a.
  - `check_index_complete`/`check_frontmatter` primenjuju se SAMO na `pages` iz `load_pages(kb_root, PROFILE)` — pošto `extracts` NIJE u `PAGE_DIRS`, `core.load_pages` ih nikad ne učitava; ne pokušavati ih "provući" kroz `page_dirs` jer bi to pokrenulo pogrešan frontmatter enum sudar (D3).
  - **(pregled-plana ispravka)** Bez Zadatka 1 frontmatter backfill-a, `check_frontmatter`/`check_index_complete` FAIL-uju za svih 28 postojećih `by-event`/`by-structure` stranica — "prazna skela fail=0" acceptance kriterijum je nedostižan bez tog koraka.
- **Testing:** Proveri da li wyckoff-ai ima pytest konvenciju za jednokratne `scripts/*.py` alatke — `tests/` sadrži testove za MCP servere/eval harness (`test_mcp_config.py`, `test_eval_orchestrator.py`...), ali NE za `scripts/extract_book_pdf.py`, `scripts/scrape_crypto_archive.py`, `scripts/download_fraser_images.py` (utility/one-off skripte bez testova, potvrđeno `ls scripts/` vs `ls tests/`). **Odluka: NE pisati novi test fajl** — `validate_expert_analyses.py`/`kb_ingest.py` su iste prirode (jednokratne ingest-alatke, ne runtime servisi), i njihov STVARNI test JESTE runner E2E gate (B01 fail=0 je funkcionalni dokaz) — dodavanje pytest sloja bi bio novi presedan bez postojećeg konvencijskog oslonca u ovom repou. Ako implementator kasnije proceni drugačije, dokumentovati zašto u istom PR-u.
- **Validation:** `cd ~/projekti/wyckoff-ai && uv run python scripts/validate_expert_analyses.py --kb-root research/expert-analyses --json --skip-git` (mora vratiti validan JSON, `summary.fail == 0` na skeli POSLE Zadatka 1 backfill-a i Zadatka 2 linkovanja — nema extract fajlova još, i svih 28 `by-event`/`by-structure` stranica imaju minimalan frontmatter + index link, tako da provere prolaze; `parse_batches` mora vratiti 29 batch-eva)

### Zadatak 6 — `scripts/kb_ingest.py` + `config/kb_ingest.yaml` (seam + PR-tok)

- **Action:** create seam wrapper sa grana+PR korakom
- **Files:** `scripts/kb_ingest.py`, `config/kb_ingest.yaml`, edit `pyproject.toml` (dodaj `pyyaml`)
- **Instruction:**
  - `config/kb_ingest.yaml`: mirror aerodrom oblik — `runner: {putanja: /Users/ssmiljanic/projekti/poligon/scripts/ingest_runner.py, transport: subprocess}`, `kb: {expert-analyses: {kb_root: research/expert-analyses, validator_script: scripts/validate_expert_analyses.py}}`.
  - `scripts/kb_ingest.py`: kopiraj aerodrom `kb_ingest.py` skeleton (`ucitaj_konfig`, `razresi_runner` sa env `WYCKOFF_INGEST_RUNNER`, cwd tvrda provera, `parse_args` sa `--kb` default `expert-analyses`, subprocess poziv na runner sa `--kb-root`/`--validator-script`).
  - **Dodaj PR-tok KOJI AERODROM NEMA** (issue #219 nalaz 2 — "PR-tok = wrapper oko poziva, ne izmena runnera"): PRE subprocess poziva runneru, napravi/pređi na granu `wiki-ingest/<kb>-<batch-id-ili-timestamp>` (npr. `wiki-ingest/expert-analyses-B01` ili `wiki-ingest/expert-analyses-20260709T1200` ako batch-id nije unapred poznat pri pozivu — runner sam bira sledeći pending batch, pa ime grane MOŽE biti timestamp-baziran umesto batch-ID-baziran ako se batch saznaje tek POSLE poziva). POSLE uspešnog runner poziva (`returncode == 0` — runner exit 0 znači bar jedan batch je uspešno prošao gate; runner exit != 0 ILI "nema više pending batch-eva" NE sme otvoriti PR), commit-uj promene (`git add research/ && git commit`), `git push -u origin <grana>`, `gh pr create --title "#<issue> Wiki ingest (research/expert-analyses, <batch-opis>)" --body-file <temp-fajl>` — **NIKAD inline multi-line string** (poznata zamka, poligon sesija istog dana).
  - **PR-tok issue broj — OTVORENO PITANJE (vidi Notes)**: koristi `#89` (najbliži postojeći otvoreni wyckoff issue koji upravlja `research/expert-analyses/` deliverable-om) kao DEFAULT u title template-u, ALI flaguj u kodu (komentar) i u ovom planu da orkestrator/operator treba da potvrdi da li #89 ostaje referentni issue za SVE B01-B29 PR-ove, ili treba nov dedikovan wyckoff-strani issue ("Faza 3 runner-konzumacija") — nijedan postojeći wyckoff issue (#89, #90, #92, #93) nije doslovno "runner onboarding", #89 je najbliži (isti deliverable, corpus index).
  - `pyproject.toml`: dodaj `"pyyaml>=6.0"` u `[project] dependencies` (potvrđeno da NE postoji trenutno — `grep -ri yaml pyproject.toml` prazan rezultat). Pokreni `uv add pyyaml` (per CLAUDE.md globalno pravilo — koristi `uv`, ne `pip`) da ažurira `uv.lock`.
  - `mkdir -p config` (folder trenutno ne postoji u repou).
- **Pattern:** `aerodrom/scripts/kb_ingest.py:1-125` (CEO fajl, oblik), `aerodrom/config/kb_ingest.yaml:1-12`
- **Gotchas:**
  - `gh pr create --body-file` NIKAD inline `--body "multi\nline"` — koristi privremeni fajl (`tempfile.NamedTemporaryFile` ili scratch putanja) pa `-F <fajl>`.
  - Runner sam bira SLEDEĆI pending/partial batch (`select_next_batch`) — wrapper ne zna UNAPRED koji batch-ID će biti obrađen dok runner ne završi; ime grane/PR naslova mora se izvesti IZ `batches.md` STANJA POSLE poziva (pročitaj koji red je upravo prešao u `complete`/`partial` — diff pre/posle poziva, ili parsiraj runner-ov stdout ako loguje batch-ID).
  - Ako runner obradi VIŠE batch-eva u jednom pozivu (bez `--max-batches 1`), PR treba da pokrije SVE obrađene batch-eve u tom pozivu — title/body treba da nabroji opseg, ne samo prvi.
  - Tvrda cwd provera (kao aerodrom) — pokretati SAMO iz korena wyckoff-ai repoa.
- **Validation:** `cd ~/projekti/wyckoff-ai && uv run python scripts/kb_ingest.py --kb expert-analyses -- --dry-run --skip-git` (mora ispisati tačnu runner komandu bez greške; `--dry-run` POSTOJI kao runner flag — potvrđeno `ingest_runner.py:1328-1332`)

### Zadatak 7 — Napomena na stari plan (istorijski dokument)

- **Action:** dopiši kratku napomenu na VRH postojećeg fajla, BEZ prepisivanja Zadataka 3-8
- **Files:** `PRPs/plans/research-expert-analyses-index.plan.md`
- **Instruction:** Dodaj novu sekciju "## Napomena (2026-07-09) — izvršenje zamenjeno" ODMAH POSLE naslova (pre postojeće "## Izmene od pregled-plana" sekcije): "Izvršenje Zadataka 3-8 (sweep preko `prp-implement`-a) ZAMENJENO je runner batches.md arhitekturom — vidi `PRPs/plans/wyckoff-onboarding-runner.plan.md`. Zadaci 0-2 (skela) ostaju DONE i tačni. Zadaci 3-8 OSTAJU ovde kao istorijski dokument discipline (Batch protokol: serije ≤20, stop na 50% konteksta — ta disciplina je prenesena u novi plan's B01 prompt tekst), ali se više NE IZVRŠAVAJU preko `prp-implement`-a." NE menjati/brisati Zadatke 3-8 — samo dopis na vrhu.
- **Pattern:** N/A (dokumentaciona konvencija, nema koda)
- **Gotchas:** ne diraj postojeći sadržaj ispod dopisa — plan ostaje čitljiv istorijski trag
- **Validation:** `grep -q "izvršenje zamenjeno" PRPs/plans/research-expert-analyses-index.plan.md`

## Testing Strategy

Nema unit-testova (odluka D9, Zadatak 5 Testing napomena — konzistentno sa postojećom `scripts/` konvencijom ovog repoa gde jednokratne ingest-alatke nemaju pytest sloj). Validacija je STRUKTURNA + E2E:

- **Strukturna** (Zadaci 1-6 Validation Commands, izvršiti REDOM posle svakog zadatka)
- **E2E (posle svih zadataka, PRE PR-a za samo B01 sadržaj)**: `uv run python scripts/kb_ingest.py --kb expert-analyses -- --max-batches 1` nad PRAVIM B01 promptom (book page_001-020) — ovo je STVARNO izvršenje prvog batch-a, van dosega ovog plana (batch-izvršenje samo, ne infrastruktura), ALI je jedini pravi dokaz da infrastruktura radi. Mini-PRD Faza 3 success signal: "B01 novog KB-a prolazi runner E2E — validator fail=0, PR otvoren wrapper-om" — OVO je acceptance kriterijum SLEDEĆEG poziva (implementacija ovog plana), ne ovog plan-pisanja poziva.
- **Domenski spot-check**: posle B01 E2E, ručno pregledati 3-5 extract kartica (isti obrazac kao stari plan Testing Strategy).

## Validation Commands

```bash
cd /Users/ssmiljanic/projekti/wyckoff-ai

# 1. Restrukturiranje + frontmatter backfill (Zadatak 1)
test -d research/expert-analyses/wiki/extracts
test -d research/expert-analyses/wiki/by-event
test -d research/expert-analyses/wiki/by-structure
! test -d research/expert-analyses/extracts
test -f research/expert-analyses/EXTRACT_TEMPLATE.md   # ostaje na kb-root nivou
test -f research/expert-analyses/_progress.md           # ostaje na kb-root nivou
for f in research/expert-analyses/wiki/by-event/*.md research/expert-analyses/wiki/by-structure/*.md; do
  head -1 "$f" | grep -q '^---$' || { echo "MISSING FRONTMATTER: $f"; exit 1; }
done

# 2. wiki/index.md (Zadatak 2/3) — svih 28 postojećih stranica linkovane
test -f research/expert-analyses/wiki/index.md
grep -q "Dva frontmatter režima" research/expert-analyses/wiki/index.md
for f in research/expert-analyses/wiki/by-event/*.md research/expert-analyses/wiki/by-structure/*.md; do
  rel="$(basename $(dirname $f))/$(basename $f)"
  grep -q "$rel" research/expert-analyses/wiki/index.md || { echo "NOT LINKED: $rel"; exit 1; }
done

# 3. batches.md strukturna validnost (Zadatak 4) — 29 batch-eva, B01 pun prompt
grep -c '^| B[0-9]' research/expert-analyses/batches.md   # očekuje 29
grep -q '^### B01' research/expert-analyses/batches.md
grep -A3 '^### B01' research/expert-analyses/batches.md | grep -q '```'  # code-block prompt

# 4. Validator (Zadatak 5) — PROFILE ugovor + regex + skela (posle backfill/linkovanja) FAIL=0
uv run python scripts/validate_expert_analyses.py --kb-root research/expert-analyses --json --skip-git
python3 -c "
import sys
sys.path.insert(0, 'scripts')
import validate_expert_analyses as v
assert v.PROFILE is not None
m = v.RAW_UNIT_RE.search('raw/book/pages/page_001.md')
assert m and m.group(1) == 'page_001', m
m2 = v.RAW_UNIT_RE.search('raw/crypto_archive/posts/wyckoff-crypto-report-53.md')
assert m2 and m2.group(1) == 'wyckoff-crypto-report-53', m2
print('OK raw_unit_re')
"

# 5. Runner --delta profile loading (PROFILE ugovor iz runner strane)
POLIGON=~/projekti/poligon
uv run python "$POLIGON/scripts/ingest_runner.py" \
  --kb-root research/expert-analyses \
  --validator-script scripts/validate_expert_analyses.py \
  --delta --dry-run --skip-git 2>&1 | head -20   # ne sme pući na "ne izlaže PROFILE"

# 6. Seam wrapper (Zadatak 6)
test -f config/kb_ingest.yaml
grep -q "expert-analyses" config/kb_ingest.yaml
grep -q "pyyaml" pyproject.toml
uv run python scripts/kb_ingest.py --kb expert-analyses -- --skip-git --max-batches 0 2>&1 | head -5

# 7. Stari plan napomena (Zadatak 7)
grep -q "izvršenje zamenjeno" PRPs/plans/research-expert-analyses-index.plan.md
grep -q "Zadaci 3-8" PRPs/plans/research-expert-analyses-index.plan.md
```

## Acceptance Criteria

- [ ] `research/expert-analyses/wiki/{extracts,by-event,by-structure}/` postoje; stari putanje bez `wiki/` prefiksa NE postoje
- [ ] Svih 23 `wiki/by-event/*.md` + 5 `wiki/by-structure/*.md` postojećih stranica ima minimalan validan frontmatter (`title/description/type/status/updated/sources`) — backfill, ne novi sadržaj (pregled-plana popravka)
- [ ] `research/expert-analyses/wiki/index.md` postoji sa objašnjenjem dva frontmatter režima I eksplicitno linkuje svih 28 postojećih `by-event`/`by-structure` stranica
- [ ] `research/expert-analyses/batches.md` ima TAČNO 29 redova (B01-B29), parse-validan (`parse_batches` iz core-a ne baca grešku, vraća 29 batch objekata)
- [ ] B01 red pokriva `page_001-020` book (identičan opseg starom Zadatku 3.1) i ima PUN copy/paste prompt tekst (ne placeholder)
- [ ] B02-B29 imaju strukturno validne `### Bxx` sekcije (TODO placeholder dozvoljen)
- [ ] Poslednji batch svakog izvora (B13/B16/B29) ima `semantic-lint` marker u koloni "Posebna kapija"
- [ ] `scripts/validate_expert_analyses.py` izlaže modul-level `PROFILE: CorpusProfile` (runner-consumed ugovor #220)
- [ ] `RAW_UNIT_RE` ima tačno jednu capture grupu i pokriva sva tri raw podstabla
- [ ] **Validator POSLE Zadatka 1 backfill-a i Zadatka 2 linkovanja vraća `fail=0`** (ispravljen kriterijum — ranije tvrđeno za "praznu skelu" pre backfill-a, što je bilo nedostižno; pregled-plana popravka)
- [ ] `check_complete_coverage` NIJE pozvana u wrapperovom `collect_findings` (namerna devijacija D4, dokumentovana u docstring-u)
- [ ] `scripts/kb_ingest.py` + `config/kb_ingest.yaml` postoje, `--kb expert-analyses` razrešava ispravan `kb_root`/`validator_script`
- [ ] `kb_ingest.py` sadrži grana+PR korak (ne samo subprocess poziv kao aerodrom) sa `gh pr create --body-file` (ne inline string)
- [ ] `pyproject.toml` sadrži `pyyaml` zavisnost, `uv.lock` ažuriran
- [ ] Stari plan `research-expert-analyses-index.plan.md` ima dopis-napomenu na vrhu, Zadaci 3-8 netaknuti ispod
- [ ] Nijedan fajl u `~/projekti/poligon` nije izmenjen

## Completion Checklist

- [ ] Zadaci 1-7 izvršeni (Zadatak 1 uključuje frontmatter backfill)
- [ ] Svih 7 Validation Commands blokova prolazi
- [ ] Svi acceptance kriterijumi čekirani
- [ ] E2E B01 poziv (`kb_ingest.py --kb expert-analyses`) POKUŠAN bar jednom (uspeh nije obavezan za OVAJ plan da se smatra "implementiranim" — infrastruktura je isporuka; B01 fail=0 E2E je mini-PRD Faza 3 success signal, prati se odvojeno posle merge-a ovog plana)
- [ ] PR otvoren za OVAJ plan (infrastruktura, "lagani" review po CLAUDE.md §0.2 tabeli — "sirovi data scripts")
- [ ] Otvorena pitanja iz Notes preneta operatoru (PR-tok issue broj)

## Risks and Mitigations

| Rizik | Verovatnoća | Uticaj | Mitigacija |
|---|---|---|---|
| `wiki/` restrukturiranje previđa neko drugo mesto gde runner/core hardkoduje `kb_root/raw` ili slično van `wiki/` | Srednja | Visok | Pre implementacije, `grep -n "kb_root /" ~/projekti/poligon/scripts/*.py` — potvrditi da su SVA hardkodovanja mapirana (ovaj plan je mapirao `wiki`, `wiki/index.md`, `wiki/log.md`, `raw` — ali novi runner commit-ovi mogu dodati još) |
| `check_complete_coverage` izostavljanje sakriva STVARNU rupu (batch označen complete a extract-i nedostaju) | Srednja | Srednji | `check_progress_ledger_sane` + ručni spot-check (Testing Strategy) ostaju kao zamenska odbrana; ako se pokaže nedovoljno, razmotriti NOVU core funkciju `check_ledger_coverage(ledger, batches)` kao BUDUĆI core doprinos (van obima ovog plana) |
| `raw_unit_re` sa jednom deljenom capture grupom preko tri različita imenska obrasca (numerička book vs slug crypto/fraser) hvata pogrešan segment na graničnim slučajevima (npr. fajl sa `/` u imenu) | Niska | Nizak | Validation Command #4 eksplicitno testira sva tri obrasca pre commit-a |
| PR-tok issue broj (#89 default) je pogrešan izbor — operator kasnije odluči da treba nov issue | Visoka (otvoreno pitanje) | Nizak | Broj je konfigurabilan (template string), lako izmenjiv posle odluke; ne blokira infrastrukturu |
| `pyyaml` dodavanje kao nova zavisnost unosi rizik konflikta sa postojećim `mcp`/`anthropic` zavisnostima | Niska | Nizak | `uv add pyyaml` + `uv sync` proverava kompatibilnost automatski; PyYAML je stabilna, retko konfliktna biblioteka |
| Runner-ov `--dry-run`/`--max-batches` CLI flag ne postoji tačno pod tim imenom (pretpostavka iz konteksta, nije direktno pročitan CLI parser blok) | Srednja | Nizak | **Potvrđeno pregled-planom**: oba flaga postoje (`ingest_runner.py:1328-1332`). Nema dalje akcije. |
| **(pregled-plana, novo) `by-event`/`by-structure` NISU prazni — bez Zadatak 1 frontmatter backfill-a, validator gate trajno FAIL-uje** | Bila izvesna (KRITIČNO) | Visok | Rešeno u ovoj reviziji — Zadatak 1 sada uključuje backfill + Zadatak 2 linkovanje; Validation Command #1/#2/#4 to eksplicitno proveravaju |
| **(pregled-plana, novo) `--delta` raw-backlog grana neaktivna zbog D2 (raw izvan kb_root)** | Izvesna | Nizak | Dokumentovano ograničenje (vidi §Izmene od pregled-plana tačka 2); `W-STALE-REINGEST` polovina delta detekcije i dalje radi; raw korpus ne raste (istorijska literatura), nizak realan uticaj |

## Notes

- **Otvoreno pitanje (operator/orkestrator odluka potrebna)**: PR-tok issue broj. `#89` je najbliži postojeći otvoreni wyckoff issue (isti `research/expert-analyses/` deliverable), korišćen kao DEFAULT u `kb_ingest.py` PR title template-u. Alternativa: otvoriti nov dedikovan issue "Faza 3: runner-konzumacija za expert-analyses" pre prvog PR-a. Ne blokira implementaciju — lako izmenjiv posle odluke.
- **Zašto wrapper NE koristi `core.run_cli`/`core.collect_findings` (D5)**: `validate_skills_kb.py` (i `validate_issues_kb.py`) mogu jer njihov sadržajni model je BIJEKTIVAN (1 issue/skill = 1 wiki stranica) i frontmatter šablon je VEĆ llm-wiki-konformni (nema domenskog sukoba tipa/statusa). Wyckoff-ov `extracts/` model je namerno filtriran/nebijektivan (istraživačka kuracija, ne katalogizacija), i njegov frontmatter šablon (Faza A, `EXTRACT_TEMPLATE.md`) je namerno domenski specifičan (event/structure/phase/image_path polja koja core ne poznaje). Ovo NIJE gubitak reuse-a — core i dalje nosi SVU mehaniku koja se primenjuje (frontmatter/index/linkovi za by-event/by-structure, batch šema, stale-reingest, raw integritet obrazac) — samo se ne poziva kroz JEDAN monolitni `collect_findings()` poziv nego kroz eksplicitnu kompoziciju funkcija + domenske dopune. Buduci konzument sa ISTIM nebijektivnim modelom (npr. neki drugi "kuracioni" KB) bi mogao da nasledi ovaj wrapper OBLIK kao NOVI uzorak (van obima da se sada formalizuje kao "core v2").
- **Batch particija brojevi** (13 book + 3 crypto + 13 fraser = 29) su RAČUNSKA projekcija iz `total_files` (248/46/243) i serije ≤20 pravila — implementator MORA potvrditi tačan broj fajlova (`ls raw/book/pages | wc -l` itd.) pre pisanja `batches.md` u slučaju da se raw korpus promenio od pisanja ovog plana (2026-07-09, potvrđeno 248/46/243 i pregled-planom nezavisno re-potvrđeno istim brojevima).
- **Eksterni research**: nije potreban — ceo posao je interna parametrizacija postojeće poligon infrastrukture nad postojećim wyckoff podacima.
- **Sledeći korak**: implementacija ovim revidiranim planom (`prp-implement` ekvivalent, ili direktno sprovođenje Zadataka 1-7 redom).

---
Izvor: orkestrator brief (poligon#221 grupa, Faza 3, mini-PRD `visekorpusni-validirani-ingest.mini-prd.md`) | Generisano: 2026-07-09 | Revidirano `/pregled-plana`: 2026-07-09
