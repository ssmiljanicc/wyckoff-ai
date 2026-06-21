# Pregled Plana — research-expert-analyses-index

**Datum**: 2026-06-22
**Plan**: `PRPs/plans/research-expert-analyses-index.plan.md`
**Presuda**: REVISE-PLAN

## Zaključak

Premisa plana je zdrava i dobro utemeljena: napraviti pretraživ, **prebrojan** index ekspertskih
Wyckoff analiza iz tri immutable raw izvora kao Korak 0 za #89, sa ciljem da `corpus-count` tabela
deblokira #84. Tvrdnje o postojećem stanju su skoro sve tačne (provereno: 23 events, 5 structures,
248/243/46 izvora, 119 book slika, 0 lokalnih Fraser slika, eval analyst je stvarno NO-tools).
Najveći logički propust nije u redosledu taskova (on je ispravan: proizvođači pre potrošača) već u
**mehanizmu nastavka rada i u validaciji koja ne hvata tihu grešku**: pošto je tačan broj korpusa
ceo smisao posla, a sweep „verovatno prekoračuje jednu sesiju" (sopstveni Risk plana), a resume se
oslanja na brojanje postojećih extract-a — nedovršen prolaz izgleda identično kao završen prolaz sa
niskim hit-rate-om, pa `Ukupno pregledano` može biti tiho netačan. Uz to, Validation #3 proverava
samo 4 od ~10 obaveznih polja, i to labavim substring grep-om koji daje false-positive. Nepotrebne
kompleksnosti skoro da nema — dvostruka taksonomija (`by-event` + `by-structure`) je traženo #89-om.

**Ocene:** Premisa 9/10 · Tok 8/10 · Nužnost kompleksnosti 8/10

## Nalazi po težini

