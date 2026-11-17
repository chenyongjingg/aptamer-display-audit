#!/bin/bash
set -e
cd /root/faudit
while true; do
  state=$(python3 -c "import json;print(json.load(open('runs/prereg_zs_20261117/status.json')).get('state',''))" 2>/dev/null || echo "")
  echo "waiting prereg_zs state=$state $(date -u +%H:%M:%SZ)"
  if [ "$state" = "done" ]; then break; fi
  if [ "$state" = "failed" ] || [ "$state" = "blocked" ]; then echo "prereg_zs $state"; exit 2; fi
  sleep 60
done
python3 run_hybrid_confirm.py --config configs/prereg_or.yaml
python3 evaluate_or.py
echo "OR_PIPELINE_DONE"
