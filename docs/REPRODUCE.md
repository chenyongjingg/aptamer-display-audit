# Reproducing the audit

## 0. Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

A single 24 GB GPU is sufficient. The reference run used an RTX 4090.

## 1. Documents

This repository does not redistribute publisher text. Build `data/docs.jsonl`
from the companion review's retrieval and screening chain
(`chenyongjingg/aptamer-display-map`), or from the same PubMed / Europe PMC /
OpenAlex queries. Each record needs:

```json
{"doc_id": "S187_abs", "paper_id": "S187", "level": "abstract",
 "text_kind": "abstract", "doi": "...", "year": 2017, "text": "..."}
```

Full texts: `level="full"`, `text_kind="fulltext"`. Keep 82 abstracts and the
20 machine-readable open-access full texts for the reported benchmark.

## 2. Freeze

```bash
cp prereg.example.json prereg.json
python scripts/make_prereg.py
```

S0 refuses to run if `protocol.md`, `prompts/p2.md` or `configs/full_auto.yaml`
change after this step.

## 3. Silver and audit pipeline

```bash
python run_pipeline.py --config configs/full_auto.yaml --run-id full_auto --detach
python run_pipeline.py --config configs/full_auto.yaml --run-id full_auto --resume
```

Stages: S0 freeze → S1 corpus → S2a silver sources → S2b consensus/QA →
S3 splits → S4 prompt hash → S5 per-fold QLoRA (exploratory) → S6 OOF inference →
S7 verifier → S8 metrics → S9 checksums.

For the value-extraction experiment (no fine-tuning):

```bash
python value_extract.py --silver runs/full_auto/audit/silver_v2.jsonl \
  --limit 200 --out runs/value_exp_full
```

For the verifier feasibility check:

```bash
python verifier2.py --pred runs/value_exp_full/pred_hybrid.jsonl \
  --out runs/value_exp_full/verified2/pred_verified2.jsonl --limit 5
```

## 4. Expected values

See `results/value_experiments.json` and `results/confirmatory_20261117.json`.

**Confirmatory (frozen before inference, S0 passed):**

```bash
python run_pipeline.py --config configs/prereg_zs.yaml   --run-id prereg_zs_20261117 --detach
python run_hybrid_confirm.py --config configs/prereg_or.yaml
python evaluate_or.py
```

- rules value-F1 0.3969; zero-shot 0.0298; hybrid 0.4181 on 102 documents;
- presence macro-F1 0.9903 (hybrid), 0.9750 (zero-shot); quote validity 1.000 (hybrid);
- temporal hybrid: 0.4027 on 2025+ (n=25), 0.4653 pre-2025 (n=77);
- H4 (Tier-1 < Tier-2) falsified: 0.4409 > 0.2868.

**Exploratory (post-hoc):** rules 0.394; zero-shot 0.030; hybrid 0.415; verifier2
degrades value-F1 0.696 → 0.535 on 5 documents.

## 5. What is not reproduced

Q5 stability, Q6 decoy and Q7 AutoPK external anchor are not run in this release.
They require additional model calls or external data; report them as
`not_run`/`not_available`, not as passed.
