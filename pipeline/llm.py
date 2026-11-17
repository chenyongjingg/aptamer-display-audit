from __future__ import annotations

import os
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .common import FIELD_NAMES, safe_json

try:
    torch._dynamo.config.disable = True
except Exception:
    pass
try:
    torch.backends.cuda.matmul.allow_tf32 = True
except Exception:
    pass


def _prompt() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "p2.md"
    return p.read_text(encoding="utf-8")


class LLM:
    def __init__(self, model_path: str, max_doc_tokens: int = 6000,
                 max_new_tokens: int = 1200, load_in_4bit: bool = True,
                 adapter_path: str | None = None):
        self.model_path = model_path
        self.max_doc_tokens = max_doc_tokens
        self.max_new_tokens = max_new_tokens
        self.load_in_4bit = load_in_4bit
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path, trust_remote_code=True, fix_mistral_regex=True
            )
        except TypeError:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        kwargs = dict(device_map="auto", trust_remote_code=True)
        if load_in_4bit:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
        else:
            kwargs["torch_dtype"] = torch.bfloat16
        self.model = AutoModelForCausalLM.from_pretrained(model_path, **kwargs)
        if adapter_path:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter_path)
        self.model.eval()
        for k in ("temperature", "top_p", "top_k"):
            if hasattr(self.model.generation_config, k):
                setattr(self.model.generation_config, k, None)

    def _chat(self, user: str) -> str:
        messages = [
            {"role": "system", "content": _prompt()},
            {"role": "user", "content": user},
        ]
        try:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
        except TypeError:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

    def _generate(self, prompt: str, max_new_tokens: int | None = None) -> str:
        inputs = self.tokenizer(
            [prompt], return_tensors="pt", truncation=True, max_length=10000
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        with torch.inference_mode():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens or self.max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        gen = out[0, inputs["input_ids"].shape[1] :]
        return self.tokenizer.decode(gen, skip_special_tokens=True)

    def generate(self, system: str, user: str, max_new_tokens: int | None = None) -> str:
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        try:
            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
        return self._generate(prompt, max_new_tokens)

    def _split(self, text: str) -> list[str]:
        ids = self.tokenizer(text or "", add_special_tokens=False).input_ids
        if len(ids) <= self.max_doc_tokens:
            return [text or ""]
        chunks = []
        step = self.max_doc_tokens - 200
        for i in range(0, len(ids), step):
            chunk_ids = ids[i : i + self.max_doc_tokens]
            chunks.append(self.tokenizer.decode(chunk_ids, skip_special_tokens=True))
        return chunks

    def _extract_one(self, text: str, doc_id: str) -> tuple[dict | None, str]:
        prompt = self._chat(
            f"Document id: {doc_id}\n\n<document>\n{text}\n</document>\n\n"
            "Return the JSON object now."
        )
        inputs = self.tokenizer(
            [prompt], return_tensors="pt", truncation=True, max_length=self.max_doc_tokens + 2500
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        t0 = time.time()
        with torch.inference_mode():
            out = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        gen = out[0, inputs["input_ids"].shape[1] :]
        raw = self.tokenizer.decode(gen, skip_special_tokens=True)
        obj = safe_json(raw)
        if obj is None:
            obj = {"_parse_error": True, "_raw": raw[:2000], "_seconds": round(time.time() - t0, 1)}
        return obj, raw

    def extract(self, text: str, doc_id: str = "") -> tuple[dict | None, str]:
        chunks = self._split(text)
        merged = {
            f: {"status": "not_reported", "values": [], "absence_evidence": "no_chunk_reported"}
            for f in FIELD_NAMES
        }
        raws = []
        for i, chunk in enumerate(chunks):
            obj, raw = self._extract_one(chunk, f"{doc_id}#c{i}")
            raws.append(raw)
            if not isinstance(obj, dict) or obj.get("_parse_error"):
                continue
            for f in FIELD_NAMES:
                x = obj.get(f)
                if not isinstance(x, dict):
                    continue
                vals = x.get("values") or []
                if x.get("status") == "reported" and isinstance(vals, list) and vals:
                    merged[f]["status"] = "reported"
                    merged[f]["values"].extend([v for v in vals if isinstance(v, dict)])
                elif merged[f]["status"] != "reported" and x.get("status") == "not_applicable":
                    merged[f]["status"] = "not_applicable"
        for f in FIELD_NAMES:
            if merged[f]["status"] == "reported":
                merged[f]["absence_evidence"] = None
        return merged, "\n---CHUNK---\n".join(raws)

    def empty(self) -> dict:
        return {
            f: {"status": "not_reported", "values": [], "absence_evidence": "llm_empty"}
            for f in FIELD_NAMES
        }