### [VAŽNO] Resume mehanizam ne razlikuje „pregledano i odbačeno" od „nije pregledano" — PLAN DEFECT
**Tvrdnja plana**: Risks → „resume preko brojanja postojećih `extracts/<source>_*.md`" (linija 297);
istovremeno „Obim (537 dok.) prekoračuje jednu sesiju — **Visoka** verovatnoća".
**Stvarnost**: I odbačen dokument (nije ekspertska analiza) i još-nepregledan dokument proizvode
**isti rezultat** — odsustvo extract fajla. Brojanje extract-a po izvoru ne može da rekonstruiše
dokle je sweep stigao. Za Fraser (243 dok., eksplicitno „nizak hit-rate", linija 298) ovo je realno:
ako agent stane na dokumentu 120, ništa to ne signalizira.
**Posledica**: `Ukupno pregledano` u corpus tabeli (čiji je ceo smisao da deblokira #84) može biti
tiho netačan, a sve Acceptance Criteria i Validation Commands i dalje prolaze — jer nijedan ne
zahteva potvrdu pune pokrivenosti po izvoru.
**Popravka**: uvesti per-source progress ledger (npr. `research/expert-analyses/_progress.md` koji
beleži, po izvoru, listu/poslednji pregledani fajl i `reviewed_count`), učiniti `Ukupno pregledano`
izvedenim iz njega (ne iz broja extract-a), i dodati Acceptance + Validation kriterijum da
`reviewed_count` po izvoru == ukupan broj fajlova (248/243/46) pre nego što se plan smatra završenim.
Ledger je pod `research/`, dakle ne dira eval izolaciju.

### [VAŽNO] Validation #3 proverava 4 od ~10 obaveznih polja, labavim grep-om — PLAN DEFECT
**Tvrdnja plana**: Acceptance → „Svaki extract fajl ima **sva obavezna polja** i `status: candidate`"
(linija 280); Task 1 nabraja 10 polja (`source`, `page`/`post_url`, `asset`, `timeframe`,
`wyckoff_event`, `structure`, `phase`, `image_path`, `type`, `status`).
**Stvarnost**: Validation #3 (linije 245–249) proverava samo `source wyckoff_event type status`, i to
sa `grep -q "$k"` bez sidra — `source` matchuje `primary_source`/`sources`/bilo koju reč u verbatim
citatu; `type`/`status` matchuju bilo gde u telu. Polja `asset`, `timeframe`, `structure`, `phase`,
`image_path`, `page`/`post_url` se **uopšte ne validiraju**.
**Posledica**: extract bez `image_path` ili `phase` (ili sa praznim frontmatter-om a tim rečima u
citatu) prolazi validaciju — Acceptance kriterijum „sva obavezna polja" je lažno zelen.
**Popravka**: sidriti proveru na YAML ključeve frontmatter-a (`^source:`, `^wyckoff_event:`, …) i
proveriti **svih** obaveznih polja; za `page|post_url` proveriti da postoji bar jedan od dva.

### [VAŽNO] `image_path` se nigde ne validira, iako je obavezno polje sa netrivijalnom konverzijom — PLAN DEFECT
**Tvrdnja plana**: Task 4 gotcha → „crypto img putanja je `../images/<report>/<n>.png` relativno —
**konvertuj** u repo-relativnu `raw/crypto_archive/images/...`" (linija 182).
**Stvarnost**: Validation #4 (linije 252–254) proverava samo `.md` pointere (regex `raw/...\.md`).
Slike (`.png`/`.jpg`) nisu pokrivene. Pogrešno konvertovan `image_path` (realan rizik koji plan sam
ističe) tiho prolazi.
**Posledica**: corpus može imati extract-e koji pokazuju na nepostojeću sliku — kasniji potrošač
(#86 kuracija, #91 ML) dobija mrtve pointere.
**Popravka**: dodati Validation korak koji za svaki `image_path` koji nije `(remote…)` ni prazan
potvrđuje `test -f`; za Fraser/remote eksplicitno dozvoliti `(remote: …)` oblik.

### [SITNO] WIKI_GAP za paywalled crypto post se rutira u „odgovarajući by-event fajl", a event je nepoznat — PLAN DEFECT
**Tvrdnja plana**: Task 4 → „za paywalled, umesto extract-a ubaci **WIKI_GAP** napomenu … u
odgovarajući `by-event` fajl" (linija 180).
**Stvarnost**: Paywalled znači da sadržaj nije skrejpovan (`status: paywalled`, 10 postova) — pa se
**ne zna** koji je Wyckoff event, dakle ni koji je „odgovarajući" `by-event` fajl.
**Posledica**: agent ili pogađa event (kontaminacija taksonomije) ili zapne.
**Popravka**: rutirati paywalled WIKI_GAP u `index.md` (sekcija „WIKI_GAP / paywalled") ili u
namenski `research/expert-analyses/_gaps.md`, ne u event-specifičan fajl.

## Van scope-a (post-code)
- Nema klasičnih IMPLEMENTATION DRIFT / VALIDATION GAP nalaza za post-code review — output je
  dokumentacija, nema runtime koda. Domenski spot-check (5 uzoraka, već u planu) ostaje kao
  ljudska kontrola kvaliteta posle izvršenja.

## Šta drži
- **Redosled taskova je ispravan** — skela/template (1) → taksonomija skeleti (2) → sweep-ovi (3/4/5)
  → popunjavanje pointera (6) → count+index (7) → finalna validacija (8). Proizvođači su pre potrošača.
- **Provenance/citat disciplina** (pointer + verbatim, nikad cela kopija; word-cap heuristika) je
  zdrava i usklađena sa CLAUDE.md §5/§7.
- **Tvrdnje o kodu su tačne** — eval izolacija stvarno postoji (`orchestrator.py:213` NO-tools), Fraser
  stvarno nema lokalne slike (0), brojevi izvora se poklapaju. Drift broja linije za `analyst_prompt`
  je plan već priznao u Risks.
- **Nužnost kompleksnosti** — dvostruka taksonomija i pun set skeleta su traženi #89-om, ne over-build.
