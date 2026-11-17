# Protocol (v3 consensus silver)

- Corpus: 82 abstracts (4 title-only) + 20 machine-readable open-access full texts from the companion review.
- Silver sources: deterministic rules + Llama-3.1-8B-Instruct + Ministral-8B-Instruct + the review's targeted extraction.
- Consensus: >=2 sources agreeing on status and value; verbatim-quote gate; absence gate.
- Primary endpoint: **value set-F1** on high-confidence reported fields (high+medium positives),
  paper-level 5-fold out-of-fold. Presence macro-F1 is secondary.
- No human annotation. Silver is not truth; coverage and uncertainty are reported.
- External anchor (AutoPK) is not run in this release; report `not_available`, not passed.
- Q5 stability, Q6 decoy, Q7 external anchor are not run; report `not_run`.
