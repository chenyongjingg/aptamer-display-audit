"""Value-F1 stratified by document level (abstract vs full text) and year."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.common import FIELD_NAMES, load_jsonl
from pipeline.audit_metrics import value_scores
from pipeline.rules import extract_rules

docs = load_jsonl(ROOT / "data/docs.jsonl")
silver = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/prereg_zs_20261117/audit/silver_v2.jsonl")}
zs = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/prereg_zs_20261117/pred_zero_shot.jsonl")}
hy = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/hybrid_confirm/pred_hybrid.jsonl")}
rules = {d["doc_id"]: {"fields": extract_rules(d.get("text", ""))} for d in docs}
systems = {"E0_rules": rules, "E1_zero_shot": zs, "HYBRID": hy}


def value_macro(pred, ids):
    per = []
    for f in FIELD_NAMES:
        vals = []
        for d in ids:
            g = silver[d]["fields"].get(f, {})
            if g.get("status") == "reported" and g.get("confidence") in {"high", "medium"}:
                v = value_scores(pred[d]["fields"].get(f, {}), g)["value_f1"]
                if v is not None:
                    vals.append(v)
        if vals:
            per.append(sum(vals) / len(vals))
    return sum(per) / len(per) if per else None, len(per)


def yr(d):
    try:
        return int(str(d.get("year"))[:4])
    except Exception:
        return 0


groups = {
    "abstract": [d["doc_id"] for d in docs if d.get("level") == "abstract"],
    "full_text": [d["doc_id"] for d in docs if d.get("level") == "full"],
    "pre2025": [d["doc_id"] for d in docs if 0 < yr(d) < 2025],
    "2025plus": [d["doc_id"] for d in docs if yr(d) >= 2025],
}
out = {g: {"n_docs": len(ids), "systems": {}} for g, ids in groups.items()}
for g, ids in groups.items():
    ids = [d for d in ids if d in silver]
    out[g]["n_docs"] = len(ids)
    for s, rows in systems.items():
        v, nf = value_macro(rows, ids)
        out[g]["systems"][s] = {"value_macro_f1": v, "n_fields_with_positive": nf}
dest = ROOT / "runs/robustness/stratified.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, indent=1))
