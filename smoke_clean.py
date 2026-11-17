import sys, subprocess, json
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.llm import LLM
from pipeline.silver import norm_source

cmd = [sys.executable, "train_qlora.py", "--docs", "data/docs.jsonl",
       "--silver", "runs/smoke2/audit/silver_v2.jsonl", "--out", "runs/train_clean",
       "--model", "/model/ModelScope/Qwen/Qwen2.5-0.5B-Instruct", "--epochs", "1",
       "--splits", "runs/smoke2/audit/splits.json", "--fold", "0", "--limit-docs", "5"]
print("train rc", subprocess.run(cmd, cwd="/root/faudit").returncode)
docs = load_jsonl("data/docs.jsonl")
d = [x for x in docs if x["doc_id"] == "S0_full"][0]
ev = LLM("/model/ModelScope/Qwen/Qwen2.5-0.5B-Instruct", load_in_4bit=True,
         adapter_path="runs/train_clean/adapter")
obj, raw = ev.extract(d["text"], d["doc_id"])
print("RAW", raw[:1200])
print("PARSED", json.dumps(obj, ensure_ascii=False)[:800] if isinstance(obj, dict) else type(obj))
