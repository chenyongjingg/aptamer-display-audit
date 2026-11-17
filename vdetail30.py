import sys, json
sys.path.insert(0,"/root/faudit")
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
base="runs/full_auto"
docs={d["doc_id"]:d.get("text","") for d in load_jsonl("data/docs.jsonl")}
sil=load_jsonl(base+"/audit/silver_v2.jsonl")
pred=load_jsonl("runs/value_exp30/pred_hybrid.jsonl")
r=evaluate_v2(pred,sil,docs,confidence="high")
print("value",r["value_macro_f1"],"presence",r["macro_f1"],"quote",r["quote_valid_rate"],"cov",r["coverage_high"])
for f,x in r["per_field"].items():
    print(f,"presence",x["presence_f1"],"value",x["value_f1"],"nval",x["n_value_docs"],"nctx",x["n_context_docs"])
