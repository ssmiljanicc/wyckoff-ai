# Project structure — Wyckoff AI

## Kanonski steering dokumenti

Jedini kanonski živi steering dokumenti su `product.md`, `tech.md` i `structure.md`.

- `product.md` definiše svrhu, centralnu hipotezu, uloge dva wikija i granice tvrdnji projekta.
- `tech.md` definiše ingest granice, Docling odluku, model-selection disciplinu i ciljni eval.
- `structure.md` pokazuje gde se nalaze izvori istine i gde pripada novi sadržaj.

Steering dokumenti ne zamenjuju `CLAUDE.md`, runbookove, schemu ni coverage ledger. Oni povezuju te
izvore u jednu projektnu sliku za buduće sesije.

## Mapa repozitorijuma

```text
raw/                                  nepromenljivi izvorni korpus
  book/                               knjiga: PDF, page Markdown, slike
  bruce_fraser/                       članci i lokalne slike
  crypto_archive/                     crypto postovi i lokalne slike

knowledge/wiki/                       glavni wiki: teorija i sinteza
  concepts/ events/ structures/
  crypto/ scenarios/ sources/

research/expert-analyses/             konkretne ekspertske analize
  EXTRACT_TEMPLATE.md                 schema jednog validnog extracta
  batches.md                          definicije i promptovi ingest batch-eva
  _progress.md                        jedini izvor istine za sweep napredak
  _gaps.md                            nedostupni i problematični izvori
  run-log.md                          operativni zapis
  wiki/extracts/                      validni pasus–slika primeri
  wiki/by-event/                      indeksi po događaju
  wiki/by-structure/                  indeksi po strukturi

skills/wyckoff-trader-skill/          runtime ugovor tržišne analize
scripts/eval/                         eval build, orchestration i scoring kod
runbooks/                             operator procedure za ingest i eval
data/eval/                            javni eval podaci; privatni key je gitignored
docs/eval/reports/                    verzionisani eval izveštaji
docs/decisions/                       trajne tehničke odluke i okidači za preispitivanje
PRPs/                                 planovi, izveštaji i istorija implementacije

.claude/steering/                     trajni projektni pravac
  product.md
  tech.md
  structure.md
```

## Gde pripada nova informacija

- Wyckoff definicija ili sinteza pripada `knowledge/wiki/` prema `CLAUDE.md` schemi.
- Konkretan ekspertov pasus povezan sa konkretnim grafikonom pripada
  `research/expert-analyses/wiki/extracts/`.
- Batch napredak pripada `_progress.md`; ne upisivati ručne procene u steering kao novi izvor
  istine.
- Ponovljiva operatorska procedura pripada `runbooks/`.
- Runtime ponašanje analysta pripada `skills/wyckoff-trader-skill/`.
- Benchmark implementacija pripada `scripts/eval/`, a trajni rezultat `docs/eval/reports/`.
- Arhitektonska ili produktna odluka koja menja pravac prvo se usaglašava sa operatorom, pa ažurira
  `product.md` ili `tech.md` i povezani izvor istine.

## Pravila za buduće sesije

Pre rada koji dira wiki, expert ingest, Docling, izbor modela ili eval:

1. pročitaj sva tri steering dokumenta;
2. proveri živi status u `_progress.md`, GitHub tiketima i git granama/worktreevima;
3. ne zaključuj iz steering datuma da je operativno stanje i dalje isto;
4. ne mešaj pomoćni ingest benchmark sa završnim tržišnim benchmarkom;
5. ne pokreći naplativi model samo zato što je naveden kao moguća eskalacija.
