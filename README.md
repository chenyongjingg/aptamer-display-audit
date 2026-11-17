# aptamer-display-audit

**Auditing What Is Absent** — a consensus-silver benchmark and automated auditor for
pharmacokinetic and display-parameter reporting in aptamer–nanostructure cancer literature.

This repository is the companion to the scoping review
[`aptamer-display-map`](https://github.com/chenyongjingg/aptamer-display-map). The review
maps the reporting gap; this repository measures whether the gap can be audited
automatically, and where value extraction still fails.

## What is here

| Path | Content |
|---|---|
| `pipeline/` | consensus-silver construction, QA, metrics, failure taxonomy, splits |
| `run_pipeline.py` | unattended S0–S9 orchestrator (hash gates, manifests, status, resume) |
| `value_extract.py` | two-stage value extraction: candidate sentences → field-level LLM → hybrid |
| `verifier2.py` | field-level verifier with forced JSON (negative result; see results) |
| `train_qlora.py` | per-fold QLoRA trainer (exploratory; small-n collapse documented) |
| `data/silver_labels.jsonl` | 102-document consensus silver labels (quote excerpts only) |
| `data/docs_manifest.jsonl` | document identifiers, levels, DOIs and licences; no full text |
| `data/silver_qa_v2.json` | Q1–Q4/Q8 QA; Q5–Q7 are reported separately |
| `data/splits.json` | 5-fold paper-level splits, leakage = 0 |
| `results/` | value-F1 results and verifier negative result |
| `docs/AUDIT_SUMMARY.md` | audit findings and negative results (no publisher text) |

## Headline results (102 documents, 204 high+medium positives)

| System | presence macro-F1 | **value-F1 (primary)** | quote valid |
|---|---|---|---|
| E0 rules | 0.998 | **0.394** | 1.000 |
| E1 Qwen2.5-7B zero-shot | 0.975 | **0.030** | 0.600 |
| E1cand field-level LLM | 0.990 | **0.415** | 1.000 |
| **HYBRID (rules + field-level LLM)** | 0.990 | **0.415** | 1.000 |

Presence is high because most fields are `not_reported`; it is not extraction performance.
The value bottleneck is real: zero-shot 0.030, hybrid 0.415. Rules do most of the work;
the field-level LLM adds +0.021 over rules. A field-level verifier with forced JSON
degrades value-F1 from 0.696 to 0.535 on 5 documents (negative result).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) build the local document set from the companion review's retrieval scripts
#    (publisher text is not redistributed here; see data/README.md)
# 2) freeze the protocol
cp prereg.example.json prereg.json
python scripts/make_prereg.py

# 3) run the unattended pipeline
python run_pipeline.py --config configs/full_auto.yaml --run-id full_auto --detach
python run_pipeline.py --config configs/full_auto.yaml --run-id full_auto --resume
```

The pipeline writes `runs/<id>/manifest.json`, `status.json`, per-stage artifacts and
checksums. Gates fail closed: S0 refuses a changed protocol; S2b refuses low silver
coverage; S5/S7 failures are recorded, never silently skipped.

## Pre-registration

A confirmatory zero-shot audit was frozen before inference on 2026-11-17:
`docs/PREREGISTRATION.md`, `prereg.json`, `configs/prereg_zs.yaml` (run id
`prereg_zs_20261117`, S0 passed). The earlier `full_auto` run remains archived
as **post-hoc exploratory**; do not cite it as pre-registered. QLoRA is
exploratory/negative and is not claimed as bitwise reproducible.

## Scientific scope

- No human annotation. Silver labels are a **machine consensus**, not human truth;
  only high-confidence fields enter presence metrics, high+medium positives enter value-F1.
- Only 20 open-access full texts are machine-readable; 8 publisher PDFs were unavailable
  or error pages. The benchmark is scoped accordingly.
- The 30-document high-positive subset was selected for feasibility, not random sampling.
- Q5 stability, Q6 decoy and Q7 external AutoPK anchor are **not run** in this release;
  they must be reported as `not_run`/`not_available`, never as passed.
- Fine-tuning is exploratory: with ~50–65 training documents per fold, 7B QLoRA collapses
  to `not_reported`; this is documented as a negative result, not hidden.

## Licences

- Code: MIT (`LICENSE`).
- Annotations, metrics, splits and figures: CC BY 4.0 (`LICENSE-data`).
- Publisher text is **not** redistributed. `data/silver_labels.jsonl` contains only
  labels and ≤25-word quote excerpts; full texts must be regenerated from the companion
  review's retrieval scripts under their original licences.

## Citation

See `CITATION.cff`. This is a research benchmark, not a clinical decision tool.
