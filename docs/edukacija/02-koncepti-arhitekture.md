# Koncepti i arhitektura — od pitanja do PRD-ova

> Pratilac uz [`01-masinsko-ucenje.md`](./01-masinsko-ucenje.md). Pokriva sve ostale teme o kojima smo pričali tokom planiranja Wyckoff AI projekta — od pitanja "crtež ili brojevi" do razdvajanja MCP-a i skill-a. Razdvaja **opšte koncepte** (važe za bilo koji AI agent projekat) od **specifičnih** odluka koje su nas vodile do PRD-ova ovog konkretnog projekta.
>
> **Strana terminologija** — svaki engleski pojam je preveden i objašnjen prvi put kad se pojavi.

---

## Sadržaj

1. [Slike vs brojevi za AI](#1-slike-vs-brojevi-za-ai) (**OPŠTE**)
2. [OHLCV — šta to znači](#2-ohlcv--sta-to-znaci) (specifično za trading)
3. [Vision captions — most između epoha](#3-vision-captions--most-izmedju-epoha) (**OPŠTE**)
4. [LLM vs Vision modeli — šta zapravo "vide"](#4-llm-vs-vision-modeli--sta-zapravo-vide) (**OPŠTE**)
5. [Skill vs MCP — slojevi a ne alternative](#5-skill-vs-mcp--slojevi-a-ne-alternative) (**OPŠTE**)
6. [Šta je MCP server detaljnije](#6-sta-je-mcp-server-detaljnije) (**OPŠTE**)
7. [Šta je Claude Skill detaljnije](#7-sta-je-claude-skill-detaljnije) (**OPŠTE**)
8. [Modovi u skill-u (mode discriminator)](#8-modovi-u-skill-u-mode-discriminator) (specifično za naš projekat)
9. [Provenance i llm-wiki pattern](#9-provenance-i-llm-wiki-pattern) (**OPŠTE**, Karpathy pattern)
10. [Faze projekta — zašto baš tri](#10-faze-projekta--zasto-bas-tri) (specifično za naš projekat)
11. [Generalno vs specifično — sažetak](#11-generalno-vs-specificno--sazetak)

Sekcije označene **OPŠTE** opisuju principe primenljive na **bilo koji** AI agent projekat. Ostale su specifične za naš Wyckoff AI.

---

## 1. Slike vs brojevi za AI

(**OPŠTE** — primenljivo na svaki projekat koji se bavi vizuelnim i numeričkim podacima)

### 1.1 Pitanje koje smo postavili

Kad smo razmišljali o tome kako će agent analizirati grafike, postavili smo se ovo pitanje:

> "Ako mu dam OHLCV brojeve, da li ih AI u pozadini konvertuje u sliku da bi razumeo strukturu? Ili obratno — ako mu dam sliku, da li je konvertuje u brojeve?"

Intuicija je razumna: AI često radi sa nekom "internom" reprezentacijom, pa pitamo koja je primarna.

### 1.2 Odgovor — ni jedno

LLM (Large Language Model — veliki jezički model) ne radi konverziju "slika ↔ brojevi" u smislu kako ljudi to zamišljaju.

**Kad prosleđuješ sliku** (npr. preko Claude Vision):
1. Slika prolazi kroz **vizuelni enkoder** (Convolutional Neural Network — konvolucionu neuronsku mrežu — ili Vision Transformer)
2. Enkoder pretvara sliku u **embedding vektore** — sequence of high-dimensional vectors koji predstavljaju vizuelne osobine (oblike, boje, prostorne odnose, tekst u slici)
3. Ti vektori se ubacuju u text decoder zajedno sa text promptom
4. Model "razume" sliku kao **vizuelnu informaciju**, ne kao listu piksela ili brojeva

LLM **ne** ekstraktuje OHLCV iz slike grafika kao numeričku listu. Vidi sliku slično čoveku — pattern recognition, ne tačno čitanje.

**Kad prosleđuješ brojeve** (npr. OHLCV niz):
1. Brojevi su tokeni kao bilo koji tekst — `42000.5`, `43200`, itd.
2. LLM može da "računa" do neke mere (mali brojevi, prosti odnosi), ali za stotine bara to postaje neefikasno
3. Model **ne renderuje internu sliku** od brojeva — radi na tokenima

### 1.3 Šta je dobro za šta

| Zadatak | Bolji format | Zašto |
|---|---|---|
| Prepoznavanje pattern-a ("da li je ovo spring?") | Slika | Vizuelni enkoder hvata spatial relationships dobro |
| Tačno čitanje vrednosti ("koja je cena AR-a?") | Brojevi (OHLCV) | Vision nije precizan na cifre u grafiku |
| Brojanje bara, merenje rasstojanja | Brojevi | Vision pravi greške na brojanju |
| Identifikacija tipa grafika (candlestick vs line) | Slika | Trivijalno za vision |
| Kalkulacija statistika (volatilnost, SMA) | Brojevi (programski) | Brzo, precizno |

### 1.4 Pravi pristup je hibrid

Daj **OBE** vrste informacija LLM-u:

```
OHLCV brojevi              →  preciznost (tačne cene, statistike)
+
Rendered slika grafika     →  pattern recognition (struktura, sekvenca)
+
Wiki tekstualno znanje    →  metodologija (šta je spring, kako se interpretira)
                                                                   ↓
                                                              Bogata analiza
```

Ovo je tačno ono što naša Faza 2 MCP arhitektura radi:
- `get_ohlcv()` → brojevi
- `render_chart()` → slika za Vision
- Wiki citacije → kontekst iz knjige

LLM dobija sve tri i može da svaku iskoristi za ono za šta je najbolja.

### 1.5 Šta važi za bilo koji projekat

Princip je univerzalan:
- **Numerička preciznost** → struktuirani podaci u JSON / brojevi
- **Pattern recognition** → vizuelni input (slike, dijagrami)
- **Domensko znanje** → tekst (dokumentacija, knjige, articles)

Kombinuj sve tri kad god je relevantno. Ne biraj samo jednu — to je samonametnuto ograničenje.

---

## 2. OHLCV — šta to znači

(specifično za trading / finansijski projekti)

OHLCV je standardni format **tržišnih podataka po vremenskim intervalima**. Svaki "bar" ili "sveća" (engleski: *candle*) sadrži **5 brojeva**:

- **O**pen — cena na **početku** intervala
- **H**igh — najviša cena **u intervalu**
- **L**ow — najniža cena **u intervalu**
- **C**lose — cena na **kraju** intervala
- **V**olume — koliko **se istrgovalo** u tom intervalu (broj jedinica imovine)

### Primer

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1d",
  "timestamp": "2024-05-24T00:00:00Z",
  "open": 42000,
  "high": 43500,
  "low": 41800,
  "close": 43200,
  "volume": 12500
}
```

Bar je trajao 24 sata. Tržište se otvorilo na $42,000, dostiglo $43,500, palo na $41,800, zatvorilo na $43,200. Ukupno je trgovano 12,500 BTC tog dana.

### Vizuelni prikaz — sveca (candlestick)

```
   High ──→  │
             │  ← gornji wick (knot)
             ┃
   Open ──→  ┃  ← telo (body) — zeleno ako Close > Open, crveno suprotno
             ┃
  Close ──→  ┃
             │  ← donji wick
   Low ───→  │
```

Boja: zelena/bela ako je Close iznad Open (cena rasla), crvena ako je Close ispod Open (pala).

### Kako se pulluje

Sa exchange API-ja:
```python
import requests
url = "https://api.binance.com/api/v3/klines"
params = {
    "symbol": "BTCUSDT",
    "interval": "1d",
    "limit": 200  # poslednjih 200 dana
}
data = requests.get(url, params=params).json()
# data = [[timestamp, open, high, low, close, volume, ...], ...]
```

Binance vraća listu lista — svaka lista je jedan OHLCV bar + nekoliko dodatnih polja (close time, quote asset volume, broj trgovaca, itd.).

### Timeframes (vremenski okviri)

Standardni:
- `1m`, `5m`, `15m`, `30m` — intraday (unutar dana)
- `1h`, `4h` — kratkoročno
- `1d` — dnevno (osnovni okvir za većinu analize)
- `1w` — nedeljno
- `1M` — mesečno

**Wyckoff analiza** najčešće koristi 1d i 1w za strateški pregled, 4h i 1h za taktiku.

---

## 3. Vision captions — most između epoha

(**OPŠTE** princip — primenljiv kad god treba poredjenje vizuelnog sadržaja sa različitih izvora)

### 3.1 Problem koji rešavamo

Imamo dva izvora vizuelnih informacija:

1. **Wyckoff knjiga** iz 1930-ih (Villahermosa rekonstrukcija) — schematic dijagrami, hand-drawn primeri, B&W
2. **Live tržište 2026** — candlestick grafici sa Binance-a, renderovani kroz `mplfinance`

Kad agent analizira BTC danas, želimo da pita: **"da li ovo liči na figure 17.3 iz knjige?"**

Direktno poređenje slika ne radi pouzdano. Style različitog, rezolucija različita, formatlazi različiti. Vision modeli mogu da opišu obe slike, ali "find similar image" je nepouzdano.

### 3.2 Rešenje — captions kao zajednički jezik

**Caption** (na srpskom: opis, alt-text) = tekstualni opis slike koji je dovoljno specifičan da uhvati strukturu, ali dovoljno apstraktan da se može uporediti sa drugim opisom.

```
Knjiska sema → [Vision pass] → "Schematic of accumulation with SC at support, AR
                                  to upper range boundary, ST on lighter volume,
                                  and spring breaking below SC before phase D markup"
                                
Live BTC      → [Vision pass] → "BTC 1d showing 6-week range with climactic low
                                  at $30k on high volume, recovery rally to $38k,
                                  multiple tests of $30k, recent probe below"

Poređenje: tekst-vs-tekst
LLM zaključuje semantičku sličnost:
"Both show SC + recovery + tests + spring sequence — same structural pattern"
```

### 3.3 Šta captions zapravo jesu (tehnički)

Caption je **alt text** (alternativna tekstualna verzija) za sliku u Markdownu:

```markdown
![Accumulation schematic with SC, AR, spring](images/page_142_fig_3.png)
```

Sve od `![` do `](` je caption. To je deo Markdown standardna za accessibility (čitači ekrana, indeksiranje).

U našem projektu, **#5 Vision caption pass** generiše ove caption-e automatski:
1. Loaduje svaku sliku iz `raw/`
2. Šalje je Claude Vision-u sa promptom "opiši ovaj grafik u 1-2 rečenice fokusiraj se na strukturu i fazu"
3. Upisuje rezultat kao alt text

Posle toga je svaki grafik **pretraživ kao tekst** — wiki može da koristi caption za poređenje i ljudski čitalac vidi kratak opis bez gledanja slike.

### 3.4 Zašto je ovo "soft numbers"

Razgovarali smo o pojmu "mekih brojeva" — predstavljanje slike u formatu koji nije tačan piksel-prikaz ali nije ni potpuna verbalna naracija.

Captions su upravo to. Oni:
- Sažimaju vizuelnu informaciju u strukturirane reči
- Omogućavaju **semantic search** (pretraga po značenju)
- Mogu dalje da se enkoduju u **embedding vektore** za similarity search (vidi sekciju 8.2 ML lekcije)
- Su jeftiniji za poređenje od slika

To ne znači da su zamena za sliku. Često je dobro **imati i sliku i caption** — slika za vizuelnu validaciju, caption za pretragu i poređenje.

### 3.5 Šta važi za bilo koji projekat

Princip:
> **Kad god poredjuješ vizuelne objekte koji dolaze iz različitih izvora ili u različitim formatima, generuj tekstualnu reprezentaciju (caption) i poredjuj na nivou teksta.**

Primeri primene van trading-a:
- Medical imaging: poređenje rentgena pacijenta sa knjiškim primerima
- Quality control u industriji: poređenje defekta proizvoda sa katalogom poznatih defekata
- Edukacija: poređenje crteža studenta sa template-ima

---

## 4. LLM vs Vision modeli — šta zapravo "vide"

(**OPŠTE** — pojašnjenje kako moderni multimodalni AI radi)

Diskusija je naslovila ovo, ali da razložimo detaljnije.

### 4.1 Šta je LLM

**LLM** (Large Language Model — veliki jezički model) je neuronska mreža istreniranja na ogromnom korpusu teksta. Modeli kao GPT-4, Claude Opus 4.7, Gemini.

Princip: dat niz tokena (delovi reči), predvidi sledeći token. Ponavlja se autoregresivno → generiše tekst.

**LLM sam vidi samo tokene.** Brojevi, znakovi, reči — sve postaje token, sve se obrađuje istim mehanizmom (attention layers).

### 4.2 Šta je vizuelni model

**Vision encoder** je posebna mreža (često CNN ili Vision Transformer) trenirana da ekstraktuje **vizuelne osobine** iz slika.

Princip:
1. Slika se podeli na patches (16×16 pixel komadi)
2. Svaki patch se konvertuje u embedding vektor
3. Attention layers povezuju patches da uhvate strukturu (linije, oblike, prostorne odnose, tekst u slici)
4. Izlaz: sekvenca embedding vektora koja predstavlja sliku

### 4.3 Šta je multimodalni LLM

Multimodalni LLM kao **Claude Sonnet/Opus sa Vision-om**:
- Ima text decoder (standardni LLM)
- Ima vision encoder
- Embedding vektori iz vision encoder-a se **ubacuju u tok teksta** kao da su tokeni

```
User input: "Šta vidiš?" + [slika]

Internal:
  [tok: 'Š'] [tok: 'ta'] [tok: ' vidiš'] [tok: '?'] [embed_1] [embed_2] ... [embed_256]
                                                    ↑ ovo su iz slike
                                                    
Decoder generiše odgovor: "Vidim grafik BTC..."
```

Decoder ne zna gde se završio tekst a počele slike u embedding prostoru — sve mu je homogen tok vektora. Zato može da "razmišlja" o slici i tekstu zajedno.

### 4.4 Šta znači "AI ne radi konverziju"

Kad korisnik kaže "ali da li interno konvertuje sliku u brojeve?", odgovor je:

**Da, u embedding vektore. Ali to NIJE OHLCV. To su apstraktni vizuelni feature-i** — verovatno hiljade dimenzija, koje predstavljaju vizuelne pattern-e (linije, oblike, boju), ne tržišne vrednosti.

Niko (uključujući istraživače Anthropic-a) ne može da uzme embedding vektor i pročita "ah, ovde je close cena $42,000". Embedding je naučen distributivno i nije čovekovski razumljiv.

### 4.5 Implikacija za naš dizajn

Ne možemo da kažemo: "daćemo agentu sliku grafika, on će ga konvertovati u OHLCV i odatle raditi precizne računice".

Moramo da:
- Dajemo sliku **za pattern recognition**
- Dajemo OHLCV **za precizne računice**
- Ostavimo agentu da odluči koji izvor koristi za koji deo odgovora

Ovo je razlog **hibridne MCP arhitekture** (Faza 2) — i `get_ohlcv()` i `render_chart()`.

---

## 5. Skill vs MCP — slojevi a ne alternative

(**OPŠTE** princip — primenljivo na svaki AI agent projekat)

### 5.1 Naša konfuzija na početku

Postavili smo pitanje: "Da li nam treba skill ako imamo MCP? Ili dva skill-a? Ili samo MCP?"

Rešenje je razdvajanje koncepata.

### 5.2 Skill = mozak (metodologija)

**Skill** (Claude Skill) je strukturirana instrukcija LLM-u kako da pristupi nekoj klasi problema.

Format:
- Markdown fajl (`SKILL.md`) sa workflow-om, pravilima, output contract-om
- Često ima i prateće fajlove (reference, primere)
- Učitava se na početku konverzacije kao deo sistemskog prompta

**Skill ne donosi nove sposobnosti modelu** — samo ga usmerava kako da koristi postojeće.

Primer: bez Wyckoff skill-a, Claude može da priča o Wyckoff metodologiji generičkim rečima. Sa Wyckoff skill-om, Claude zna da:
- Prvo proveri kontekst, ne pattern
- Uvek pruži scenarijo + alternativu, ne predikciju
- Output ima 9 sekcija
- itd.

Iste informacije, ali sa **disciplinom**.

### 5.3 MCP = ruke i oči (sposobnosti)

**MCP** (Model Context Protocol) je standardni protokol koji LLM-ovima daje pristup **alatima i resursima van njegovog konteksta**.

MCP server je **eksterni proces** (Python, Node, bilo šta) koji izlaže **alate** (engleski: *tools*) preko standardnog interfejsa. LLM može da poziva ove alate tokom razgovora.

Primer alata:
- `get_ohlcv(symbol, timeframe)` — pulluje podatke sa Binance API-ja
- `render_chart(data)` — renderuje grafik
- `query_database(sql)` — postavlja upite ka bazi
- `send_email(to, subject, body)` — šalje mejl

**MCP donosi nove sposobnosti modelu** — ono što LLM ne može sam (web pristup, baza, izvršavanje koda).

### 5.4 Suštinska razlika

| Aspekt | Skill | MCP |
|---|---|---|
| Tip artefakta | Markdown / tekst | Pokrenutni proces sa interfejsom |
| Gde "živi" | Inside LLM prompt | Eksterno (na disku, mreži) |
| Šta menja | Kako LLM razmišlja | Šta LLM može da uradi |
| Bez njega | Imaš sposobnosti bez discipline | Imaš disciplinu bez sposobnosti |
| Analogija | Mozak, lekcija, knjiga koju je naučio | Ruke, oči, telefon, Google pretraga |

**Oni se ne isključuju — komplementarni su.**

### 5.5 Naš konkretan dizajn

```
┌────────────────────────────────────────────────────┐
│                                                    │
│   Skill (jedan!)                                   │
│   skills/wyckoff-trader-skill/SKILL.md             │
│   - 4 moda: scenario / concept / diagnostic /      │
│     signal                                         │
│   - Output contracts per mod                       │
│   - Wyckoff methodology rules                      │
│   - "label last", "scenarios not certainties"      │
│                                                    │
│                  ↓ koristi                         │
│                                                    │
│   MCP serveri (više njih)                          │
│   - market_data_server.py    → OHLCV               │
│   - chart_renderer.py        → PNG slike           │
│   - spread_chart.py          → ratio charts        │
│   - portfolio_server.py      → virtual P&L         │
│   - signal_logger.py         → log signala         │
│   - scanner.py               → multi-symbol scan   │
│   - backtest_runner.py       → istorijski testovi  │
│   - classifier_mcp.py        → ML predikcije       │
│                                                    │
└────────────────────────────────────────────────────┘
```

Jedan skill (Wyckoff metodologija) — više MCP servera (svaki za jednu klasu zadataka).

### 5.6 Zašto NE dva skilla

Razmišljali smo da li trebaju dva skill-a — edukativni (kao original) i trading. Ali:

- **Wyckoff metodologija je ista** za edukaciju i trading. Spring je spring, akumulacija je akumulacija.
- Razlika je u **šta agent radi sa tom analizom** — objašnjava (edukacija) ili daje signal sa entry/SL/TP (trading).
- "Šta agent radi" je **mod**, ne **različito znanje**.
- Jedan skill sa 4 moda > dva skill-a sa duplim sadržajem.

**Princip:** **uvek jedan skill po domenu znanja.** Variabilnost output-a hendluj preko **modova** unutar skill-a.

### 5.7 Šta važi za bilo koji projekat

Pre nego što počneš novi AI agent projekat, pitaj:

1. **Šta agent treba da zna?** → to ide u skill (metodologija, vocabulary, workflow, rules)
2. **Šta agent treba da uradi?** → to ide u MCP (alati za akciju)
3. **Da li imamo različite scenarije korišćenja istog znanja?** → modovi u skill-u, ne više skill-ova

---

## 6. Šta je MCP server detaljnije

(**OPŠTE**)

### 6.1 Anatomija MCP servera

MCP server izlaže tri vrste interfejsa:

1. **Tools** (alati) — funkcije koje agent može da pozove (npr. `get_ohlcv()`)
2. **Resources** (resursi) — staticki ili dinamički podaci koji agent može da čita (npr. dokumentacija, fajl)
3. **Prompts** (prompt-ovi) — strukturirani prompt template-i koje agent može da koristi

Najčešće koristimo **tools**.

### 6.2 Komunikacija

MCP servers komuniciraju sa LLM klijentom (Claude Desktop, custom agent) preko:
- **stdio** (standard input/output) — za lokalne servere
- **HTTP / SSE** — za udaljene

Format poruka: **JSON-RPC 2.0** — standardni protokol za remote procedure calls.

Primer poruke od LLM klijenta:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_ohlcv",
    "arguments": {"symbol": "BTC/USDT", "timeframe": "1d", "limit": 200}
  }
}
```

Odgovor:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{"type": "text", "text": "[{\"timestamp\": ..., \"open\": ...}, ...]"}]
  }
}
```

### 6.3 Kako se piše

Postoje SDK-ovi za:
- Python (`mcp-python` paket)
- TypeScript / JavaScript (`@modelcontextprotocol/sdk`)
- I drugi jezici

Pseudo-kod u Pythonu:
```python
from mcp.server import Server
from mcp.types import Tool

server = Server("wyckoff-market-data")

@server.tool()
async def get_ohlcv(symbol: str, timeframe: str, limit: int = 200) -> list:
    """Fetch OHLCV from Binance public API."""
    # ... HTTP request ...
    return ohlcv_list

server.run()
```

LLM klijent automatski "vidi" registrovane alate i može da ih poziva.

### 6.4 Kada NE koristiti MCP

- Ako agent ne treba nove sposobnosti (samo razmišljanje na osnovu prompta) → skill je dovoljan
- Ako je akcija deo browser-a / IDE-a (npr. uređivanje fajla) — možda postoji native tool koji bolje radi
- Ako je akcija tako specifična da ne može da se generalizuje (npr. "klikni na pixel 234, 567") — bolje custom integracija

### 6.5 Open ecosystem

MCP je otvoren standard razvijen od strane Anthropic-a (2024+). Postoje javni referentni serveri:
- Filesystem MCP — čitanje/pisanje fajlova
- GitHub MCP — interakcija sa repoima
- Sentry MCP — error tracking
- Brave Search MCP — web pretraga

Možeš da pišeš sopstvene, kao mi (Wyckoff MCP-ovi).

---

## 7. Šta je Claude Skill detaljnije

(**OPŠTE**)

### 7.1 Struktura skill-a

Claude Skill je folder sa konvencionalnim layout-om:

```
skills/<naziv-skill-a>/
├── SKILL.md              ← obavezan; glavni instrukcioni fajl
├── references/           ← opcionalno; pomoćni materijali
│   ├── glossary.md
│   ├── examples.md
│   └── ...
└── agents/               ← opcionalno; integracioni stub-ovi
    └── openai.yaml       ← za OpenAI Agents SDK
```

### 7.2 SKILL.md sadržaj

Konvencija (na osnovu Claude Code skill formata):

```markdown
---
name: nazi-skill-a
description: Kratak opis kada koristiti skill (1-2 rečenice)
---

# Naslov skill-a

## Overview
Generalni pregled

## When To Use It
Konkretne situacije za invokaciju

## Core Rules
Lista pravila / principa

## Workflow
Korak-po-korak proces

## Output Contract
Šta se očekuje kao izlaz

## References
Linkovi na pomoćne fajlove
```

### 7.3 Skill se ne "izvršava" — interpretira

Skill **nije program**. Skill je **instrukcija LLM-u**. Kad korisnik pomene relevantnu temu (određeno preko `description` polja), Claude Code skill loader doda SKILL.md sadržaj u sistemski prompt.

LLM ga čita kao deo svog "razmišljanja" i prati instrukcije.

To znači:
- Skill može sadržati pseudo-kod, ali samo kao primer (LLM ga neće izvršiti)
- Skill se ne "kompajlira"
- Performanse skill-a zavise od koliko LLM razume prompt — ako napišeš nejasno, neće raditi
- Skill može biti malo (par stranica) ili veliko (više fajlova kao naš sa references/)

### 7.4 Razlika od MCP-a još jednom

| | Skill | MCP |
|---|---|---|
| Tip | Markdown / tekst | Server proces |
| Učitavanje | U prompt na početku | Dinamično, tokom razgovora |
| Šta dobija LLM | Nove instrukcije | Nove sposobnosti |
| Iziska | Samo SKILL.md | Pokrenut proces, SDK |
| Promena u tom skill-u → | LLM odmah prati nova pravila | — |
| Dodavanje MCP tool-a → | — | LLM može da ga poziva |

### 7.5 Best practice za skill-ove

- **Jedan domen po skill-u.** Ne pravi "general assistant" skill — specijalizuj.
- **Output contract obavezno.** Bez jasnog formata izlaza, LLM će svaki put da odgovara drugačije.
- **Workflow ide korak-po-korak**, ne kao opšta pravila.
- **Reference fajlovi** ako skill treba dubinu (vocabulary, dataset, primeri) — ne stavljaj sve u SKILL.md.
- **Test sa stvarnim prompt-ovima.** Ne izlaze li po contractu? Revidiraj skill.

---

## 8. Modovi u skill-u (mode discriminator)

(specifično za naš projekat, ali princip je **OPŠTI**)

### 8.1 Problem

Originalni Wyckoff skill imao je **jedan** output format — 9-sekcijski scenario tree. Primenjivao ga na svako pitanje.

Kad korisnik pita "šta je spring?", dobija punu 9-sekcijsku scenario analizu o springu — sa context, story, evidence, alternates, triggers. **Previše za prosto definicijsko pitanje.**

### 8.2 Rešenje — modovi

Skill prepoznaje **tip pitanja** i koristi različit output format:

| Mode | Trigger | Output |
|---|---|---|
| **Scenario** | "Analiziraj X", "Sagledaj X", "Šta je sledeće za X" | Pun 9-sekcijski contract |
| **Concept** | "Šta je X?", "Definiši X", "Kako radi X?" | Kratka definicija + wiki citacija + jedan worked example |
| **Diagnostic** | "Koja je faza X?", "Da li je ovo spring?" | Verdict + 3-5 evidence bullets + alt verdict |
| **Signal** (Faza 3) | "Daj mi signal za X", "Skeniraj top 20 alts" | Signal sa entry/SL/TP/virtual position |

### 8.3 Kako se mod određuje

U SKILL.md, dodaješ sekciju "Mode discriminator":

```markdown
## Mode discriminator

Pre nego što odgovoriš, identifikuj mod query-ja:
- Ako query sadrži "šta je", "definiši", "objasni" → **Concept mode**
- Ako query sadrži "koja faza", "da li je", "identifikuj" → **Diagnostic mode**
- Ako query sadrži "daj signal", "trade", "skeniraj" → **Signal mode**
- Inače → **Scenario mode** (default)

Output u tom modu prati contract opisan u sekciji ## Output Contract per mode.
```

LLM čita ovo na početku, klasifikuje query, primenjuje odgovarajući format.

### 8.4 Princip koji važi opšte

Bilo koji domen-skill može imati ovaj problem. Kad god ima više vrsta query-ja, ne pravi mega-output koji pokriva sve. Pravi modove.

**Anti-pattern:** "univerzalan output contract koji pokriva sve scenarije". Postaje predug, irelevantan za polovinu query-ja, sporiji.

**Pattern:** mode discriminator + zaseban output per mod.

---

## 9. Provenance i llm-wiki pattern

(**OPŠTE** — Karpathy pattern)

### 9.1 Šta je provenance

**Provenance** (na srpskom: poreklo, izvor) — sposobnost da se za svaku tvrdnju u znanju utvrdi **gde dolazi**.

Loša provenance:
> "Spring je test ispod support-a koji se odmah okrene gore."

Dobra provenance:
> "Spring je test ispod support-a koji se odmah okrene gore. ([wiki: events/spring.md](knowledge/wiki/events/spring.md) → [knjiga str. 142](raw/book/page_142.md))"

Razlika je **proveravost**. Sa dobrom provenance, korisnik može da:
- Otvori wiki stranicu spring-a i pročita kontekst
- Otvori sirov izvor i potvrdi da definicija nije izmišljena
- Ažurira wiki ako se knjiga pojavi u novom izdanju

### 9.2 Karpathy LLM-wiki pattern

Andrej Karpathy je 2024. opisao **llm-wiki pattern** kao način čuvanja domain knowledge za LLM agente.

Princip — **tri sloja**:

```
┌─────────────────────────────────────┐
│  Sloj 1: RAW SOURCES                │
│  Sirovi izvori (knjige, članci,     │
│  raw data) — IMMUTABLE              │
│                                     │
│  Naš: raw/book/, raw/bruce_fraser/, │
│        raw/crypto_archive/          │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  Sloj 2: WIKI                       │
│  LLM-pisan markdown sa citacijama   │
│  - svaka stranica ima provenance    │
│  - LLM održava ovaj sloj            │
│  - kompounduje preko vremena        │
│                                     │
│  Naš: knowledge/wiki/               │
│       concepts/ events/ structures/ │
│       crypto/ scenarios/ sources/   │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  Sloj 3: SCHEMA (CLAUDE.md)         │
│  Domen-specifične konvencije        │
│  - struktura foldera                │
│  - vocabulary                       │
│  - ingest priority                  │
│  - WIKI_GAP marker                  │
│                                     │
│  Naš: /CLAUDE.md                    │
└─────────────────────────────────────┘
```

### 9.3 Zašto je ovo bolje od alternativa

**Alternativa 1: Embeddings + vector DB**

Stari pristup: chunk-uješ dokumente, embed-uješ ih u vector DB, na svako pitanje radiš similarity search.

Mane:
- Skupo (treba embedding model, vector store, infrastruktura)
- Crna kutija (zašto je baš taj chunk vraćen?)
- Loš za relacijske veze (spring je deo Phase C — embedding može da vrati spring chunk ali ne i Phase C chunk)
- Bez ažurnosti (ako se izvori menjaju, treba re-embeddovati sve)

**Alternativa 2: Plain markdown reference (kao originalni Wyckoff skill)**

Skill se referiše na markdown fajlove sa ručno destilovanim sadržajem.

Mane:
- Bez provenance (čovek je distilovao; gde piše šta?)
- Bez kompounding-a (ako naučiš nešto novo, gde to ide?)
- Bez mehaničkog ažuriranja (nov izvor = ručno re-destilovanje)

**Alternativa 3 (llm-wiki): kompromis**

Plain markdown + striktna provenance + LLM održavanje.

Prednosti:
- Bez ekstra infrastrukture (samo fajlovi)
- Provenance ugrađena
- LLM može sam da održava (ingest pipeline)
- Skala do ~hiljade stranica bez problema
- Iznad toga: dodaješ BM25 ili vector search **opciono**

Originalni Karpathy blog ovo karakterizuje kao "moderate scale" pristup — **~100 izvora generišu ~stotine wiki stranica**, bez potrebe za vector DB-em.

Naš slučaj: ~350 izvora (knjige + arhive + Fraser) → ~70 wiki stranica. Sweet spot za ovaj pristup.

### 9.4 Karakteristika koja se prenosi na bilo koji projekat

Ovaj pattern se prenosi na bilo koji **domain-specific LLM assistant**:

- Medical: raw papers + wiki sa medical concepts + schema za citiranje publikacija
- Legal: raw zakoni + wiki sa case interpretacijama + schema za jurisdikcije
- Codebase: raw code + wiki sa architectural concepts + schema za izvor projekta

Ako pravimo nov AI projekat za domen X, **prvo pitanje je** da li ima dovoljan corpus znanja da llm-wiki ima smisla. Ako da, llm-wiki je default izbor.

---

## 10. Faze projekta — zašto baš tri

(specifično za naš projekat)

### 10.1 Šta je vodilo razdvajanje

Originalni `naiemk/wyckoff-ai` skill imao je jednu viziju — **edukativni Wyckoff asistent za crypto**. To je dobar, ograničen scope.

Mi smo poželeli više:
1. Da to bolje uradimo (provenance, slike, modovi) — **upstream-kompatibilno**
2. Da agent može sam da pulluje grafike — **MCP layer**
3. Da agent može da simulira trading i nauči iz istorije — **trading + ML**

Tri različita bratstva.

### 10.2 Šta je bilo alternativno

Mogli smo:
- **Jedan veliki PRD** sa svih 3 brata u jednom dokumentu → konfuzno, scope creep
- **Više malih PRD-ova po milestone-u** (M1, M2, M3, M4, M5, M6) → previše dokumenata, hard to see big picture
- **Tri PRD-a po bratstvu** ← izabrali smo ovo

### 10.3 Granice između faza

Bitno je da granice budu **observable** (vidljive iz spolja) i **decidable** (može da se utvrdi da li je granica prešla):

**Faza 1 → Faza 2 granica:**
- Observable: PR otvoren protiv `naiemk/wyckoff-ai`
- Decidable: ima ili nema PR

**Faza 2 → Faza 3 granica:**
- Observable: agent može autonomno da odgovori na "Analyze BTC 1d" sa samo simbol-input-om
- Decidable: pokreneš query, gledaš da li MCP tool-call trace postoji

**Faza 3 → kraj granica:**
- Observable: classifier MCP daje predikciju koju agent integriše
- Decidable: query agentu, vidi da li u outputu cita ML prediction

### 10.4 Princip — granice se određuju output-om, ne radom

**Anti-pattern:** "Faza 1 je gotova kad imamo wiki." (Šta to znači? Kakav wiki?)
**Pattern:** "Faza 1 je gotova kad E2E validacija (#13) prolazi na ≥6 od 8 prompt-ova." (Konkretno, merljivo.)

Ovo je opšti princip projekt menadžmenta — definiraj **acceptance kriterijum** za svaku fazu, ne samo "skup zadataka".

---

## 11. Generalno vs specifično — sažetak

Tabela koja sumira: koji koncepti su prenosivi na bilo koji projekat, a koji su specifični za Wyckoff AI.

### Opšte (primenljivo na bilo koji AI agent projekat)

| Koncept | Sekcija | Sažetak |
|---|---|---|
| Slike vs brojevi za AI | §1 | Vision za pattern recognition, brojevi za preciznost, kombinuj oboje |
| Vision captions kao most | §3 | Tekstualni opisi slika omogućavaju semantic poređenje |
| LLM vs Vision modeli — šta zapravo "vide" | §4 | Multimodalni LLM-ovi obrađuju embeddinge, ne tačne konverzije |
| Skill vs MCP — slojevi | §5 | Skill = mozak (metodologija), MCP = ruke i oči (sposobnosti) |
| MCP server arhitektura | §6 | Standardni protokol za alate, resurse, prompt-ove |
| Claude Skill arhitektura | §7 | Strukturirani sistemski prompt, jedan po domenu |
| Modovi u skill-u | §8 | Mode discriminator > univerzalni output format |
| Provenance i llm-wiki | §9 | Tri sloja: raw → wiki → schema; sweet spot ~100-1000 izvora |
| Granice faza — observable + decidable | §10 | Acceptance kriterijum, ne lista zadataka |

### Specifično za naš Wyckoff AI projekat

| Koncept | Sekcija | Sažetak |
|---|---|---|
| OHLCV format | §2 | Open/High/Low/Close/Volume — standard za tržišne podatke |
| Specifični modovi u skill-u | §8 | Scenario / Concept / Diagnostic / Signal — naših 4 |
| Wiki layout (concepts/, events/, structures/, crypto/, scenarios/, sources/) | §9 (kontekstualno) | Wyckoff-domen specifična podela |
| Faze 1/2/3 i zašto baš te 3 | §10 | Faza 1 = upstream-kompatibilna, Faza 2 = MCP, Faza 3 = trading + ML |

### Najveći takeaway-ovi

Ako ti sve ovo treba da prevedeš u **5 principa** za buduće projekte:

1. **Skill je mozak, MCP je ruke.** Razdvoji metodologiju od sposobnosti.
2. **Mode discriminator > univerzalni output.** Različita pitanja zaslužuju različite formate.
3. **Provenance je obavezna** za bilo koje LLM znanje koje će se koristiti dugoročno.
4. **Slika + brojevi + tekst, ne samo jedno.** Daj LLM-u sve formate, neka sam bira.
5. **Granice faza su acceptance kriterijumi, ne zadaci.** Observable + decidable.

---

## Sledeći korak

Sad imaš:
- [`01-masinsko-ucenje.md`](./01-masinsko-ucenje.md) — uvod u ML i šta od fitness trackera ide u Fazu 3
- Ovaj fajl — koncepti i arhitektura koje su nas vodile do PRD-ova
- [`.claude/PRPs/prds/README.md`](../../.claude/PRPs/prds/README.md) — pregled svih 3 PRD-a (srpski)
- [`.claude/PRPs/prds/faza-1-skill-modernization.prd.md`](../../.claude/PRPs/prds/faza-1-skill-modernization.prd.md) — Phase 1 detalji
- [`.claude/PRPs/prds/faza-2-live-market-analysis.prd.md`](../../.claude/PRPs/prds/faza-2-live-market-analysis.prd.md) — Phase 2 detalji
- [`.claude/PRPs/prds/faza-3-trading-and-ml.prd.md`](../../.claude/PRPs/prds/faza-3-trading-and-ml.prd.md) — Phase 3 detalji

Kad budeš spreman da nastaviš implementaciju Faze 1, otvori kildove (komande u glavnoj konverzaciji).
