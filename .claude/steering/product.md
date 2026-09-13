# Product direction — Wyckoff AI

## Svrha projekta

Wyckoff AI treba da proveri i, samo ako dokazi to podrže, izgradi sistem koji koristi Wyckoff
znanje da protumači tržišni grafikon do preseka vremena `T`. Sistem treba da obrazloži strukturu,
fazu, događaje, alternativne scenarije i uslove koji bi potvrdili ili oborili analizu.

Centralna hipoteza projekta je proverljiva: LLM koji dobije kvalitetno Wyckoff znanje i relevantne
prethodne ekspertske primere može da napravi analizu približnu ljudskom ekspertu, a njegovi uslovni
scenariji mogu kasnije da se provere prema kretanju posle `T`.

Projekat još nije dokazao ovu hipotezu. Wiki ingest, izbor modela i Docling pilot služe pripremi
korpusa. Oni nisu dokaz sposobnosti predviđanja tržišta.

## Dva odvojena wikija

### Glavni Wyckoff wiki

`knowledge/wiki/` je baza teorije i sintetizovanog domenskog znanja. Sadrži Wyckoff zakone,
koncepte, događaje, faze, strukture, crypto prilagođavanja i scenario ugovore izvedene iz knjige,
Bruce Fraser tekstova i crypto arhive.

Glavni wiki odgovara na pitanje: „Koja pravila, pojmove i obrasce sistem treba da zna?“

### Wiki ekspertskih analiza

`research/expert-analyses/wiki/` je korpus konkretnih primera. Svaki validan extract povezuje:

- lokalni izvor i tačan pasus ekspertske analize;
- odgovarajući grafikon ili shemu;
- asset i timeframe kada su poznati;
- Wyckoff događaj, strukturu, fazu i tip analize;
- status i proverljivu provenijenciju.

Ekspertski wiki odgovara na pitanje: „Kako je ekspert primenio Wyckoff znanje na ovom konkretnom
grafikonu?“ Ne sme da postane druga kopija teorijskog wikija.

## Kako se wikiji kasnije koriste zajedno

U završnom tržišnom testu model dobija glavni wiki kao teorijsku osnovu i samo ranije ekspertske
primere koji nisu ciljni slučaj. Model dobija grafikon ili OHLCV podatke samo do vremena `T`.

Ciljna ekspertska analiza ostaje skriven etalon. Podaci posle `T` takođe ostaju skriveni i služe
kao odvojen etalon realizovanog ishoda. Time merimo dve različite stvari:

1. koliko je modelova analiza slična ekspertovoj analizi;
2. koliko su modelovi uslovni scenariji saglasni sa kasnijim tržišnim kretanjem.

Sličnost sa ekspertom sama po sebi ne dokazuje prediktivnu vrednost. Realizovani ishod bez dobrog
obrazloženja takođe nije dovoljan, jer može biti slučajan pogodak.

## Granice i pravila odluke

- Ne menjati više promenljivih u istom poređenju. Modeli dele isti ulaz, prompt i evaluator;
  pretprocesori dele isti model, dokumente i evaluator.
- Ne birati model samo po utisku ili jednom lepom primeru. Čuvati semantički skor, provenijenciju,
  greške, potrošnju tokena i cenu.
- Izbor strukturnog pretprocesora zasniva se na provenance i A/B dokazima; aktuelna odluka je u
  `tech.md` i povezanom ADR-u.
- Ne dozvoliti ciljnoj ekspertskoj analizi, anotacijama ili budućim svećama da uđu u analyst
  kontekst.
- Ne predstavljati sistem kao signal feed niti kao dokazan alat za trgovanje dok eval to ne pokaže.
