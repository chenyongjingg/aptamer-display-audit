"""Zero-shot audit with an arbitrary instruct model under the frozen p2 prompt."""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.common import load_jsonl, write_jsonl
from pipeline.audit_metrics import evaluate_v2
from run_pipeline import _infer_rows


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--silver", default="runs/prereg_zs_20261117/audit/silver_v2.jsonl")
    ap.add_argument("--b-sample", default="runs/prereg_zs_20261117/b_sample.json")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    docs = load_jsonl(ROOT / args.docs)
    if args.limit:
        docs = docs[: args.limit]
    silver = load_jsonl(ROOT / args.silver)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(json.dumps(
        {"state": "loading", "model": args.model, "updated_utc": now()}, indent=2), encoding="utf-8")
    rows = _infer_rows(args.model, None, docs)
    write_jsonl(out / "pred_zero_shot.jsonl", rows)
    texts = {d["doc_id"]: d.get("text", "") for d in docs}
    full = evaluate_v2(rows, silver, texts, confidence="high")
    # clean subset: papers without any document used as a silver-B source
    b = set(json.loads((ROOT / args.b_sample).read_text(encoding="utf-8"))) if (ROOT / args.b_sample).exists() else set()
    clean_papers = {d["paper_id"] for d in docs if d["doc_id"] not in b}
    clean = evaluate_v2(rows, silver, texts, confidence="high", paper_ids=clean_papers)
    res = {"tag": args.tag, "model": args.model, "n_docs": len(rows),
           "full": full, "clean_minus_B": clean,
           "n_clean_papers": len(clean_papers)}
    (out / "metrics.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "model": args.model, "docs": args.docs, "silver": args.silver,
        "n_docs": len(rows), "finished_utc": now(),
        "value_f1": full["value_macro_f1"], "presence": full["macro_f1"],
        "value_f1_clean_minus_B": clean["value_macro_f1"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "status.json").write_text(json.dumps(
        {"state": "done", "done": len(rows), "updated_utc": now()}, indent=2), encoding="utf-8")
    print("DONE value_f1", full["value_macro_f1"], "presence", full["macro_f1"],
          "clean", clean["value_macro_f1"], flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
