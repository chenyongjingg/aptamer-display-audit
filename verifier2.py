"""Field-level verifier with short evidence windows and forced JSON.

Fixes the pilot failure (verifier wrote prose, parse_error, reject-all):
- one field at a time;
- only the candidate sentences, not the full document;
- strict JSON-only prompt, 200 tokens;
- on parse failure, keep the original value and flag it (do not silently delete).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.common import FIELD_NAMES, load_jsonl, quote_valid_relaxed, safe_json, write_jsonl
from pipeline.llm import LLM
from value_extract import FIELD_SPEC, candidates

SYSTEM = """You verify ONE extraction field. Use ONLY the provided sentences.
Return ONLY a JSON object, no prose:
{"decision": "accept|reject|correct", "corrected": null, "reason": "short"}
- accept: the value is supported by a verbatim quote that contains it;
- reject: the value is absent, unsupported, or the quote is not verbatim;
- correct: a supported value exists but differs; put it in "corrected" as
  {"status":"reported","values":[{"value","unit","quote","context"}]}.
Never use general knowledge."""


def verify_field(llm: LLM, field: str, text: str, field_obj: dict) -> tuple[dict, str]:
    cands = candidates(text, field, k=3)
    if not cands:
        return field_obj, "no_candidate_keep"
    user = (f"Field: {field} ({FIELD_SPEC[field][0]}).\n\nSentences:\n"
            + "\n".join(f"- {c}" for c in cands)
            + "\n\nCandidate:\n" + json.dumps({field: field_obj}, ensure_ascii=False)[:1200]
            + "\n\nReturn the JSON object now.")
    raw = llm.generate(SYSTEM, user, max_new_tokens=200)
    dec = safe_json(raw)
    if not isinstance(dec, dict):
        return field_obj, "parse_error_keep"
    d = str(dec.get("decision", "")).lower()
    if d == "reject":
        return {"status": "not_reported", "values": [], "absence_evidence": dec.get("reason", "verifier_reject")}, "reject"
    if d == "correct":
        corr = dec.get("corrected")
        if isinstance(corr, dict) and corr.get("values"):
            vals = []
            for v in corr["values"]:
                if isinstance(v, dict) and quote_valid_relaxed(v.get("quote", ""), text, v.get("value")):
                    vals.append(v)
            if vals:
                return {"status": "reported", "values": vals, "absence_evidence": None}, "correct"
    return field_obj, "accept"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="/model/ModelScope/Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    docs = {d["doc_id"]: d for d in load_jsonl(args.docs)}
    preds = load_jsonl(args.pred)[: args.limit]
    llm = LLM(args.model, load_in_4bit=True)
    rows, stats = [], {"accept": 0, "reject": 0, "correct": 0, "parse_error_keep": 0, "no_candidate_keep": 0}
    for i, p in enumerate(preds, 1):
        d = docs.get(p["doc_id"], {})
        text = d.get("text", "")
        fields = {}
        for f in FIELD_NAMES:
            x = p["fields"].get(f, {})
            if x.get("status") != "reported" or not x.get("values"):
                fields[f] = x
                continue
            y, tag = verify_field(llm, f, text, x)
            fields[f] = y
            stats[tag] = stats.get(tag, 0) + 1
        rows.append({"doc_id": p["doc_id"], "paper_id": p.get("paper_id"),
                     "level": p.get("level"), "fields": fields})
        print(f"[verifier2] {i}/{len(preds)}", flush=True)
    write_jsonl(args.out, rows)
    stats_path = Path(args.out).with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
