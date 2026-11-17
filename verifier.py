"""Independent verifier: accept/reject/correct each candidate field.

The verifier is a model that is neither a silver source nor the evaluated
extractor (Qwen2.5-Coder-7B-Instruct by default). It sees the document and the
candidate JSON only; it must ground every accepted value in a verbatim quote.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from pipeline.common import FIELD_NAMES, load_jsonl, safe_json, write_jsonl

SYSTEM = """You are an independent verifier for a pharmacokinetics extraction audit.
For each candidate field, decide:
- accept: the document supports the value and the quote is verbatim and contains the value;
- reject: the value is absent, unsupported, or the quote is not verbatim;
- correct: the value is wrong but a supported value exists; return the corrected value.
Return JSON only: {"field": {"decision": "accept|reject|correct", "corrected": {...}, "reason": "..."}}
Never use general knowledge. If the document does not state it, reject."""


class Verifier:
    def __init__(self, model_path: str, load_in_4bit: bool = True):
        self.tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, quantization_config=bnb, device_map="auto", trust_remote_code=True)
        self.model.eval()

    def verify(self, text: str, candidates: dict) -> dict:
        payload = json.dumps(candidates, ensure_ascii=False)
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"<document>\n{text}\n</document>\n\nCandidates:\n{payload}\n\nReturn JSON now."}]
        try:
            prompt = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                                  enable_thinking=False)
        except TypeError:
            prompt = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = self.tok([prompt], return_tensors="pt", truncation=True, max_length=10000).to(self.model.device)
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=1200, do_sample=False,
                                      pad_token_id=self.tok.pad_token_id)
        raw = self.tok.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return safe_json(raw) or {"_parse_error": True, "_raw": raw[:1000]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--pred", default=None)
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--model", default="/model/ModelScope/Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run = Path(args.run)
    out = Path(args.out) if args.out else run / "verified"
    out.mkdir(parents=True, exist_ok=True)
    docs = {d["doc_id"]: d for d in load_jsonl(args.docs)}
    pred_path = Path(args.pred) if args.pred else (run / "pred_eval.jsonl")
    preds = load_jsonl(pred_path)[: args.limit]
    ver = Verifier(args.model)
    rows = []
    for i, p in enumerate(preds, 1):
        d = docs.get(p["doc_id"], {})
        cand = {f: p["fields"].get(f, {}) for f in FIELD_NAMES}
        dec = ver.verify(d.get("text", ""), cand)
        fields = {}
        for f in FIELD_NAMES:
            x = cand.get(f, {})
            v = dec.get(f, {}) if isinstance(dec, dict) else {}
            decision = (v.get("decision") or "reject").lower()
            if decision == "reject":
                fields[f] = {"status": "not_reported", "values": [], "absence_evidence": v.get("reason", "verifier_reject")}
            elif decision == "correct" and isinstance(v.get("corrected"), dict):
                fields[f] = v["corrected"]
            else:
                fields[f] = x
        rows.append({"doc_id": p["doc_id"], "paper_id": p.get("paper_id"), "level": p.get("level"),
                     "fields": fields, "verifier_raw": dec})
        if i % 5 == 0:
            print(f"[verifier] {i}/{len(preds)}", flush=True)
    write_jsonl(out / "pred_verified.jsonl", rows)
    (out / "verifier_manifest.json").write_text(json.dumps({"model": args.model, "n": len(rows)},
                                                           ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
