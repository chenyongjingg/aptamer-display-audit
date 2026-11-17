"""Q5 stability: same model, paraphrased p2 prompt."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import pipeline.llm as pll

PARA = (ROOT / "prompts" / "p2_paraphrase.md").read_text(encoding="utf-8")
pll._prompt = lambda: PARA

import run_zs_eval

if __name__ == "__main__":
    sys.argv = [sys.argv[0]] + sys.argv[1:]
    raise SystemExit(run_zs_eval.main())
