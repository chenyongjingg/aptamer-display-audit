from __future__ import annotations

import re

from .common import FIELD_NAMES, norm_text

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def sentences(text: str) -> list[str]:
    text = norm_text(text)
    parts = SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def _sent_with(text: str, m: re.Match) -> str:
    start, end = max(0, m.start() - 300), min(len(text), m.end() + 300)
    window = text[start:end]
    ss = SENT_SPLIT.split(window)
    for s in ss:
        if m.group(0)[:40] in s:
            return s.strip()
    return window.strip()


def _num(pat: str, text: str, unit_group: int | None = None, field: str = "") -> list[dict]:
    out = []
    for m in re.finditer(pat, text, re.I):
        value = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
        unit = m.group(unit_group) if unit_group and m.lastindex and m.lastindex >= unit_group else ""
        out.append({"value": value, "unit": unit, "quote": _sent_with(text, m)})
    return out


def extract_rules(text: str) -> dict:
    t = norm_text(text)
    res = {}
    for f in FIELD_NAMES:
        res[f] = {"status": "not_reported", "values": [], "absence_evidence": "rule_scan_no_candidate"}

    # Kd
    vals = []
    vals += _num(r"(?:apparent\s+)?K\s*[dD]\s*(?:of|was|=|:)?\s*([<>~]?\s*\d+(?:\.\d+)?)\s*(nM|µM|uM|μM|pM|mM)", t, 2)
    if not vals:
        vals += _num(r"(?:dissociation\s+constant)[^.]{0,80}?([<>~]?\s*\d+(?:\.\d+)?)\s*(nM|µM|uM|μM|pM|mM)", t, 2)
    if vals:
        res["kd"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # %ID/g
    vals = []
    vals += _num(r"([<>~]?\s*\d+(?:\.\d+)?)\s*%\s*ID\s*/\s*g", t, None)
    if vals:
        res["id_per_g"] = {"status": "reported", "values": vals[:6], "absence_evidence": None}

    # half-life
    vals = _num(r"(?:half[-\s]?life|t\s*1/2|t½)[^.]{0,60}?([<>~]?\s*\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|min|minutes?|days?)", t, 2)
    if vals:
        res["half_life"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # dose
    vals = _num(r"(\d+(?:\.\d+)?)\s*(mg/kg|µg/kg|ug/kg|nmol/kg|µmol/kg|umol/kg)", t, 2)
    if vals:
        res["dose"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # route
    route_terms = ["intravenous", "i.v.", "iv ", "intravesical", "subcutaneous", "s.c.", "intraperitoneal", "i.p.", "oral"]
    for term in route_terms:
        m = re.search(re.escape(term), t, re.I)
        if m:
            res["route"] = {"status": "reported", "values": [{"value": term.strip(), "unit": "", "quote": _sent_with(t, m)}], "absence_evidence": None}
            break

    # time points (only near a PK/biodistribution readout)
    vals = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|days?)", t, re.I):
        sent = _sent_with(t, m)
        if re.search(r"%\s*ID|tumou?r|biodistribution|accumulat|uptake|retention", sent, re.I):
            vals.append({"value": m.group(1), "unit": m.group(2), "quote": sent})
    if vals:
        res["time_points"] = {"status": "reported", "values": vals[:8], "absence_evidence": None}

    # numeric efficacy
    vals = _num(r"(\d+(?:\.\d+)?)\s*%\s*(?:tumou?r\s+growth\s+inhibition|inhibition|TGI)", t, None)
    if not vals:
        vals = _num(r"(?:inhibited|inhibition)[^.]{0,30}?(\d+(?:\.\d+)?)\s*%", t, None)
    if vals:
        res["numeric_efficacy"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # serum stability (avoid "serum-free" and plain incubation times)
    vals = _num(r"(?:serum(?!-free)|nuclease)[^.]{0,80}?(?:stable|stability|half[-\s]?life|degrad)[^.]{0,40}?([<>~]?\s*\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|min|minutes?)", t, 2)
    if vals:
        res["serum_stability"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # valency
    vals = _num(r"(\d+)\s*(?:aptamers?|ligands?)\s*(?:per|on|at|in)?", t, None)
    if not vals:
        vals = _num(r"(?:valency|valence)\s*(?:of|=|:)?\s*(\d+)", t, None)
    if vals:
        # keep integer-like values
        vals = [v for v in vals if re.fullmatch(r"\d+", str(v["value"]).strip())][:6]
        if vals:
            res["valency"] = {"status": "reported", "values": vals, "absence_evidence": None}

    # spacing
    vals = _num(r"(?:spacing|distance|separated|interval)[^.]{0,60}?(\d+(?:\.\d+)?)\s*nm", t, None)
    if not vals:
        vals = _num(r"(\d+(?:\.\d+)?)\s*nm\s*(?:spacing|apart|intervals?)", t, None)
    if vals:
        res["spacing"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # linker length
    vals = _num(r"(?:linker|spacer)[^.]{0,60}?(\d+)\s*(nt|nucleotides?)", t, 2)
    if vals:
        res["linker_length"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # linker chemistry
    for term in ["poly-A", "polyA", "PEG", "TEG", "poly-T", "oligo-T", "cholesterol", "triethylene glycol"]:
        m = re.search(r"" + re.escape(term) + r"", t, re.I)
        if m:
            res["linker_chemistry"] = {"status": "reported", "values": [{"value": term, "unit": "", "quote": _sent_with(t, m)}], "absence_evidence": None}
            break

    # size
    vals = _num(r"(?:size|diameter|edge\s+length|hydrodynamic)[^.]{0,60}?(\d+(?:\.\d+)?)\s*nm", t, None)
    if not vals:
        vals = _num(r"(\d+(?:\.\d+)?)\s*nm\s*(?:in\s+size|diameter|edge)", t, None)
    if vals:
        res["size"] = {"status": "reported", "values": vals[:4], "absence_evidence": None}

    # attachment / orientation
    for term in ["vertex", "vertices", "edge", "face", "5' end", "3' end", "5′-end", "3′-end", "apex"]:
        m = re.search(r"" + re.escape(term) + r"", t, re.I)
        if m:
            quote = _sent_with(t, m)
            if re.search(r"acknowledg|fund|thank", quote, re.I):
                continue
            res["attachment"] = {"status": "reported", "values": [{"value": term, "unit": "", "quote": quote}], "absence_evidence": None}
            break

    # comparator arm
    for term in ["free aptamer", "monovalent", "naked", "unmodified aptamer", "free drug", "comparator"]:
        m = re.search(re.escape(term), t, re.I)
        if m:
            res["comparator"] = {"status": "reported", "values": [{"value": term, "unit": "", "quote": _sent_with(t, m)}], "absence_evidence": None}
            break

    # immune readout
    for term in ["CpG", "immunostim", "innate immune", "cytokine", "TLR", "interferon"]:
        m = re.search(re.escape(term), t, re.I)
        if m:
            res["immune"] = {"status": "reported", "values": [{"value": term, "unit": "", "quote": _sent_with(t, m)}], "absence_evidence": None}
            break

    return res
