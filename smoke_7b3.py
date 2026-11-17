import sys, json
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.llm import LLM
docs = load_jsonl("data/docs.jsonl")
d = [x for x in docs if x["doc_id"] == "S24_full"][0]
ev = LLM("/model/ModelScope/Qwen/Qwen2.5-7B-Instruct", load_in_4bit=True,
         adapter_path="runs/train_7b_pos/adapter")
obj, raw = ev.extract(d["text"], d["doc_id"])
print("RAW", raw[:1000])
print("PARSED", json.dumps(obj, ensure_ascii=False)[:800] if isinstance(obj, dict) else type(obj))
