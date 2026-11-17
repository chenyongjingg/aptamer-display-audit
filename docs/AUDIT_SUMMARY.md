# Audit summary

- The first fully automated run completed S0–S9, but its fine-tuned E4 branch collapsed
  to `not_reported`; its presence 0.99 was discarded as an artefact.
- The 7B QLoRA branch was not viable at this corpus size (9 positive documents in one
  training fold; adapters dropped field keys or predicted absence). It is retained as an
  exploratory/negative result, not as the main method.
- The primary endpoint was changed from presence macro-F1 to **value set-F1** on
  high+medium reported fields, because presence saturates in an absence-dominated corpus.
- Two-stage value extraction (candidate sentences → field-level LLM → hybrid with rules)
  reaches value-F1 0.415 on 102 documents versus 0.394 for rules and 0.030 for zero-shot.
- A field-level verifier with forced JSON works technically but degrades value-F1
  (0.696 → 0.535 on five documents); LLM verification is a negative result.
- Q5 stability, Q6 decoy, Q7 external AutoPK anchor, P1–P4 contamination probes and
  E2/E3/E8/E9 are not run. They are reported as `not_run`/`not_available`, never passed.
