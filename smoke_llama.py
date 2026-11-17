import sys, json, time, gc
sys.path.insert(0, "/root/faudit")
from pipeline.common import load_jsonl
from pipeline.llm import LLM
docs = load_jsonl("/root/faudit/docs.jsonl")
d = [x for x in docs if x["level"] == "abstract" and x.get("text_kind") == "abstract"][0]
for name, path in [("llama", "/model/ModelScope/LLM-Research/Meta-Llama-3.1-8B-Instruct"),
                   ("ministral", "/model/ModelScope/AI-ModelScope/Ministral-8B-Instruct-2410")]:
    t0 = time.time(); llm = LLM(path, load_in_4bit=True); print(name, "load", round(time.time()-t0,1), flush=True)
    t0 = time.time(); obj, raw = llm.extract(d["text"], d["doc_id"]); print(name, "gen", round(time.time()-t0,1), flush=True)
    print(name, "keys", list(obj.keys())[:8] if isinstance(obj, dict) else type(obj), flush=True)
    print(name, "raw", (raw or "")[:300].replace("\n", " "), flush=True)
    del llm; gc.collect(); 
    import torch; torch.cuda.empty_cache()
