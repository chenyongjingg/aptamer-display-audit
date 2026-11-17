"""Recompute the value-F1 table from the archived predictions (no GPU)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
from pipeline.rules import extract_rules

base = Path(__file__).resolve().parent
docs = load_jsonl(base / "data/docs.jsonl")
texts = {d["doc_id"]: d.get("text", "") for d in docs}
silver = load_jsonl(base / "runs/full_auto/audit/silver_v2.jsonl")
pred_zs = load_jsonl(base / "runs/full_auto/pred_zero_shot.jsonl")
pred_hy = load_jsonl(base / "runs/value_exp_full/pred_hybrid.jsonl")
rules = [{"doc_id": d["doc_id"], "paper_id": d.get("paper_id"),
          "fields": extract_rules(d.get("text", ""))} for d in docs]

out = {}
for name, rows in [("E0_rules", rules), ("E1_zero_shot", pred_zs), ("HYBRID", pred_hy)]:
    r = evaluate_v2(rows, silver, texts, confidence="high")
    out[name] = {"presence_macro_f1": r["macro_f1"], "value_f1": r["value_macro_f1"],
                 "quote_valid_rate": r["quote_valid_rate"], "coverage_high": r["coverage_high"],
                 "n_docs": r["n_docs"], "per_field": r["per_field"]}
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_field"} for k, v in out.items()}, indent=2))
Path(base / "results/audit_metrics_full.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
