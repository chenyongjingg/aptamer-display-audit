from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from .common import (
    is_negated,
    FIELD_NAMES,
    canon_value,
    norm_text,
    quote_valid,
    sha256_text,
    values_match,
    write_jsonl,
)
from .rules import extract_rules

VALID_STATUS = {"reported", "not_reported", "not_applicable"}


def norm_status(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in {"reported", "yes", "present", "true"}:
        return "reported"
    if s in {"not_reported", "not_reported_in_text", "absent", "no", "false", "none"}:
        return "not_reported"
    if s in {"not_applicable", "na", "n/a"}:
        return "not_applicable"
    return "not_reported"


def norm_values(values) -> list[dict]:
    out = []
    if not isinstance(values, list):
        values = [values] if values else []
    for v in values:
        if isinstance(v, dict):
            out.append(
                {
                    "value": v.get("value"),
                    "unit": v.get("unit", ""),
                    "quote": v.get("quote", ""),
                    "context": v.get("context", {}),
                }
            )
        elif v not in (None, ""):
            out.append({"value": v, "unit": "", "quote": "", "context": {}})
    return out


def norm_source(obj: dict | None) -> dict:
    if not isinstance(obj, dict) or obj.get("_parse_error"):
        return {"_missing": True}
    out = {}
    for f in FIELD_NAMES:
        x = obj.get(f)
        if isinstance(x, dict):
            out[f] = {
                "status": norm_status(x.get("status")),
                "values": norm_values(x.get("values")),
                "absence_evidence": x.get("absence_evidence"),
            }
        else:
            out[f] = {"_missing": True}
    return out


def _val_match(a: dict, b: dict) -> bool:
    if a.get("value") is None or b.get("value") is None:
        return norm_text(str(a.get("value"))) == norm_text(str(b.get("value")))
    return values_match(a, b)


def _agree_values(vals_a: list[dict], vals_b: list[dict]) -> list[dict]:
    agreed = []
    for a in vals_a:
        for b in vals_b:
            if _val_match(a, b):
                agreed.append(a)
                break
    return agreed


def _validate_source(src: dict, text: str, field: str) -> dict:
    """Drop values whose quote is not a verbatim substring containing the value."""
    if src.get("_missing"):
        return src
    vals = []
    dropped = 0
    for v in src.get("values", []):
        if quote_valid(v.get("quote", ""), text, v.get("value")) and not is_negated(v.get("quote", ""), v.get("value")):
            vals.append(v)
        else:
            dropped += 1
    out = dict(src)
    out["values"] = vals
    out["dropped_invalid_quotes"] = dropped
    if src.get("status") == "reported" and not vals:
        out["status"] = "not_reported"
        out["absence_evidence"] = "all_values_failed_quote_gate"
    return out


def consensus_field(field: str, sources: dict[str, dict], text: str) -> dict:
    present = {k: v for k, v in sources.items() if not v.get("_missing")}
    statuses = {k: v["status"] for k, v in present.items()}
    reporting = {k: v for k, v in present.items() if v["status"] == "reported"}
    absent = {k: v for k, v in present.items() if v["status"] == "not_reported"}
    na = {k: v for k, v in present.items() if v["status"] == "not_applicable"}

    # agree on reported + at least one matching value
    if len(reporting) >= 2:
        keys = list(reporting)
        base = reporting[keys[0]]["values"]
        for k in keys[1:]:
            base = _agree_values(base, reporting[k]["values"])
        if base:
            return {
                "status": "reported",
                "values": base,
                "confidence": "high",
                "provenance": keys,
                "absence_evidence": None,
            }
        return {
            "status": "conflict",
            "values": [],
            "confidence": "low",
            "provenance": keys,
            "absence_evidence": "status_agree_values_disagree",
        }

    if len(reporting) == 1:
        k = next(iter(reporting))
        if k == "rule" and len(absent) >= 1:
            return {"status": "conflict", "values": [], "confidence": "low",
                    "provenance": list(statuses), "absence_evidence": "rule_reports_llm_absent"}
        return {
            "status": "reported",
            "values": reporting[k]["values"],
            "confidence": "medium",
            "provenance": [k],
            "absence_evidence": None,
        }

    if len(na) >= 2 and len(absent) == 0:
        return {"status": "not_applicable", "values": [], "confidence": "high",
                "provenance": list(na), "absence_evidence": "all_sources_na"}

    if len(absent) >= 2 and len(reporting) == 0:
        # rule source absence + LLM absence
        return {"status": "not_reported", "values": [], "confidence": "high",
                "provenance": list(absent), "absence_evidence": "all_sources_absent"}

    return {
        "status": "conflict",
        "values": [],
        "confidence": "low",
        "provenance": list(statuses),
        "absence_evidence": f"statuses={statuses}",
    }


def build_silver(
    docs: list[dict],
    llm_a=None,
    llm_b=None,
    out_dir: str | Path = "data",
    limit: int | None = None,
    cache_dir: str | Path = "cache",
    b_sample: set[str] | None = None,
) -> dict:
    out_dir = Path(out_dir)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (out_dir).mkdir(parents=True, exist_ok=True)

    if limit:
        # prefer full texts, then abstracts
        docs = sorted(docs, key=lambda d: (d.get("level") != "full", d.get("doc_id", "")))[:limit]

    rows = []
    sources_rows = []
    for i, doc in enumerate(docs, 1):
        text = doc.get("text", "")
        did = doc.get("doc_id", "")
        rule = extract_rules(text)
        llm_a_out = None
        llm_b_out = None
        for tag, model in (("A", llm_a), ("B", llm_b)):
            if model is None:
                continue
            if tag == "B" and b_sample is not None and did not in b_sample:
                continue
            cpath = cache_dir / f"{tag}_{sha256_text(model.model_path)[:10]}_{did}.json"
            if cpath.exists():
                try:
                    payload = json.loads(cpath.read_text(encoding="utf-8"))
                    obj = payload.get("obj") if isinstance(payload, dict) else None
                except Exception:
                    obj = None
            else:
                obj, raw = model.extract(text, did)
                cpath.write_text(json.dumps({"obj": obj, "raw": raw}, ensure_ascii=False), encoding="utf-8")
            if tag == "A":
                llm_a_out = obj
            else:
                llm_b_out = obj
        sources = {"rule": rule}
        if llm_a_out is not None:
            sources["llmA"] = norm_source(llm_a_out)
        if llm_b_out is not None:
            sources["llmB"] = norm_source(llm_b_out)

        # quote gate: validate against the exact text each model saw (chunk union)
        src_texts = {"rule": text}
        if llm_a is not None:
            src_texts["llmA"] = chr(10).join(llm_a._split(text))
        if llm_b is not None:
            src_texts["llmB"] = chr(10).join(llm_b._split(text))
        sources = {
            k: (_validate_source(v, src_texts.get(k, text), "") if k != "rule" else v)
            for k, v in sources.items()
        }

        fields = {}
        for f in FIELD_NAMES:
            fsrc = {k: (v.get(f) if isinstance(v, dict) and not v.get("_missing") else {"_missing": True})
                    for k, v in sources.items()}
            fields[f] = consensus_field(f, fsrc, text)

        row = {
            "_sources": sources,
            "doc_id": did,
            "paper_id": doc.get("paper_id"),
            "level": doc.get("level"),
            "text_kind": doc.get("text_kind"),
            "doi": doc.get("doi"),
            "year": doc.get("year"),
            "fields": fields,
        }
        rows.append(row)
        sources_rows.append(
            {
                "doc_id": did,
                "sources": sources,
                "raw_llm_a": llm_a_out,
                "raw_llm_b": llm_b_out,
            }
        )
        if i % 5 == 0:
            print(f"[silver] {i}/{len(docs)} docs", flush=True)

    write_jsonl(out_dir / "silver_raw.jsonl", rows)
    clean = [{k: v for k, v in r.items() if k != "_sources"} for r in rows]
    write_jsonl(out_dir / "silver_v1.0.jsonl", clean)
    write_jsonl(out_dir / "silver_sources.jsonl", sources_rows)
    qa = silver_qa(rows)
    (out_dir / "silver_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"rows": len(rows), "qa": qa}


def _kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for binary reported vs not_reported."""
    pairs = [(a, b) for a, b in pairs if a in {"reported", "not_reported"} and b in {"reported", "not_reported"}]
    if not pairs:
        return None
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    pa = sum(1 for a, _ in pairs if a == "reported") / n
    pb = sum(1 for _, b in pairs if b == "reported") / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def silver_qa(rows: list[dict]) -> dict:
    n = len(rows)
    per_field = {}
    total_values = 0
    valid_values = 0
    for f in FIELD_NAMES:
        conf = Counter()
        status = Counter()
        prov = Counter()
        pairs_ra, pairs_rb, pairs_ab = [], [], []
        for r in rows:
            x = r["fields"].get(f, {})
            conf[x.get("confidence", "low")] += 1
            status[x.get("status", "conflict")] += 1
            for p in x.get("provenance", []):
                prov[p] += 1
            vals = x.get("values", [])
            total_values += len(vals)
            valid_values += len(vals)  # already gated
        high = conf.get("high", 0)
        per_field[f] = {
            "high": high,
            "medium": conf.get("medium", 0),
            "low": conf.get("low", 0),
            "coverage_high": round(high / n, 3) if n else 0,
            "status": dict(status),
            "provenance": dict(prov),
        }
    # inter-source agreement (rule vs llmA/B), binary reported vs not
    for f in FIELD_NAMES:
        pa, pb, pc = [], [], []
        for r in rows:
            srcs = r.get("_sources")
            if not srcs:
                continue
            def st(k):
                x = srcs.get(k, {}).get(f, {}) if isinstance(srcs.get(k), dict) else {}
                if x.get("_missing"):
                    return None
                return x.get("status", "not_reported")
            sa, sb, sc = st("rule"), st("llmA"), st("llmB")
            if sa is not None and sb is not None:
                pa.append((sa, sb))
            if sa is not None and sc is not None:
                pb.append((sa, sc))
            if sb is not None and sc is not None:
                pc.append((sb, sc))
        per_field[f]["kappa_rule_llmA"] = _kappa(pa)
        per_field[f]["kappa_rule_llmB"] = _kappa(pb)
        per_field[f]["kappa_llmA_llmB"] = _kappa(pc)
    return {
        "n_docs": n,
        "quote_valid_rate": round(valid_values / total_values, 3) if total_values else None,
        "total_values": total_values,
        "fields": per_field,
        "notes": "Inter-source kappa is computed only where the source rows are available in memory; "
                 "for persisted runs, recompute from silver_sources.jsonl.",
    }
