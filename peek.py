import json
base = "runs/full_auto"
for name in ["pred_finetuned.jsonl", "pred_zero_shot.jsonl"]:
    print("===", name)
    rows = [json.loads(l) for l in open(base + "/" + name) if l.strip()]
    print("rows", len(rows))
    for r in rows[:2]:
        print("doc", r["doc_id"])
        for f in ["kd", "id_per_g", "half_life", "valency", "size", "comparator"]:
            x = r["fields"].get(f, {})
            print(" ", f, x.get("status"), x.get("values", [])[:2])
    print()
print("=== silver v2 sample ===")
rows = [json.loads(l) for l in open(base + "/audit/silver_v2.jsonl") if l.strip()]
for r in rows[:2]:
    print("doc", r["doc_id"])
    for f in ["kd", "id_per_g", "half_life", "valency", "size", "comparator"]:
        x = r["fields"].get(f, {})
        print(" ", f, x.get("status"), x.get("confidence"), x.get("values", [])[:2])
