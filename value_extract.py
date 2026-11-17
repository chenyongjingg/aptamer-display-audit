"""Two-stage value extraction: candidate sentences -> field-specific LLM -> hybrid.

This is the value-extraction repair for the pilot. It does not train; it uses
the existing Qwen2.5-7B zero-shot model on short, field-specific evidence
windows, then fuses with the deterministic rule extractor.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.common import FIELD_NAMES, load_jsonl, quote_valid_relaxed, safe_json, write_jsonl
from pipeline.llm import LLM
from pipeline.rules import extract_rules

SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")

FIELD_SPEC = {
    "kd": ("apparent dissociation constant; nM/uM/pM", r"\bK\s*[dD]\b|dissociation constant|apparent K"),
    "id_per_g": ("normalized tumour accumulation %ID/g; include organ and time", r"%\s*ID|ID\s*/\s*g|injected dose"),
    "half_life": ("half-life or clearance; h or mL/h/kg", r"half[-\s]?life|t\s*1/2|clearance"),
    "dose": ("administered dose with unit", r"mg\s*/\s*kg|nmol\s*/\s*kg|µg\s*/\s*kg|dose"),
    "route": ("administration route", r"intravenous|i\.v\.|intraperitoneal|subcutaneous|oral|intravesical"),
    "time_points": ("time points of PK/biodistribution readout", r"\b\d+\s*(h|hr|hours?|days?)\b"),
    "numeric_efficacy": ("numeric % tumour growth inhibition or % cell inhibition", r"%|inhibition|tumou?r growth"),
    "serum_stability": ("serum/nuclease stability with conditions", r"serum|nuclease|stabilit"),
    "valency": ("integer number of aptamers/ligands", r"aptamer|ligand|valen"),
    "spacing": ("ligand-ligand distance in nm", r"spacing|distance|separat|interval"),
    "linker_length": ("linker/spacer length in nt", r"linker|spacer"),
    "linker_chemistry": ("linker/spacer chemistry", r"PEG|poly-?A|poly-?T|TEG|cholesterol|triethylene"),
    "size": ("construct size in nm and method", r"\bsize\b|diameter|edge length|hydrodynamic"),
    "attachment": ("attachment site/orientation", r"vertex|vertices|edge|face|5'|3'|apex"),
    "comparator": ("free/monovalent/naked comparator arm", r"free aptamer|monovalent|naked|comparator|free drug"),
    "immune": ("CpG or innate-immune/cytokine readout", r"CpG|immun|cytokine|TLR|interferon"),
}

SYSTEM = """You extract one reporting field from preclinical cancer-therapy text.
Use ONLY the provided sentences. Do not use general knowledge.
Return JSON: {"status": "reported|not_reported", "values": [{"value": "...", "unit": "...", "quote": "...", "context": {}}], "absence_evidence": "..."}
Every quote must be copied verbatim from the sentences and must contain the value.
If the sentences do not state the value, return not_reported."""


def candidates(text: str, field: str, k: int = 3) -> list[str]:
    pat = re.compile(FIELD_SPEC[field][1], re.I)
    sents = [s.strip() for s in SENT.split(text or "") if s.strip()]
    scored = []
    for i, s in enumerate(sents):
        if pat.search(s):
            window = " ".join(sents[max(0, i - 1): min(len(sents), i + 2)])
            scored.append((len(pat.findall(s)), i, window))
    scored.sort(reverse=True)
    out, seen = [], set()
    for _, _, w in scored:
        if w not in seen:
            seen.add(w)
            out.append(w)
        if len(out) >= k:
            break
    return out


def parse_field(raw: str, field: str) -> dict:
    obj = safe_json(raw)
    if not isinstance(obj, dict):
        return {"status": "not_reported", "values": [], "absence_evidence": "parse_error"}
    if field in obj and isinstance(obj[field], dict):
        obj = obj[field]
    elif len(obj) == 1 and isinstance(next(iter(obj.values())), dict):
        obj = next(iter(obj.values()))
    status = str(obj.get("status", "not_reported")).lower()
    vals = []
    for v in obj.get("values", []) or []:
        if isinstance(v, dict):
            vals.append({"value": v.get("value"), "unit": v.get("unit", ""),
                         "quote": v.get("quote", ""), "context": v.get("context", {})})
    return {"status": "reported" if status == "reported" and vals else "not_reported",
            "values": vals, "absence_evidence": obj.get("absence_evidence")}


def extract_doc(llm: LLM, doc: dict) -> tuple[dict, dict]:
    text = doc.get("text", "")
    rule = extract_rules(text)
    llm_fields = {}
    for f in FIELD_NAMES:
        # if the rule already reports a valid value, hybrid will use it; skip the LLM call
        rf = rule.get(f, {})
        if rf.get("status") == "reported" and rf.get("values") and all(
                quote_valid_relaxed(v.get("quote", ""), text, v.get("value")) for v in rf["values"]):
            llm_fields[f] = rf
            continue
        cands = candidates(text, f)
        if not cands:
            llm_fields[f] = {"status": "not_reported", "values": [], "absence_evidence": "no_candidate"}
            continue
        user = (f"Field: {f} ({FIELD_SPEC[f][0]}).\n\nSentences:\n"
                + "\n".join(f"- {c}" for c in cands)
                + "\n\nReturn the JSON object now.")
        raw = llm.generate(SYSTEM, user, max_new_tokens=300)
        x = parse_field(raw, f)
        vals = []
        for v in x["values"]:
            if quote_valid_relaxed(v.get("quote", ""), text, v.get("value")):
                vals.append(v)
        if vals:
            x["values"] = vals
        else:
            x = {"status": "not_reported", "values": [], "absence_evidence": "quote_gate"}
        llm_fields[f] = x
    hybrid = {}
    for f in FIELD_NAMES:
        r = rule.get(f, {})
        l = llm_fields[f]
        if r.get("status") == "reported" and r.get("values"):
            hybrid[f] = r
        elif l.get("status") == "reported" and l.get("values"):
            hybrid[f] = l
        else:
            hybrid[f] = {"status": "not_reported", "values": [], "absence_evidence": "no_rule_no_llm"}
    return llm_fields, hybrid


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--silver", required=True)
    ap.add_argument("--model", default="/model/ModelScope/Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--out", default="runs/value_exp")
    args = ap.parse_args()
    docs = load_jsonl(args.docs)
    sil = load_jsonl(args.silver)
    smap = {r["doc_id"]: r for r in sil}
    def pos(d):
        return sum(1 for f in FIELD_NAMES
                   if smap.get(d["doc_id"], {}).get("fields", {}).get(f, {}).get("confidence") in {"high", "medium"}
                   and smap.get(d["doc_id"], {}).get("fields", {}).get(f, {}).get("status") == "reported")
    docs = sorted(docs, key=pos, reverse=True)[: args.limit]
    print("docs", len(docs), "positives", sum(pos(d) for d in docs), flush=True)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    llm = LLM(args.model, load_in_4bit=True)
    llm_rows, hy_rows = [], []
    for i, d in enumerate(docs, 1):
        lf, hy = extract_doc(llm, d)
        llm_rows.append({"doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "fields": lf})
        hy_rows.append({"doc_id": d["doc_id"], "paper_id": d.get("paper_id"), "fields": hy})
        if i % 3 == 0:
            print(f"[value] {i}/{len(docs)}", flush=True)
    write_jsonl(out / "pred_llm_candidates.jsonl", llm_rows)
    write_jsonl(out / "pred_hybrid.jsonl", hy_rows)
    print("wrote", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
