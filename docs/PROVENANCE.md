# Provenance and honest caveats

## Final archived results are post-hoc, not pre-registered

At 2026-11-17T00:53Z the S0 gate **blocked** because `prereg.json` hashed
`configs/full_auto.yaml`, while the zero-shot rerun used
`configs/full_zeroshot.yaml`. To avoid rerunning the 102-document inference, the
rerun was started with:

```bash
python3 run_pipeline.py --config configs/full_zeroshot.yaml \
  --run-id full_auto --from S6_infer --force --detach
```

Therefore:

- the final S6–S9 results are **post-hoc exploratory**, not a pre-registered run;
- `runs/full_auto/manifest.json` still records the **initial** `full_auto` config
  (`ffb29230…`), not the zero-shot config; do not use it as the provenance of the
  final metrics;
- exact hashes of actual inputs are in `PROVENANCE.json`.

This is recorded rather than hidden. A journal claim of pre-registration must
not be based on this archived run; a fresh S0-passed run is required.

## Confirmatory runs (S0 passed)

Two runs were frozen **before** inference and passed the S0 hash gate:

| Run | Config | Preregister | Completed |
|---|---|---|---|
| `prereg_zs_20261117` | `configs/prereg_zs.yaml` | `prereg.json` | 2026-11-17T03:16:45Z |
| `hybrid_confirm` | `configs/prereg_or.yaml` | `prereg_or.json` | 2026-11-17T03:29:07Z |

`or_confirm` then computed cross-system metrics, temporal subsets and the AutoPK
reference. The confirmatory zero-shot predictions are byte-identical to the
archived exploratory predictions (`sha256 aab29c3c…`), i.e. the exploratory
ranking was not an artefact of a different inference path.

The primary endpoint, corpus, silver file and quote gate were unchanged between
the exploratory and confirmatory runs; only the freezing (S0) differs.

## Seeds and training

- The archived QLoRA adapters (`runs/full_auto/train/fold*/adapter`) were trained
  **before** an explicit `torch.manual_seed` patch; they are exploratory/negative
  evidence (all-negatives collapse), not a reproducible performance result.
- Zero-shot and field-level inference use `do_sample=False`; CUDA nondeterminism
  can still cause small token-level differences.
- The value-extraction results are reproducible from the archived predictions
  without a GPU: `python reproduce_value_results.py` reproduces the table.

## Models

Base model paths and config/index hashes are in `environment/environment.json`.
Base weights are public and not redistributed; the local paths are ModelScope
snapshots. If re-downloaded under the same names, verify the config/index hashes
before rerunning.

## Data

`data/docs.jsonl` contains publisher abstracts/full texts and is **local-only**.
The public repository contains only labels and ≤25-word quote excerpts.
