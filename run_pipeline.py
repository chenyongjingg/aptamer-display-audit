"""Unattended S0-S9 pipeline for the consensus-silver audit.

Design rules:
- one GPU stage at a time (S2a/S5/S6/S7);
- every stage is idempotent and writes an artifact + manifest entry;
- gates fail closed (S0 hash, silver coverage, adapter presence);
- failures are recorded, never silently retried to success;
- `--detach` starts a background child; `status` reads status.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline.audit_metrics import evaluate_v2
from pipeline.common import FIELD_NAMES, load_jsonl, sha256_file, write_jsonl
from pipeline.failure import analyze as failure_analyze
from pipeline.llm import LLM
from pipeline.reconsensus import build_v2, qa_v2
from pipeline.rules import extract_rules
from pipeline.silver import build_silver, norm_source
from pipeline.splits import make_splits, write_splits

STAGES = ["S0_freeze", "S1_corpus", "S2a_silver", "S2b_consensus", "S3_splits",
          "S4_prompts", "S5_train", "S6_infer", "S7_verify", "S8_metrics", "S9_release"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ctx:
    def __init__(self, run_dir: Path, config: dict):
        self.run_dir = run_dir
        self.config = config
        self.status_path = run_dir / "status.json"
        self.manifest_path = run_dir / "manifest.json"
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    def log(self, msg: str):
        line = f"[{now()}] {msg}"
        print(line, flush=True)
        with (self.run_dir / "logs" / "pipeline.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def status(self, stage: str, state: str, progress: str | None = None, **extra):
        payload = {"run_id": self.run_dir.name, "stage": stage, "state": state,
                   "updated_utc": now(), **extra}
        if progress:
            payload["progress"] = progress
        self.status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_done(manifest: dict, stage: str) -> bool:
    for s in manifest.get("stages", []):
        if s.get("name") == stage and s.get("status") == "done":
            return all(Path(p).exists() for p in s.get("outputs", {}).values())
    return False


def record(manifest: dict, stage: str, status: str, **kw):
    manifest["stages"] = [s for s in manifest.get("stages", []) if s.get("name") != stage]
    manifest["stages"].append({"name": stage, "status": status, "end_utc": now(), **kw})
    return manifest


def sample_ids(docs, ratio: float, seed: int = 0) -> set[str]:
    if ratio >= 1:
        return {d["doc_id"] for d in docs}
    by = defaultdict(list)
    for d in docs:
        try:
            ybin = "2024+" if int(str(d.get("year"))[:4]) >= 2024 else "pre2024"
        except Exception:
            ybin = "unknown"
        by[(d.get("level"), ybin)].append(d)
    rng = random.Random(seed)
    out = set()
    for items in by.values():
        k = max(1, int(round(len(items) * ratio)))
        out.update(d["doc_id"] for d in rng.sample(items, k))
    return out


# ---------------- stages ----------------

def s0(ctx: Ctx):
    prereg = ROOT / "prereg.json"
    if not prereg.exists():
        return {"status": "blocked", "reason": "prereg.json missing"}
    p = json.loads(prereg.read_text(encoding="utf-8"))
    checked, ok = {}, True
    for rel, expected in p.get("hashes", {}).items():
        actual = sha256_file(ROOT / rel)
        checked[rel] = {"expected": expected, "actual": actual, "match": actual == expected}
        ok = ok and actual == expected
    out = ctx.run_dir / "artifacts" / "S0_freeze.json"
    out.write_text(json.dumps({"check": checked, "ok": ok}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "done" if ok else "blocked", "reason": "hash match" if ok else "prereg hash mismatch",
            "outputs": {str(out): str(out)}, "check": checked}


def s1(ctx: Ctx):
    docs = load_jsonl(ROOT / ctx.config["docs"])
    papers = load_jsonl(ROOT / ctx.config["papers"])
    stats = {"n_docs": len(docs), "n_papers": len(papers),
             "n_abstract": sum(1 for d in docs if d["level"] == "abstract"),
             "n_full": sum(1 for d in docs if d["level"] == "full"),
             "n_title_only": sum(1 for d in docs if d.get("text_kind") == "title_only")}
    out = ctx.run_dir / "artifacts" / "S1_corpus.json"
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "done", "outputs": {str(out): str(out)}, "stats": stats}


def s2a(ctx: Ctx):
    docs = load_jsonl(ROOT / ctx.config["docs"])
    out_dir = ctx.run_dir
    sources = out_dir / "silver_sources.jsonl"
    cache = Path(ctx.config["silver"].get("cache_dir") or (out_dir / "cache"))
    if sources.exists() and len(load_jsonl(sources)) >= len(docs):
        return {"status": "done", "note": "sources already complete", "outputs": {str(sources): str(sources)}}
    cfg = ctx.config["silver"]
    ctx.status("S2a_silver", "loading_models")
    llm_a = LLM(cfg["model_a"], load_in_4bit=cfg.get("load_in_4bit", True))
    llm_b = LLM(cfg["model_b"], load_in_4bit=cfg.get("load_in_4bit", True))
    b_sample = sample_ids(docs, cfg.get("b_sample", 0.2), cfg.get("seed", 0))
    (out_dir / "b_sample.json").write_text(json.dumps(sorted(b_sample), indent=2), encoding="utf-8")
    ctx.status("S2a_silver", "running", progress=f"0/{len(docs)}")
    build_silver(docs, llm_a=llm_a, llm_b=llm_b, out_dir=out_dir, cache_dir=cache, b_sample=b_sample)
    del llm_a, llm_b
    import gc
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    ctx.status("S2a_silver", "done")
    return {"status": "done", "n_docs": len(docs), "n_b_sample": len(b_sample),
            "outputs": {str(sources): str(sources)}}


def s2b(ctx: Ctx):
    docs = load_jsonl(ROOT / ctx.config["docs"])
    sources = ctx.run_dir / "silver_sources.jsonl"
    if not sources.exists():
        return {"status": "blocked", "reason": "silver_sources.jsonl missing"}
    audit_dir = ctx.run_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    # rebuild from cache: raw outputs are the ground truth of what the models saw
    cache = Path(ctx.config["silver"].get("cache_dir") or (ctx.run_dir / "cache"))
    rows = []
    for d in docs:
        src = {"rule": extract_rules(d.get("text", ""))}
        for tag, key in (("A", "llmA"), ("B", "llmB")):
            files = sorted(cache.glob(f"{tag}_*_{d['doc_id']}.json"))
            if not files:
                continue
            try:
                payload = json.loads(files[0].read_text(encoding="utf-8"))
                obj = payload.get("obj") if isinstance(payload, dict) else None
            except Exception:
                obj = None
            if obj is not None:
                src[key] = norm_source(obj)
        rows.append({"doc_id": d["doc_id"], "sources": src})
    rebuilt = audit_dir / "silver_sources_v2.jsonl"
    write_jsonl(rebuilt, rows)
    review = ROOT / ctx.config.get("review_extraction", "data/extraction.csv")
    build_v2(docs, rebuilt, audit_dir, review_path=str(review) if review.exists() else None)
    qa = json.loads((audit_dir / "silver_qa_v2.json").read_text(encoding="utf-8"))
    tiers = qa.get("tier_coverage", {})
    coverage = sum(v["high"] for v in tiers.values()) / max(1, sum(v["n"] for v in tiers.values()))
    min_cov = ctx.config.get("gates", {}).get("min_high_coverage", 0.40)
    out = {"status": "done" if coverage >= min_cov else "blocked",
           "coverage_high": coverage, "min_high_coverage": min_cov,
           "outputs": {str(audit_dir / "silver_v2.jsonl"): str(audit_dir / "silver_v2.jsonl")}}
    if coverage < min_cov:
        out["reason"] = f"high coverage {coverage:.3f} < {min_cov}"
    return out


def s3(ctx: Ctx):
    papers = load_jsonl(ROOT / ctx.config["papers"])
    splits = make_splits(papers, folds=ctx.config.get("cv", {}).get("folds", 5), seed=0)
    path = ctx.run_dir / "audit" / "splits.json"
    write_splits(splits, path)
    return {"status": "done", "leakage": splits["leakage_train_test_paper_overlap"],
            "outputs": {str(path): str(path)}}


def s4(ctx: Ctx):
    prompt = ROOT / ctx.config.get("prompt", "prompts/p2.md")
    out = ctx.run_dir / "artifacts" / "S4_prompts.json"
    data = {"prompt": str(prompt), "sha256": sha256_file(prompt),
            "models": [ctx.config["silver"]["model_a"], ctx.config["silver"]["model_b"]]}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "done", "outputs": {str(out): str(out)}, **data}


def s5(ctx: Ctx):
    """Train one QLoRA adapter per fold, on that fold's training papers only."""
    cfg = ctx.config.get("train", {})
    if not cfg.get("enabled", True):
        return {"status": "skipped", "reason": "train.enabled=false"}
    silver = ctx.run_dir / "audit" / "silver_v2.jsonl"
    splits = ctx.run_dir / "audit" / "splits.json"
    if not silver.exists() or not splits.exists():
        return {"status": "blocked", "reason": "silver_v2.jsonl or splits.json missing"}
    folds = min(int(cfg.get("folds", ctx.config.get("cv", {}).get("folds", 5))),
                json.loads(splits.read_text(encoding="utf-8"))["folds"])
    outs = {}
    for k in range(folds):
        out = ctx.run_dir / "train" / f"fold{k}"
        cmd = [sys.executable, str(ROOT / "train_qlora.py"),
               "--docs", str(ROOT / ctx.config["docs"]),
               "--silver", str(silver), "--out", str(out),
               "--model", cfg.get("model", "/model/ModelScope/Qwen/Qwen2.5-7B-Instruct"),
               "--epochs", str(cfg.get("epochs", 1.0)),
               "--splits", str(splits), "--fold", str(k)]
        if cfg.get("positive_only"):
            cmd.append("--positive-only")
        log = ctx.run_dir / "logs" / f"S5_train_fold{k}.log"
        ctx.status("S5_train", "running", progress=f"fold {k}/{folds}")
        with log.open("a", encoding="utf-8") as fh:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
        adapter = out / "adapter" / "adapter_config.json"
        if rc != 0 or not adapter.exists():
            return {"status": "failed", "reason": f"fold{k} rc={rc}, adapter={adapter.exists()}",
                    "log": str(log)}
        outs[str(out / "adapter")] = str(out / "adapter")
    return {"status": "done", "outputs": outs, "folds": folds}


