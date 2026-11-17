"""Q5 stability, Q6 decoy and Q7 external-anchor checks.

These are separate from `reconsensus.qa_v2` because they require model calls or
external data. If they cannot run, they must report `not_available`/`not_run`,
never `pass`.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from pipeline.common import FIELD_NAMES, load_jsonl


def q7_external_anchor(data_dir: str | Path = "data/autopk") -> dict:
    p = Path(data_dir)
    if not p.exists():
        return {"status": "not_available", "reason": f"{p} missing",
                "consequence": "PK conclusions remain exploratory"}
    files = sorted([x for x in p.rglob("*") if x.is_file()])
    if not files:
        return {"status": "not_available", "reason": "no files"}
    return {"status": "files_present_not_scored", "n_files": len(files),
            "note": "a scorer must be implemented against the specific AutoPK release format"}


def q5_stability(docs: list[dict], model, silver_rows: list[dict], sample_n: int = 10,
                 prompt_variants: tuple[str, ...] = ("p1", "p3")) -> dict:
    """Re-run the extractor with prompt/temperature variants; report label flips."""
    silver = {r["doc_id"]: r for r in silver_rows}
    rng = random.Random(0)
    sample = rng.sample(docs, min(sample_n, len(docs)))
    flips, total = 0, 0
    details = []
    for d in sample:
        base = silver.get(d["doc_id"], {}).get("fields", {})
        for variant in prompt_variants:
            obj, _ = model.extract(d.get("text", ""), d["doc_id"])
            # the LLM class uses p2; a real variant run needs prompt swapping.
            # We record the variant and compare statuses only.
            pred = obj if isinstance(obj, dict) else {}
            for f in FIELD_NAMES:
                p = pred.get(f, {}) if isinstance(pred.get(f), dict) else {}
                g = base.get(f, {})
                if g.get("confidence") != "high":
                    continue
                total += 1
                if (p.get("status", "not_reported") != g.get("status")):
                    flips += 1
            details.append({"doc_id": d["doc_id"], "variant": variant})
    return {"status": "ran" if total else "not_run", "flips": flips, "total": total,
            "flip_rate": flips / total if total else None,
            "note": "prompt swapping is not wired into LLM yet; this is a status-only stability check",
            "details": details}


def q6_decoy(docs: list[dict], model, sample_n: int = 5) -> dict:
    """Insert a fake value into a copy; a faithful extractor should not accept it."""
    rng = random.Random(0)
    sample = rng.sample(docs, min(sample_n, len(docs)))
    accepted = 0
    total = 0
    details = []
    for d in sample:
        text = d.get("text", "") + "\n\nFor completeness, the apparent Kd was 999 nM."
        obj, _ = model.extract(text, d["doc_id"] + "_decoy")
        kd = obj.get("kd", {}) if isinstance(obj, dict) else {}
        total += 1
        if kd.get("status") == "reported":
            vals = [str(v.get("value")) for v in kd.get("values", []) if isinstance(v, dict)]
            if any("999" in v for v in vals):
                accepted += 1
        details.append({"doc_id": d["doc_id"], "accepted": accepted})
    return {"status": "ran" if total else "not_run", "false_accept": accepted,
            "n": total, "false_accept_rate": accepted / total if total else None,
            "details": details}
