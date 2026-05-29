---
name: wyckoff-wiki-ingest
description: Operativni protokol za batched ingest sirovih izvora (book, crypto archive, Bruce Fraser) u knowledge/wiki/. Koristi se za batched ingest tokom Issue #7 i za ad-hoc wiki update-e posle Batch 9 (trim-uje se, ne briše). Sadrži cross-batch awareness pravila, citation verification protokol, validation skripte i review checklist. Pozivaj se eksplicitno na početku svakog batch-a i pre svakog PR review-a.
---

# Wyckoff Wiki Ingest (Codex wrapper)

Run the canonical runbook:

`runbooks/wyckoff-wiki-ingest.md`

Use the Codex adapter section in that runbook.

Treat the user's prompt as the runbook input — tipično batch broj (1–9), PR broj za review, ili `spot-check <PR>` za semantic review.

## Quick reference

- Pokretanje novog batch-a: `skills/wyckoff-wiki-ingest/operations/ingest-batch.md`
- Mehanički PR review: `skills/wyckoff-wiki-ingest/operations/review-pr.md`
- Semantic spot-check: `skills/wyckoff-wiki-ingest/operations/semantic-spot-check.md`

## Disciplinske invariante (skraćeno — pun tekst u runbook-u)

- **Path depth:** runbook §2 — citation linkovi razrešavaju iz stvarne dubine stranice
- **Cross-batch awareness:** runbook §3 — proveri postojeći wiki pre nego što napišeš novu stranicu
- **Unknown claim protocol:** runbook §3.5 — svaka tvrdnja je direktan quote, parafraza, sinteza, ili WIKI_GAP; training data nije citativan izvor
- **Citation verification:** runbook §3.6 — pre pisanja `[book p.XXX]` linka, otvori + grep raw stranicu
- **Context budget:** runbook §3.7 — commit po logičkim grupama, stop signal na ~75% konteksta

Codex policy: `agents/openai.yaml` drži `allow_implicit_invocation: false` — skill se ne aktivira automatski, samo na eksplicitan poziv.

Posle Batch 9 skill se **trim-uje** (batch-specifični delovi se uklanjaju), **ne briše** — discipline ostaje za ad-hoc wiki update-e i buduće izvore (vidi runbook §7).
