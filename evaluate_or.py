import json, sys
from pathlib import Path
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
from pipeline.rules import extract_rules

root = Path("/root/faudit")
docs = load_jsonl(root/"data/docs.jsonl")
texts = {d["doc_id"]: d.get("text", "") for d in docs}
silver = load_jsonl(root/"runs/prereg_zs_20261117/audit/silver_v2.jsonl")
zs = load_jsonl(root/"runs/prereg_zs_20261117/pred_zero_shot.jsonl")
hy = load_jsonl(root/"runs/hybrid_confirm/pred_hybrid.jsonl")
rules = [{"doc_id": d["doc_id"], "paper_id": d.get("paper_id"),
          "fields": extract_rules(d.get("text", ""))} for d in docs]
out = {}
for name, rows in [("E0_rules", rules), ("E1_zero_shot", zs), ("HYBRID", hy)]:
    out[name] = evaluate_v2(rows, silver, texts, confidence="high")
# temporal subsets
def year(d):
    try: return int(str(d.get("year"))[:4])
    except Exception: return 0
late = {d["paper_id"] for d in docs if year(d) >= 2025}
early = {d["paper_id"] for d in docs if 0 < year(d) < 2025}
for name, rows in [("E1_zero_shot", zs), ("HYBRID", hy)]:
    out[f"{name}__late_2025plus"] = evaluate_v2(rows, silver, texts, confidence="high", paper_ids=late)
    out[f"{name}__early_pre2025"] = evaluate_v2(rows, silver, texts, confidence="high", paper_ids=early)
out["_autopk_reference"] = json.loads((root/"results/autopk_external_reference.json").read_text()) if (root/"results/autopk_external_reference.json").exists() else None
dest = root/"runs/or_confirm"; dest.mkdir(parents=True, exist_ok=True)
(dest/"audit_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
lines = ["# Original Research confirmatory metrics", "",
         "Primary: value set-F1 on high+medium reported fields.", "",
         "| system | value-F1 | presence | quote | coverage |",
         "|---|---|---|---|---|"]
for k in ["E0_rules","E1_zero_shot","HYBRID"]:
    r=out[k]; lines.append(f"| {k} | {r['value_macro_f1']} | {r['macro_f1']} | {r['quote_valid_rate']} | {r['coverage_high']} |")
lines += ["", "Temporal:", ""]
for k in out:
    if "__" in k:
        lines.append(f"- {k}: value-F1 {out[k]['value_macro_f1']} (n={out[k]['n_docs']})")
(dest/"audit_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
(dest/"manifest.json").write_text(json.dumps({"run":"or_confirm","n_docs":len(docs),"primary":"value_macro_f1"},indent=2),encoding="utf-8")
print(json.dumps({k:{"value":v["value_macro_f1"],"presence":v["macro_f1"]} for k,v in out.items() if not k.startswith("_")},indent=2))
