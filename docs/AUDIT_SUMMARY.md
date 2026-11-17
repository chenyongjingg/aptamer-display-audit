# Audit summary

- The first fully automated run completed S0–S9, but its fine-tuned E4 branch collapsed
  to `not_reported`; its presence 0.99 was discarded as an artefact.
- The 7B QLoRA branch was not viable at this corpus size (9 positive documents in one
  training fold; adapters dropped field keys or predicted absence). It is retained as an
  exploratory/negative result, not as the main method; it is not claimed as bitwise
  reproducible (the explicit seed patch landed after the archived run).
- The primary endpoint was changed from presence macro-F1 to **value set-F1** on
  high+medium reported fields, because presence saturates in an absence-dominated corpus.
- **Confirmatory (frozen before inference, S0 passed):** rules 0.3969, zero-shot 0.0298,
  hybrid 0.4181 on 102 documents; presence 0.9903 for the hybrid; quote validity 1.000.
  H1–H3 supported; the pre-registered tier hypothesis H4 was **falsified** (Tier-1 0.4409
  > Tier-2 0.2868). See `docs/CONFIRMATORY_RESULTS.md`.
- Exploratory (post-hoc): two-stage value extraction reaches 0.415 versus 0.394 for rules
  and 0.030 for zero-shot — consistent with the confirmatory ranking (+0.021 hybrid gain).
- A field-level verifier with forced JSON works technically but degrades value-F1
  (0.696 → 0.535 on five documents); LLM verification is a negative result.
- Q5 stability, Q6 decoy, P1–P4 contamination probes and E2/E3/E8/E9 are not run. They are
  reported as `not_run`/`not_available`, never passed.
- The AutoPK 100-table anchor (Q7) **cannot be rerun**: the 605 human-labeled tables are
  not publicly released (only DOIs and code). Published F1 0.92 (half-life) / 0.91
  (clearance) are used as a task-level comparator only; no head-to-head claim.
