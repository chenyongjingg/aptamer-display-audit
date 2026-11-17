import sys, json
sys.path.insert(0,"/root/faudit")
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2
from pipeline.rules import extract_rules
base="runs/full_auto"
sil=load_jsonl(base+"/audit/silver_v2.jsonl")
texts={d["doc_id"]:d.get("text","") for d in load_jsonl("data/docs.jsonl")}
sub=load_jsonl("runs/value_exp8/pred_hybrid.jsonl")
ids={r["doc_id"] for r in sub}
zs=[r for r in load_jsonl(base+"/pred_zero_shot.jsonl") if r["doc_id"] in ids]
rules=[{"doc_id":r["doc_id"],"paper_id":None,"fields":extract_rules(texts[r["doc_id"]])} for r in sub]
for name,rows in [("E0_rules",rules),("E1_zero_shot_subset",zs),("E1cand_llm",load_jsonl("runs/value_exp8/pred_llm_candidates.jsonl")),("HYBRID",sub)]:
    r=evaluate_v2(rows,sil,texts,confidence="high")
    print(name,"presence",round(r["macro_f1"],3) if r["macro_f1"] else None,
          "value",round(r["value_macro_f1"],3) if r["value_macro_f1"] is not None else None,
          "quote",r["quote_valid_rate"],"coverage",round(r["coverage_high"],3))
    for f,x in r["per_field"].items():
        if x["value_f1"] not in (None,0.0):
            print("  ",f,round(x["value_f1"],3),"n",x["n_value_docs"])
