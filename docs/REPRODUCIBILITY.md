# Reproducibility status

## What is reproducible now

- **Value-extraction table** (no GPU): `python reproduce_value_results.py`
  recomputes E0 0.394, E1 0.030, hybrid 0.415 from the archived predictions and
  silver labels. This is the strongest reproducibility claim of the archive.
- **Silver labels**: `data/silver_v2.jsonl` (local snapshot) + `silver_qa_v2.json`
  + `silver_sources_v2.jsonl`; 102 documents; high coverage 0.873/0.848/0.770.
- **Splits**: 5 paper-level folds, leakage 0.
- **Environment**: `environment/environment.json` + `environment/pip-freeze.txt`
  (Python 3.10.12, torch 2.5.1+cu124, transformers 4.57.6, RTX 4090 24 GB).
- **Base models**: paths, config/index hashes in `environment/environment.json`.
  Weights are public and not archived.
- **Snapshot integrity**: `SHA256SUMS.txt`; `scripts/check_snapshot.py` checks
  counts and recomputes the table.

## Known gaps (do not overclaim)

1. **S0 was not passed for the final zero-shot rerun.** `prereg.json` hashes
   `configs/full_auto.yaml`; the rerun used `configs/full_zeroshot.yaml` and was
   started with `--from S6_infer`. The final metrics are post-hoc exploratory,
   not pre-registered. See `docs/PROVENANCE.md`.
2. **`runs/full_auto/manifest.json` records the initial config hash**
   (`ffb29230…`), not the zero-shot config. Do not use it as the final provenance.
3. **QLoRA adapters were trained without explicit `torch.manual_seed`.** A seed
   patch was added after archiving; the archived adapters are exploratory and
   collapse to absence. Do not claim bitwise reproducibility for E4.
4. **Base weights are not hashed**, only their config/index files. Public model
   snapshots may change; verify config/index hashes before rerunning.
5. **Archived manifests/logs contain absolute `/root/faudit` paths.** Artifacts
   are relative to the snapshot root; use `scripts/rewrite_paths.py` or read
   paths relative to the tree.
6. **Only 20 open-access full texts**, not 24–28. Q5–Q7 and P1–P4 are not run.