def _infer_rows(model_path, adapter, docs, limit=None):
    ev = LLM(model_path, load_in_4bit=True, adapter_path=str(adapter) if adapter else None)
    rows = []
    for i, d in enumerate(docs[: limit] if limit else docs, 1):
        obj, raw = ev.extract(d.get("text", ""), d["doc_id"])
        ns = norm_source(obj)
        fields = {f: ns.get(f, {"status": "not_reported", "values": []}) for f in FIELD_NAMES}
        rows.append({"doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "level": d.get("level"),
                     "fields": fields, "raw": raw[:1000]})
        if i % 5 == 0:
            print(f"[infer] {i}/{len(docs)}", flush=True)
    del ev
    import gc
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    return rows


def s6(ctx: Ctx):
    """Out-of-fold inference: adapter k predicts fold k only."""
    cfg = ctx.config.get("infer", {})
    docs = load_jsonl(ROOT / ctx.config["docs"])
    splits = json.loads((ctx.run_dir / "audit" / "splits.json").read_text(encoding="utf-8"))
    assignment = splits["assignment"]
    folds = splits["folds"]
    out_name = "pred_finetuned.jsonl" if cfg.get("use_adapter", True) else "pred_zero_shot.jsonl"
    out = ctx.run_dir / out_name
    rows = []
    for k in range(folds):
        adapter = ctx.run_dir / "train" / f"fold{k}" / "adapter"
        if cfg.get("use_adapter", True) and not (adapter / "adapter_config.json").exists():
            return {"status": "blocked", "reason": f"fold{k} adapter missing"}
        test_papers = {p for p, f in assignment.items() if f == k}
        docs_fold = [d for d in docs if d.get("paper_id") in test_papers]
        ctx.status("S6_infer", "running", progress=f"fold {k}/{folds} n={len(docs_fold)}")
        rows.extend(_infer_rows(cfg.get("model", "/model/ModelScope/Qwen/Qwen2.5-7B-Instruct"),
                                adapter if cfg.get("use_adapter", True) else None,
                                docs_fold, cfg.get("limit")))
    write_jsonl(out, rows)
    # optional zero-shot baseline on a subset (for E1); full 102-doc zero-shot is expensive
    zsl = cfg.get("zero_shot_limit")
    if zsl:
        # choose documents with the most high-confidence reported fields, so E1 has value support
        try:
            sil = {r["doc_id"]: r for r in load_jsonl(ctx.run_dir / "audit" / "silver_v2.jsonl")}
            def score(d):
                return sum(1 for f in FIELD_NAMES
                           if sil.get(d["doc_id"], {}).get("fields", {}).get(f, {}).get("confidence") == "high"
                           and sil.get(d["doc_id"], {}).get("fields", {}).get(f, {}).get("status") == "reported")
            zs_docs = sorted(docs, key=score, reverse=True)[: int(zsl)]
        except Exception:
            zs_docs = docs[: int(zsl)]
        ctx.status("S6_infer", "running", progress=f"zero-shot n={len(zs_docs)}")
        zs_rows = _infer_rows(cfg.get("model", "/model/ModelScope/Qwen/Qwen2.5-7B-Instruct"),
                              None, zs_docs, None)
        write_jsonl(ctx.run_dir / "pred_zero_shot.jsonl", zs_rows)
    return {"status": "done", "n": len(rows), "outputs": {str(out): str(out)}}


