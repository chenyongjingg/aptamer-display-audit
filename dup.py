import json
from collections import Counter
base="runs/full_auto"
rows=[json.loads(l) for l in open(base+"/pred_finetuned.jsonl") if l.strip()]
print("rows",len(rows),"unique",len({r['doc_id'] for r in rows}))
c=Counter(r["doc_id"] for r in rows)
print("dups",[k for k,v in c.items() if v>1][:10])
for r in rows:
    if r["doc_id"]=="S24_full":
        print("S24_full fields kd", r["fields"].get("kd"))
        print("raw", (r.get("raw") or "")[:300])
