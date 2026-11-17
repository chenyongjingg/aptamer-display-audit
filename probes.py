"""Contamination / memorization probes P1-P4.

P1 title-only: if the model reproduces values from the title alone, it likely
memorized the paper. P2 number-scramble: if it reproduces values after all
numbers are replaced, it is not reading. P3 entity-swap: replace aptamer names.
P4 temporal subset: compare accuracy on 2025-26 vs earlier.
"""
from __future__ import annotations

import argparse
import random
import re
from pathlib import Path

from pipeline.common import FIELD_NAMES, load_jsonl
from pipeline.llm import LLM


def scramble_numbers(text: str) -> str:
    return re.sub(r"\d+(?:\.\d+)?", "[NUM]", text or "")


def swap_entities(text: str) -> str:
    # replace common aptamer names with a neutral token
    for name in ("AS1411", "Sgc8c", "Sgc8", "SL2B", "C2NP", "MUC1", "PD-L1", "sgc8"):
        text = re.sub(re.escape(name), "APTAMER_X", text, flags=re.I)
    return text


def run_probe(model, docs, silver, mode: str, limit: int = 10) -> dict:
    smap = {r["doc_id"]: r for r in silver}
    rng = random.Random(0)
    sample = rng.sample(docs, min(limit, len(docs)))
    vals, total = 0, 0
    for d in sample:
        s = smap.get(d["doc_id"], {})
        text = d.get("text", "")
        if mode == "P1":
            text = f"{d.get('title','')}. {d.get('journal','')} {d.get('year','')}."
        elif mode == "P2":
            text = scramble_numbers(text)
        elif mode == "P3":
            text = swap_entities(text)
        obj, _ = model.extract(text, d["doc_id"] + "_" + mode)
        for f in FIELD_NAMES:
            g = s.get("fields", {}).get(f, {})
            if g.get("confidence") != "high" or g.get("status") != "reported":
                continue
            total += 1
            p = obj.get(f, {}) if isinstance(obj, dict) else {}
            if p.get("status") == "reported" and p.get("values"):
                # any overlap with a gold value counts as a hit
                gv = [str(v.get("value")) for v in g.get("values", [])]
                pv = [str(v.get("value")) for v in p.get("values", [])]
                if any(any(g in p or p in g for p in pv) for g in gv):
                    vals += 1
    return {"mode": mode, "hits": vals, "n": total,
            "hit_rate": vals / total if total else None,
            "interpretation": "high hit_rate on P1/P2/P3 indicates memorization/leakage"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--silver", required=True)
    ap.add_argument("--model", default="/model/ModelScope/Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", default="runs/probes")
    args = ap.parse_args()
    docs = load_jsonl(args.docs)
    silver = load_jsonl(args.silver)
    model = LLM(args.model, load_in_4bit=True)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    import json
    results = {}
    for mode in ("P1", "P2", "P3"):
        results[mode] = run_probe(model, docs, silver, mode, args.limit)
        print(mode, results[mode], flush=True)
    # P4 temporal: split high-confidence reported fields by year
    early = [r for r in silver if str(r.get("year", "")) < "2025"]
    late = [r for r in silver if str(r.get("year", "")) >= "2025"]
    results["P4"] = {"n_early": len(early), "n_late": len(late),
                     "note": "accuracy split must be computed from predictions, not from silver alone"}
    (out / "probes.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
