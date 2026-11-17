import sys, json
sys.path.insert(0,"/root/faudit")
from pipeline.common import load_jsonl
from pipeline.audit_metrics import value_scores
base="runs/full_auto"
sil={r["doc_id"]:r for r in load_jsonl(base+"/audit/silver_v2.jsonl")}
pred={r["doc_id"]:r for r in load_jsonl("runs/value_exp30/pred_hybrid.jsonl")}
n=0
for did,p in pred.items():
    g=sil.get(did,{})
    for f,x in g.get("fields",{}).items():
        if x.get("status")=="reported" and x.get("confidence") in {"high","medium"}:
            n+=1
            vs=value_scores(p.get("fields",{}).get(f,{}),x)
            print(did,f,"conf",x.get("confidence"),"nvals",len(x.get("values",[])),"vs",vs)
            if n>=12: raise SystemExit
