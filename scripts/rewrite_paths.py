"""Rewrite /root/faudit paths in archived JSON files to a new root (optional)."""
import sys
from pathlib import Path
old = sys.argv[1] if len(sys.argv) > 1 else "/root/faudit"
new = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).resolve().parent.parent)
for p in Path(new).rglob("*.json"):
    if "/.git/" in str(p) or "/adapter/" in str(p):
        continue
    try:
        s = p.read_text(encoding="utf-8")
    except Exception:
        continue
    if old not in s:
        continue
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("rewrote", p)