def s7(ctx: Ctx):
    cfg = ctx.config.get("verify", {})
    if not cfg.get("enabled", True):
        return {"status": "skipped", "reason": "verify.enabled=false"}
    use_adapter = ctx.config.get("infer", {}).get("use_adapter", True)
    pred = ctx.run_dir / ("pred_finetuned.jsonl" if use_adapter else "pred_zero_shot.jsonl")
    if not pred.exists():
        pred = ctx.run_dir / ("pred_zero_shot.jsonl" if use_adapter else "pred_finetuned.jsonl")
    if not pred.exists():
        return {"status": "blocked", "reason": "no prediction file"}
    out = ctx.run_dir / "verified"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "verifier.py"), "--run", str(ctx.run_dir),
           "--pred", str(pred), "--out", str(out),
           "--model", cfg.get("model", "/model/ModelScope/Qwen/Qwen2.5-Coder-7B-Instruct"),
           "--limit", str(cfg.get("limit", 30))]
    log = ctx.run_dir / "logs" / "S7_verify.log"
    with log.open("a", encoding="utf-8") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
    outfile = out / "pred_verified.jsonl"
    if rc != 0 or not outfile.exists():
        return {"status": "failed", "reason": f"verifier rc={rc}", "log": str(log)}
    return {"status": "done", "outputs": {str(outfile): str(outfile)}, "log": str(log)}


