"""Check the archived snapshot for the files and counts needed to reproduce."""
import json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
must = [
 "data/docs.jsonl", "data/splits.json", "data/silver_qa_v2.json",
 "runs/full_auto/audit/silver_v2.jsonl", "runs/full_auto/audit/splits.json",
 "runs/full_auto/pred_zero_shot.jsonl", "runs/value_exp_full/pred_hybrid.jsonl",
 "runs/value_exp_full/pred_llm_candidates.jsonl",
 "runs/value_exp30/verified2/pred_verified2.jsonl",
 "results/value_experiments.json", "results/audit_metrics_full.json",
 "environment/environment.json", "environment/pip-freeze.txt",
 "prereg.json", "protocol.md", "prompts/p2.md",
]
ok = True
for f in must:
    p = root / f
    print(("OK  " if p.exists() else "MISS"), f)
    ok = ok and p.exists()
docs = [json.loads(l) for l in open(root/"data/docs.jsonl", encoding="utf-8")]
sil = [json.loads(l) for l in open(root/"runs/full_auto/audit/silver_v2.jsonl", encoding="utf-8")]
sp = json.load(open(root/"data/splits.json"))
print("docs", len(docs), "silver", len(sil), "leakage", sp["leakage_train_test_paper_overlap"])
if len(docs) != 102 or len(sil) != 102 or sp["leakage_train_test_paper_overlap"] != 0:
    ok = False
sys.path.insert(0, str(root))
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
from pipeline.rules import extract_rules
texts = {d["doc_id"]: d.get("text", "") for d in docs}
for name, rows in [
    ("E0_rules", [{"doc_id": d["doc_id"], "paper_id": d.get("paper_id"),
                   "fields": extract_rules(d.get("text", ""))} for d in docs]),
    ("E1_zero_shot", load_jsonl(root/"runs/full_auto/pred_zero_shot.jsonl")),
    ("HYBRID", load_jsonl(root/"runs/value_exp_full/pred_hybrid.jsonl")),
]:
    r = evaluate_v2(rows, sil, texts, confidence="high")
    print(name, "value_f1", round(r["value_macro_f1"], 3), "presence", round(r["macro_f1"], 3))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
