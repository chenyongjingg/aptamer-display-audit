import json
from pathlib import Path
from pipeline.common import load_jsonl, write_jsonl
from pipeline.rules import extract_rules
from pipeline.silver import norm_source
from pipeline.reconsensus import build_v2

docs = load_jsonl("data/docs.jsonl")
cache = Path("runs/full/cache")
have = {}
for f in cache.glob("A_*.json"):
    did = f.name.split("_", 2)[-1][:-5]
    have[did] = f
rows = []
for d in docs:
    did = d["doc_id"]
    if did not in have:
        continue
    src = {"rule": extract_rules(d.get("text", ""))}
    for tag, key in (("A", "llmA"), ("B", "llmB")):
        fs = sorted(cache.glob(f"{tag}_*_{did}.json"))
        if fs:
            try:
                obj = json.loads(fs[0].read_text())["obj"]
            except Exception:
                obj = None
            if obj is not None:
                src[key] = norm_source(obj)
    rows.append({"doc_id": did, "sources": src})
write_jsonl("/tmp/src_partial.jsonl", rows)
sub = [d for d in docs if d["doc_id"] in have]
build_v2(sub, "/tmp/src_partial.jsonl", "/tmp/audit_partial", review_path="data/extraction.csv")
qa = json.load(open("/tmp/audit_partial/silver_qa_v2.json"))
print("docs", len(sub))
print(json.dumps(qa["tier_coverage"], indent=2))
