"""Document-level QLoRA on high-confidence consensus silver.

One example per document. The target contains only high-confidence fields; the
prompt is the same 16-field audit prompt used at inference. This keeps training
and inference formats aligned (no field-conditioned mismatch).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

from pipeline.common import FIELD_NAMES, load_jsonl

SYSTEM = Path(__file__).resolve().parent / "prompts" / "p2.md"


def split_tokens(text: str, tok, max_tokens: int = 2500) -> list[str]:
    ids = tok(text or "", add_special_tokens=False).input_ids
    out = []
    step = max_tokens - 200
    for i in range(0, len(ids), step):
        out.append(tok.decode(ids[i : i + max_tokens], skip_special_tokens=True))
    return out or [""]


def build_examples(docs, silver, tok, limit_docs=None, positive_only=False):
    smap = {r["doc_id"]: r for r in silver}
    rows = []
    for d in docs:
        s = smap.get(d["doc_id"])
        if not s:
            continue
        high = {}
        for f in FIELD_NAMES:
            x = s["fields"].get(f, {})
            if x.get("confidence") != "high":
                continue
            vals = []
            for v in x.get("values", []):
                if not isinstance(v, dict):
                    continue
                vals.append({"value": v.get("value"), "unit": v.get("unit", ""),
                             "quote": v.get("quote", ""), "context": v.get("context", {})})
            high[f] = {"status": x.get("status"), "values": vals,
                       "absence_evidence": "not_reported" if x.get("status") != "reported" else None}
        if positive_only:
            high = {f: x for f, x in high.items() if x.get("status") == "reported" and x.get("values")}
        if len(high) < 1:
            continue
        chunks = split_tokens(d.get("text", ""), tok)
        quotes = " ".join(str(v.get("quote", "")) for x in high.values() for v in x.get("values", []))
        best, best_score = chunks[0], -1
        for c in chunks:
            score = len(set(quotes.lower().split()) & set(c.lower().split()))
            if score > best_score:
                best, best_score = c, score
        rows.append({"text": best, "target": json.dumps(high, ensure_ascii=False),
                     "paper_id": d.get("paper_id")})
        if limit_docs and len(rows) >= limit_docs:
            break
    return rows


class DS(torch.utils.data.Dataset):
    def __init__(self, rows, tok, max_len=4096):
        self.rows, self.tok, self.max_len = rows, tok, max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        system = SYSTEM.read_text(encoding="utf-8")
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": r["text"] + "\n\nReturn the JSON object now."}]
        prompt = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        full = prompt + r["target"] + self.tok.eos_token
        enc = self.tok(full, truncation=True, max_length=self.max_len, add_special_tokens=False)
        plen = len(self.tok(prompt, truncation=True, max_length=self.max_len, add_special_tokens=False)["input_ids"])
        labels = list(enc["input_ids"])
        labels[:plen] = [-100] * plen
        if all(x == -100 for x in labels):
            labels[-min(128, len(labels)):] = enc["input_ids"][-min(128, len(labels)):]
        return {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"], "labels": labels}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs.jsonl")
    ap.add_argument("--silver", required=True)
    ap.add_argument("--out", default="runs/train")
    ap.add_argument("--model", default="/model/ModelScope/Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--limit-docs", type=int, default=None)
    ap.add_argument("--positive-only", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--splits", default=None)
    ap.add_argument("--fold", type=int, default=None)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    docs = load_jsonl(args.docs)
    silver = load_jsonl(args.silver)
    if args.splits and args.fold is not None:
        sp = json.loads(Path(args.splits).read_text(encoding="utf-8"))
        train_papers = {p for p, f in sp["assignment"].items() if f != args.fold}
        docs = [d for d in docs if d.get("paper_id") in train_papers]
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    rows = build_examples(docs, silver, tok, args.limit_docs, args.positive_only)
    rng = random.Random(0); rng.shuffle(rows)
    papers = sorted({r["paper_id"] for r in rows})
    if args.splits and args.fold is not None:
        sp = json.loads(Path(args.splits).read_text(encoding="utf-8"))
        val_papers = {p for p, f in sp["assignment"].items() if f == args.fold}
        train = [r for r in rows if r["paper_id"] not in val_papers]
        val = []
    else:
        val_papers = set(papers[: max(1, len(papers) // 5)])
        train = [r for r in rows if r["paper_id"] not in val_papers]
        val = [r for r in rows if r["paper_id"] in val_papers]
    print(f"document examples train={len(train)} val={len(val)} papers={len(papers)}", flush=True)
    (out / "train_manifest.json").write_text(json.dumps({
        "model": args.model, "n_train": len(train), "n_val": len(val),
        "val_papers": sorted(val_papers), "format": "document-level 16-field",
        "positive_only": args.positive_only,
        "fold": args.fold, "splits": args.splits,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb,
                                                 device_map="auto", trust_remote_code=True)
    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable()
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    targs = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        bf16=True,
        logging_steps=5,
        save_strategy="epoch",
        eval_strategy="no",
        report_to=[],
        remove_unused_columns=False,
        dataloader_pin_memory=False,
        seed=args.seed,
        data_seed=args.seed,
    )
    trainer = Trainer(
        model=model, args=targs, train_dataset=DS(train, tok), eval_dataset=None,
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
    )
    trainer.train()
    model.save_pretrained(out / "adapter")
    tok.save_pretrained(out / "adapter")
    (out / "train_result.json").write_text(json.dumps(trainer.state.log_history, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
