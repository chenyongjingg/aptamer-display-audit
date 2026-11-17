from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

FIELDS = [
    # name, tier, canonical unit, tolerance (relative or absolute)
    ("kd", 1, "nM", 0.10),
    ("id_per_g", 1, "%ID/g", 0.10),
    ("half_life", 1, "h", 0.10),
    ("dose", 1, "mg/kg", 0.0),
    ("route", 1, "", 0.0),
    ("time_points", 1, "h", 0.0),
    ("numeric_efficacy", 1, "%", 2.0),
    ("serum_stability", 1, "h", 0.10),
    ("valency", 2, "count", 0.0),
    ("spacing", 2, "nm", 0.5),
    ("linker_length", 2, "nt", 0.0),
    ("linker_chemistry", 2, "", 0.0),
    ("size", 2, "nm", 0.05),
    ("attachment", 2, "", 0.0),
    ("comparator", 3, "", 0.0),
    ("immune", 3, "", 0.0),
]
FIELD_NAMES = [f[0] for f in FIELDS]
FIELD = {f[0]: {"tier": f[1], "unit": f[2], "tol": f[3]} for f in FIELDS}


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def norm_quote(text: str) -> str:
    return norm_text(text).lower()


def skeleton(text: str) -> str:
    text = norm_text(text).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def quote_valid_relaxed(quote: str, source: str, value: str | None = None) -> bool:
    q, s = skeleton(quote), skeleton(source)
    if len(q) < 5 or q not in s:
        return False
    if value:
        v = skeleton(str(value))
        if v and v not in q:
            return False
    return True


NEG_RE = re.compile(r"not\s+(?:determined|reported|measured|assessed|available|shown|detectable)|n\.d\.", re.I)
CONTRAST_RE = re.compile(r"(?:^|[ ,;])(but|however|whereas|while|although|yet)(?:[ ,;]|$)", re.I)


def is_negated(quote: str, value: str | None = None) -> bool:
    """Heuristic: a negation near the quote, without a contrast clause."""
    if not quote:
        return False
    if CONTRAST_RE.search(quote):
        return False
    return bool(NEG_RE.search(quote))


def quote_valid(quote: str, source: str, value: str | None = None) -> bool:
    q = norm_quote(quote)
    s = norm_quote(source)
    if len(q) < 5 or q not in s:
        return False
    if value:
        v = norm_quote(str(value))
        if v and v not in q:
            return False
    return True


NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def parse_number(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = NUM_RE.search(str(x).replace(",", ""))
    return float(m.group(0)) if m else None


UNIT_MAP = {
    "nm": ("nM", 1.0),
    "nanomolar": ("nM", 1.0),
    "um": ("nM", 1000.0),
    "µm": ("nM", 1000.0),
    "μm": ("nM", 1000.0),
    "micromolar": ("nM", 1000.0),
    "mm": ("nM", 1_000_000.0),
    "pm": ("nM", 0.001),
    "h": ("h", 1.0),
    "hr": ("h", 1.0),
    "hrs": ("h", 1.0),
    "hour": ("h", 1.0),
    "hours": ("h", 1.0),
    "min": ("h", 1 / 60.0),
    "minutes": ("h", 1 / 60.0),
    "d": ("h", 24.0),
    "day": ("h", 24.0),
    "days": ("h", 24.0),
    "nt": ("nt", 1.0),
    "nucleotide": ("nt", 1.0),
    "nucleotides": ("nt", 1.0),
    "%": ("%", 1.0),
}


def canon_unit(unit: str) -> tuple[str, float] | None:
    u = (unit or "").strip().lower().replace("μ", "µ")
    return UNIT_MAP.get(u)


def canon_value(value, unit: str) -> tuple[float | None, str]:
    # if the model put the unit inside the value string, split it
    if not unit and isinstance(value, str):
        m = re.match(r"^([<>~]?\s*\d+(?:\.\d+)?)\s*([A-Za-z%µμ/]+.*)$", value.strip())
        if m:
            value, unit = m.group(1), m.group(2)
    num = parse_number(value)
    cu = canon_unit(unit)
    if num is None or cu is None:
        return None, (unit or "")
    return num * cu[1], cu[0]


WORD_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100,
}


def word_number(x) -> int | None:
    s = norm_text(str(x)).lower().strip()
    if s in WORD_NUM:
        return WORD_NUM[s]
    return None


def _numeric(x) -> float | None:
    w = word_number(x)
    if w is not None:
        return float(w)
    return parse_number(x)


def values_match(a: dict, b: dict) -> bool:
    if not (a.get("unit") or b.get("unit")):
        wa, wb = _numeric(a.get("value")), _numeric(b.get("value"))
        if wa is not None and wb is not None:
            return wa == wb
    av, au = canon_value(a.get("value"), a.get("unit", ""))
    bv, bu = canon_value(b.get("value"), b.get("unit", ""))
    if av is None or bv is None:
        return norm_text(str(a.get("value"))) == norm_text(str(b.get("value")))
    if au != bu:
        # one side has no unit: compare the numeric value (silver often omits units)
        if au == "" or bu == "":
            tol = 0.10
            return abs(av - bv) <= max(abs(av), abs(bv), 1e-9) * tol
        return False
    tol = 0.10
    return abs(av - bv) <= max(abs(av), abs(bv), 1e-9) * tol


def chunk_text(text: str, max_chars: int = 24000) -> list[str]:
    """Character chunking with paragraph boundaries; keeps evidence spans local."""
    text = text or ""
    if len(text) <= max_chars:
        return [text]
    paras = re.split(r"\n\s*\n", text)
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 > max_chars and cur:
            chunks.append(cur)
            cur = p
        else:
            cur = (cur + "\n\n" + p).strip() if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def safe_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None
