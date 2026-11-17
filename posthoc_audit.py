"""Post-hoc scientific audit of a completed pilot/full run.

Consumes the persisted silver sources, rebuilds the consensus with the fixed
rules (multi-value, context, Tier coverage), and re-evaluates the predictions
on high-confidence silver. No model calls; safe to run while the GPU is busy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.audit_metrics import evaluate_v2
from pipeline.failure import analyze as failure_analyze
from pipeline.common import FIELD_NAMES, load_jsonl, sha256_file
from pipeline.reconsensus import build_v2
from pipeline.splits import make_splits, write_splits


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--papers", default="data/papers.jsonl")
    ap.add_argument("--review", default="data/extraction.csv")
    ap.add_argument("--out", default=None)
    ap.add_argument("--rebuild-cache", action="store_true")
    args = ap.parse_args()

    run = Path(args.run)
    out = Path(args.out) if args.out else run / "audit"
    out.mkdir(parents=True, exist_ok=True)
    docs = load_jsonl(args.docs)
    papers = load_jsonl(args.papers)
    doc_by_id = {d["doc_id"]: d for d in docs}
    text_by_doc = {d["doc_id"]: d.get("text", "") for d in docs}

    # S0: pre-registration hash check
    prereg = json.loads(Path("prereg.json").read_text(encoding="utf-8")) if Path("prereg.json").exists() else {}
    s0 = {"status": "failed", "reason": "prereg.json missing", "checked": {}}
    if prereg:
        ok = True
        checked = {}
        for rel, expected in prereg.get("hashes", {}).items():
            actual = sha256_file(rel)
            checked[rel] = {"expected": expected, "actual": actual, "match": actual == expected}
            ok = ok and actual == expected
        s0 = {"status": "done" if ok else "failed", "checked": checked,
              "reason": "hash match" if ok else "protocol/prompt/config changed since prereg"}
    (out / "freeze_report.json").write_text(json.dumps(s0, ensure_ascii=False, indent=2), encoding="utf-8")
    if s0["status"] != "done":
        print("S0 FAILED:", s0["reason"], flush=True)

    # S2b: re-consensus + QA
    sources = run / "silver_sources.jsonl"
    if args.rebuild_cache:
        from pipeline.rules import extract_rules
        from pipeline.silver import norm_source
        cache = run / "cache"
        rows = []
        for d in docs:
            did = d["doc_id"]
            src = {"rule": extract_rules(d.get("text", ""))}
            for tag, key in (("A", "llmA"), ("B", "llmB")):
                files = sorted(cache.glob(f"{tag}_*_{did}.json"))
                if not files:
                    continue
                try:
                    payload = json.loads(files[0].read_text(encoding="utf-8"))
                    obj = payload.get("obj") if isinstance(payload, dict) else None
                except Exception:
                    obj = None
                if obj is not None:
                    src[key] = norm_source(obj)
            rows.append({"doc_id": did, "sources": src})
        sources = out / "silver_sources_v2.jsonl"
        from pipeline.common import write_jsonl
        write_jsonl(sources, rows)
        print(f"rebuilt sources from cache: {len(rows)}", flush=True)
    if not sources.exists():
        raise SystemExit(f"missing {sources}")
    res = build_v2(docs, sources, out, review_path=args.review)
    print("silver v2", res["rows"], flush=True)

    # S3: paper-level splits
    splits = make_splits(papers, folds=5, seed=0)
    write_splits(splits, out / "splits.json")

    silver_v2 = load_jsonl(out / "silver_v2.jsonl")
    pred_eval = load_jsonl(run / "pred_eval.jsonl")
    pred_rules = load_jsonl(run / "pred_rules.jsonl")

    failure = failure_analyze(pred_eval, silver_v2, text_by_doc)
    (out / "failure_taxonomy.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")

    results = {}
    for name, preds in (("rules", pred_rules), ("qwen2.5-7b-zero-shot", pred_eval)):
        for conf in ("high", ("high", "medium"), "all"):
            key = f"{name}__{'high' if conf == 'high' else ('high_medium' if isinstance(conf, tuple) else 'all')}"
            results[key] = evaluate_v2(preds, silver_v2, text_by_doc, confidence=conf)
            print(key, results[key]["macro_f1"], results[key]["coverage_high"], flush=True)

    # 5-fold paper-level out-of-fold evaluation
    assignment = splits["assignment"]
    fold_results = {}
    for k in range(splits["folds"]):
        test_papers = {p for p, f in assignment.items() if f == k}
        for name, preds in (("rules", pred_rules), ("qwen2.5-7b-zero-shot", pred_eval)):
            fold_results[f"{name}__fold{k}"] = evaluate_v2(
                preds, silver_v2, text_by_doc, confidence="high", paper_ids=test_papers)
    fold_macro = {}
    for name in ("rules", "qwen2.5-7b-zero-shot"):
        vals = [fold_results[f"{name}__fold{k}"]["macro_f1"] for k in range(splits["folds"])]
        vals = [v for v in vals if v is not None]
        fold_macro[name] = sum(vals) / len(vals) if vals else None
    results["oof"] = {"folds": fold_macro, "n_folds": splits["folds"]}
    results["fold_detail"] = fold_results
    (out / "audit_metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # report
    lines = ["# Post-hoc scientific audit", "", f"run: `{run}`", f"generated: {now()}", ""]
    lines += ["## Silver v2 QA", "", "```json",
              json.dumps(res["qa"], ensure_ascii=False, indent=2)[:12000], "```", ""]
    lines += ["## Metrics", "",
              "| system | confidence | macro-F1 | 95% CI | coverage | Tier-1 | Tier-2 | Tier-3 | value-F1 | context-F1 | quote(skeleton) | quote(exact) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in results.items():
        if "macro_f1" not in r:
            continue
        ci = r["macro_f1_ci95"]
        lines.append(
            f"| {k} | {r['confidence']} | {r['macro_f1']} | {ci} | {r['coverage_high']} | "
            f"{r['tier_macro_f1'].get(1)} | {r['tier_macro_f1'].get(2)} | {r['tier_macro_f1'].get(3)} | "
            f"{r['value_macro_f1']} | {r['context_macro_f1']} | {r['quote_valid_rate']} | {r['quote_exact_rate']} |"
        )
    lines += ["", "## Splits", "", "```json", json.dumps(splits, ensure_ascii=False, indent=2)[:4000], "```", ""]
    lines += ["## Scope notes", "",
              "- Primary = high-confidence consensus silver; high+medium and all are sensitivity.",
              "- `quote(skeleton)` is the operational quote gate (robust to tokenizer whitespace); `quote(exact)` is the strict substring rate.",
              "- Silver is not human truth; external AutoPK anchor is not run unless stated in `silver_qa_v2.json`.",
              "- Q5 stability, Q6 decoy, Q7 external anchor are separate checks; if not present, they are not passed."]
    (out / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    stages = {
        "S0_freeze": s0,
        "S1_corpus": {"status": "done", "n_docs": len(docs), "n_papers": len(papers)},
        "S2a_silver_sources": {"status": "done", "path": str(sources)},
        "S2b_reconsensus_qa": {"status": "done", "path": str(out / "silver_v2.jsonl")},
        "S3_splits": {"status": "done", "path": str(out / "splits.json"),
                      "leakage": splits["leakage_train_test_paper_overlap"]},
        "S4_prompts": {"status": "done", "sha256": sha256_file("prompts/p2.md")},
        "S5_train": {"status": "not_run", "note": "no QLoRA adapter in this run"},
        "S6_infer": {"status": "done", "path": str(run / "pred_eval.jsonl")},
        "S7_verifier": {"status": "not_run", "note": "no independent verifier in this run"},
        "S8_metrics": {"status": "done", "path": str(out / "audit_metrics.json")},
        "S9_release": {"status": "done", "path": str(out / "release")},
    }
    # S9: audit release package (no publisher text)
    rel = out / "release"
    rel.mkdir(parents=True, exist_ok=True)
    import shutil
    for f in ("silver_v2.jsonl", "silver_qa_v2.json", "audit_metrics.json", "audit_report.md", "splits.json"):
        if (out / f).exists():
            shutil.copy2(out / f, rel / f)
    checks = {}
    for f in sorted(rel.iterdir()):
        if f.is_file():
            checks[f.name] = sha256_file(f)
    (rel / "checksums.txt").write_text(
        chr(10).join(f"{k}  {v}" for k, v in checks.items()) + chr(10), encoding="utf-8")
    (rel / "RELEASE.md").write_text(
        "# Audit release" + chr(10) + chr(10)
        + "This package contains annotations, metrics, splits and a report. "
        + "It does not redistribute publisher text. Silver is machine consensus, not human truth."
        + chr(10), encoding="utf-8")
    (out / "stages.json").write_text(json.dumps(stages, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
