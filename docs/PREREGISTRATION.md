# Pre-registration — confirmatory zero-shot audit

**Frozen at:** 2026-11-17T02:20Z
**Run id:** `prereg_zs_20261117`
**Config:** `configs/prereg_zs.yaml`
**Prereg file:** `prereg.json` (hashes below)

## Frozen inputs

| Input | SHA-256 |
|---|---|
| `protocol.md` | `9f6ee66882cc15495e7c9a76b0e2bd3cfd75485bdcf6c7ffe5f35456f4650df1` |
| `prompts/p2.md` | `7c1970d20d0288036aae9757738ed056c530440a0efbeafec7f56fdf14951c4a` |
| `configs/prereg_zs.yaml` | `afb2d0f4d3fa4be2e3d37b381c95d51283dcbaa3a2b848809c17b631ab1ec4e0` |

## Hypotheses (pre-specified)

- **H1 (primary):** zero-shot Qwen2.5-7B value set-F1 on high+medium reported
  fields is **< 0.10** on the 102-document corpus.
- **H2 (secondary):** presence macro-F1 is **> 0.90**, i.e. absence detection is
  easy relative to value extraction.
- **H3 (secondary):** rules (E0) have higher value-F1 than zero-shot (E1).
- **Not in this run:** QLoRA, verifier, hybrid, Q5–Q7, contamination probes.
  These are exploratory or not run; they cannot be reported as confirmatory.

## Design

- Corpus: 82 abstracts (4 title-only) + 20 open-access full texts = 102 documents.
- Silver: frozen `runs/full_auto/audit/silver_v2.jsonl` (consensus silver; 102 docs;
  high coverage 0.873/0.848/0.770); 5 paper-level folds, leakage 0.
- Systems: E0 deterministic rules; E1 Qwen2.5-7B zero-shot (`do_sample=False`).
- Primary endpoint: value set-F1 on high+medium reported fields, 102 documents.
- Secondary: presence macro-F1, quote valid rate, per-tier value-F1, 5-fold OOF.
- No training; no verifier; no model selection on the test set.
- All 102 documents are evaluated; no document-level exclusions.

## Deviations from the earlier archived run

The earlier `full_auto` run was **post-hoc**: S0 blocked because `prereg.json`
hashed `configs/full_auto.yaml`, while the final zero-shot rerun used
`configs/full_zeroshot.yaml` and `--from S6_infer`. This document and
`prereg.json` freeze the confirmatory run **before** its inference, with S0
passing. The earlier run remains archived as exploratory.

## Commands

```bash
python3 run_pipeline.py --config configs/prereg_zs.yaml \
  --run-id prereg_zs_20261117 --detach
```

Expected artifacts: `runs/prereg_zs_20261117/audit/audit_metrics.json`,
`pred_zero_shot.jsonl`, `manifest.json`, `stages` in `manifest.json`.

## Outcome (run completed 2026-11-17T03:16:45Z)

`prereg_zs_20261117` finished with `state=done`; 102/102 documents.

| Quantity | Observed |
|---|---|
| E0 rules value-F1 | 0.3969 |
| E1 zero-shot value-F1 | 0.0298 |
| E1 presence macro-F1 | 0.9750 |
| quote valid (E1) | 0.600 |
| coverage high | 0.8517 |
| n high fields | 1,390 |

- **H1 supported:** 0.0298 < 0.10.
- **H2 supported:** presence 0.9750 > 0.90.
- **H3 supported:** rules 0.3969 > zero-shot 0.0298.

Aggregates: `results/confirmatory_20261117.json`; narrative:
`docs/CONFIRMATORY_RESULTS.md`.
