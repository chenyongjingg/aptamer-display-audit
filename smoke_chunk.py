import sys, time
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.llm import LLM
docs = load_jsonl("/root/faudit/docs.jsonl")
d = [x for x in docs if x["level"] == "full"][0]
llm = LLM("/model/ModelScope/LLM-Research/Meta-Llama-3.1-8B-Instruct", load_in_4bit=True)
chunks = llm._split(d["text"])
print("chars", len(d["text"]), "chunks", len(chunks), flush=True)
t0 = time.time()
obj, raw = llm.extract(d["text"], d["doc_id"])
print("total_s", round(time.time()-t0,1), "keys", len(obj) if isinstance(obj, dict) else None, flush=True)
print(str(obj)[:500], flush=True)
