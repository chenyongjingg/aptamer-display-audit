# Data

- `silver_labels.jsonl` — 102 documents, 16 fields. Each value carries `value`, `unit`,
  `context`, and a **≤25-word quote excerpt**. Full quotes and full texts are not
  redistributed; regenerate documents with the companion review's retrieval scripts.
- `predictions_hybrid_labels.jsonl` — hybrid (rules + field-level LLM) predictions,
  same redaction rule.
- `docs_manifest.jsonl` — doc_id, paper_id, level, DOI, year, journal, title, licence.
  No abstract or full-text body.
- `silver_qa_v2.json` — coverage, sanity, cross-field checks, per-field counts.
- `splits.json` — 5-fold paper-level splits (leakage 0).

The companion review repository `chenyongjingg/aptamer-display-map` contains the search
strings, screening chain and targeted extraction table. This repository does not
re-publish publisher text.
