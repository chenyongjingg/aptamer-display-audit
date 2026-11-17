import json, os
base = "runs/full_auto"
print("=== audit files ===")
for f in sorted(os.listdir(base + "/audit")):
    p = base + "/audit/" + f
    print(f, os.path.getsize(p))
m = json.load(open(base + "/audit/audit_metrics.json"))
print("\n=== metrics ===")
for k, r in m.items():
    if k.startswith("_"):
        continue
    print(k, "macro", r.get("macro_f1"), "ci", r.get("macro_f1_ci95"),
          "cov", r.get("coverage_high"), "tier", r.get("tier_macro_f1"),
          "value", r.get("value_macro_f1"), "ctx", r.get("context_macro_f1"),
          "quote", r.get("quote_valid_rate"), "exact", r.get("quote_exact_rate"))
print("\n=== OOF ===")
print(json.dumps(m.get("_oof"), ensure_ascii=False, indent=1))
print("\n=== subsets ===")
print("E4_on_zero_shot_subset", (m.get("E4_on_zero_shot_subset") or {}).get("macro_f1"))
print("E4_on_verified_subset", (m.get("E4_on_verified_subset") or {}).get("macro_f1"))
print("\n=== failure E4 ===")
print(json.dumps(m.get("_failure_E4"), ensure_ascii=False)[:1500])
qa = json.load(open(base + "/audit/silver_qa_v2.json"))
print("\n=== silver QA ===")
print("n_docs", qa.get("n_docs"), "sanity", qa.get("sanity_pass_rate"))
print("tier", json.dumps(qa.get("tier_coverage"), ensure_ascii=False))
print("cross", json.dumps(qa.get("cross_field"), ensure_ascii=False))
sp = json.load(open(base + "/audit/splits.json"))
print("\n=== splits ===")
print("folds", sp.get("folds"), "leakage", sp.get("leakage_train_test_paper_overlap"),
      "sizes", sp.get("fold_sizes"))
