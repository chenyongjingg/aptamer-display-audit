import sys, json
sys.path.insert(0,"/root/faudit")
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
base="runs/full_auto"
sil=load_jsonl(base+"/audit/silver_v2.jsonl")
texts={d["doc_id"]:d.get("text","") for d in load_jsonl("data/docs.jsonl")}
hy=load_jsonl("runs/value_exp8/pred_hybrid.jsonl")
vf=load_jsonl("runs/value_exp8/verified/pred_verified.jsonl")
ids={r["doc_id"] for r in vf}
hy=[r for r in hy if r["doc_id"] in ids]
for name,rows in [("HYBRID_5",hy),("VERIFIED_5",vf)]:
    r=evaluate_v2(rows,sil,texts,confidence="high")
    print(name,"presence",r["macro_f1"],"value",r["value_macro_f1"],"quote",r["quote_valid_rate"],"cov",r["coverage_high"])
    for f,x in r["per_field"].items():
        if x["value_f1"] not in (None,0.0): print("  ",f,x["value_f1"],x["n_value_docs"])
