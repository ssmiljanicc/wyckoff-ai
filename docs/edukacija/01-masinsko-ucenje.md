# Mašinsko učenje — od nule do našeg projekta

> Detaljna lekcija za nekoga ko ne zna ništa o mašinskom učenju. Vodi te od osnovnih pojmova do tehnika koje koristi `razni-tutorijali/ml-fitness-tracker` repo, i objasnjava šta od toga ulazi u naš Wyckoff AI projekat i kako.
>
> **Strana terminologija** je svuda gde je domena to zahteva, ali svaki engleski pojam je preveden i objašnjen kad se prvi put pojavi. Pojmovnik je na kraju.

---

## Sadržaj

1. [Šta je mašinsko učenje (ML)](#1-sta-je-masinsko-ucenje-ml)
2. [Tri velike grane ML-a](#2-tri-velike-grane-ml-a)
3. [Pojmovnik osnovnih pojmova](#3-pojmovnik-osnovnih-pojmova)
4. [Posebnost rada sa vremenskim serijama](#4-posebnost-rada-sa-vremenskim-serijama)
5. [Pregled `ml-fitness-tracker` repoa](#5-pregled-ml-fitness-tracker-repoa)
6. [Tehnike iz repoa — detaljno](#6-tehnike-iz-repoa--detaljno)
7. [Šta od ovoga ide u naš projekat](#7-sta-od-ovoga-ide-u-nas-projekat)
8. [Šta NE ide (za sada) i zašto](#8-sta-ne-ide-za-sada-i-zasto)
9. [Naš ML pipeline plan](#9-nas-ml-pipeline-plan)
10. [Pojmovnik (glossary)](#10-pojmovnik-glossary)

---

## 1. Šta je mašinsko učenje (ML)

### 1.1 Šta NIJE mašinsko učenje

Klasično programiranje izgleda ovako:

```
Pravila (kod koji čovek piše) + Podaci  →  Odgovori
```

Primer: imaš podatke o vremenu, čovek piše pravilo "ako temperatura > 25°C piši 'toplo'". Program primeni pravilo i da odgovor.

Problem: ima problema gde **čovek ne ume jasno da napiše pravilo**. Kako napisati pravilo za:
- "Da li ova slika sadrži mačku?"
- "Da li je ovaj email spam?"
- "Da li je grafik BTC-a u akumulaciji ili distribuciji?"

Pravila su prekomplikovana ili ne postoje u jasnom obliku.

### 1.2 Šta JESTE mašinsko učenje

Mašinsko učenje preokreće formulu:

```
Podaci + Odgovori  →  Pravila (model koji program uči sam)
```

Daješ kompjuteru **mnogo primera ulaza i tačnih izlaza**, i on **sam pronađe obrazac** (engleski: *pattern*) koji povezuje ulaz sa izlazom. Taj naučeni obrazac se zove **model** (engleski: *model*, **isti termin se koristi i u srpskom**).

Primer iz fitness trackera:
- Senzor (akcelerometar) na ruci snima 6 brojeva (3D ubrzanje + 3D rotacija) 25 puta u sekundi dok osoba radi vežbe
- Za svaki snimak, čovek označi: "ovo je squat", "ovo je deadlift", "ovo je bench press"
- ML model gleda hiljade takvih označenih snimaka i nauči **bez eksplicitnih pravila** kakav obrazac ima svaki tip vežbe
- Kasnije, dobije nesnimljen niz brojeva i može da predvidi: "ovo je 90% verovatno squat"

### 1.3 Zašto je ovo važno za nas

Wyckoff metodologija ima sličan problem:
- Čovek može da pogleda grafik i kaže "ovo je akumulacija u fazi B" — ali pravila su intuitivna, ne mehanička
- Postoji **mnogo primera** (knjiga, Fraser arhiva, krypto arhiva — sve to dolazi sa labelama tipa "vidiš li spring ovde?")
- Ako napravimo ML model koji nauči iz tih primera, on bi mogao da automatski klasifikuje fazu sa OHLCV podataka

To je suština **Faze 3** našeg projekta.

---

## 2. Tri velike grane ML-a

ML se deli na tri glavna pristupa, koja se razlikuju po **kakvom obliku su odgovori**.

### 2.1 Supervised learning — učenje sa nadzorom

**Definicija:** imaš ulaze **i** tačne odgovore (engleski: *labels* = labele, oznake). Model uči da mapira ulaz na odgovor.

Tip problema:
- **Klasifikacija** (engleski: *classification*) — odgovor je iz konačnog skupa kategorija (squat / deadlift / bench press; spam / nije spam; akumulacija / distribucija)
- **Regresija** (engleski: *regression*) — odgovor je broj na kontinuiranoj skali (predviđanje cene BTC-a za 30 dana, predviđanje težine osobe iz visine)

**Najpoznatiji algoritmi:**
- **Random Forest** (slučajna šuma) — pravi stotine "stabala odluke" i glasanjem dolazi do predikcije
- **Support Vector Machine** (SVM, mašina sa potpornim vektorima) — pronalazi hiperravan koja najbolje deli klase
- **K-Nearest Neighbors** (KNN, K najbližih suseda) — "kakvi su ti susedi u prostoru karakteristika, taj si i ti"
- **Neural networks** (neuronske mreže) — slojevi simuliranih neurona; deep learning je ovo na steroidima
- **Decision Tree** (stablo odluke) — niz "if-then" pitanja koja vode do odgovora
- **Naive Bayes** (Bajesov klasifikator) — koristi teorema verovatnoće da nađe najverovatniju klasu

**Fitness tracker koristi ovo.** I naš ML deo (Faza 3) takođe — klasifikacija faze (A/B/C/D/E) sa OHLCV podataka.

### 2.2 Unsupervised learning — učenje bez nadzora

**Definicija:** imaš samo ulaze, **bez labela**. Model traži strukturu sam — grupe sličnih ulaza, anomalije, dimenzije.

Tip problema:
- **Klasterovanje** (engleski: *clustering*) — pronaći prirodne grupe (koji kupci se slično ponašaju?)
- **Smanjenje dimenzija** (engleski: *dimensionality reduction*) — sažeti 100 promenljivih u 5 koje čuvaju većinu informacije
- **Detekcija anomalija** (engleski: *anomaly detection*) — naći podatke koji "odudaraju" od ostalih

**Najpoznatiji algoritmi:**
- **K-Means** — podeli podatke u K klastera tako da svaki klaster minimizuje rastojanje od centra
- **PCA** (Principal Component Analysis, analiza glavnih komponenti) — pronađe najinformativnije pravce u podacima i odbaci ostatak
- **DBSCAN** — klasterovanje gustinom (dobar za nepravilne oblike)

**Fitness tracker koristi K-Means i PCA.** U našem projektu, ovo bi bilo korisno za:
- Grupisanje "sličnih tržišnih stanja" (klaster 7 = "BTC pre haltinga", klaster 12 = "altcoin sezona", itd.)
- Smanjenje 30+ feature-a (vidi sekciju 6) na nekoliko ključnih

### 2.3 Reinforcement learning — pojačano učenje

**Definicija:** agent **interaguje** sa okruženjem, dobija **nagrade** za dobre akcije i **kazne** za loše, i uči strategiju koja maksimizuje ukupnu nagradu.

Primeri: igranje šaha, Go-a, samovozeci automobili.

**Mi NE koristimo ovo.** Pominje se samo radi kompletnosti — moglo bi se primeniti kasnije za trading strategiju, ali to je daleko van scope-a Faze 3. Klasifikator faze + rule-based strategija je dovoljna.

---

## 3. Pojmovnik osnovnih pojmova

Pre nego što uđemo u tehnike, treba razumeti rečnik:

### 3.1 Feature (karakteristika, atribut)

**Definicija:** jedna brojčana veličina koju model koristi kao ulaz.

Primer u fitness trackeru:
- Trenutno ubrzanje na X osi
- Rolling mean ubrzanja na Y osi u poslednjih 100 uzoraka
- FFT amplituda za frekvenciju od 2.5Hz

Primer u našem projektu:
- 20-bar SMA (simple moving average, jednostavna pokretna sredina) close cene
- 20-bar standardna devijacija (volatilnost)
- Odnos body/range poslednjeg bara
- Volume relative to 20-bar volume MA

**Feature vector** (vektor karakteristika) = niz svih feature-a za jedan trenutak. Npr. ako imaš 30 feature-a, feature vector je broj dimenzija 30.

### 3.2 Label (labela, oznaka, ciljna vrednost)

**Definicija:** tačan odgovor za trening primer. Onaj koji model pokušava da predvidi.

Fitness tracker: `"squat"` ili `"deadlift"`.
Naš projekat: `"Phase A"`, `"Phase B"`, `"Phase C"`, `"Phase D"`, `"Phase E"`.

Engleski sinonimi: *target*, *class label*, *ground truth* (osnovna istina).

### 3.3 Training set i test set

**Trening skup** (engleski: *training set*) — podaci na kojima model uči obrazac.
**Test skup** (engleski: *test set*) — podaci koje model NIJE video tokom učenja; koriste se da se proveri da li je naučio nešto stvarno korisno ili samo "zapamtio" trening podatke.

Tipičan odnos: 80% trening, 20% test. Ili 70/15/15 (trening, **validacioni** skup, test).

**Validacioni skup** (engleski: *validation set*) — koristi se za podešavanje hiperparametara (vidi 3.7) **tokom** treniranja.

### 3.4 Overfitting (prenaučenost)

Model je naučio **previše specifično** trening podatke i ne ume da generalizuje na nove.

Analogija: učenik koji je naučio 100 ispitnih pitanja napamet, ali kad dobije slično pitanje formulisano drugačije, ne ume.

**Znaci overfittinga:**
- Visoka tačnost (engleski: *accuracy*) na trening setu (99%)
- Mnogo niža tačnost na test setu (60%)

**Kako se borimo:**
- Više podataka
- Jednostavniji model
- Regularizacija (penalizovanje preteranih parametara)
- Cross-validation (vidi 3.6)

### 3.5 Underfitting (nedovoljno naučeno)

Suprotno — model je **prejednostavan**, ne može da uhvati obrazac.

Znaci:
- Niska tačnost na trening setu (60%)
- Slično niska tačnost na test setu (55%)

**Kako se borimo:**
- Složeniji model
- Bolji feature-i
- Više vremena treniranja

### 3.6 Cross-validation (unakrsna validacija)

Tehnika za pouzdanije ocenjivanje modela:

1. Podeli trening podatke u **K delova** (npr. K=5)
2. Treniraj na 4 dela, testiraj na 1
3. Ponovi to 5 puta (svaki put drugi deo je test)
4. Uprosečiš 5 rezultata

**Zašto?** Jedan random podelak može da daje optimistične ili pesimistične rezultate. K-fold cross-validation smanjuje tu varijansu.

`GridSearchCV` iz fitness trackera radi tačno ovo + traženje najboljih hiperparametara.

### 3.7 Hyperparameter (hiperparametar)

**Parametar modela** — broj koji model **uči** iz podataka (npr. težine u neuronskoj mreži).
**Hiperparametar** — broj koji **ti biraš pre** nego što počneš treniranje (npr. koliko stabala u Random Forest-u, koja stopa učenja u neuronskoj mreži).

Hiperparametri se traže **eksperimentisanjem** — probaš mnogo kombinacija, vidiš koja daje najbolji rezultat na validacionom skupu. `GridSearchCV` automatizuje to.

### 3.8 Loss / Cost function (funkcija gubitka)

Broj koji meri **koliko je model loš**. Trening je proces **minimizovanja gubitka**.

Klasifikacija: tipično **cross-entropy loss**.
Regresija: tipično **mean squared error** (MSE, srednja kvadratna greška).

Ne treba duboko ulaziti za sada — Random Forest i scikit-learn ovo rešavaju ispod haube.

### 3.9 Accuracy, Precision, Recall, F1

Metrike za ocenjivanje klasifikatora.

Zamisli problem: imamo 1000 grafika, 100 su springs (pozitivni), 900 nisu (negativni). Model klasifikuje:

|  | Stvarnost: Spring | Stvarnost: Nije spring |
|---|---|---|
| Model: Spring | 80 (TP — true positive) | 50 (FP — false positive) |
| Model: Nije spring | 20 (FN — false negative) | 850 (TN — true negative) |

**Accuracy** (tačnost) = (TP + TN) / sve = (80+850)/1000 = 93%

**Precision** (preciznost) = TP / (TP + FP) = 80 / (80+50) = 62%
"Kad model kaže 'spring', koliko često je u pravu?"

**Recall** (osetljivost) = TP / (TP + FN) = 80 / (80+20) = 80%
"Koliko stvarnih springova model uspe da uhvati?"

**F1** = harmonijska sredina precision i recall = 0.70
Korisno kad imaš class imbalance (vidi 3.10) — accuracy može da bude varljiva (model koji uvek kaže "nije spring" ima 90% accuracy bez ikakve korisnosti).

### 3.10 Class imbalance (neravnoteža klasa)

Kad jedna klasa ima mnogo više primera od druge.

Wyckoff primer: Phase B traje 4-8 nedelja, Phase C 1-3 dana. U random sampling-u tržišta, **ogromna većina trenutaka je u Phase B**. Klasifikator koji uvek kaže "Phase B" će imati visoku accuracy ali biti beskoristan.

**Kako se borimo:**
- **Class weights** (težine klasa) — kažeš modelu "greške na Phase C su 10x skuplje od grešaka na Phase B"
- **Oversampling** (vise-uzorkovanje) retke klase: SMOTE (Synthetic Minority Over-sampling Technique) generiše sintetičke primere retke klase
- **Undersampling** (manje-uzorkovanje) česte klase: nasumice izbaciš deo Phase B primera

### 3.11 Confusion matrix (matrica konfuzije)

Tabela kao u 3.9 — pokazuje gde model meša klase. Ovo je **najinformativnija jedna grafika** za ocenu klasifikatora.

Primer:

```
                 Predicted:
                 A    B    C    D    E
Actual:  A   [  45   8    2    0    1 ]   ← model dobro vidi A
         B   [  10  130  20    5    0 ]   ← model često zameni A i B (10) ali većinom prepozna B
         C   [   2  15   38    8    2 ]   ← C teško prepoznaje (samo 38 od 65)
         D   [   0   5    7   60   10 ]
         E   [   1   1    1   12   55 ]
```

Vidi se gde su problemi. C je najteža klasa za prepoznavanje.

---

## 4. Posebnost rada sa vremenskim serijama

Klasičan ML pretpostavlja da su primeri **nezavisni** (IID = independent and identically distributed). Za time series to **nije tačno**:

- Današnji bar OHLCV zavisi od jučerašnjeg
- Cene imaju memoriju, trendove, autokorelaciju
- Trening podaci ne mogu da se "izmešaju" nasumice — vreme se ne sme bacati

### 4.1 Walk-forward validation (validacija u napred)

**Pogrešan pristup:** random split. Stavi nasumice 80% bara u trening, 20% u test → leakage (curenje) iz budućnosti u prošlost. Model "vidi" buduće informacije tokom treninga.

**Pravi pristup:** strogi vremenski split.

```
2020 ─────────── 2023 │ 2024 ─── 2025
       trening         │     test
       (4 godine)      │   (2 godine)
                       ↑
              cutoff vremena
```

Ili **walk-forward** (rolling):

```
Pass 1: train 2020-2022 → test 2023
Pass 2: train 2020-2023 → test 2024
Pass 3: train 2020-2024 → test 2025

Uprosečiš rezultate iz 3 pass-a.
```

**Bitno** za naš projekat: ovo MORA biti walk-forward. Inače dobiješ overoptimistic rezultate koji ne važe na stvarnom tržištu.

### 4.2 Feature engineering za time series

Sirov OHLCV (5 brojeva po bar-u) nije dovoljan ulaz. Treba **izgraditi feature-e** koji sumarizuju vremenski kontekst:

- **Rolling stats** (statistike u kliznom prozoru): mean, std, max, min poslednjih N bar-ova
- **Lags** (zaostajanja): vrednost cene/volumena pre N bar-ova kao feature
- **Cycles** (ciklusi): preko FFT-a (vidi 6.6) ekstrahuješ dominantne periode
- **Volatility**: kvantifikacija "koliko se cena pomera"
- **Trend slope** (nagib trenda): koliko brzo SMA raste/pada
- **Relativni odnosi**: današnji volume kao odnos prema 20-bar prosečnom

Ovo je tačno ono što fitness tracker radi sa svojom `TemporalAbstraction.py` i `FrequencyAbstraction.py`. Vidi sekciju 6.

### 4.3 Stationarity (stacionarnost)

**Stacionarni signal** = statistika (mean, variance) ne menja se kroz vreme.
**Nestacionarni signal** = menja se — tipično za cene (BTC je 2017. bio na $1k, danas na $50k).

ML modeli rade bolje na **stacionarnim ulazima**. Trik: ne koristi sirove cene, već **promene**:
- Log-returns: `log(close_t / close_{t-1})` umesto `close_t`
- Procentualne promene
- Razlike

To se zove **diferenciranje** (differencing). Standardan korak feature engineering-a u finance ML.

---

## 5. Pregled `ml-fitness-tracker` repoa

Repo: https://github.com/razni-tutorijali/ml-fitness-tracker

Cilj projekta: snimaš pokrete sa nosivim senzorom (akcelerometar + žiroskop na ruci), ML predviđa koju vežbu radiš (squat, bench press, deadlift, overhead press, row).

### 5.1 Struktura repoa (cookiecutter-data-science šablon)

```
ml-fitness-tracker/
├── data/                        ← podaci u različitim fazama
│   ├── raw/                     ← sirovi senzorski snimci (CSV, JSON)
│   ├── interim/                 ← srednji koraci (čišćeni, outlieri uklonjeni)
│   └── processed/               ← finalni dataset za trening
├── notebooks/                   ← Jupyter notebook-ovi za eksperimentisanje
├── models/                      ← sačuvani trenirani modeli (.joblib, .pkl)
├── reports/                     ← evaluacije, grafici, klasifikacioni izveštaji
├── references/                  ← referentne knjige, papers
├── src/                         ← kod
│   ├── data/                    ← skripte za učitavanje podataka
│   │   ├── make_dataset.py      ← spajanje sirovih senzora u DataFrame
│   │   └── yt_download.py
│   ├── features/                ← feature engineering
│   │   ├── build_features.py    ← orchestrator
│   │   ├── DataTransformation.py    ← LowPassFilter, PCA
│   │   ├── TemporalAbstraction.py   ← rolling stats
│   │   ├── FrequencyAbstraction.py  ← FFT
│   │   └── remove_outliers.py       ← Chauvenet's criterion
│   ├── models/                  ← treniranje i predikcija
│   │   ├── train_model.py
│   │   ├── predict_model.py
│   │   └── LearningAlgorithms.py    ← skupina scikit-learn klasifikatora
│   └── visualization/           ← grafici
├── pyproject.toml / requirements.txt
└── README.md
```

### 5.2 Pipeline koji repo gradi

Ovo je tipičan **ML pipeline** (cevovod):

```
1. Učitaj sirove senzore      → src/data/make_dataset.py
2. Ukloni outliere             → src/features/remove_outliers.py (Chauvenet)
3. Imputacija (popuni rupe)    → interpolation
4. Smoothing (smanji šum)      → DataTransformation.LowPassFilter
5. Smanjenje dimenzija         → DataTransformation.PrincipalComponentAnalysis
6. Temporal abstraction        → TemporalAbstraction.NumericalAbstraction (rolling)
7. Frequency abstraction       → FrequencyAbstraction.FourierTransformation
8. Sastavi finalni dataset     → src/features/build_features.py
9. Treniraj modele             → src/models/train_model.py
                                    koristi LearningAlgorithms (MLP, SVM, KNN, ...)
                                    sa GridSearchCV za hyperparametre
10. Evaluiraj                   → reports/
```

### 5.3 Inspiracija (originalno akademsko delo)

Repo je zasnovan na knjizi **"Machine Learning for the Quantified Self"** (Hoogendoorn & Funk, 2017, Springer). Mnogi fajlovi (`TemporalAbstraction.py`, `FrequencyAbstraction.py`) su iz Chapter 4 te knjige.

Ovo je **standardna metodologija za time-series ML** — ne nešto eksperimentalno. Iste tehnike se koriste u IoT, biomedicini, finansijama, predviđanju proizvodnje.

---

## 6. Tehnike iz repoa — detaljno

Sad ulazimo u svaki korak pipeline-a sa primerima.

### 6.1 Data pipeline (raw → interim → processed)

**Princip:** podaci prolaze kroz **slojeve** gde svaki sloj radi jednu vrstu transformacije. Sirovi podaci se nikad ne menjaju.

```
data/raw/
  acc_x_2020-01-15.csv    ← akcelerometar, X-osa, surov snimak
  ...
        ↓ make_dataset.py
data/interim/
  01_data_processed.pkl   ← spojeni svi senzori u jedan DataFrame
        ↓ remove_outliers.py
  02_outliers_removed.pkl ← outliers uklonjeni
        ↓ build_features.py
data/processed/
  03_data_features.pkl    ← finalni dataset sa svim engineered feature-ima
```

**Format `.pkl`** = Python pickle, binarni snapshot pandas DataFrame-a. Brže učitavanje od CSV-a.

**Zašto slojevi a ne jedna mega-skripta?** Reprodukcija. Ako u koraku 4 nešto pogrešiš, vraćaš se na `interim/02_*` i nastavljaš odatle, ne moraš opet da pokreneš sve od početka.

**Mi ćemo koristiti isti pristup u Fazi 3 — vidi `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md`.**

### 6.2 Outlier removal — Chauvenet's criterion

**Šta je outlier:** podatak koji "odudara" od ostalih do mere da ga treba ukloniti pre obrade. Npr. senzor je glitchovao i snimio 9999 umesto 1.2.

**Chauvenet-ov kriterijum** (Chauvenet's criterion): statistički test za uklanjanje outliera.

**Princip:**
1. Pretpostavi da podaci dolaze iz normalne raspodele (Gauss-ova zvonka kriva)
2. Za svaku tačku izračunaj koliko je daleko od proseka u standardnim devijacijama
3. Izračunaj **verovatnoću** da bi tačka tako daleko bila viđena u N pokušaja
4. Ako je ta verovatnoća < 1/(2N), izbaci je

Formula: izbaci `x_i` ako `P(|X - mean| > |x_i - mean|) < 1/(2N)`.

**Praktično:** za N=1000 podataka, izbacujemo sve preko ~3.3 standardne devijacije.

**Primer:**
```python
import numpy as np
import scipy.stats as stats

def chauvenet(values):
    mean = values.mean()
    std = values.std()
    N = len(values)
    threshold = 1 / (2 * N)
    
    # za svaku tačku, izračunaj p
    z_scores = np.abs((values - mean) / std)
    probabilities = 2 * (1 - stats.norm.cdf(z_scores))
    
    mask = probabilities >= threshold
    return values[mask]  # zadržavamo samo non-outliere
```

**U našem projektu** — primenićemo na sirov OHLCV. Cilj: izbaciti **flash crash bar-ove**, **fat-finger bar-ove**, **glitched ticks**. Detektovani outlieri se ne brišu uvek (mogu biti stvarni!), ali se barem flag-uju za pažnju.

### 6.3 Imputation (popunjavanje rupa) — interpolation

**Šta je rupa:** nedostajuća vrednost u podacima. Senzor je za par sekundi izgubio konekciju, OHLCV nije zabeleženo zbog pauze na berzi.

**Tehnike popunjavanja:**
- **Forward fill** — kopiraj poslednju poznatu vrednost
- **Backward fill** — kopiraj prvu sledeću vrednost
- **Linear interpolation** — povuci pravu liniju između dve poznate tačke i izračunaj međuvrednosti
- **Spline interpolation** — kao linearno ali sa krivama (smoothiji)

Fitness tracker koristi **pandas `.interpolate()`** koji defaultno radi linearnu interpolaciju.

**U našem projektu** — OHLCV sa Binance-a obično nema rupa (24/7 tržište), ali za neke alts ili manje frekventne timeframe-ove (npr. nedeljni) može doći do nedostajućih vrednosti. Linear interpolation je dovoljna za retke slučajeve.

### 6.4 Low-pass filter — smanjivanje šuma

**Šta je šum:** brze, slučajne fluktuacije koje ne nose informaciju o stvarnom trendu.

Akcelerometar dok stojiš mirno: `9.81 ± 0.05` (vrednost zbog gravitacije). Tih ±0.05 je šum (vibracije, elektronika, mikropokreti tela).

**Low-pass filter** (filter niskih frekvencija): propušta sporije promene, blokira brze. Analog je smoothing.

**Najjednostavniji:** moving average (pokretna sredina).
```
filtered[i] = mean(raw[i-N], ..., raw[i])
```

Sofisticiranije: **Butterworth filter** (matematički definisan, zadrži amplitudu sporih promena, prigušuje brze).

Fitness tracker koristi `LowPassFilter` iz `DataTransformation.py` koji je Butterworth.

**U našem projektu:** OHLCV već je u suštini "diskretizovano" tržište (svaka 1d sveća je sumarizacija 24h). Dodatno smoothing-uju se MA-ovi (klasično TA). Možda ne treba poseban filter — već imamo rolling means u feature setu.

### 6.5 PCA — Principal Component Analysis

**Problem:** imaš 30 feature-a po primeru. Neki su jako korelisani (rolling_mean_5, rolling_mean_10, rolling_mean_20 su slični). Model se buni, treniranje sporije.

**PCA** uradi sledeće:
1. Pronađe **pravce** u 30-dimenzionalnom prostoru gde su podaci najviše rasipani (najviša varijansa)
2. Te pravce zove **glavne komponente** (principal components, PC1, PC2, PC3, ...)
3. Sortira ih po važnosti (PC1 sadrži najviše informacija, PC2 manje, itd.)
4. Možeš da odbaciš poslednje (npr. zadržiš samo PC1-PC5)

Rezultat: 30 feature-a → 5 PC-a sa minimalnim gubitkom informacija.

**Vizualizacija (2D primer):**
```
Original podaci (X, Y koreliсаны):
Y │     . . .
  │   . . . .
  │ . . . .
  │_______________ X

PCA pronađe:
- PC1 = pravac duž "dijagonale" (gde je najviše varijanse)
- PC2 = pravac upravan na PC1

Ako odbaciš PC2, podaci su sad 1-D ali zadrže veliki deo strukture.
```

**Matematički:** PCA je eigenvalue decomposition kovarijanske matrice.

**U našem projektu:** koristićemo PCA **opciono**. Sa OHLCV-derivanim feature-ima (~30 ukupno) možda nije neophodno smanjivanje, ali je dobar dijagnostički alat — koliko ti je stvarno feature-a potrebno?

### 6.6 Temporal abstraction — rolling stats

Datoteka: `src/features/TemporalAbstraction.py` u fitness trackeru. Zasnovana na Chapter 4 knjige Hoogendoorn & Funk.

**Šta radi:** za svaku tačku u vremenskoj seriji, izračuna **statistike u kliznom prozoru** prethodnih N tačaka.

```python
window = 100  # prethodnih 100 uzoraka

# za svaki uzorak i:
rolling_mean[i] = mean(values[i-100:i])
rolling_std[i] = std(values[i-100:i])
rolling_max[i] = max(values[i-100:i])
rolling_min[i] = min(values[i-100:i])
rolling_median[i] = median(values[i-100:i])
```

**Šta ti to daje:**
- `rolling_mean` — tipičan nivo u skorijem prošlosti (kao SMA)
- `rolling_std` — koliko je "razdrmano" (volatilnost)
- `rolling_max/min` — recent high/low
- `rolling_median` — robusniji od mean-a (manje osetljiv na outliere)

**Praktično:** ako prediktor cilja u trenutku `t`, dodaješ ga skup feature-a koji opisuju kontekst proteklih 100 trenutaka. Model uči obrasce poput: "kad rolling_std raste a rolling_mean stagnira → verovatnoća zaokreta".

**Veličina prozora (window size)** — bira se prema problemu:
- Fitness: 100 uzoraka ≈ 4 sekunde pokreta (25Hz sampling)
- Naš: 20-bar (4 nedelje na 1d), 50-bar, 200-bar (klasično za TA)

Više prozora paralelno (20+50+200) daje multiscale feature-e — model "vidi" trenutni kontekst, srednji trend, i dugoročnu poziciju.

**Glavni feature za naš projekat** — ovo je verovatno najproduktivnija tehnika iz repoa.

### 6.7 Frequency abstraction — FFT (Fast Fourier Transform)

Datoteka: `src/features/FrequencyAbstraction.py`. Takođe iz knjige Hoogendoorn & Funk.

**Princip:** svaki vremenski signal može se predstaviti kao **suma sinusoidalnih talasa različitih frekvencija** (Fourier-ovo teorija). FFT izračuna **koliko ima koje frekvencije**.

**Vizualizacija:**

```
Time domain (vremensko domen):     Frequency domain (frekvencijsko domen, posle FFT):

  signal                              amplituda
   ∧∨∧∨∧∨∧∨∧∨    →                    │
                                       │  ●        ← veliki vrh na 5Hz
                                       │
                                       │       ●   ← manji vrh na 12Hz
                                       │___________
                                       0  5 10 15  frekvencija
```

**Šta to znači u fitnessu:** dok radiš squat, dominantna frekvencija je ~0.5Hz (jedan squat svake 2 sekunde). Dok trčiš, dominantna frekvencija je ~2Hz (dva koraka u sekundi). Model može da prepozna vežbu samo iz **frekvencijskog spektra** signala, bez gledanja apsolutnih vrednosti.

**FFT u Pythonu:**
```python
import numpy as np

signal = np.array([...])  # 256 uzoraka
sampling_rate = 25  # Hz

fft_result = np.fft.rfft(signal)
amplitudes = np.abs(fft_result)
frequencies = np.fft.rfftfreq(len(signal), 1/sampling_rate)

# najveća amplituda govori dominantnu frekvenciju
dominant_idx = np.argmax(amplitudes)
print(f"Dominantna frekvencija: {frequencies[dominant_idx]} Hz")
```

**U našem projektu:** FFT nad close cenom otkriva **dominantne tržišne cikluse**.

- Da li BTC ima 90-dnevni ciklus? FFT će to pokazati.
- Da li altseason dolazi sa ~6-mesečnim periodom?
- "Cause" u Wyckoff-u (širina range-a) ima implicitnu cikličnost — FFT je matematički alat za detekciju.

**Feature-i iz FFT-a:**
- Dominantna frekvencija
- Amplituda dominantne frekvencije
- Spektralna entropija (koliko je signal koncentrisan u jednoj frekvenciji vs raspojen)

### 6.8 Clustering — K-Means

**Šta radi K-Means:**
1. Ti zadaš broj klastera K (npr. K=5)
2. Algoritam slučajno postavlja 5 centroida u feature space-u
3. Svaka tačka se dodeli najbližem centroidu
4. Centroidi se pomeraju u centar svojih dodeljenih tačaka
5. Ponavlja se dok se centroidi ne ustale

Rezultat: svaka tačka ima oznaku klastera (0 do K-1).

**Vizualizacija (2D):**

```
prije K-Means:               posle K-Means (K=3):

  Y │ . . . .                  Y │ A A . .
    │  . . .                     │  A A B
    │ . . . .                    │ A B B B
    │ .  . . .                   │ C C B B
    │ . .                        │ C C C
    │_______________ X           │_______________ X
```

**Fitness tracker primer:** ako ne znaš labele vežbi, K-Means grupiše snimke u K klastera. Naknadno čovek pogleda i kaže "klaster 1 je squat, klaster 2 je deadlift, ...". To je **semi-supervised** pristup.

**U našem projektu:** K-Means na feature vektorima istorijskih trenutaka može da otkrije:
- Klaster "BTC pre haltinga"
- Klaster "altseason"
- Klaster "bear market kapitulacija"
- Klaster "tihi sideways"

Možeš onda da pitaš agenta: "trenutno stanje BTC-a je u klasteru 7, koji se istorijski u 65% slučajeva nastavio bullish — ali pažljivo, klaster 7 je i ranije imao značajan recall u nasuprot pravac u 25%".

Daje **istorijsku analognost** kao dodatnu evidenciju za scenario.

### 6.9 Classification — algoritmi

Datoteka: `src/models/LearningAlgorithms.py` u fitness trackeru — wrapper oko scikit-learn klasifikatora.

Pregled algoritama koje koristi:

#### MLPClassifier (Multi-Layer Perceptron — višeslojni perceptron)

Najjednostavnija **neuronska mreža**. Slojevi neurona međusobno povezani; svaki neuron primenjuje linearnu kombinaciju ulaza + nelinearnu funkciju (sigmoid, ReLU).

```
Input  →  Hidden Layer 1  →  Hidden Layer 2  →  Output (klasa)
30 fea.    50 neurona         30 neurona         5 klasa
```

**Prednosti:** može da uhvati složene nelinearne obrasce
**Mane:** sklon overfittingu, potrebno više podataka, sporiji za treniranje

#### SVC / LinearSVC (Support Vector Classifier — klasifikator sa potpornim vektorima)

Pronalazi **hiperravan** koja razdvaja klase sa **najvećom marginom** (najvećim razmakom između najbližih tačaka različitih klasa).

```
       O O
      O O O
     O O O ╲     ← najbliža negativna tačka
              ╲
    ──────────╲──── ← hiperravan (max margin)
                ╲
            X    ╲   ← najbliža pozitivna tačka
          X X X
         X X X X
```

**LinearSVC** = linearna hiperravan. **SVC** = može da koristi **kernel** (RBF, polynomial) za nelinearne granice.

**Prednosti:** robusno, dobar kod malo podataka, jaka teorijska osnova
**Mane:** sporo za milione tačaka, multiklass-ifikacija zahteva više modela

#### KNeighborsClassifier (KNN — K najbližih suseda)

**Najjednostavniji od svih:** za nepoznatu tačku, pogledaj K najbližih primera iz trening seta i glasaj.

```
new point  →  ?
            ●     najbliža 5 (K=5):
           ● ●     3 zelena + 2 crvena → predikcija: zeleno
          ● ? ●
           ●
```

**Prednosti:** trivijalan za razumeti, ne treba "treniranje" (lazy learner)
**Mane:** sporo za predikciju (mora da gleda sve trening tačke svaki put), osetljiv na irelevantne feature-e

**Bitno:** **scale feature-e pre KNN-a** (StandardScaler ili MinMaxScaler) — inače feature sa velikim brojevima dominira distanc-om.

#### DecisionTreeClassifier (stablo odluke)

Niz "if-then" pitanja koja vode do klase.

```
      Da li je rolling_std > 0.5?
       /                       \
     DA                         NE
      |                          |
   Da li je volume_ma > 1000?    klasa: B
       /                  \
     DA                    NE
      |                     |
   klasa: C              klasa: D
```

**Prednosti:** **interpretabilno** (vidiš pravila koje je model naučio), brzo
**Mane:** sklon overfittingu — može da bukvalno memoriše trening set

#### RandomForestClassifier (slučajna šuma)

**Ensemble** (skup) stabala odluke. Pravi N stabala (npr. 100), svako stablo trenirano na drugačijem random podskupu trening podataka i feature-a. Predikcija = glasanje svih N stabala.

**Princip:** "mudrost gomile" — 100 osrednjih stabala daje bolji rezultat od 1 super stabla.

**Prednosti:**
- Robusno, malo se overfit-uje
- Feature importance (vidi koje su feature najvažniji)
- Radi out-of-the-box, malo hiperparametara za podesiti
- Vrlo dobar default za tabularne podatke

**Najčešća prva preporuka kod tabularnih klasifikacionih problema.**

**Ovo je MVP izbor za naš projekat.**

#### GaussianNB (Naive Bayes)

Koristi Bayes-ovu teoremu pretpostavljajući da su feature-i nezavisni (zato "naivni"). Iako pretpostavka često nije tačna, surprisingly radi dobro za neke probleme.

**Prednosti:** brz, jednostavan, dobar za visokodimenzionalne sparsne podatke (tekst)
**Mane:** pretpostavka nezavisnosti često se krši; nije sjajan za fina granična pravila

### 6.10 GridSearchCV — hyperparameter tuning

Sistematska pretraga **rešetke kombinacija hiperparametara** sa cross-validation.

```python
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier

param_grid = {
    'n_estimators': [100, 200, 500],
    'max_depth': [10, 20, None],
    'min_samples_split': [2, 5, 10]
}

clf = GridSearchCV(
    RandomForestClassifier(),
    param_grid,
    cv=5,                # 5-fold cross-validation
    scoring='f1_weighted'
)
clf.fit(X_train, y_train)
print(f"Najbolji parametri: {clf.best_params_}")
print(f"Najbolji rezultat: {clf.best_score_}")
```

Probaće 3 × 3 × 3 = 27 kombinacija, svaku sa 5-fold CV → 135 treninga. Sporo ali sistematično.

**Alternativa:** RandomizedSearchCV (random sampling iz rešetke — brže za velike grid-ove). Ili Bayesian optimization (još pametnije, biblioteke kao Optuna).

---

## 7. Šta od ovoga ide u naš projekat

Mapiranje tehnika fitness trackera → Wyckoff AI Phase 3:

| Fitness tracker tehnika | Naša primena | Prioritet | Issue |
|---|---|---|---|
| Cookiecutter struktura (data/raw → interim → processed, src/, notebooks/, reports/) | Direktan import — koristimo isti layout | **MUST** | #26 |
| Outlier removal (Chauvenet) | Detekcija flash crash / fat-finger bar-ova u OHLCV | SHOULD | #26 |
| Imputation (interpolation) | Za nedeljne timeframe-ove gde mogu biti rupe | SHOULD | #26 |
| Low-pass filter (Butterworth) | Verovatno NE — rolling MA-ovi su dovoljno smoothing | NICE-TO-HAVE | — |
| PCA | Dijagnostika "koliko stvarno feature-a treba" | NICE-TO-HAVE | #26 |
| Temporal abstraction (rolling stats) | **GLAVNI feature engineering** — rolling mean/std/max/min na 20/50/200 bar prozorima | **MUST** | #26 |
| Frequency abstraction (FFT) | Detekcija dominantnih ciklusa u close cenama | SHOULD | #26 |
| K-Means clustering | Klasterovanje istorijskih tržišnih stanja → "similar historical" feature za skill | SHOULD | #25 |
| RandomForestClassifier | **Baseline klasifikator faze** | **MUST** | #27 |
| MLPClassifier, SVC, KNN | Comparison set u baseline pass-u | SHOULD | #27 |
| GridSearchCV | Hyperparameter tuning za primarni model | **MUST** | #27 |

### 7.1 Direktan code reuse

Tri fajla možemo skoro verbatim da uzmemo (uz attribution):

1. **`TemporalAbstraction.py`** — `NumericalAbstraction` klasa sa `abstract_numerical()` metodom
2. **`FrequencyAbstraction.py`** — `FourierTransformation` klasa
3. **`remove_outliers.py`** — Chauvenet-ova funkcija

Sve dolaze iz Hoogendoorn & Funk knjige (otvoreno akademsko delo), trebamo samo da damo kredit u komentarima i (ako koristimo verbatim) u licenci.

### 7.2 Šta moramo sami da napišemo

- **`make_dataset.py`** ekvivalent — sklapanje OHLCV po simbol/timeframe iz Faza-2 MCP-a (radi se u tasku #26 zajedno sa feature-ima)
- **`build_features.py`** ekvivalent — orchestrator za naš slučaj
- **`annotate.py`** — LLM-asistirana anotacija (zadatak #25; fitness tracker nije imao ovaj problem jer su labele već došle sa snimcima)
- **`train_model.py`** — adaptiran za walk-forward validation (fitness tracker ima random split — kod nas to neće raditi)
- **`classifier_mcp.py`** — MCP server koji izlaže trenirani model agentu (zadatak #28)

---

## 8. Šta NE ide (za sada) i zašto

### 8.1 Deep learning (neuronske mreže, LSTM, Transformer)

**Razlozi:**
- Baseline RandomForest je dovoljno snažan za prvu verziju
- DL traži mnogo više podataka (Wyckoff ima ~500 labelovanih primera u našem MVP-u)
- Tradeoff "snaga vs interpretabilnost" — Random Forest daje feature importance, DL je crna kutija
- DL ima eksperimentalni karakter — ne želimo da ML deo bude blocker za Trading MCP

**Možda kasnije** ako baseline accuracy ne pređe 70%.

### 8.2 Embedding-based similarity search

**Šta je to:** umesto kategoričkih klastera, predstaviš svaki istorijski period kao **vektor u prostoru velike dimenzije** (npr. 768D) gde slični periodi imaju slične vektore. Za novi period nađeš **k najbližih komšija**.

**Zašto ne sad:**
- Treba embedding model (klasifikatorom je teško, treba nešto kao contrastive learning ili pretrained transformer)
- Kompleksno za debagovanje
- K-Means + Random Forest pokriva 80% iste koristi sa 20% kompleksnosti

**Možda kasnije** kao optimizacija "find_similar_historical" tool-a u classifier MCP-u.

### 8.3 Reinforcement learning (RL)

**Šta je to:** agent uči direktno **trading politiku** maksimizujući P&L u simulaciji.

**Zašto ne:**
- RL je notorno nestabilan za finance (skup hyperparametara, lako overfit-uje istorijske podatke)
- Naša filozofija je **rule-based scenario tree + ML kao dodatna evidencija**, ne autonomna politika
- Wyckoff je metodologija "scenario sa trigger i invalidation" — RL bi to potencijalno prešao u "kupi sad"

**Verovatno NIKAD** u skill-u. Možda kao istraživački eksperiment u zasebnom repu, ne ovde.

### 8.4 Online learning (model se ažurira tokom korišćenja)

Klasifikator se trenira jednom (offline), koristi se dok ne odluče da retreniramo (kvartalno?).

Razlog: bezbednost. Online learning otvara mogućnost da agent "pomeri prag" odluke nesvesno kako tržište evoluira — to može biti i dobro (adaptivnost) i loše (drift od originalnog koncepta faze).

---

## 9. Naš ML pipeline plan

Konkretizacija za Fazu 3 / Milestone M6:

### 9.1 Struktura foldera (post-Faza-3)

```
wyckoff-ai/
├── data/
│   ├── raw/                          ← OHLCV snapshotovi za reproducibilnost
│   ├── annotations/
│   │   ├── schema.json
│   │   └── manifest.json             ← lista (symbol, window_start, window_end, phase) tuple-ova
│   ├── interim/
│   │   └── 02_outliers_removed.pkl
│   └── processed/
│       └── 03_features.pkl           ← finalni dataset za trening
├── notebooks/
│   ├── 01_exploration.ipynb          ← početno razgledanje
│   ├── 02_baseline_classifier.ipynb  ← trening + evaluacija
│   └── 03_feature_importance.ipynb   ← which features matter
├── models/
│   └── baseline_phase_classifier_2026-MM-DD.joblib
├── reports/
│   └── baseline-classifier-2026-MM-DD.md
└── scripts/ml/
    ├── annotate.py                   ← LLM-asistirana anotacija
    ├── features.py                   ← feature engineering (uzme iz fitness trackera + dodaje naše)
    ├── train.py                      ← walk-forward training
    └── classifier_mcp.py             ← MCP server za predikcije
```

### 9.2 Workflow

```
1. annotate.py → data/annotations/manifest.json
   (Faza 1 wiki mora biti gotov da bi phase definicije bile stabilne)

2. OHLCV iz Faza-2 MCP-a → data/raw/<symbol>-<timeframe>.parquet
   (može se pulli na zahtev kad trebamo)

3. features.py → data/processed/03_features.pkl
   - Učitavamo anotirane prozore
   - Za svaki prozor izračunamo feature vector (30+ feature-a per zadatak #26)
   - Joinujemo sa labelama
   
4. train.py → models/baseline_phase_classifier_<date>.joblib
   - Walk-forward split (train 2020-2023, test 2024-2025)
   - GridSearchCV nad RandomForest
   - Confusion matrix + per-class metrics → reports/

5. classifier_mcp.py → MCP server koji agent može da zove
   - tool: classify_phase(symbol, timeframe, end_date=None)
   - tool: find_similar_historical(symbol, timeframe, n=5)
```

### 9.3 Acceptance kriterijumi (iz PRD-3)

- **Anotacija:** ≥ 500 labelovanih tuple-ova, svaka faza ima ≥ 75 primera, sample od 30 ima ≥ 90% slaganje sa LLM labelama (manuelni spot-check)
- **Feature engineering:** ≥ 30 feature-a, fixed-shape vector, no NaN bombs, dokumentovano u `data/features/feature_dictionary.md`
- **Klasifikator:** ≥ 60% balanced accuracy na test setu (4-klasa), F1 per class ≥ 0.4, cross-validation std < 0.1
- **MCP server:** agent ga zove, integriše predikciju kao **dodatnu evidence** uz rule-based read (ne kao primarni verdict)

---

## 10. Pojmovnik (glossary)

Skup termina za referencu. Trudio sam se da svaki uvedem prvi put kad se pojavi, ali ovo je za brz lookup.

| Termin (en) | Prevod | Definicija (1 rečenica) |
|---|---|---|
| **Accuracy** | tačnost | (tačne / sve) — udeo tačnih predikcija |
| **Algorithm** | algoritam | matematički recept koji ML model implementira (npr. Random Forest, MLP) |
| **Batch** | grupa | skup primera koji se zajedno obrađuju (npr. tokom treninga) |
| **Bias** | pristrasnost | sistematska greška modela; takođe naziv za "intercept" u linearnim modelima |
| **Classification** | klasifikacija | predviđanje kategorijske oznake (spam/ne-spam) |
| **Class imbalance** | neravnoteža klasa | kad jedna klasa ima mnogo više primera |
| **Clustering** | klasterovanje | grupisanje sličnih primera bez labela |
| **Confusion matrix** | matrica konfuzije | tabela tačnih i pogrešnih predikcija po klasama |
| **Cross-validation** | unakrsna validacija | tehnika za pouzdanije ocenjivanje modela kroz K različitih podela podataka |
| **Cutoff** | prag | tačka razdvajanja (u vremenu ili u veroatnoći) |
| **Dataset** | skup podataka | (uglavnom se kaže "dataset" i u srpskom) |
| **Decision Tree** | stablo odluke | klasifikator koji koristi niz if-then pitanja |
| **Deep learning** | duboko učenje | neuronske mreže sa mnogo slojeva (4+) |
| **Dimensionality reduction** | smanjenje dimenzija | redukcija broja feature-a uz minimalan gubitak informacije |
| **Embedding** | utiskivanje (rede), češće se zadrži "embedding" | vektorska reprezentacija nekog objekta (reč, slika, period tržišta) u prostoru velike dimenzije |
| **Ensemble** | ansambl | skup više modela koji glasaju (Random Forest je ensemble stabala) |
| **F1 score** | F1 mera | harmonijska sredina precision i recall |
| **Feature** | karakteristika, atribut | jedna brojčana ili kategorijska veličina koja opisuje primer |
| **Feature engineering** | inženjering karakteristika | proces konstruisanja feature-a iz sirovih podataka |
| **FFT (Fast Fourier Transform)** | brza Fourier-ova transformacija | algoritam za prebacivanje signala iz vremenskog u frekvencijski domen |
| **Generalization** | generalizacija | sposobnost modela da radi dobro na novim podacima |
| **Ground truth** | osnovna istina | tačna oznaka primera, dobijena od čoveka ili iz pouzdanog izvora |
| **GridSearchCV** | (zadržava se engleski) | sistematska pretraga hyperparametara sa cross-validation |
| **Hyperparameter** | hiperparametar | parametar koji čovek zadaje pre treninga (broj stabala, learning rate, ...) |
| **Imputation** | imputacija | popunjavanje rupa u podacima |
| **Inference** | inferencija | korišćenje treniranog modela za predikciju |
| **K-fold** | K-fold (rede prevodi) | varijanta cross-validation gde se podaci dele na K delova |
| **Label** | labela, oznaka | tačan odgovor za jedan primer u supervised learning-u |
| **Leakage** | curenje | greška kad informacija iz testa "iscuri" u trening podatke |
| **Learning rate** | stopa učenja | hyperparametar koji kontroliše koliko model menja u svakoj iteraciji |
| **Loss function** | funkcija gubitka | numerička mera koliko je model loš na primeru |
| **MA (Moving Average)** | pokretna sredina | average over a sliding window |
| **Model** | model | (zadržava se "model") obučeni klasifikator/regresor/klaster |
| **Multi-class** | višeklasni | klasifikacija sa 3+ klasa |
| **Neural network** | neuronska mreža | model inspirisan biološkim neuronima, sa slojevima |
| **Normalization** | normalizacija | skaliranje feature-a u zajednički opseg (npr. 0–1) |
| **Outlier** | (zadržava se), izgnanik | podatak koji odudara od ostalih |
| **Overfitting** | prenaučenost | model je "zapamtio" trening podatke i ne generalizuje |
| **PCA (Principal Component Analysis)** | analiza glavnih komponenti | smanjenje dimenzija nalaženjem pravaca maksimalne varijanse |
| **Pipeline** | cevovod | niz koraka obrade podataka |
| **Precision** | preciznost | TP / (TP + FP) — kad model kaže "da", koliko je često u pravu |
| **Random Forest** | slučajna šuma | ensemble klasifikator od mnogih stabala odluke |
| **Recall** | osetljivost | TP / (TP + FN) — koliko stvarnih "da" model uhvati |
| **Regression** | regresija | predviđanje kontinuirane numeričke vrednosti |
| **Regularization** | regularizacija | tehnika protiv overfitting-a (kažnjavanje preteranih parametara) |
| **Reinforcement learning** | pojačano učenje | agent uči interakcijom sa okruženjem preko nagrada |
| **Rolling window** | klizni prozor | metod obrade gde se prozor pomera kroz vremensku seriju |
| **Sample** | uzorak | jedan primer iz dataset-a |
| **Scaling** | skaliranje | pretvaranje feature-a u zajedničku skalu |
| **scikit-learn** | (proper noun) | Python biblioteka za klasični ML |
| **Sparse** | retka | vektor koji ima malo ne-nula vrednosti |
| **Stationary** | stacionaran | statistike (mean, variance) ne menjaju se kroz vreme |
| **Stratification** | stratifikacija | osiguravanje da svaki fold cross-validation-a ima sličan odnos klasa |
| **Supervised learning** | učenje sa nadzorom | učenje iz labelovanih primera |
| **SVM (Support Vector Machine)** | mašina sa potpornim vektorima | klasifikator koji traži hiperravan max margin |
| **Test set** | test skup | podaci na kojima ocenjujemo finalni model |
| **Time series** | vremenska serija | podaci ređani po vremenu, sa autokorelacijom |
| **Training set** | trening skup | podaci na kojima se model uči |
| **Underfitting** | nedovoljno naučeno | model je previše jednostavan za problem |
| **Unsupervised learning** | učenje bez nadzora | učenje obrazaca bez labela |
| **Validation set** | validacioni skup | podaci za podešavanje hiperparametara tokom treninga |
| **Walk-forward** | (rede prevodi) "validacija u napred" | strogi vremenski split za time series — trenira se na prošlosti, testira na budućnosti |

---

## Sledeći korak

Kad Faza 1 dovrši wiki (#7 ingest barem 80%), počinje rad na M6:

1. Zadatak #25 — anotacija pipeline-a
2. Zadatak #26 — feature engineering (verovatno koristeći verbatim TemporalAbstraction.py i FrequencyAbstraction.py)
3. Zadatak #27 — baseline klasifikator
4. Zadatak #28 — classifier MCP server

Vidi `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md` za pun PRD.
