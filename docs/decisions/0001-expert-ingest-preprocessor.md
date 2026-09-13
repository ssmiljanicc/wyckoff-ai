# ADR 0001: Zadržati PyMuPDF/DOM za expert ingest

**Status:** accepted  
**Datum:** 2026-09-12  
**Odluka:** Ne uvoditi Docling kao pretprocesor za `research/expert-analyses/`.

## Kontekst

Expert ingest mora pouzdano da sačuva vezu između izvornog pasusa, grafikona i lokalne putanje.
Pretprocesor ne odlučuje Wyckoff značenje, ali njegov izlaz direktno utiče na LLM kontekst,
provenijenciju i cenu.

Docling je razmatran zato što obećava layout, reading-order, image i table strukturu iz originalnih
PDF/HTML dokumenata. Poređen je sa postojećim tokom:

- PyMuPDF za book PDF;
- postojeći HTML/DOM parser za Bruce Fraser i crypto članke.

## Odluka

Zadržati postojeći PyMuPDF/DOM tok za sva tri trenutna source tipa. Ne dodavati Docling dependency,
Docling adapter niti hibridni izuzetak u B02–B29 expert ingest.

Razlozi su:

- current grana je prošla exact-source hard gate sa 20/20 doslovnih citata; Docling je prošao sa
  13/19 i promenio šest citata normalizacijom whitespace-a i tipografskih znakova;
- slepi Sol-high evaluator rangirao je current 92, Docling 87;
- Docling je imao slabiji passage–image pairing (22 prema 25) i provenijenciju (9 prema 15);
- Docling je propustio jedan crypto extract;
- Docling je Sol-medium kandidatu dodao 57.109 input tokena, odnosno 20,2%;
- full-page Fraser HTML dao je 57 body slika, od kojih je 48 page furniture, naspram devet stvarnih
  article slika u postojećem DOM toku;
- precizno Docling mapiranje dve slike sa book PDF stranice nije donelo semantičku ni token korist.

Detaljan ugovor, uzorak, blind postupak, brojke i ograničenja nalaze se u
[`docs/eval/reports/docling-expert-ingest-ab-2026-09-12.md`](../eval/reports/docling-expert-ingest-ab-2026-09-12.md).

## Posledice

- B02–B29 ingest koristi PyMuPDF/DOM pakete i `gpt-5.6-sol` medium, uz obaveznu schema, path, image,
  coverage i exact-verbatim validaciju.
- Optimizacija tokena treba prvo da ukloni nerelevantne DOM elemente i skrati postojeći package
  contract, bez novog parser sloja.
- Originalne HTML/PDF reprezentacije i dalje vrede za reproducibility i raw-data audit, ali njihovo
  čuvanje nije razlog da se promeni izabrani pretprocesor.
- Nedekodabilni crypto asset otkriven testom vodi se kroz
  [#102 — popraviti crypto vol.25 asset sa HTML payloadom i `.png` sufiksom](https://github.com/ssmiljanicc/wyckoff-ai/issues/102);
  ne pripisuje se nijednom parseru.

## Kada ponovo razmatrati Docling

Ovu odluku ne otvarati ponovo samo zbog nove preporuke agenta ili opšte Docling tvrdnje. Novi spike
ima smisla samo ako se pojavi bar jedan od sledećih okidača:

- novi korpus čine OCR-only ili table-heavy PDF dokumenti koje PyMuPDF/DOM ne može pouzdano da obradi;
- nova Docling verzija nativno čuva byte-verbatim tekst, content-only HTML scope i stabilnu
  source-to-local-image provenijenciju;
- produkcioni podaci pokažu merljiv failure trenutnog parsera koji je Docling specifično sposoban da
  ukloni.

Svaki novi test mora koristiti isti model, prompt, schemu, source uzorak i slepi evaluator u obe
grane. Postojeći parser ostaje pobednik u slučaju nerešenog rezultata.