def s8(ctx: Ctx):
    docs = load_jsonl(ROOT / ctx.config["docs"])
    text_by_doc = {d["doc_id"]: d.get("text", "") for d in docs}
    silver = load_jsonl(ctx.run_dir / "audit" / "silver_v2.jsonl")
    splits = json.loads((ctx.run_dir / "audit" / "splits.json").read_text(encoding="utf-8"))
    systems = {}
    # E0 rules
    rule_rows = [{"doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "level": d.get("level"),
                  "fields": extract_rules(d.get("text", ""))} for d in docs]
    systems["E0_rules"] = (rule_rows, "rules")
    # E1 zero-shot if persisted
    zs = Path(ctx.config.get("zero_shot_pred", ctx.run_dir / "pred_eval.jsonl"))
    if not zs.exists():
        zs = ctx.run_dir / "pred_zero_shot.jsonl"
    if zs.exists():
        systems["E1_zero_shot"] = (load_jsonl(zs), "zero-shot")
    # E4 fine-tuned: only when training is enabled for this run
    ft = ctx.run_dir / "pred_finetuned.jsonl"
    if ctx.config.get("train", {}).get("enabled", True) and ft.exists():
        systems["E4_finetuned"] = (load_jsonl(ft), "fine-tuned")
    # E7 verified
    vf = ctx.run_dir / "verified" / "pred_verified.jsonl"
    if vf.exists():
        systems["E7_verified"] = (load_jsonl(vf), "verified")

    metrics, oof = {}, {}
    folds = splits["folds"]
    assignment = splits["assignment"]
    for name, (rows, _) in systems.items():
        metrics[name] = evaluate_v2(rows, silver, text_by_doc, confidence="high")
        fold_vals = []
        for k in range(folds):
            test_papers = {p for p, f in assignment.items() if f == k}
            r = evaluate_v2(rows, silver, text_by_doc, confidence="high", paper_ids=test_papers)
            if r["macro_f1"] is not None:
                fold_vals.append(r["macro_f1"])
        oof[name] = {"folds": fold_vals, "mean": sum(fold_vals) / len(fold_vals) if fold_vals else None}
    if "E1_zero_shot" in systems and "E4_finetuned" in systems:
        zs_ids = {r["doc_id"] for r in systems["E1_zero_shot"][0]}
        e4_sub = [r for r in systems["E4_finetuned"][0] if r["doc_id"] in zs_ids]
        metrics["E4_on_zero_shot_subset"] = evaluate_v2(e4_sub, silver, text_by_doc, confidence="high")
    if "E7_verified" in systems and "E4_finetuned" in systems:
        vf_ids = {r["doc_id"] for r in systems["E7_verified"][0]}
        e4_sub = [r for r in systems["E4_finetuned"][0] if r["doc_id"] in vf_ids]
        metrics["E4_on_verified_subset"] = evaluate_v2(e4_sub, silver, text_by_doc, confidence="high")
    metrics["_oof"] = oof
    metrics["_failure_E4"] = failure_analyze(systems["E4_finetuned"][0], silver, text_by_doc) if "E4_finetuned" in systems else None
    out = ctx.run_dir / "audit" / "audit_metrics.json"
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    report = ctx.run_dir / "audit" / "audit_report.md"
    lines = ["# Automated audit report", "",
             "Primary: value set-F1 on high-confidence reported fields; presence macro-F1 is secondary.", "",
             "| system | value-F1 (primary) | presence macro-F1 | coverage | Tier-1 presence | OOF presence |",
             "|---|---|---|---|---|---|"]
    for name in systems:
        m = metrics[name]
        lines.append(f"| {name} | {m['value_macro_f1']} | {m['macro_f1']} | {m['coverage_high']} | {m['tier_macro_f1'].get(1)} | {oof[name]['mean']} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "done", "outputs": {str(out): str(out), str(report): str(report)}, "systems": list(systems)}


def s9(ctx: Ctx):
    rel = ctx.run_dir / "release"
    rel.mkdir(parents=True, exist_ok=True)
    import shutil
    for src in [ctx.run_dir / "audit" / "silver_v2.jsonl",
                ctx.run_dir / "audit" / "silver_qa_v2.json",
                ctx.run_dir / "audit" / "audit_metrics.json",
                ctx.run_dir / "audit" / "audit_report.md",
                ctx.run_dir / "audit" / "splits.json"]:
        if src.exists():
            shutil.copy2(src, rel / src.name)
    (rel / "MODEL_CARD.md").write_text(
        "# Model card" + chr(10) + chr(10)
        + "Base: Qwen2.5-7B-Instruct; adapter: QLoRA r=16, alpha=32; trained per fold on high-confidence silver."
        + chr(10) + "Intended use: research audit of PK/design reporting; not a clinical decision tool."
        + chr(10), encoding="utf-8")
    (rel / "DATASHEET.md").write_text(
        "# Datasheet" + chr(10) + chr(10)
        + "Annotations and metrics only; publisher text is not redistributed."
        + chr(10) + "Silver is machine consensus, not human truth; see silver_qa_v2.json."
        + chr(10), encoding="utf-8")
    checks = {f.name: sha256_file(f) for f in sorted(rel.iterdir()) if f.is_file()}
    (rel / "checksums.txt").write_text(chr(10).join(f"{k}  {v}" for k, v in checks.items()) + chr(10),
                                       encoding="utf-8")
    return {"status": "done", "outputs": {str(rel): str(rel)}}


STAGE_FUNCS = {
    "S0_freeze": s0, "S1_corpus": s1, "S2a_silver": s2a, "S2b_consensus": s2b,
    "S3_splits": s3, "S4_prompts": s4, "S5_train": s5, "S6_infer": s6,
    "S7_verify": s7, "S8_metrics": s8, "S9_release": s9,
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--detach", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--from", dest="from_stage", default=None)
    ap.add_argument("--to", dest="to_stage", default=None)
    args = ap.parse_args(argv)
    cfg_path = Path(args.config).resolve()
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "runs" / run_id

    if args.detach:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        log = run_dir / "logs" / "launch.log"
        cmd = [sys.executable, str(Path(__file__).resolve()), "--config", str(cfg_path),
               "--run-id", run_id, "--resume"]
        if args.force:
            cmd.append("--force")
        if args.only:
            cmd += ["--only", args.only]
        if args.from_stage:
            cmd += ["--from", args.from_stage]
        if args.to_stage:
            cmd += ["--to", args.to_stage]
        with log.open("ab") as fh:
            proc = subprocess.Popen(cmd, stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
                                    start_new_session=True, cwd=ROOT)
        (run_dir / "pid").write_text(str(proc.pid), encoding="utf-8")
        print(f"detached pid={proc.pid} run_id={run_id} log={log}")
        return 0

    ctx = Ctx(run_dir, config)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("run_id", run_id)
    manifest.setdefault("config", str(cfg_path))
    manifest.setdefault("config_sha256", sha256_file(cfg_path))
    manifest.setdefault("started_utc", now())
    manifest.setdefault("stages", [])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    stages = STAGES
    if args.only:
        stages = [s for s in stages if s == args.only]
    if args.from_stage:
        stages = [s for s in stages if STAGES.index(s) >= STAGES.index(args.from_stage)]
    if args.to_stage:
        stages = [s for s in stages if STAGES.index(s) <= STAGES.index(args.to_stage)]

    for stage in stages:
        if not args.force and stage_done(manifest, stage):
            ctx.log(f"{stage} done; skip")
            continue
        ctx.status(stage, "running")
        ctx.log(f"{stage} start")
        try:
            res = STAGE_FUNCS[stage](ctx)
        except Exception as exc:
            ctx.log(f"{stage} FAILED: {exc}\n{traceback.format_exc()}")
            manifest = record(manifest, stage, "failed", error=str(exc))
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            ctx.status(stage, "failed", error=str(exc))
            return 2
        status = res.get("status", "done")
        manifest = record(manifest, stage, status, outputs=res.get("outputs", {}), **{k: v for k, v in res.items() if k not in {"status", "outputs"}})
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.log(f"{stage} {status}")
        if status == "blocked":
            ctx.status(stage, "blocked", reason=res.get("reason"))
            return 3
        if status == "failed":
            ctx.status(stage, "failed", reason=res.get("reason"))
            return 2
    ctx.status("done", "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
