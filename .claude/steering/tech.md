# Technical direction — Wyckoff AI

## Trenutni izvori i ekstrakcija

`raw/` je nepromenljivi sloj izvora:

- `raw/book/` sadrži PDF, Markdown stranice i slike izvučene pomoću PyMuPDF-a;
- `raw/bruce_fraser/` sadrži lokalne članke i slike, sa redosledom izvedenim iz HTML/DOM strukture;
- `raw/crypto_archive/` sadrži lokalne postove i slike iz crypto arhive.

Postojeća ekstrakcija već povezuje tekst i slike na nivou stranice ili članka. LLM zatim odlučuje
koji pasus predstavlja konkretnu ekspertsku analizu, koja slika mu pripada, šta treba odbaciti i
kojom Wyckoff taksonomijom označiti validan primer.

## Ciljni expert-ingest tok

```text
raw dokument
  -> strukturni pretprocesor
  -> kandidatne grupe teksta, slika i tabela
  -> LLM semantička selekcija i klasifikacija
  -> schema i provenance validacija
  -> research/expert-analyses/wiki/
```

Pretprocesor ne donosi konačnu domensku odluku. Njegov posao je da sačuva redosled čitanja,
prostornu blizinu, hijerarhiju, slike, tabele i lokatore. LLM odlučuje da li grupa zaista sadrži
ekspertsku interpretaciju grafikona i kako se klasifikuje.

## Docling odluka

Docling 2.126.0 je odbijen kao expert-ingest pretprocesor posle original-source i slepog semantičkog
A/B testa. Zadržati PyMuPDF za knjigu i postojeće DOM tokove za Fraser/crypto; ne dodavati Docling
dependency niti hibridni izuzetak za sadašnji korpus.

Current grana je prošla exact-verbatim hard gate i slepi skor 92, dok je Docling pao hard gate,
dobio 87 i povećao input 20,2%. Trajna odluka, testirani uzorak, ograničenja i uslovi za ponovno
razmatranje nalaze se u [`docs/decisions/0001-expert-ingest-preprocessor.md`](../../docs/decisions/0001-expert-ingest-preprocessor.md).

## Izbor modela za ingest

Modeli se porede pod istim uslovima: isti izvori, prompt, schema, evaluator i prag kvaliteta. Svaki
kandidat prvo prolazi determinističku proveru oblika, source putanja, postojećih slika i verbatim
citata. Slepi evaluator zatim ocenjuje selekciju, razloge odbacivanja, klasifikaciju, provenijenciju
i korisnost rezultata. Identitet kandidata otkriva se tek posle ocenjivanja.

Birati najjeftiniji model koji pouzdano prelazi unapred definisan prag, a ne nužno model sa najvećim
apsolutnim skorom. Rezultati iz drugog domena ili benchmarka nisu dokaz kvaliteta Wyckoff
chart/expert ingest-a.

## Expert-ingest invarijante

Svaki prihvaćeni extract mora da ima:

- tačan lokalni source path i page/post lokator;
- verbatim pasus koji postoji u navedenom izvoru;
- postojeću lokalnu image path kada extract zavisi od slike;
- eksplicitne event, structure, phase, type i status vrednosti prema postojećoj schemi;
- pointere iz odgovarajućih `by-event` i `by-structure` stranica;
- ažuriran coverage ledger u `research/expert-analyses/_progress.md`.

Odbijanje je legitiman rezultat i mora imati razlog. Broj extract fajlova nije mera pregledanog
korpusa; `_progress.md` je izvor istine.

## Ciljni tržišni eval

Završni eval treba da razdvoji javni analyst kontekst od privatnih etalona:

```text
analyst dobija:
  podatke do T + glavni wiki + netarget ekspertske primere

privatno ostaje:
  ciljna ekspertska analiza + anotacije + podaci posle T

skorovi:
  expert alignment + realized outcome + kvalitet obrazloženja/kalibracije
```

Target-case holdout mora sprečiti direktno i posredno curenje istog slučaja kroz expert wiki,
prompt, naziv fajla, slike ili retrieval. Retrospektivni slučajevi ne dobijaju realized-outcome
skor. Rezultate malog skupa označiti kao indikativne, ne statistički merodavne.

## Izvori istine

- Wiki schema i projektna pravila: `CLAUDE.md`
- Glavni ingest protokol: `runbooks/wyckoff-wiki-ingest.md`
- Expert ingest raspored: `research/expert-analyses/batches.md`
- Expert ingest stanje: `research/expert-analyses/_progress.md`
- Expert extract schema: `research/expert-analyses/EXTRACT_TEMPLATE.md`
- Postojeći eval tok: `runbooks/faza-4-eval-orchestrator.md`
- Odluka o pretprocesoru: `docs/decisions/0001-expert-ingest-preprocessor.md`
