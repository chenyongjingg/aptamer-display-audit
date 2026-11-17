"""Summarise cross-family replication and prompt-stability comparisons."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.common import load_jsonl
from pipeline.audit_metrics import evaluate_v2

docs = load_jsonl(ROOT / "data/docs.jsonl")
texts = {d["doc_id"]: d.get("text", "") for d in docs}
silver = load_jsonl(ROOT / "runs/prereg_zs_20261117/audit/silver_v2.jsonl")
b = set(json.loads((ROOT / "runs/prereg_zs_20261117/b_sample.json").read_text(encoding="utf-8")))
clean_papers = {d["paper_id"] for d in docs if d["doc_id"] not in b}
ids_rep = set(json.loads((ROOT / "data/ids_replication.json").read_text(encoding="utf-8")))
base_zs = load_jsonl(ROOT / "runs/prereg_zs_20261117/pred_zero_shot.jsonl")
base_hy = load_jsonl(ROOT / "runs/hybrid_confirm/pred_hybrid.jsonl")
base_zs_sub = [r for r in base_zs if r["doc_id"] in ids_rep]


def m(rows, subset=None):
    r = evaluate_v2(rows, silver, texts, confidence="high", paper_ids=subset)
    return {k: r[k] for k in ("value_macro_f1", "macro_f1", "quote_valid_rate",
                              "coverage_high", "n_docs")}


out = {"baseline_full": {"E1_zero_shot": m(base_zs), "HYBRID": m(base_hy)},
       "baseline_replication_subset": {"E1_zero_shot": m(base_zs_sub)}}
paths = {
    "zs_ministral": ROOT / "runs/extra/zs_ministral/pred_zero_shot.jsonl",
    "hybrid_ministral": ROOT / "runs/extra/hybrid_ministral/pred_hybrid.jsonl",
    "zs_qwen_paraphrase": ROOT / "runs/extra/zs_qwen_paraphrase/pred_zero_shot.jsonl",
    "hybrid_qwen_paraphrase": ROOT / "runs/extra/hybrid_qwen_paraphrase/pred_hybrid.jsonl",
}
for name, p in paths.items():
    if not p.exists():
        out[name] = {"status": "missing"}
        continue
    rows = load_jsonl(p)
    entry = {"n_docs": len(rows), "full": m(rows)}
    if name.startswith("hybrid"):
        entry["clean_minus_B"] = m(rows, clean_papers)
    out[name] = entry

mapping = {
    "zs_ministral": "baseline_replication_subset::E1_zero_shot",
    "zs_qwen_paraphrase": "baseline_replication_subset::E1_zero_shot",
    "hybrid_ministral": "baseline_full::HYBRID",
    "hybrid_qwen_paraphrase": "baseline_full::HYBRID",
}
for name, ref in mapping.items():
    if "full" not in out.get(name, {}):
        continue
    base = out[ref.split("::")[0]][ref.split("::")[1]]
    out[name]["delta_vs_baseline"] = {
        "value_f1": out[name]["full"]["value_macro_f1"] - base["value_macro_f1"],
        "presence": out[name]["full"]["macro_f1"] - base["macro_f1"],
        "quote": out[name]["full"]["quote_valid_rate"] - base["quote_valid_rate"]}

dest = ROOT / "runs/extra/eval_extra.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, indent=1))
