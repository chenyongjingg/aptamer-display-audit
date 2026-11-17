# Pre-registration — Original Research hybrid confirmatory run

**Frozen at:** 2026-11-17T02:35Z
**Run id:** `hybrid_confirm`
**Config:** `configs/prereg_or.yaml`
**Preregister:** `prereg_or.json`

## Frozen inputs

- `protocol.md` — `9f6ee668…`
- `prompts/p2.md` — `7c1970d2…`
- `value_extract.py` — `820ef443…`
- `runs/full_auto/audit/silver_v2.jsonl` — `4ac27068…`
- `configs/prereg_or.yaml` — see `prereg_or.json`

## Hypotheses

- **H1:** zero-shot Qwen2.5-7B value-F1 < 0.10 (confirmatory, same as `prereg_zs`).
- **H2:** hybrid (rules + field-level LLM) value-F1 > 0.30 and > zero-shot.
- **H3:** hybrid value-F1 ≥ rules (non-inferior; rules are the fallback).
- **H4:** Tier-1 (PK) value-F1 < Tier-2 (design) value-F1.
- **External comparator:** AutoPK reports human-labeled table F1 0.92 (half-life) and 0.91
  (clearance) on 605 tables. The 605-table dataset is **not publicly released**
  (only DOIs/code), so we do **not** rerun it; it is cited as an external table benchmark,
  not used as a label source.

## Design

- 102 documents (82 abstracts + 20 full texts), frozen silver `silver_v2.jsonl`.
- Hybrid: rule extractor first; field-level Qwen2.5-7B only for fields where rules have
  no quote-valid value; every value must pass the verbatim quote gate.
- No training, no verifier, no human annotation.
- Primary endpoint: value set-F1 on high+medium reported fields (102 docs).
- Secondary: presence macro-F1, quote validity, per-tier value-F1, 5-fold OOF.
- No document exclusions; no model selection on test documents.

## Outcome (`hybrid_confirm` done 2026-11-17T03:29:07Z; metrics 03:38Z)

102/102 documents; no document exclusions; no training; no verifier.

| System | value-F1 | presence | quote valid | coverage high |
|---|---|---|---|---|
| E0 rules | 0.3969 | 0.9979 | 1.000 | 0.8517 |
| E1 zero-shot | 0.0298 | 0.9750 | 0.600 | 0.8517 |
| HYBRID | 0.4181 | 0.9903 | 1.000 | 0.8517 |

- **H1 supported:** zero-shot 0.0298 < 0.10.
- **H2 supported:** hybrid 0.4181 > 0.30 and > zero-shot.
- **H3 supported:** hybrid 0.4181 ≥ rules 0.3969.
- **H4 falsified:** Tier-1 (PK) 0.4409 > Tier-2 (design) 0.2868; the
  pre-registered direction was the reverse. Reported as a falsified hypothesis,
  not repaired post hoc.
- Temporal value-F1 (hybrid): 0.4027 on 2025+ (n=25), 0.4653 pre-2025 (n=77);
  zero-shot 0.0249 / 0.0306 — ranking stable.
- External AutoPK comparator remains **literature-only** (605 tables not public;
  anchor not rerun).

Aggregates: `results/confirmatory_20261117.json`; narrative:
`docs/CONFIRMATORY_RESULTS.md`.
