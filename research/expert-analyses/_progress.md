# Coverage Ledger — `research/expert-analyses/`

Ovaj fajl je **izvor istine** za pokrivenost sweep-a (ne broj extract fajlova).
`reviewed` kolona mora biti == ukupan broj fajlova po izvoru pre nego što se zadatak smatra završenim.

Sweep zadaci (3.1–3.3, 4, 5.1–5.3) ažuriraju ovaj fajl posle svake serije.
Resume se vrši isključivo preko `last_reviewed` kolone — ne preko broja extract fajlova.

| source  | total_files | reviewed | valid | rejected | paywalled | last_reviewed |
|---------|-------------|----------|-------|----------|-----------|---------------|
| book    | 248         | 20       | 2     | 18       | 0         | raw/book/pages/page_020.md |
| crypto  | 46          | 0        | 0     | 0        | 0         | —             |
| fraser  | 243         | 0        | 0     | 0        | 0         | —             |

## Napomene

- `total_files`: book=248 (page_001–page_248), crypto=46, fraser=243
- `reviewed`: svaki dokument koji je pregledan (validan + odbačen + paywalled)
- `valid`: broj extract fajlova kreiran za ovaj izvor
- `rejected`: pregledan ali nije zadovoljio kriterijume validnog para (#89)
- `paywalled`: status paywalled iz manifesta — sadržaj nije dostupan; zaveden u `_gaps.md`
- `last_reviewed`: poslednji pregledani fajl (za resume), npr. `raw/book/pages/page_020.md`
