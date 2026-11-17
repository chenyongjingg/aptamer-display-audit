import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
p = "/model/ModelScope/Qwen/Qwen2.5-0.5B-Instruct"
tok = AutoTokenizer.from_pretrained(p, trust_remote_code=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16)
m = AutoModelForCausalLM.from_pretrained(p, quantization_config=bnb, device_map="auto", trust_remote_code=True)
msgs = [{"role": "user", "content": 'Reply with JSON {"ok": true}'}]
text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
inp = tok([text], return_tensors="pt").to(m.device)
out = m.generate(**inp, max_new_tokens=20, do_sample=False)
print(tok.decode(out[0, inp["input_ids"].shape[1]:], skip_special_tokens=True))
print("ok", round(torch.cuda.memory_allocated()/1e9, 2))
