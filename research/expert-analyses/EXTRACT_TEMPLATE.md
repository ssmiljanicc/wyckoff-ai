---
# Obavezna polja — sva moraju biti popunjena (Validation #3)
source: raw/book/pages/page_XXX.md           # tačan raw .md iz jednog od tri dozvoljena podstabla
page: XXX                                    # book: mora odgovarati page_NNN.md source filename-u
# page_range: XXX-YYY                        # book opciono: samo source strana + neposredno sledeća
# post_url: https://...                      # Fraser/crypto: doslovno isti URL kao raw `URL:` header; bez page/page_range
asset: unknown                               # ticker ili "unknown" ako nije naveden
timeframe: unknown                           # npr. daily, weekly, 60min, ili "unknown"
wyckoff_event: spring                        # postojeći wiki/by-event slug; "none" samo kada event ne postoji/ne primenjuje se
# related_events: upthrust,secondary-test    # opciono: comma-separated dodatni stvarno prisutni by-event slugovi
structure: accumulation                     # postojeći wiki/by-structure slug; "none" samo kada structure ne primenjuje se
# related_structures: reaccumulation         # opciono: comma-separated dodatni stvarno prisutni by-structure slugovi
phase: C                                     # A|B|C|D|E; "unknown" samo kada faza postoji u domenu ali nije utvrdiva
image_path: raw/book/images/page_XXX_fig_1.png  # obavezna proverljiva slika; Fraser remote samo uz manifest mapiranje
type: forward                                # forward | retrospective | schematic
status: candidate                            # candidate | validated | eval-used (promocija je van obima #89)
---

## Sentinel i range pravila

- `unknown` znači „metadata postoji, ali je izvor ne navodi dovoljno precizno“. Dozvoljen je za
  `asset`, `timeframe` i `phase`; nije dozvoljen za `wyckoff_event` ili `structure`.
- `none` znači „polje se ne primenjuje na ovaj concept schematic“. Dozvoljen je samo za
  `wyckoff_event` i `structure`, ali ta dva polja ne smeju oba biti `none`: svaki extract mora imati
  bar jedan stvarni taksonomijski pointer. Ne izmišljati event, structure ni phase da bi se popunilo
  polje. Concept-only schematic koji se prirodno ne mapira ni na jedan postojeći event/structure
  indeks (na primer opšti `Speed` dijagram) nije extract za ovaj korpus i odbacuje se.
- Singularni `wyckoff_event` i `structure` ostaju primary klasifikacije. Kada isti konkretni
  grafikon i ekspertov pasus zaista prikazuju više event/structure klasifikacija, dodatne slugove
  navedi u opcionim comma-separated poljima `related_events`/`related_structures`. Svaka deklarisana taxonomy
  stranica mora imati pointer na extract i njegov raw `source`; nedeklarisana stranica ne sme da ga
  linkuje. Ne koristi related liste za labave asocijacije ili zaobilaženje primary klasifikacije.
- Kada book slika stoji na strani `N`, a interpretacija se nastavlja na neposredno sledećoj strani,
  postavi `source`/`page` na `N` i dodaj `page_range: N-(N+1)`. Validator proverava obe raw strane,
  doslovni citat nad tim opsegom i image manifest. Slika mora pripadati primary `source`/`page`
  strani `N`; `N+1` je dozvoljen samo kao nastavak citata. Širi ili neuzastopni rasponi nisu
  dozvoljeni.
- `source` je ograničen na `raw/book/pages/*.md`, `raw/crypto_archive/posts/*.md` ili
  `raw/bruce_fraser/posts/*.md`. `bez slike` nije validan expert extract; takav kandidat se odbacuje
  ili evidentira kao gap.
- Za deterministički dokaz koriste se samo doslovni raw naslov ili direktna chart tvrdnja, redosled
  susednih Markdown slika i tekst iz `Kontekst` sekcije. Kada je isti verbatim pasus ponovljen,
  postoji više susednih kandidata, token nije jednoznačan ili izvor koristi alias, validator ne
  nagađa: dokaz ostaje nerešen i ide na semantičku procenu. P&F je forma grafikona, ne timeframe;
  bez zasebnog intervala (`daily`, `weekly`, `60min`...) ne dokazuje vremenski okvir.
- `Kontekst` ne sme protivrečiti frontmatter `asset`/`timeframe` vrednostima kada ih navodi
  jednoznačno. Izbor i klasifikacija `event/structure/phase` ostaju semantička procena; validator
  proverava samo njihove enum/sentinel i taxonomy pointer ugovore, ne zaključuje ih iz teksta ili
  piksela slike u standardnom toku.

## Opcioni Fraser header OCR dokaz

Apple Vision OCR je isključivo lokalni, ručno uključen dokazni sloj za lokalne Fraser slike. Na
podržanom macOS hostu dvokoračni tok je:

```bash
uv run python scripts/fraser_header_ocr.py --kb-root research/expert-analyses --output /tmp/fraser-header-ocr-v1.json
uv run python scripts/validate_expert_analyses.py --kb-root research/expert-analyses --skip-git --ocr-evidence /tmp/fraser-header-ocr-v1.json
```

Standardni runner ne prosleđuje `--ocr-evidence` i validator bez tog flag-a ne pokreće OCR niti
zahteva macOS/Vision. Samo validan `fraser-header-ocr/v1` zapis sa odgovarajućim image SHA-256 i dva
ista jednoznačna prolaza sme da blokira različitu poznatu `asset`/`timeframe` vrednost. `unknown`,
nečitljiv, dvosmislen, nestabilan, nedostajući ili zastareo dokaz ne pravi hard failure.
Artefakt ne popunjava metadata, ne menja extract karticu, nije novi source of truth i ne zaključuje
`event/structure/phase`.

## Verbatim pasus

> Ovde ide **verbatim citat** (doslovan prepis, ne parafraza) ekspertovog pasusa koji
> nosi konkretnu Wyckoff interpretaciju grafikona. Samo relevantni deo — ne ceo dokument.
> OCR artefakte (npr. "gre ater", "selle rs") citiraj verbatim, ne "popravljaj".

## Kontekst

Kratka napomena (1–2 rečenice) za navigaciju — nije citat, nego locating aid:
- Šta se vidi na grafikonu (asset, period ako je poznat)
- Zašto je ovo validan par (konkretna interpretacija, ne samo definicija)

Ako ovde eksplicitno ponavljaš asset ili timeframe, vrednost mora odgovarati frontmatter-u. Kada
raw dokaz nije jednoznačan, zadrži `unknown`; ne zaključuj iz aliasa, P&F forme ili same slike.

## Napomene

<!-- Opciono: granični slučaj, OCR artefakt, nejasan timeframe, veza sa drugim extractom -->
