"""Rebuild silver sources from the raw model cache.

The first run applied a strict quote gate before persisting sources, which may
have dropped values whose chunk-decoded quote differed only in whitespace. The
cache contains the raw model JSON; this script rebuilds sources from it and lets
`reconsensus` apply the relaxed, chunk-aware gate.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.common import load_jsonl, write_jsonl
from pipeline.rules import extract_rules
from pipeline.silver import norm_source


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    docs = load_jsonl(args.docs)
    cache = Path(args.cache)
    rows = []
    for d in docs:
        did = d["doc_id"]
        sources = {"rule": extract_rules(d.get("text", ""))}
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
                sources[key] = norm_source(obj)
        rows.append({"doc_id": did, "sources": sources})
    write_jsonl(args.out, rows)
    print(f"wrote {args.out} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
