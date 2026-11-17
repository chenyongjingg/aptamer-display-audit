#!/bin/bash
set -u
cd /root/faudit || exit 1
echo "[extra] start $(date -u)"
python3 run_zs_eval.py --model /model/ModelScope/AI-ModelScope/Ministral-8B-Instruct-2410 \
  --docs data/docs_replication.jsonl --out runs/extra/zs_ministral --tag cross_family_ministral
echo "[extra] zs_ministral done $(date -u)"
python3 run_hybrid_confirm.py --config configs/prereg_or_ministral.yaml
echo "[extra] hybrid_ministral done $(date -u)"
python3 run_zs_paraphrase.py --docs data/docs_replication.jsonl \
  --out runs/extra/zs_qwen_paraphrase --tag q5_paraphrase
echo "[extra] zs_paraphrase done $(date -u)"
python3 run_hybrid_paraphrase.py --config configs/prereg_or.yaml --out runs/extra/hybrid_qwen_paraphrase
echo "[extra] hybrid_paraphrase done $(date -u)"
python3 eval_extra.py
echo "[extra] eval done $(date -u)"
echo "[extra] ALL DONE"
