# Results

`value_experiments.json` is the primary results file. It separates:

- **presence macro-F1** (what is reported / not reported) — easily saturated;
- **value-F1** (whether the value is extracted correctly) — the actual bottleneck;
- **quote valid rate** (verbatim evidence gate).

Headline: on 102 documents, rules achieve value-F1 0.394; zero-shot Qwen2.5-7B 0.030;
the rule + field-level LLM hybrid 0.415. Presence is ~0.99 for all systems, which is a
property of an absence-dominated corpus, not evidence of extraction quality.

`audit_metrics_full.json` is the recomputed full table (E0/E1/HYBRID) from the archived predictions.
`../data/silver_qa_v2.json` is the silver QA (coverage, sanity, cross-field checks).
