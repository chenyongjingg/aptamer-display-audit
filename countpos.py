import json, sys
sys.path.insert(0,"/root/faudit")
from pipeline.common import load_jsonl
s=load_jsonl("runs/full_auto/audit/silver_v2.jsonl")
n=0; nv=0; byf={}
for r in s:
    for f,x in r["fields"].items():
        if x.get("confidence") in {"high","medium"} and x.get("status")=="reported":
            n+=1
            if x.get("values"): nv+=1
            byf[f]=byf.get(f,0)+1
print("reported high/medium",n,"with values",nv)
print(byf)
