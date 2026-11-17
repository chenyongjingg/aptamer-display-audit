import json, sys
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
base="runs/full_auto"
docs={d["doc_id"]:d.get("text","") for d in load_jsonl("data/docs.jsonl")}
sil=load_jsonl(base+"/audit/silver_v2.jsonl")
for name in ["pred_rules.jsonl","pred_zero_shot.jsonl","pred_finetuned.jsonl"]:
    p=load_jsonl(base+"/"+name) if __import__("os").path.exists(base+"/"+name) else []
    if not p: continue
    r=evaluate_v2(p,sil,docs,confidence="high")
    print(name,"value",r["value_macro_f1"],"ctx",r["context_macro_f1"],"presence",r["macro_f1"])
    for f,x in r["per_field"].items():
        if x["value_f1"] not in (None,0.0):
            print("  ",f,x["value_f1"],x["n_value_docs"])
