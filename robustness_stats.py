"""Bootstrap CIs, paired comparisons and failure taxonomy on confirmatory predictions."""
import json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.common import FIELD_NAMES, load_jsonl
from pipeline.audit_metrics import value_scores, TIER
from pipeline.rules import extract_rules
from pipeline.failure import analyze

docs = load_jsonl(ROOT / "data/docs.jsonl")
texts = {d["doc_id"]: d.get("text", "") for d in docs}
silver = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/prereg_zs_20261117/audit/silver_v2.jsonl")}
zs = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/prereg_zs_20261117/pred_zero_shot.jsonl")}
hy = {r["doc_id"]: r for r in load_jsonl(ROOT / "runs/hybrid_confirm/pred_hybrid.jsonl")}
rules = {d["doc_id"]: {"doc_id": d["doc_id"], "paper_id": d.get("paper_id"),
                       "fields": extract_rules(d.get("text", ""))} for d in docs}
systems = {"E0_rules": rules, "E1_zero_shot": zs, "HYBRID": hy}
ids = sorted(set(silver) & set(zs) & set(hy))


def value_macro(pred, gold, doc_ids):
    out = []
    for f in FIELD_NAMES:
        vals = []
        for d in doc_ids:
            g = gold[d]["fields"].get(f, {})
            if g.get("status") == "reported" and g.get("confidence") in {"high", "medium"}:
                v = value_scores(pred[d]["fields"].get(f, {}), g)["value_f1"]
                if v is not None:
                    vals.append(v)
        if vals:
            out.append(sum(vals) / len(vals))
    return sum(out) / len(out) if out else None


def ci(sample, lo=0.025, hi=0.975):
    s = sorted(x for x in sample if x is not None)
    return (s[int(lo * len(s))], s[int(hi * len(s)) - 1]) if s else (None, None)


rng = random.Random(0)
B = 2000
boot = {k: [] for k in systems}
diff = {("HYBRID", "E0_rules"): [], ("HYBRID", "E1_zero_shot"): []}
for _ in range(B):
    sample = [ids[rng.randrange(len(ids))] for _ in ids]
    vals = {k: value_macro(v, silver, sample) for k, v in systems.items()}
    for k in systems:
        boot[k].append(vals[k])
    for (a, b), acc in diff.items():
        if vals[a] is not None and vals[b] is not None:
            acc.append(vals[a] - vals[b])

out = {"n_docs": len(ids), "n_boot": B, "systems": {}, "paired": {}}
for k, vals in boot.items():
    point = value_macro(systems[k], silver, ids)
    out["systems"][k] = {"value_macro_f1": point, "ci95": ci(vals),
                         "bootstrap_mean": sum(vals) / len(vals)}
for (a, b), d in diff.items():
    d_sorted = sorted(d)
    out["paired"][f"{a}_minus_{b}"] = {
        "delta_mean": sum(d) / len(d),
        "ci95": (d_sorted[int(0.025 * len(d))], d_sorted[int(0.975 * len(d)) - 1]),
        "p_two_sided_approx": 2 * min(sum(1 for x in d if x <= 0), sum(1 for x in d if x >= 0)) / len(d),
        "n": len(d)}

tiers = {}
for t in (1, 2, 3):
    fields = [f for f in FIELD_NAMES if TIER[f] == t]
    vals = []
    for _ in range(1000):
        sample = [ids[rng.randrange(len(ids))] for _ in ids]
        acc = []
        for f in fields:
            fv = []
            for d in sample:
                g = silver[d]["fields"].get(f, {})
                if g.get("status") == "reported" and g.get("confidence") in {"high", "medium"}:
                    v = value_scores(hy[d]["fields"].get(f, {}), g)["value_f1"]
                    if v is not None:
                        fv.append(v)
            if fv:
                acc.append(sum(fv) / len(fv))
        if acc:
            vals.append(sum(acc) / len(acc))
    point = None
    acc = []
    for f in fields:
        fv = []
        for d in ids:
            g = silver[d]["fields"].get(f, {})
            if g.get("status") == "reported" and g.get("confidence") in {"high", "medium"}:
                v = value_scores(hy[d]["fields"].get(f, {}), g)["value_f1"]
                if v is not None:
                    fv.append(v)
        if fv:
            acc.append(sum(fv) / len(fv))
    point = sum(acc) / len(acc) if acc else None
    tiers[f"tier{t}"] = {"value_macro_f1": point, "ci95": ci(vals), "n_fields": len(fields)}
out["hybrid_tiers"] = tiers

tax = {}
for k, rows in systems.items():
    a = analyze(list(rows.values()), list(silver.values()), texts)
    tax[k] = {"counts": a["counts"], "absence_jaccard_mean": a["absence_jaccard_mean"],
              "absence_jaccard_n": a["absence_jaccard_n"]}
    full = ROOT / "runs/robustness" / f"failure_{k}.json"
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
out["failure_taxonomy"] = tax

dest = ROOT / "runs/robustness/robustness_stats.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "failure_taxonomy"}, indent=1))
