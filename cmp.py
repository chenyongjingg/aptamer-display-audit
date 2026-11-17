import json
base="runs/full_auto"
pred={r["doc_id"]:r for r in (json.loads(l) for l in open(base+"/pred_finetuned.jsonl") if l.strip())}
sil={r["doc_id"]:r for r in (json.loads(l) for l in open(base+"/audit/silver_v2.jsonl") if l.strip())}
for did in ["S24_full","S0_full","S113_full"]:
    if did not in pred: continue
    print("===",did)
    for f in ["kd","id_per_g","half_life","valency","size","comparator","route","dose"]:
        p=pred[did]["fields"].get(f,{}); g=sil[did]["fields"].get(f,{})
        if p.get("status")=="reported" or g.get("status")=="reported":
            print(f,"PRED",p.get("status"),p.get("values",[])[:2])
            print(f,"GOLD",g.get("status"),g.get("values",[])[:2])
