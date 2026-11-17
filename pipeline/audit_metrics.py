"""Confidence-aware metrics for the consensus silver standard.

Differences from the pilot metrics:
- primary analysis filters to high-confidence silver fields;
- context tuples are scored separately from value+unit;
- multi-value fields use set F1;
- Tier-1/2/3 macro-F1 and coverage are reported;
- paired bootstrap compares two systems on the same docs.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict

from .common import FIELD_NAMES, quote_valid, quote_valid_relaxed, values_match

TIER = {
    "kd": 1, "id_per_g": 1, "half_life": 1, "dose": 1, "route": 1,
    "time_points": 1, "numeric_efficacy": 1, "serum_stability": 1,
    "valency": 2, "spacing": 2, "linker_length": 2, "linker_chemistry": 2,
    "size": 2, "attachment": 2, "comparator": 3, "immune": 3,
}
STATUSES = ["reported", "not_reported", "not_applicable"]


def _f1(tp, fp, fn):
    if tp == 0:
        return 0.0
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def presence(pred: dict, gold: dict) -> float | None:
    yp = pred.get("status", "not_reported")
    yg = gold.get("status", "not_reported")
    scores = []
    for c in STATUSES:
        tp = int(yp == c and yg == c)
        fp = int(yp == c and yg != c)
        fn = int(yp != c and yg == c)
        if tp + fn == 0:
            continue
        scores.append(_f1(tp, fp, fn))
    return sum(scores) / len(scores) if scores else None


def _context_match(p: dict, g: dict) -> bool | None:
    gc = g.get("context") or {}
    pc = p.get("context") or {}
    keys = [k for k in ("method", "buffer", "temperature", "cell_line", "time_point", "route", "dose")
            if gc.get(k) not in (None, "", [])]
    if not keys:
        return None
    hits = 0
    for k in keys:
        if pc.get(k) in (None, "", []):
            continue
        a, b = str(pc[k]).lower().strip(), str(gc[k]).lower().strip()
        if a == b or a in b or b in a:
            hits += 1
    return hits == len(keys)


def value_scores(pred: dict, gold: dict) -> dict:
    pvals = [v for v in pred.get("values", []) if isinstance(v, dict)]
    gvals = [v for v in gold.get("values", []) if isinstance(v, dict)]
    if not gvals:
        return {"value_f1": None, "context_f1": None, "n_pred": len(pvals), "n_gold": 0}
    used = set()
    matched = 0
    ctx_scores = []
    for g in gvals:
        for j, p in enumerate(pvals):
            if j in used:
                continue
            if values_match(p, g):
                matched += 1
                used.add(j)
                c = _context_match(p, g)
                if c is not None:
                    ctx_scores.append(1.0 if c else 0.0)
                break
    prec = matched / len(pvals) if pvals else 0.0
    rec = matched / len(gvals)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "value_f1": f1,
        "context_f1": sum(ctx_scores) / len(ctx_scores) if ctx_scores else None,
        "n_pred": len(pvals), "n_gold": len(gvals),
    }


def _eligible(gold_field: dict, confidence: str | set[str]) -> bool:
    if confidence == "all":
        return True
    allowed = {confidence} if isinstance(confidence, str) else set(confidence)
    return gold_field.get("confidence") in allowed


def evaluate_v2(
    pred_rows: list[dict],
    silver_rows: list[dict],
    text_by_doc: dict[str, str],
    confidence: str | set[str] = "high",
    seed: int = 0,
    paper_ids: set[str] | None = None,
    positive_confidence: set[str] = {"high", "medium"},
) -> dict:
    gold = {r["doc_id"]: r for r in silver_rows}
    pred = {r["doc_id"]: r for r in pred_rows}
    docs = sorted(set(gold) & set(pred))
    if paper_ids is not None:
        docs = [d for d in docs if gold[d].get("paper_id") in paper_ids]
    per_field = {}
    tier_scores = defaultdict(list)
    all_field_scores = []
    value_scores_all = []
    context_scores_all = []
    quote_total = 0
    quote_valid_n = 0
    quote_exact_n = 0
    omission = 0
    gold_reported = 0
    n_high_fields = 0
    n_all_fields = 0
    doc_allcorrect = 0
    doc_allcorrect_den = 0
    field_docs = defaultdict(int)

    for f in FIELD_NAMES:
        fs = []
        vs = []
        cs = []
        for d in docs:
            g = gold[d]["fields"].get(f, {})
            p = pred[d]["fields"].get(f, {})
            n_all_fields += 1
            if _eligible(g, confidence):
                n_high_fields += 1
                field_docs[f] += 1
                x = presence(p, g)
                if x is not None:
                    fs.append(x)
            # value scoring uses the positive-confidence set, independent of presence eligibility
            if g.get("status") == "reported" and g.get("confidence") in positive_confidence:
                gold_reported += 1
                if p.get("status") != "reported":
                    omission += 1
                vsx = value_scores(p, g)
                if vsx["value_f1"] is not None:
                    vs.append(vsx["value_f1"])
                if vsx["context_f1"] is not None:
                    cs.append(vsx["context_f1"])
            for v in p.get("values", []):
                quote_total += 1
                src = text_by_doc.get(d, "")
                if quote_valid_relaxed(v.get("quote", ""), src, v.get("value")):
                    quote_valid_n += 1
                if quote_valid(v.get("quote", ""), src, v.get("value")):
                    quote_exact_n += 1
        per_field[f] = {
            "presence_f1": sum(fs) / len(fs) if fs else None,
            "n_docs": len(fs),
            "value_f1": sum(vs) / len(vs) if vs else None,
            "n_value_docs": len(vs),
            "context_f1": sum(cs) / len(cs) if cs else None,
            "n_context_docs": len(cs),
            "tier": TIER[f],
        }
        if fs:
            all_field_scores.append(sum(fs) / len(fs))
            tier_scores[TIER[f]].append(sum(fs) / len(fs))
        if vs:
            value_scores_all.append(sum(vs) / len(vs))
        if cs:
            context_scores_all.append(sum(cs) / len(cs))

    macro = sum(all_field_scores) / len(all_field_scores) if all_field_scores else None
    tier_macro = {t: (sum(v) / len(v) if v else None) for t, v in tier_scores.items()}

    # document-level all-or-nothing over eligible fields
    for d in docs:
        eligible = [f for f in FIELD_NAMES if _eligible(gold[d]["fields"].get(f, {}), confidence)]
        if not eligible:
            continue
        doc_allcorrect_den += 1
        ok = True
        for f in eligible:
            g = gold[d]["fields"].get(f, {})
            p = pred[d]["fields"].get(f, {})
            if g.get("status") != p.get("status"):
                ok = False
                break
        doc_allcorrect += int(ok)

    # bootstrap over docs (resample docs, recompute field macros)
    rng = random.Random(seed)
    boots = []
    for _ in range(1000):
        sample = [docs[rng.randrange(len(docs))] for _ in docs] if docs else []
        scores = []
        for f in FIELD_NAMES:
            vals = []
            for d in sample:
                g = gold[d]["fields"].get(f, {})
                if not _eligible(g, confidence):
                    continue
                x = presence(pred[d]["fields"].get(f, {}), g)
                if x is not None:
                    vals.append(x)
            if vals:
                scores.append(sum(vals) / len(vals))
        if scores:
            boots.append(sum(scores) / len(scores))
    boots.sort()
    ci = (boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]) if boots else (None, None)

    return {
        "n_docs": len(docs),
        "confidence": confidence,
        "primary": "value_macro_f1",
        "secondary": "macro_f1",
        "positive_confidence": sorted(positive_confidence),
        "macro_f1": macro,
        "macro_f1_ci95": ci,
        "tier_macro_f1": tier_macro,
        "value_macro_f1": sum(value_scores_all) / len(value_scores_all) if value_scores_all else None,
        "context_macro_f1": sum(context_scores_all) / len(context_scores_all) if context_scores_all else None,
        "quote_valid_rate": quote_valid_n / quote_total if quote_total else None,
        "quote_exact_rate": quote_exact_n / quote_total if quote_total else None,
        "omission_rate": omission / gold_reported if gold_reported else None,
        "coverage_high": n_high_fields / n_all_fields if n_all_fields else None,
        "n_high_fields": n_high_fields,
        "n_all_fields": n_all_fields,
        "doc_all_or_nothing": doc_allcorrect / doc_allcorrect_den if doc_allcorrect_den else None,
        "per_field": per_field,
    }


def compare_systems(a: dict, b: dict, silver_rows: list[dict], confidence: str = "high",
                    seed: int = 0) -> dict:
    """Paired bootstrap of the macro-F1 difference on the same docs."""
    a_docs = {r["doc_id"]: r for r in a["pred_rows"]}
    b_docs = {r["doc_id"]: r for r in b["pred_rows"]}
    gold = {r["doc_id"]: r for r in silver_rows}
    docs = sorted(set(a_docs) & set(b_docs) & set(gold))
    rng = random.Random(seed)
    diffs = []
    for _ in range(1000):
        sample = [docs[rng.randrange(len(docs))] for _ in docs] if docs else []
        sa, sb = [], []
        for f in FIELD_NAMES:
            va, vb = [], []
            for d in sample:
                g = gold[d]["fields"].get(f, {})
                if not _eligible(g, confidence):
                    continue
                xa = presence(a_docs[d]["fields"].get(f, {}), g)
                xb = presence(b_docs[d]["fields"].get(f, {}), g)
                if xa is not None:
                    va.append(xa)
                if xb is not None:
                    vb.append(xb)
            if va:
                sa.append(sum(va) / len(va))
            if vb:
                sb.append(sum(vb) / len(vb))
        if sa and sb:
            diffs.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    diffs.sort()
    return {
        "delta": sum(diffs) / len(diffs) if diffs else None,
        "ci95": (diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]) if diffs else (None, None),
        "p_two_sided_approx": (sum(1 for x in diffs if x <= 0) / len(diffs)) if diffs else None,
        "n_docs": len(docs),
    }
