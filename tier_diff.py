import json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.common import FIELD_NAMES, load_jsonl
from pipeline.audit_metrics import value_scores, TIER

silver = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/prereg_zs_20261117/audit/silver_v2.jsonl")}
hy = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/hybrid_confirm/pred_hybrid.jsonl")}
ids = sorted(set(silver) & set(hy))
fields_t = {t: [f for f in FIELD_NAMES if TIER[f] == t] for t in (1, 2, 3)}

def macro(doc_ids, fields):
    per = []
    for f in fields:
        vals = []
        for d in doc_ids:
            g = silver[d]["fields"].get(f, {})
            if g.get("status") == "reported" and g.get("confidence") in {"high", "medium"}:
                v = value_scores(hy[d]["fields"].get(f, {}), g)["value_f1"]
                if v is not None:
                    vals.append(v)
        if vals:
            per.append(sum(vals) / len(vals))
    return sum(per) / len(per) if per else None

rng = random.Random(0)
diffs = []
for _ in range(2000):
    sample = [ids[rng.randrange(len(ids))] for _ in ids]
    a = macro(sample, fields_t[1]); b = macro(sample, fields_t[2])
    if a is not None and b is not None:
        diffs.append(a - b)
diffs.sort()
point = macro(ids, fields_t[1]) - macro(ids, fields_t[2])
out = {"tier1_minus_tier2": point,
       "ci95": [diffs[int(0.025*len(diffs))], diffs[int(0.975*len(diffs))-1]],
       "p_two_sided_approx": 2*min(sum(1 for x in diffs if x <= 0), sum(1 for x in diffs if x >= 0))/len(diffs),
       "n": len(diffs)}
print(json.dumps(out, indent=1))
Path(ROOT/"runs/robustness/tier_diff.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
