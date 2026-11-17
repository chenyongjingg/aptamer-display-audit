import sys, json, time
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.llm import LLM
docs = load_jsonl("/root/faudit/docs.jsonl")
d = [x for x in docs if x["level"] == "full"][0]
t0 = time.time()
llm = LLM("/model/ModelScope/Qwen/Qwen3-8B", load_in_4bit=True)
print("load", round(time.time()-t0,1), "s", flush=True)
t0 = time.time()
obj, raw = llm.extract(d["text"], d["doc_id"])
print("gen", round(time.time()-t0,1), "s", flush=True)
print("keys", list(obj.keys())[:20] if isinstance(obj, dict) else type(obj))
print(json.dumps(obj, ensure_ascii=False)[:2000])
