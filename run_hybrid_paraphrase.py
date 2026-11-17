"""Q5 stability: hybrid extraction with a paraphrased field-level system prompt."""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import yaml
from pipeline.common import load_jsonl, write_jsonl
from pipeline.llm import LLM
from pipeline.audit_metrics import evaluate_v2
import value_extract as ve

ve.SYSTEM = (ROOT / "prompts" / "field_system_paraphrase.md").read_text(encoding="utf-8")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/prereg_or.yaml")
    ap.add_argument("--out", default="runs/extra/hybrid_qwen_paraphrase")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    docs = load_jsonl(ROOT / cfg["docs"])
    if args.limit:
        docs = docs[: args.limit]
    silver = load_jsonl(ROOT / cfg["silver"])
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(json.dumps({"state": "loading", "updated_utc": now()}), encoding="utf-8")
    llm = LLM(cfg["model"], load_in_4bit=True, max_new_tokens=int(cfg.get("max_new_tokens", 300)))
    rows = []
    for i, d in enumerate(docs, 1):
        _, hy = ve.extract_doc(llm, d)
        rows.append({"doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "level": d.get("level"), "fields": hy})
        (out / "status.json").write_text(json.dumps(
            {"state": "running", "done": i, "total": len(docs), "updated_utc": now()}, indent=2), encoding="utf-8")
        if i % 10 == 0:
            print(f"[hybrid-para] {i}/{len(docs)}", flush=True)
    write_jsonl(out / "pred_hybrid.jsonl", rows)
    texts = {d["doc_id"]: d.get("text", "") for d in docs}
    r = evaluate_v2(rows, silver, texts, confidence="high")
    (out / "metrics.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "status.json").write_text(json.dumps(
        {"state": "done", "done": len(rows), "updated_utc": now()}, indent=2), encoding="utf-8")
    print("DONE value_f1", r["value_macro_f1"], "presence", r["macro_f1"], flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
