import json
base="runs/full_auto"
for name in ["pred_finetuned.jsonl","pred_zero_shot.jsonl"]:
    print("===",name)
    rows=[json.loads(l) for l in open(base+"/"+name) if l.strip()]
    for r in rows[:3]:
        print("doc",r["doc_id"],"raw:",(r.get("raw") or "")[:800].replace("\n"," "))
        print()
