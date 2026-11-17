"""Leave-one-source-out sensitivity of the consensus silver standard (offline)."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.common import load_jsonl, write_jsonl
from pipeline.reconsensus import build_v2
from pipeline.rules import extract_rules
from pipeline.audit_metrics import evaluate_v2

docs = load_jsonl(ROOT / "data/docs.jsonl")
texts = {d["doc_id"]: d.get("text", "") for d in docs}
src = load_jsonl(ROOT / "runs/prereg_zs_20261117/audit/silver_sources_v2.jsonl")
b = set(json.loads((ROOT / "runs/prereg_zs_20261117/b_sample.json").read_text(encoding="utf-8")))
outdir = ROOT / "runs/robustness"
outdir.mkdir(parents=True, exist_ok=True)


def variant(name, keep):
    rows = []
    for r in src:
        s = {k: v for k, v in r["sources"].items() if k in keep}
        rows.append({"doc_id": r["doc_id"], "sources": s})
    p = outdir / f"sources_{name}.jsonl"
    write_jsonl(p, rows)
    d = outdir / name
    d.mkdir(parents=True, exist_ok=True)
    build_v2(docs, p, d, review_path=str(ROOT / "data/extraction.csv"))
    return d / "silver_v2.jsonl"


paths = {
    "full": ROOT / "runs/prereg_zs_20261117/audit/silver_v2.jsonl",
    "noB": variant("silver_noB", {"rule", "llmA"}),
    "Bonly": variant("silver_Bonly", {"rule", "llmB"}),
}
zs = load_jsonl(ROOT / "runs/prereg_zs_20261117/pred_zero_shot.jsonl")
hy = load_jsonl(ROOT / "runs/hybrid_confirm/pred_hybrid.jsonl")
rules = [{"doc_id": d["doc_id"], "paper_id": d.get("paper_id"),
          "fields": extract_rules(d.get("text", ""))} for d in docs]
systems = {"E0_rules": rules, "E1_zero_shot": zs, "HYBRID": hy}
b_papers = {d["paper_id"] for d in docs if d["doc_id"] in b}
res = {}
for name, p in paths.items():
    silver = load_jsonl(p)
    qa = json.loads((p.parent / "silver_qa_v2.json").read_text(encoding="utf-8"))
    tiers = qa.get("tier_coverage", {})
    cov = sum(v["high"] for v in tiers.values()) / max(1, sum(v["n"] for v in tiers.values()))
    res[name] = {"coverage_high": cov, "systems": {}}
    subset = b_papers if name == "Bonly" else None
    for sname, rows in systems.items():
        m = evaluate_v2(rows, silver, texts, confidence="high", paper_ids=subset)
        res[name]["systems"][sname] = {
            "value_macro_f1": m["value_macro_f1"], "presence": m["macro_f1"],
            "n_docs": m["n_docs"], "coverage_high": m["coverage_high"]}
    if name != "full":
        for sname in systems:
            a = res["full"]["systems"][sname]["value_macro_f1"]
            c = res[name]["systems"][sname]["value_macro_f1"]
            res[name]["systems"][sname]["delta_vs_full"] = None if a is None or c is None else c - a
(outdir / "silver_loo.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(res, indent=1))
