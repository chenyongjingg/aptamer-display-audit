"""Recompute the consensus silver standard from persisted source rows.

This is the scientific core of the audit: it does not call any model. It reads
`silver_sources.jsonl` (rule + LLM-A + LLM-B + optional review extraction),
re-runs the consensus rules with multi-value/context handling, applies the
evidence/absence gates, and writes `silver_v2.jsonl` plus QA.

Why this exists: the first run's consensus collapsed multi-value fields to the
first matching value and ignored context. Both are material for PK quantities.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .common import (
    is_negated,
    FIELD_NAMES,
    canon_value,
    norm_text,
    quote_valid,
    quote_valid_relaxed,
    values_match,
    write_jsonl,
)

STATUSES = {"reported", "not_reported", "not_applicable"}
VALUE_FIELDS = {
    "kd", "id_per_g", "half_life", "dose", "time_points", "numeric_efficacy",
    "serum_stability", "valency", "spacing", "linker_length", "size",
}
CONTEXT_KEYS = ("method", "buffer", "temperature", "cell_line", "time_point", "route", "dose")


def _norm_status(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in {"reported", "yes", "present", "true"}:
        return "reported"
    if s in {"not_applicable", "na", "n/a"}:
        return "not_applicable"
    return "not_reported"


def _merge_context(values: list[dict]) -> tuple[dict, bool]:
    ctx = {}
    conflict = False
    for v in values:
        c = v.get("context") or {}
        if not isinstance(c, dict):
            continue
        for k, val in c.items():
            if val in (None, "", []):
                continue
            if k not in ctx:
                ctx[k] = val
            elif norm_text(str(ctx[k])) != norm_text(str(val)):
                conflict = True
    complete = any(k in ctx for k in CONTEXT_KEYS)
    return ctx, complete and not conflict


def _cluster_values(source_values: dict[str, list[dict]]) -> list[dict]:
    """Cluster values across sources; support = number of distinct sources."""
    clusters: list[dict] = []
    for src, vals in source_values.items():
        for v in vals:
            if not isinstance(v, dict) or v.get("value") in (None, ""):
                continue
            for c in clusters:
                if values_match(c["value"], v):
                    c["sources"].add(src)
                    c["context_values"].append(v)
                    break
            else:
                clusters.append({"value": v, "sources": {src}, "context_values": [v]})
    out = []
    for c in clusters:
        ctx, complete = _merge_context(c["context_values"])
        value = dict(c["value"])
        value["context"] = ctx
        out.append(
            {
                "value": value,
                "support": len(c["sources"]),
                "sources": sorted(c["sources"]),
                "context_complete": complete,
            }
        )
    return out


def _validate_value(v: dict, text: str) -> bool:
    return quote_valid(v.get("quote", ""), text, v.get("value"))


def consensus_doc(
    doc: dict,
    source_rows: dict,
    review: dict | None = None,
    text_override: dict[str, str] | None = None,
) -> dict:
    text = doc.get("text", "")
    sources = {k: v for k, v in source_rows.items() if isinstance(v, dict) and not v.get("_missing")}
    if review:
        sources["review"] = review
    fields = {}
    for f in FIELD_NAMES:
        src_field = {}
        for k, s in sources.items():
            x = s.get(f) if isinstance(s, dict) else None
            if not isinstance(x, dict) or x.get("_missing"):
                continue
            vals = []
            for v in x.get("values", []) or []:
                vv = dict(v)
                src_text = (text_override or {}).get(k, text)
                ok = (quote_valid_relaxed(vv.get("quote", ""), src_text, vv.get("value"))
                      if k in {"llmA", "llmB"} else quote_valid(vv.get("quote", ""), src_text, vv.get("value")))
                if ok and not is_negated(vv.get("quote", ""), vv.get("value")):
                    vals.append(vv)
            src_field[k] = {
                "status": _norm_status(x.get("status")),
                "values": vals,
                "absence_evidence": x.get("absence_evidence"),
                "invalid_values_dropped": len(x.get("values", []) or []) - len(vals),
            }
        if not src_field:
            fields[f] = {
                "status": "not_reported", "values": [], "confidence": "low",
                "provenance": [], "absence_evidence": "no_source",
                "context_complete": False,
            }
            continue
        statuses = {k: v["status"] for k, v in src_field.items()}
        reporting = {k: v for k, v in src_field.items() if v["status"] == "reported" and v["values"]}
        absent = {k: v for k, v in src_field.items() if v["status"] == "not_reported"}
        na = {k: v for k, v in src_field.items() if v["status"] == "not_applicable"}

        # clusters over all reported values
        clusters = _cluster_values({k: v["values"] for k, v in reporting.items()})
        high_clusters = [c for c in clusters if c["support"] >= 2]
        all_clusters = [c for c in clusters if c["support"] >= 1]

        if high_clusters:
            fields[f] = {
                "status": "reported",
                "values": [c["value"] for c in high_clusters],
                "confidence": "high",
                "provenance": sorted({s for c in high_clusters for s in c["sources"]}),
                "absence_evidence": None,
                "context_complete": all(c["context_complete"] for c in high_clusters),
                "n_values": len(high_clusters),
                "conflicting_sources": sorted(absent) if absent else [],
            }
        elif all_clusters and len(reporting) == 1:
            fields[f] = {
                "status": "reported",
                "values": [c["value"] for c in all_clusters],
                "confidence": "medium",
                "provenance": sorted(reporting),
                "absence_evidence": None,
                "context_complete": all(c["context_complete"] for c in all_clusters),
                "n_values": len(all_clusters),
                "conflicting_sources": sorted(absent) if absent else [],
            }
        elif reporting and absent:
            fields[f] = {
                "status": "conflict", "values": [], "confidence": "low",
                "provenance": sorted(statuses), "absence_evidence": f"statuses={statuses}",
                "context_complete": False,
            }
        elif len(absent) >= 2 and not reporting and not na:
            fields[f] = {
                "status": "not_reported", "values": [], "confidence": "high",
                "provenance": sorted(absent),
                "absence_evidence": {
                    "sources": sorted(absent),
                    "evidence": {k: absent[k].get("absence_evidence") for k in absent},
                },
                "context_complete": True,
            }
        elif na and not reporting and not absent:
            fields[f] = {
                "status": "not_applicable", "values": [],
                "confidence": "high" if len(na) >= 2 else "medium",
                "provenance": sorted(na), "absence_evidence": "all_sources_na",
                "context_complete": True,
            }
        else:
            fields[f] = {
                "status": "conflict", "values": [], "confidence": "low",
                "provenance": sorted(statuses), "absence_evidence": f"statuses={statuses}",
                "context_complete": False,
            }
    return {
        "doc_id": doc.get("doc_id"), "paper_id": doc.get("paper_id"),
        "level": doc.get("level"), "text_kind": doc.get("text_kind"),
        "doi": doc.get("doi"), "year": doc.get("year"), "fields": fields,
    }


def load_review_extraction(path: str | Path) -> dict[str, dict]:
    """Map the review's 20-row extraction.csv to silver source objects.

    Only fields with a non-NA value are used. Quotes come from anchor_locator
    when it contains a quoted span; otherwise the value is used as quote and
    will fail the quote gate (by design, so it cannot enter the silver).
    """
    import csv

    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    field_map = {
        "kd_value": "kd", "id_per_g": "id_per_g", "t_half": "half_life",
        "tumor_inhibition_pct": "numeric_efficacy", "serum_stability": "serum_stability",
        "valency_n": "valency", "ligand_ligand_distance_nm": "spacing",
        "linker_length_nt": "linker_length", "linker_chemistry": "linker_chemistry",
        "size_nm": "size", "attachment_site": "attachment",
    }
    for row in csv.DictReader(open(p, encoding="utf-8")):
        cid = str(row.get("cluster_id", "")).strip()
        if not cid:
            continue
        fields = {}
        anchor = row.get("anchor_locator", "") or ""
        quote = anchor.split(":", 1)[1].strip() if ":" in anchor else ""
        for col, f in field_map.items():
            raw = (row.get(col) or "").strip()
            if raw in {"", "NA", "N/A", "None"}:
                continue
            unit = ""
            value = raw
            # split trailing unit when obvious
            for u in ("nM", "µM", "uM", "mM", "pM", "%ID/g", "nm", "nt", "h", "%", "mg/kg"):
                if raw.lower().endswith(u.lower()):
                    value = raw[: -len(u)].strip()
                    unit = u
                    break
            fields[f] = {
                "status": "reported",
                "values": [{"value": value, "unit": unit, "quote": quote, "context": {}}],
                "absence_evidence": None,
            }
        if fields:
            out[f"S{cid}_full"] = fields
    return out


def _sanity(field: str, value: dict) -> bool:
    num, unit = canon_value(value.get("value"), value.get("unit", ""))
    if num is None:
        return True  # categorical
    ranges = {
        "kd": (1e-3, 1e6), "id_per_g": (0, 100), "half_life": (0.01, 1e4),
        "dose": (0, 1e6), "time_points": (0, 1e4), "numeric_efficacy": (0, 100),
        "serum_stability": (0, 1e4), "valency": (1, 100), "spacing": (0.1, 1000),
        "linker_length": (0, 200), "size": (1, 1000),
    }
    if field not in ranges:
        return True
    lo, hi = ranges[field]
    return lo <= num <= hi


def qa_v2(rows: list[dict], docs: dict[str, dict]) -> dict:
    n = len(rows)
    per_field = {}
    total_values = 0
    valid_values = 0
    sanity_fail = 0
    for f in FIELD_NAMES:
        conf = Counter()
        status = Counter()
        prov = Counter()
        n_values = 0
        n_sanity_fail = 0
        n_context = 0
        for r in rows:
            x = r["fields"].get(f, {})
            conf[x.get("confidence", "low")] += 1
            status[x.get("status", "conflict")] += 1
            for p in x.get("provenance", []):
                prov[p] += 1
            for v in x.get("values", []):
                n_values += 1
                total_values += 1
                if _sanity(f, v):
                    valid_values += 1
                else:
                    n_sanity_fail += 1
                    sanity_fail += 1
            if x.get("status") == "reported" and x.get("context_complete"):
                n_context += 1
        high = conf.get("high", 0)
        per_field[f] = {
            "high": high, "medium": conf.get("medium", 0), "low": conf.get("low", 0),
            "coverage_high": round(high / n, 3) if n else 0,
            "status": dict(status), "provenance": dict(prov),
            "n_values": n_values, "n_sanity_fail": n_sanity_fail,
            "n_context_complete": n_context,
        }
    # cross-field checks
    cross = {}
    def get(doc, f):
        return doc["fields"].get(f, {})
    checks = {
        "id_per_g_has_time_route": lambda r: (get(r, "id_per_g").get("status") != "reported") or
            (get(r, "time_points").get("status") == "reported" and get(r, "route").get("status") == "reported"),
        "efficacy_has_comparator": lambda r: (get(r, "numeric_efficacy").get("status") != "reported") or
            (get(r, "comparator").get("status") == "reported"),
        "linker_has_chemistry": lambda r: (get(r, "linker_length").get("status") != "reported") or
            (get(r, "linker_chemistry").get("status") == "reported"),
    }
    for name, fn in checks.items():
        applicable = 0
        ok = 0
        for r in rows:
            # only where the antecedent is reported
            if name.startswith("id_per_g") and get(r, "id_per_g").get("status") != "reported":
                continue
            if name.startswith("efficacy") and get(r, "numeric_efficacy").get("status") != "reported":
                continue
            if name.startswith("linker") and get(r, "linker_length").get("status") != "reported":
                continue
            applicable += 1
            ok += int(fn(r))
        cross[name] = {"applicable": applicable, "ok": ok,
                       "rate": round(ok / applicable, 3) if applicable else None}
    tiers = defaultdict(lambda: {"high": 0, "n": 0})
    for r in rows:
        for f in FIELD_NAMES:
            x = r["fields"].get(f, {})
            tier = _tier(f)
            tiers[tier]["n"] += 1
            if x.get("confidence") == "high":
                tiers[tier]["high"] += 1
    return {
        "n_docs": n,
        "sanity_pass_rate": round(valid_values / total_values, 3) if total_values else None,
        "sanity_fail_values": sanity_fail,
        "cross_field": cross,
        "tier_coverage": {k: {"high": v["high"], "n": v["n"],
                              "rate": round(v["high"] / v["n"], 3) if v["n"] else None}
                          for k, v in tiers.items()},
        "fields": per_field,
        "notes": "Q5 stability, Q6 decoy and Q7 external AutoPK anchor are separate functions; "
                 "if not run, their status must be reported as not_run, not pass.",
    }


def _tier(f: str) -> int:
    return {"kd": 1, "id_per_g": 1, "half_life": 1, "dose": 1, "route": 1,
            "time_points": 1, "numeric_efficacy": 1, "serum_stability": 1,
            "valency": 2, "spacing": 2, "linker_length": 2, "linker_chemistry": 2,
            "size": 2, "attachment": 2, "comparator": 3, "immune": 3}[f]


def build_v2(
    docs: list[dict],
    sources_path: str | Path,
    out_dir: str | Path,
    review_path: str | Path | None = None,
) -> dict:
    sources = {r["doc_id"]: r["sources"] for r in
               (json.loads(l) for l in open(sources_path, encoding="utf-8") if l.strip())}
    review = load_review_extraction(review_path) if review_path else {}
    rows = []
    for d in docs:
        did = d["doc_id"]
        if did not in sources:
            continue
        rows.append(consensus_doc(d, sources[did], review=review.get(did)))
    write_jsonl(Path(out_dir) / "silver_v2.jsonl", rows)
    qa = qa_v2(rows, {d["doc_id"]: d for d in docs})
    (Path(out_dir) / "silver_qa_v2.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "n_docs": len(rows),
        "sources": str(sources_path),
        "review_source": str(review_path) if review_path else None,
        "fields": FIELD_NAMES,
        "consensus": "support>=2 high; single-source medium; conflict low",
        "qa": "Q1-Q4/Q8 in qa_v2; Q5-Q7 separate",
    }
    (Path(out_dir) / "silver_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"rows": len(rows), "qa": qa}
