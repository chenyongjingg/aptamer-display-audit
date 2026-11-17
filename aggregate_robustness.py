import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
R = ROOT / "runs/robustness"


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


out = {
    "bootstrap_paired": load(R / "robustness_stats.json"),
    "tier_difference": load(R / "tier_diff.json"),
    "silver_leave_one_source_out": load(R / "silver_loo.json"),
    "stratified": load(R / "stratified.json"),
    "cross_family_and_prompt_stability": load(ROOT / "runs/extra/eval_extra.json"),
}
dest = R / "robustness_summary.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", dest, dest.stat().st_size)
