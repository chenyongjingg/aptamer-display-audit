# Protocol (pilot / v3 silver)

- Corpus: 82 abstracts (4 title-only) + up to 28 open-access full texts from the companion review.
- Silver sources: deterministic rules + Qwen3-8B + Qwen3-4B + the review's targeted extraction.
- Consensus: >=2 sources agreeing on status and value; verbatim-quote gate; absence gate.
- Primary endpoint: macro-F1 over 16 fields on high-confidence silver, paper-level 5-fold out-of-fold.
- No human annotation. Silver is not truth; coverage and uncertainty are reported.
- External anchor: AutoPK public PK tables (calibration only).
