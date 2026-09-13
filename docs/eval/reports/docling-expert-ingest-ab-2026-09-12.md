# Docling naspram PyMuPDF/DOM za expert ingest

**Datum:** 2026-09-12  
**GitHub:** [#100 — ispitati Docling kao strukturni pretprocesor za expert ingest](https://github.com/ssmiljanicc/wyckoff-ai/issues/100)  
**Presuda:** `DISPROVEN` — odbaciti Docling za trenutni expert-ingest pipeline.

## Pitanje

Da li Docling nad originalnim PDF/HTML izvorima pravi bolji strukturni ulaz za LLM od postojećeg
PyMuPDF/DOM toka, bez pada provenijencije i uz manji ili opravdan dodatni trošak?

## Zaključani uzorak

| Source tip | Current ulaz | Originalni Docling ulaz |
|---|---|---|
| book | `raw/book/pages/page_218.md` i dve lokalne slike | originalni PDF, samo stranica 218 |
| Fraser | DOM Markdown i devet lokalnih article slika | autentičan sačuvani `holiday-chartfest` HTML |
| crypto | DOM Markdown i jedanaest lokalnih slika | `wyckoff-crypto-report-vol-25.html` |

Book PDF SHA-256 je
`8dfaaaeb0c7ec454287bab01819a9943f1b5923b07c1abee7d948d2f694ff5b9`. Fraser i crypto HTML
provereni su prema canonical URL-u, manifestu i postojećim downloader pravilima. Nijedan HTML nije
rekonstruisan iz Markdowna.

## Metod

1. Current i Docling parseri obradili su isti source sadržaj.
2. Slike su povezane samo deterministički: PDF page/bounding-box IoU ili HTML `img src` i postojeća
   downloader mapa. Semantičko ili prosto ordinalno nagađanje nije korišćeno.
3. Obe grane dobile su isti prompt, output schemu i 21 isti dekodabilan image attachment.
4. Svaka grana pozvana je tačno jednom kao `gpt-5.6-sol` medium.
5. Schema, coverage, source/image paths i byte-verbatim citati provereni su deterministički.
6. Rezultati su anonimizovani i zajedno ocenjeni jednim svežim `gpt-5.6-sol` high evaluatorom.
7. Mapping je otvoren tek posle trajnog upisa i SHA-256 provere judgment fajla.

Nisu korišćeni Claude/Sonnet, Astra niti ljudski ground truth.

## Parser rezultat

| Source | Current elementi/slike | Docling elementi/body slike | Current → Docling median runtime |
|---|---:|---:|---:|
| book p.218 | 6 / 2 | 6 / 2 | 0,48 ms → 240,44 ms |
| Fraser | 40 / 9 | 317 / 57 | 1,80 ms → 51,54 ms |
| crypto vol.25 | 47 / 11 | 81 / 11 | 2,53 ms → 54,26 ms |

Docling je na book stranici mapirao obe slike sa bbox IoU 0,9980 i 0,9947. Na Fraser full-page
HTML-u 48 od 57 body slika predstavljalo je page furniture, ne article sadržaj. Docling nije dao
nativnu HTML element provenance mapu; za content scope bio je potreban dodatni DOM identity adapter.

Current parser package imao je 54.840 bajtova, a Docling 226.854 bajta. Model envelope bio je 82.143
prema 289.827 bajtova.

## Deterministički i modelski rezultat

| Mera | Current | Docling |
|---|---:|---:|
| Schema i coverage | PASS | PASS |
| Prihvaćeni extracti | 20 | 19 |
| Doslovni citati prema canonical source-u | 20/20 | 13/19 |
| Hard gate | **PASS** | **FAIL** |
| Input tokeni | 282.720 | 339.829 |
| Slepi ukupni skor | **92** | **87** |
| Pairing | **25** | 22 |
| Provenijencija | **15** | 9 |

Doclingovih šest citata jeste bilo doslovno prema Docling paketu, ali ne prema canonical source-u.
Parser je promenio whitespace, navodnike ili apostrofe. To lomi ugovor da expert extract mora biti
proverljiv kao tačan citat izvora.

Docling je potrošio 57.109 više input tokena, odnosno 20,2%. Slepi evaluator je current grani dao
prednost od pet poena i označio razliku kao materijalnu. Docling je bolje odbacio jednu
caption-only PnF sliku, ali ta pojedinačna prednost nije nadoknadila citate, pairing, propušteni
crypto extract i veći kontekst.

## Presuda

Docling nije prešao nijedan unapred definisan prag koristi ni za jedan testirani source tip. Dodao
je hard-gate greške, više HTML noise-a i veći modelski ulaz. Zato se odbacuje kao opšti i kao
hibridni expert-ingest pretprocesor. PyMuPDF/DOM ostaje podrazumevani tok.

Ova presuda ne tvrdi da Docling nema vrednost za svaki mogući dokument. Test nije uključio OCR-only
ili table-heavy PDF. Takav novi source oblik zahteva zaseban, unapred zaključan spike; nije razlog da
se menja odluka za sadašnji Wyckoff korpus.

Test je otkrio nezavisan raw-data problem:
[#102 — popraviti crypto vol.25 asset sa HTML payloadom i `.png` sufiksom](https://github.com/ssmiljanicc/wyckoff-ai/issues/102).

## Dokazi

Lokalni evidence root:

```text
/Users/ssmiljanic/.prp/wyckoff-ai-472026b6/spikes/docling-original-source-ab/
```

Ključni fajlovi su `final-summary.json`, `deterministic-validation.json`, `blind-judgment.json`,
`source-provenance.json`, `parser-measurements.json`, `cost-and-usage.json` i
`evidence-manifest.json`.

Kontrolni hashovi:

- blind judgment: `4eeb0c3a2c2dca30f063e0e0bef7a48f52cc141aeb960e40682ccd4e1256f5bb`;
- sealed mapping: `3ca4e156e5ec3c347ce8b21f778c028a8532ad8c32250b505b3cf11a3847c293`;
- kompletan spike report: `0191479f2c721ca25682607272ce737086c2f6084135bb7c25ba7fd64125c784`.

Detaljan lokalni spike report:
`/Users/ssmiljanic/.prp/wyckoff-ai-472026b6/spikes/spike-docling-original-source-ab.md`.
