"""Pre-registered hybrid value extraction: rules + field-level Qwen2.5-7B."""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline.common import load_jsonl, write_jsonl
from pipeline.llm import LLM
from pipeline.audit_metrics import evaluate_v2
from value_extract import extract_doc

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parent
    docs = load_jsonl(root / cfg["docs"])
    if args.limit: docs = docs[:args.limit]
    silver = load_jsonl(root / cfg["silver"])
    out = root / cfg["out"]; out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(json.dumps({"state": "loading", "updated_utc": now()}, indent=2), encoding="utf-8")
    llm = LLM(cfg["model"], load_in_4bit=True, max_new_tokens=int(cfg.get("max_new_tokens", 300)))
    rows = []
    for i, d in enumerate(docs, 1):
        _, hy = extract_doc(llm, d)
        rows.append({"doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "level": d.get("level"), "fields": hy})
        (out / "status.json").write_text(json.dumps({"state": "running", "done": i, "total": len(docs), "updated_utc": now()}, indent=2), encoding="utf-8")
        if i % 5 == 0:
            print(f"[hybrid] {i}/{len(docs)}", flush=True)
    write_jsonl(out / "pred_hybrid.jsonl", rows)
    texts = {d["doc_id"]: d.get("text", "") for d in docs}
    r = evaluate_v2(rows, silver, texts, confidence="high")
    (out / "metrics.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "config": args.config, "n_docs": len(rows), "model": cfg["model"],
        "silver": cfg["silver"], "finished_utc": now(),
        "primary": "value_macro_f1", "value_f1": r["value_macro_f1"],
        "presence_macro_f1": r["macro_f1"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "status.json").write_text(json.dumps({"state": "done", "done": len(rows), "total": len(docs), "updated_utc": now()}, indent=2), encoding="utf-8")
    print("value_f1", r["value_macro_f1"], "presence", r["macro_f1"], flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
