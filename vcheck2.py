import json, sys
sys.path.insert(0,"/root/faudit")
from pipeline.common import load_jsonl
base="runs/full_auto"
pred={r["doc_id"]:r for r in load_jsonl(base+"/pred_zero_shot.jsonl")}
sil={r["doc_id"]:r for r in load_jsonl(base+"/audit/silver_v2.jsonl")}
n=0
for did,p in pred.items():
    g=sil.get(did,{})
    for f in ["kd","id_per_g","half_life","dose","time_points","numeric_efficacy","serum_stability","valency","spacing","linker_length","size"]:
        gx=g.get("fields",{}).get(f,{})
        px=p.get("fields",{}).get(f,{})
        if gx.get("confidence")=="high" and gx.get("status")=="reported":
            print(did,f,"GOLD",gx.get("values",[])[:2],"PRED",px.get("status"),px.get("values",[])[:2])
            n+=1
            if n>=12: raise SystemExit
