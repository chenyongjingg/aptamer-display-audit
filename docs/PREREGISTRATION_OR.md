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
