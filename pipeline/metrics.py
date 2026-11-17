from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from .common import FIELD_NAMES, quote_valid, values_match

STATUSES = ["reported", "not_reported", "not_applicable"]


def _f1(tp, fp, fn):
    if tp == 0:
        return 0.0
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def field_presence(pred: dict, gold: dict) -> dict:
    """Three-class one-vs-rest macro F1 for one field."""
    yp = pred.get("status", "not_reported")
    yg = gold.get("status", "not_reported")
    out = {"status_pred": yp, "status_gold": yg, "f1": None, "classes": {}}
    class_scores = []
    for c in STATUSES:
        tp = int(yp == c and yg == c)
        fp = int(yp == c and yg != c)
        fn = int(yp != c and yg == c)
        if tp + fn == 0:
            continue  # no gold support for this class
        f = _f1(tp, fp, fn)
        out["classes"][c] = {"tp": tp, "fp": fp, "fn": fn, "f1": f}
        class_scores.append(f)
    out["f1"] = sum(class_scores) / len(class_scores) if class_scores else None
    return out


def value_scores(pred: dict, gold: dict) -> dict:
    pvals = [v for v in pred.get("values", [])]
    gvals = [v for v in gold.get("values", [])]
    if not gvals:
        return {"precision": None, "recall": None, "f1": None, "n_pred": len(pvals), "n_gold": 0}
    matched = 0
    used = set()
    for g in gvals:
        for j, p in enumerate(pvals):
            if j in used:
                continue
            if values_match(p, g):
                matched += 1
                used.add(j)
                break
    p = matched / len(pvals) if pvals else 0.0
    r = matched / len(gvals)
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "n_pred": len(pvals), "n_gold": len(gvals)}


def evaluate(pred_rows: list[dict], silver_rows: list[dict], text_by_doc: dict[str, str], seed: int = 0) -> dict:
    gold = {r["doc_id"]: r for r in silver_rows}
    pred = {r["doc_id"]: r for r in pred_rows}
    docs = sorted(set(gold) & set(pred))
    per_field = {}
    all_f1 = []
    value_f1 = []
    quote_total = 0
    quote_valid_n = 0
    halluc = 0
    pred_values = 0
    omission = 0
    gold_reported = 0
    for f in FIELD_NAMES:
        f1s = []
        vf1s = []
        for d in docs:
            g = gold[d]["fields"].get(f, {})
            p = pred[d]["fields"].get(f, {})
            fs = field_presence(p, g)
            if fs["f1"] is not None:
                f1s.append(fs["f1"])
            if g.get("status") == "reported":
                gold_reported += 1
                if p.get("status") != "reported":
                    omission += 1
                vs = value_scores(p, g)
                if vs["f1"] is not None:
                    vf1s.append(vs["f1"])
            for v in p.get("values", []):
                pred_values += 1
                src = text_by_doc.get(d, "")
                if quote_valid(v.get("quote", ""), src, v.get("value")):
                    quote_valid_n += 1
                else:
                    halluc += 1
        per_field[f] = {
            "macro_f1": sum(f1s) / len(f1s) if f1s else None,
            "n_docs": len(f1s),
            "value_f1": sum(vf1s) / len(vf1s) if vf1s else None,
            "n_value_docs": len(vf1s),
        }
        if f1s:
            all_f1.append(sum(f1s) / len(f1s))
        if vf1s:
            value_f1.append(sum(vf1s) / len(vf1s))
    macro = sum(all_f1) / len(all_f1) if all_f1 else None
    val_macro = sum(value_f1) / len(value_f1) if value_f1 else None

    # bootstrap over docs
    rng = random.Random(seed)
    boots = []
    for _ in range(1000):
        sample = [docs[rng.randrange(len(docs))] for _ in docs] if docs else []
        fs = []
        for f in FIELD_NAMES:
            vals = []
            for d in sample:
                g = gold[d]["fields"].get(f, {})
                p = pred[d]["fields"].get(f, {})
                x = field_presence(p, g)["f1"]
                if x is not None:
                    vals.append(x)
            if vals:
                fs.append(sum(vals) / len(vals))
        if fs:
            boots.append(sum(fs) / len(fs))
    boots.sort()
    ci = (boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]) if boots else (None, None)

    return {
        "n_docs": len(docs),
        "macro_f1": macro,
        "macro_f1_ci95": ci,
        "value_macro_f1": val_macro,
        "quote_valid_rate": quote_valid_n / pred_values if pred_values else None,
        "hallucination_rate": halluc / pred_values if pred_values else None,
        "omission_rate": omission / gold_reported if gold_reported else None,
        "n_pred_values": pred_values,
        "n_gold_reported": gold_reported,
        "per_field": per_field,
    }


def write_report(result: dict, path: str | Path) -> None:
    lines = [
        "# Evaluation report",
        "",
        f"- docs: {result['n_docs']}",
        f"- macro-F1: {result['macro_f1']:.4f}" if result["macro_f1"] is not None else "- macro-F1: n/a",
        f"- macro-F1 95% CI: {result['macro_f1_ci95']}",
        f"- value macro-F1: {result['value_macro_f1']}",
        f"- quote valid rate: {result['quote_valid_rate']}",
        f"- hallucination rate: {result['hallucination_rate']}",
        f"- omission rate: {result['omission_rate']}",
        "",
        "| field | macro-F1 | n | value-F1 | n |",
        "|---|---|---|---|---|",
    ]
    for f, x in result["per_field"].items():
        lines.append(f"| {f} | {x['macro_f1']} | {x['n_docs']} | {x['value_f1']} | {x['n_value_docs']} |")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
