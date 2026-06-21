---
pr: 79
title: "fix: ispravi tri runtime greške u eval orkestratoru (#77)"
author: "ssmiljanicc"
reviewed: 2026-06-21T10:00:00+00:00
recommendation: approve
---

# PR Review: #79 — fix: ispravi tri runtime greške u eval orkestratoru (#77)

## Summary

PR ispravlja tri runtime kvara koji su blokirali prvi Claude canary u Phase 4 benchmark toku:

1. **Schema putanja umesto sadržaja** — `--json-schema` je primao putanju do fajla; ispravka: `build_argv()` čita i inline-uje JSON tekst, uz rano `json.loads` validiranje pre subprocess poziva.
2. **`--bare` + OAuth konflikt** — `--bare` ne čita OAuth/keychain prijavu u Claude Code 2.1.183; ispravka: uklonjeno `--bare`, dodate eksplicitne izolacione granice kroz `CLAUDE_ISOLATION_ARGS` konstantu.
3. **Prose/fenced JSON umesto parsabilnog objekta** — parser nije prihvatao `result` string niti fence format; ispravka: uski parser prihvata čist JSON string i tačno ```` ```json ```` / ```` ``` ```` fence, odbija sve ostalo.

Uz to: schema obogaćena sa `narrative` i `evidence` kao obaveznim poljima da bi `narrative_quality` skoring ostao konzistentan sa stvarnim analyst outputom; runbook ažuriran sa ispravnim preflight komandama, OAuth razlogom i canary checklistom.

Implementacija prati sve 7 koraka iz istraživačkog artefakta `PRPs/issues/completed/issue-77.md`.

## Implementation Context

| Artifact | Path |
| --- | --- |
| Implementation Report | `PRPs/issues/completed/issue-77.md` |
| Original Plan | Integrisan u istraživački artefakt (nije zaseban plan fajl) |
| Documented Deviations | 1 — naplativi canary pre merge-a je eksplicitno van scope-a |

## Findings

### Critical

No critical issues found.

### High

No high-priority issues found.

### Medium

No medium-priority issues found.

### Suggestions

**S1 — Treći fallback u parseru koristi čitav envelope kao output**

`runtime_adapters.py:160`: Kada ni `structured_output` ni `result` nisu prisutni u envelopi, parser koristi čitav envelope dict kao output:

```python
output = envelope.get("structured_output")
if output is None:
    output = envelope.get("result", envelope)  # fallback: envelope samo
```

Ovo je pre-existing ponašanje (dokumentovano u istraživačkom artefaktu kao "pa sam envelope"). Ako Claude vrati envelope bez ova dva ključa, dobijamo dict koji će sadržavati `usage`, `type` i druge metapodatke — što bi zatim palo na schema validaciji u `orchestrator.py:296`. Nije silent failure, ali je semantički nejasno. Opcija za budući PR: eksplicitno odbiti ako ni `structured_output` ni `result` nisu prisutni, umesto fallback-a.

Ovo nije bloker — ponašanje je intentional, pre-existing i covered schema validacijom niže.

---

**S2 — Prose iza JSON-a u `result` nije eksplicitno testiran negativnim testom**

`test_runtime_adapters.py:69-85`: Negativni testovi pokrivaju prose ispred JSON-a (`'before {"direction":"none"}'`), nepotpun fence i JSON listu. Prose iza JSON-a (`'{"direction":"none"} trailing'`) nije eksplicitni test slučaj. Implementacija ga ispravno odbija jer `json.loads` u Pythonu 3 baca `JSONDecodeError` za trailing content — ali test bi eksplicitno dokumentovao ovo ponašanje.

Nije bloker.

## Validation Results

| Check | Status | Details |
| --- | --- | --- |
| `pytest tests/test_runtime_adapters.py tests/test_eval_orchestrator.py tests/test_scoring.py -q` | ✅ Pass | 37 passed |
| `pytest -q` (full suite) | ✅ Pass | 258 passed |
| JSON schema parse | ✅ Pass | Sve `scripts/eval/schemas/*.json` parsiraju bez greške |
| `git diff --check` | ✅ Pass | Nema whitespace grešaka |
| Naplativi canary | ⏭ Skipped | Eksplicitno van scope-a (issue #77, istraživački artefakt §Scope Boundaries); obavezan post-merge |

## What's Good

- **`CLAUDE_ISOLATION_ARGS` konstanta** — isti niz se koristi u `build_argv()` i `preflight()` auth pozivu, što garantuje da preflight zaista proverava tačno onaj argv profil koji će biti korišćen u realnom pozivu. Ovo je ključan design detalj koji je sprečio tihi mismatch između capability check-a i stvarnog poziva.

- **Fence parser je intentionally strog** — prihvata isključivo tačno ```` ``` ```` ili ```` ```json ```` kao prvi red (case-sensitive, bez extra teksta), i tačno ```` ``` ```` kao poslednji. Uppercase ```` ```JSON ````, ```` ```javascript ```` i slično su odbijeni. `.strip()` na svakom redu ispravno tretira trailing spaces. Implementacija odgovara specifikaciji iz istraživačkog artefakta §Step 2 tačka 6.

- **Prompt/schema cross-validacioni test** — `test_analyst_prompt_names_every_required_schema_field` zaključava odnos između `schema["required"]` i sadržaja prompta, sprečavajući budući drift između transportnog formata i skoring ugovora.

- **Preflight auth poziv koristi isti isolation profil** — `_require_auth([self.binary, *CLAUDE_ISOLATION_ARGS, "auth", "status"])` nije samo auth check; proverava i da li instaliran CLI prihvata kombinaciju izolacionih flagova, što čini preflight-om i capability smoke-om u jednom jeftinom pozivu.

- **Runbook canary checklist** — svih 9 obaveznih polja, narrative-before-labels redosled, fence odsustvo, usage/checkpoint/judge/report i CLAUDE.md sentinel provera su eksplicitno navedeni u §2. Ovo je sprečilo da post-merge canary ostane nedefinisan.

- **Istraživački artefakt** — 5-whys analiza za sva tri uzroka, evidence chain sa konkretnim fajl:linija referencama, edge case tabela i jasne scope granice. Smanjuje rizik budućih regresija.

## Recommendation

**APPROVE**

Sve tri runtime greške su ispravno dijagnostikovane i ispravljene. Schema, prompt i testovi su usklađeni sa `narrative_quality` scoring ugovorom. Validacija prolazi u potpunosti (258 testova). Jedini preostali rizik — realan canary pre merge-a — je eksplicitno dokumentovana post-merge obaveza, ne propust implementacije.

Jedina preporučena radnja pre finalnog batch run-a: sentinel canary iz runbook §2 (CLAUDE.md sentinel fajl u snapshot-u) da bi se verifikovalo da non-bare CLI ne učitava projektni kontekst automatski. Ovo nije zahtev za blokiranjem merge-a.
