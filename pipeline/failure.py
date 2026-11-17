"""Deterministic failure taxonomy for audit predictions vs silver."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .common import FIELD_NAMES, canon_value, is_negated, norm_text, quote_valid_relaxed, values_match

NEG_RANGE = re.compile(r"[<>~]|\.{2,}|-")


def _jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", norm_text(str(a)).lower()))
    tb = set(re.findall(r"[a-z0-9]+", norm_text(str(b)).lower()))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _evidence_text(x) -> str:
    ev = x.get("absence_evidence")
    if isinstance(ev, dict):
        return " ".join(str(v) for v in ev.get("evidence", {}).values() if v)
    return str(ev or "")


def classify_field(pred: dict, gold: dict, text: str) -> str | None:
    ps, gs = pred.get("status"), gold.get("status")
    if ps == gs and ps != "reported":
        return None
    if gs == "not_reported" and ps == "reported":
        return "absence_contradiction"
    if gs == "reported" and ps == "not_reported":
        return "false_absence"
    if gs != "reported" or ps != "reported":
        return "status_error"
    pvals = [v for v in pred.get("values", []) if isinstance(v, dict)]
    gvals = [v for v in gold.get("values", []) if isinstance(v, dict)]
    if not pvals:
        return "false_absence"
    # fabrication first
    for v in pvals:
        if not quote_valid_relaxed(v.get("quote", ""), text, v.get("value")):
            return "fabrication"
        if is_negated(v.get("quote", ""), v.get("value")):
            return "negation"
    matched = []
    used = set()
    for g in gvals:
        for j, p in enumerate(pvals):
            if j in used:
                continue
            if values_match(p, g):
                matched.append((p, g))
                used.add(j)
                break
    if not matched:
        return "wrong_value"
    if len(matched) < len(gvals) or len(matched) < len(pvals):
        return "multi_value"
    for p, g in matched:
        pc, gc = p.get("context") or {}, g.get("context") or {}
        keys = [k for k in gc if gc.get(k) not in (None, "", [])]
        if keys and not all(pc.get(k) not in (None, "", []) for k in keys):
            return "context_missing"
    for p, g in matched:
        av, au = canon_value(p.get("value"), p.get("unit", ""))
        bv, bu = canon_value(g.get("value"), g.get("unit", ""))
        if av is None or bv is None:
            continue
        if au != bu:
            return "unit_error"
        if NEG_RANGE.search(str(p.get("value"))) or NEG_RANGE.search(str(g.get("value"))):
            return "range_approx"
    return None


def analyze(pred_rows: list[dict], silver_rows: list[dict], text_by_doc: dict[str, str]) -> dict:
    gold = {r["doc_id"]: r for r in silver_rows}
    pred = {r["doc_id"]: r for r in pred_rows}
    docs = sorted(set(gold) & set(pred))
    counts = Counter()
    examples = defaultdict(list)
    absence_j = []
    for d in docs:
        for f in FIELD_NAMES:
            g = gold[d]["fields"].get(f, {})
            if g.get("status") == "reported" and g.get("confidence") not in {"high", "medium"}:
                continue
            if g.get("status") != "reported" and g.get("confidence") != "high":
                continue
            p = pred[d]["fields"].get(f, {})
            c = classify_field(p, g, text_by_doc.get(d, ""))
            if c:
                counts[c] += 1
                if len(examples[c]) < 3:
                    examples[c].append({"doc_id": d, "field": f, "pred": p, "gold": g})
            if g.get("status") == "not_reported" and p.get("status") == "not_reported":
                absence_j.append(_jaccard(_evidence_text(p), _evidence_text(g)))
    return {
        "n_docs": len(docs),
        "counts": dict(counts),
        "examples": dict(examples),
        "absence_jaccard_mean": sum(absence_j) / len(absence_j) if absence_j else None,
        "absence_jaccard_n": len(absence_j),
    }
