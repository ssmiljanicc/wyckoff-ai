# Spike #75 — chart_image isporuka i izolacija

**Datum:** 2026-06-21
**Metod:** dve faze. (1) **Zero-cost introspekcija** — capability-introspekcija instaliranih CLI-jeva + čitanje koda, bez ijednog model poziva (sekcije 1–5 i prva Odluka). (2) **Operator-odobreni `--confirm` canary pozivi** — naknadno izvršeni stvarni Claude i Codex pozivi koji su empirijski potvrdili capability i oborili Codex izolaciju (sekcija „Empirijski canary status"). Početna procena je tako bez troška; konačni verdikt se oslanja na nekoliko namerno odobrenih plaćenih poziva.
**Verzije:** `claude` 2.1.185, `codex-cli` 0.141.0 (runbook navodi 2.1.183 / 0.141.0 — Claude verzija je drift-ovala za patch).

> **Kontekst.** Trenutni harness (`scripts/eval/orchestrator.py::analyst_prompt`) isporučuje **anonimizovani `candles.json` kao inline tekst** i namerno NE isporučuje `chart.png`. Glavni argument runbook-a (faza-4-eval-orchestrator.md §85): *„`claude -p` (headless) nema flag za lokalni prilog slike; Codex ima `-i`."* Spike preispituje baš tu tvrdnju protiv stvarnih CLI-jeva.

---

## 1. Claude isporuka slike — postoji li headless put?

**Nalaz: kandidat postoji, ali nije dokazan.** Messages API podržava base64 image blok, dok aktuelna Claude Code SDK dokumentacija opisuje `--input-format stream-json` kao **text-only**. Zato se ne sme zaključiti da CLI propušta image blok samo zato što API koristi isti content-block oblik.

- `claude --help` nema `--image` flag → runbook-ova tvrdnja je **doslovno tačna** (nema flag-a za prilog fajla).
- `claude -p` podržava `--input-format stream-json` (potvrđeno u `--help`: choices `"text"`, `"stream-json"`). Međutim, dokumentovani CLI/SDK ugovor trenutno garantuje tekstualne user poruke, ne proizvoljne Messages API blokove.
- Messages API (potvrđeno kroz `claude-api` skill, sekcija Vision) prihvata `{"type":"image","source":{"type":"base64","media_type":"image/png","data":"<b64>"}}`. `chart.png` u case dir-u je realan PNG (`1200x600 RGBA`), trivijalno base64-kodiv.
- `--file <file_id:rel_path>` flag NIJE ovo — on download-uje *remote* resurse po `file_id`, ne lokalni prilog.

**Posledica za izolaciju (bitna):** slika ide **u prompt** (base64), isto kao `candles.json` danas. Model runtime **ne čita fajl sa diska** — harness ugrađuje bajtove. Zato `--tools ""` (gašenje Read-a) ostaje validno i izolaciona granica je **identična postojećoj** (in-prompt embedding), ne uvodi novi file-read.

**Zaostala nepoznanica (nije zero-cost dokaziva):** da li stream-json parser baš ove verzije (2.1.185), uprkos text-only dokumentovanom ugovoru, prihvata image blok i prosleđuje ga modelu — to zahteva 1 ograničen canary poziv. Ako parser odbije blok ili model ne vrati token sa slike, Claude CLI image put je za ovaj harness **NE**.

**Implementacioni trošak:** prelazak na image-input menja I/O ugovor Claude adaptera — `--input-format stream-json` + `--output-format stream-json` (umesto trenutnog text-stdin + `--output-format json`), pa se menja i parsiranje izlaza.

---

## 2. Codex isporuka slike — isto?

**Nalaz: DA, čisto i dokumentovano — `codex exec -i/--image <FILE>...`.**

- `codex exec --help` eksplicitno navodi: `-i, --image <FILE>...  Optional image(s) to attach to the initial prompt`.
- Runbook-ova tvrdnja „Codex ima `-i`" je **tačna**.

**Posledica za izolaciju (kritična razlika u odnosu na Claude):** `-i <path>` znači da **Codex runtime sam otvara eksplicitno priloženi fajl**. Dozvoljeni `chart.png` zato mora biti unutar case root-a. Izolacija se ne testira prosleđivanjem spoljne sentinel slike kroz `-i` — to bi bio nameran prilog, ne sandbox bekstvo. Umesto toga, sentinel ostaje nepriložen van case root-a, a Codex dobija eksplicitnu naredbu da pokuša da ga pročita svojim shell alatom. JSONL zapis mora pokazati neuspešan command događaj, a sentinel ne sme biti ni u tool output-u ni u finalnom odgovoru.

---

## 3. Izolacija (oba) — sentinel-canary proširen na image slučaj

| Provider | Mehanizam dostave | Novi file-read? | Izolacija zero-cost dokaziva? |
|---|---|---|---|
| **Claude** | eksperimentalni base64 image blok u stream-json promptu | **Ne** — ako parser prihvati blok, harness ugrađuje bajtove | **Delom** — `--tools ""` gasi Read; parser/image passthrough ostaje nepoznat (1 canary) |
| **Codex** | `-i <path>` za dozvoljenu sliku unutar case root-a | **Da**, ali samo za namerno priloženi fajl | **Ne** — odvojeni nepriloženi sentinel + zabeležen tool pokušaj moraju dokazati granicu |

Proširenje sentinel-canary testa za image slučaj:
- **Claude:** pošto nema novog read-a, postojeći canary (CLAUDE.md sentinel u snapshot-u + answer key van root-a) pokriva i image slučaj bez izmene — slika je samo još jedan in-prompt blok.
- **Codex:** dozvoljena OCR slika ide kroz `-i` iz case root-a. Odvojeni sentinel fajl ostaje van root-a i **ne prosleđuje se kroz `-i`**. Canary prolazi samo ako JSONL pokazuje da je obavezni pokušaj čitanja odbijen i sentinel nigde nije procureo.

---

## 4. Simetrija dostave — uvodi li sama razlika pristrasnost?

**Mehanizmi NISU isti:** Claude = in-prompt base64 blok (harness-kontrolisan, bez model file-read-a); Codex = file-path argument koji runtime otvara.

**Procena pristrasnosti:**
- **Modalitet je simetričan.** Oba modela na kraju dobijaju **istu sliku u kontekstu**. Za cilj benchmark-a (rangiranje modela na Wyckoff chart-vision analizi) sadržaj ulaza je identičan → razlika u *mehanizmu dostave* **ne uvodi pristrasnost sadržaja**. Ovo je suštinski drugačije od originalne text-vs-slika dileme (koja je mešala modalitete); ovde oba dobijaju sliku.
- **Asimetrija je u izolaciji i operativnom riziku, ne u ulazu modela.** Codex strana nosi dodatnu površinu (runtime file-read) koja se mora odvojeno obezbediti; Claude strana nasleđuje postojeću granicu. To je razlika u *dokazivosti bezbednosti*, ne u *fer poređenju modela*.

---

## 5. Symbol-leak zamka

`render_chart_image(..., title=...)` upisuje naslov u sliku. Putevi:
- **Anon put** (`render_eval_chart` → `title="ASSET-X"`): slika nosi generički naslov → **nema više identiteta nego `candles.json`**. Precondition za čist ablation je **već zadovoljen** za anon slučaj.
- **Revealed put** (`build_snapshot(reveal=True)` → `title=f"{symbol} {tf_lower.upper()}"`): slika nosi **pravi simbol** koji `candles.json` nema. To je namerni leakage-control ugao, ne ulaz analyst-a.

**Marker (spike ne rešava, samo obeležava):** svaki novi image-input ugao mora koristiti **normalizovan naslov (`ASSET-X`)**; isporuka *revealed* charta sa pravim simbolom bi ubacila direktni symbol-recall koga danas nema u ulazu. Normalizacija naslova je preduslov za čist ablation i mora se eksplicitno štititi (npr. validatorom) ako se chart_image ikad uvede.

---

## Odluka

| Pitanje | Ishod |
|---|---|
| Postoji li headless image put za **Claude**? | **NE za testirani CLI transport** — canary završava pre model odgovora |
| Postoji li headless image put za **Codex**? | **DA** (`-i` flag, dokumentovan) |
| Je li izolacija dokaziva za **Claude image**? | **N/A** — capability gejt je prvi pao |
| Je li izolacija dokaziva za **Codex**? | **NE — empirijski palo**: `read-only --cd` dozvoljava čitanje van case root-a |
| Simetrija dostave | **Nije ostvarena** u bezbednom headless harness-u |
| Symbol-leak | Anon naslov već čist (`ASSET-X`); normalizacija naslova = preduslov, markiran |

**Zaključak (po decision rule „ako izolacija nije dokaziva za nekog providera → chart_image se za njega odbacuje"):**

- `chart_image` se **odbacuje za oba providera u sadašnjem harness-u**: Claude nema potvrđen CLI transport, a Codex nema prihvatljivu izolaciju.
- Puni text-vs-image ablation i njegov `prp-plan` se zato **ne pokreću**. Podrazumevani ugovor ostaje `ohlcv_text`.
- Codex nalaz je širi od slike: isti `read-only --cd` profil koristi i tekstualni analyst. Dok se ne uvede stvarna read-confinement granica i novi canary ne prođe, **Codex analyst run-ovi nisu bezbedni za privatni answer-key benchmark**.
- Budući pokušaj može ponovo otvoriti `chart_image` samo uz podržan Claude headless image transport i zasebno dokazanu Codex filesystem izolaciju.

**Runbook ispravka:** tvrdnja iz §85 da provider-neutralan unos slike nije dostupan još ne treba menjati u kategoričko „dostupan je". Precizno stanje je: Codex ima dokumentovan `-i`; Claude Messages API podržava slike, ali CLI stream input dokumentuje samo tekst. Provider-neutralnost i Codex anti-leakage granica ostaju empirijski gejtovi.

## Pripremljeni canary artefakti

- `scripts/eval/canary_claude_image.py` — dry-run po default-u; `--confirm` pravi tačno jedan Claude poziv. Proverava tačan OCR token, odsustvo spoljnog sentinela i odsustvo automatski učitanog `CLAUDE.md` sentinela.
- `scripts/eval/canary_codex_image.py` — dry-run po default-u; `--confirm` pravi tačno jedan Codex poziv. `-i` dobija samo sliku unutar case root-a; nepriloženi spoljni sentinel se proverava kroz obavezni shell pokušaj i JSONL tool događaj.
- `scripts/eval/canary_common.py` — zajedničko generisanje slika/tokena, izvršavanje CLI-ja i strogi verdict helper-i.
- `tests/test_image_canaries.py` — pokriva image payload, ispravan `-i` path i pozitivnu/negativnu Codex izolacionu granu.

Komande bez model poziva:

```bash
uv run python -m scripts.eval.canary_claude_image
uv run python -m scripts.eval.canary_codex_image
```

Plaćeni pozivi se ne izvršavaju bez eksplicitnog `--confirm`.

## Empirijski canary status — 2026-06-21

### Claude 2.1.185

- Prvi CLI pokušaj je otkrio runtime drift: `--mcp-config '{}'` više nije validan; 2.1.185 zahteva `{"mcpServers":{}}`. Ispravljeni su zajednički runtime adapter, test i runbook.
- Posle lokalno potvrđene autentifikacije i ispravne MCP konfiguracije, image stream-json canary je ponovo završio sa exit code 1, bez stream-json result događaja i bez model odgovora.
- **Verdikt:** Claude image capability kroz ovaj nedokumentovani CLI put **NIJE POTVRĐEN**. Po strogoj decision rule grani, `chart_image` se za Claude ne planira preko ovog puta dok se ne pronađe drugi podržan headless transport.

### Codex CLI 0.141.0

- Prvi pokušaj je otkrio zastareo runtime map: `gpt-5.1-codex` nije podržan uz aktuelni ChatGPT nalog. Lokalni model cache navodi `gpt-5.4`, `gpt-5.4-mini` i `gpt-5.5`; adapter i canary su prebačeni na `gpt-5.4`.
- Stvarni `gpt-5.4` poziv je uspešno pročitao tačan OCR token sa dozvoljene slike: **image capability PROŠAO**.
- Prvi izolacioni verdict bio je nevažeći zbog greške u evaluatoru: Codex emituje `command_execution` prvo kao `in_progress`, zatim kao terminalni događaj, a evaluator je prerano vratio prvi match. Evaluator je ispravljen da bira poslednji terminalni događaj i dodat je regression test.
- Odobreni ponovljeni poziv je ponovo tačno pročitao OCR token, zatim uspešno izvršio `/bin/cat` nad nepriloženim sentinel fajlom van case root-a (`exit_code=0`) i vratio sentinel u finalnom odgovoru.
- **Konačni verdikt:** Codex image capability **PROŠAO**; anti-leakage izolacija **PALA**. `chart_image` se za Codex odbacuje, a postojeći Codex tekstualni analyst profil ostaje zabranjen za privatni benchmark dok se filesystem izolacija ne redizajnira i ponovo dokaže.
