import hashlib, json
from pathlib import Path
files = ["protocol.md", "prompts/p2.md", "configs/full_auto.yaml"]
h = {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}
p = json.loads(Path("prereg.example.json").read_text())
p["hashes"] = h
Path("prereg.json").write_text(json.dumps(p, indent=2))
print(json.dumps(h, indent=2))
