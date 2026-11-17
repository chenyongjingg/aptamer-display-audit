"""Pilot: build a consensus silver standard and evaluate one model against it.

This is intentionally small and auditable. It does not train; it exercises
S1-S2b + S6 + S8 on a subset so the full background run can be launched.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.common import FIELD_NAMES, load_jsonl, write_jsonl
from pipeline.llm import LLM
from pipeline.metrics import evaluate, write_report
from pipeline.rules import extract_rules
from pipeline.silver import build_silver, norm_source

DEFAULT_A = "/model/ModelScope/LLM-Research/Meta-Llama-3.1-8B-Instruct"
DEFAULT_B = "/model/ModelScope/AI-ModelScope/Ministral-8B-Instruct-2410"
DEFAULT_EVAL = "/model/ModelScope/Qwen/Qwen2.5-7B-Instruct"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_status(out: Path, state: str, **extra):
    payload = {"state": state, "updated_utc": _now(), **extra}
    (out / "status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--out", default="runs/pilot")
    ap.add_argument("--model-a", default=DEFAULT_A)
    ap.add_argument("--model-b", default=DEFAULT_B)
    ap.add_argument("--eval-model", default=DEFAULT_EVAL)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--no-4bit", action="store_true")
    ap.add_argument("--skip-silver", action="store_true")
    ap.add_argument("--b-sample", type=float, default=1.0)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_status(out, "starting", docs=args.docs, limit=args.limit)
    manifest = {
        "run_id": out.name,
        "started_utc": _now(),
        "docs": args.docs,
        "limit": args.limit,
        "silver_models": [args.model_a, args.model_b],
        "eval_model": args.eval_model,
        "load_in_4bit": not args.no_4bit,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    docs = load_jsonl(args.docs)
    # prefer full texts for the pilot
    docs = sorted(docs, key=lambda d: (d.get("level") != "full", d.get("doc_id", "")))[: args.limit]
    print(f"[pilot] docs={len(docs)} full={sum(1 for d in docs if d['level']=='full')}", flush=True)
    text_by_doc = {d["doc_id"]: d.get("text", "") for d in docs}

    silver_path = out / "silver_v1.0.jsonl"
    if not args.skip_silver or not silver_path.exists():
        print("[pilot] loading silver models", flush=True)
        llm_a = LLM(args.model_a, load_in_4bit=not args.no_4bit)
        llm_b = LLM(args.model_b, load_in_4bit=not args.no_4bit)
        import random
        from collections import defaultdict
        rng = random.Random(0)
        if args.b_sample >= 1.0:
            b_sample = {d["doc_id"] for d in docs}
        else:
            by = defaultdict(list)
            for d in docs:
                by[d.get("level")].append(d)
            b_sample = set()
            for level, items in by.items():
                k = max(1, int(round(len(items) * args.b_sample)))
                b_sample.update(d["doc_id"] for d in rng.sample(items, k))
        (out / "b_sample.json").write_text(json.dumps(sorted(b_sample), indent=2), encoding="utf-8")
        print(f"[pilot] b_sample={len(b_sample)}/{len(docs)}", flush=True)
        build_silver(docs, llm_a=llm_a, llm_b=llm_b, out_dir=out, limit=None,
                     cache_dir=out / "cache", b_sample=b_sample)
        del llm_a, llm_b
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
    silver_rows = load_jsonl(silver_path)
    print(f"[pilot] silver rows={len(silver_rows)}", flush=True)
    write_status(out, "silver_done", silver_rows=len(silver_rows))

    # rules as a baseline (E0)
    rule_rows = []
    for d in docs:
        f = extract_rules(d.get("text", ""))
        rule_rows.append({
            "doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "level": d.get("level"),
            "fields": f,
        })
    write_jsonl(out / "pred_rules.jsonl", rule_rows)
    r_rule = evaluate(rule_rows, silver_rows, text_by_doc)
    (out / "metrics_rules.json").write_text(json.dumps(r_rule, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(r_rule, out / "report_rules.md")
    print(f"[pilot] rules macro-F1={r_rule['macro_f1']} quote={r_rule['quote_valid_rate']}", flush=True)

    # one open-weight evaluator, zero-shot
    print(f"[pilot] loading eval model {args.eval_model}", flush=True)
    ev = LLM(args.eval_model, load_in_4bit=not args.no_4bit)
    pred_rows = []
    for i, d in enumerate(docs, 1):
        obj, raw = ev.extract(d.get("text", ""), d["doc_id"])
        ns = norm_source(obj)
        fields = {f: ns.get(f, {"status": "not_reported", "values": []}) for f in FIELD_NAMES}
        pred_rows.append({
            "doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "level": d.get("level"),
            "fields": fields, "raw": raw[:2000],
        })
        if i % 5 == 0:
            print(f"[pilot] eval {i}/{len(docs)}", flush=True)
    write_jsonl(out / "pred_eval.jsonl", pred_rows)
    eval_text = {d["doc_id"]: chr(10).join(ev._split(d.get("text", ""))) for d in docs}
    r_eval = evaluate(pred_rows, silver_rows, eval_text)
    (out / "metrics_eval.json").write_text(json.dumps(r_eval, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(r_eval, out / "report_eval.md")
    print(f"[pilot] eval macro-F1={r_eval['macro_f1']} quote={r_eval['quote_valid_rate']}", flush=True)
    manifest["finished_utc"] = _now()
    manifest["silver_rows"] = len(silver_rows)
    manifest["eval_macro_f1"] = r_eval["macro_f1"]
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_status(out, "done", silver_rows=len(silver_rows), macro_f1=r_eval["macro_f1"],
                 quote_valid_rate=r_eval["quote_valid_rate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
