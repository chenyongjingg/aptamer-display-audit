"""Paper-level 5-fold splits with leakage checks."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path


def make_splits(papers: list[dict], folds: int = 5, seed: int = 0) -> dict:
    # group by paper_id, stratify by has_fulltext and year bin
    groups = {}
    for p in papers:
        pid = p.get("paper_id")
        if not pid:
            continue
        year = str(p.get("year") or "")
        try:
            ybin = "2024+" if int(year[:4]) >= 2024 else "pre2024"
        except Exception:
            ybin = "unknown"
        key = (bool(p.get("has_fulltext")), ybin)
        groups.setdefault(key, []).append(pid)
    rng = random.Random(seed)
    assignment = {}
    for key, pids in groups.items():
        pids = sorted(set(pids))
        rng.shuffle(pids)
        for i, pid in enumerate(pids):
            assignment[pid] = i % folds
    # leakage checks
    train_test_overlap = 0
    for k in range(folds):
        train = {p for p, f in assignment.items() if f != k}
        test = {p for p, f in assignment.items() if f == k}
        train_test_overlap += len(train & test)
    return {
        "folds": folds,
        "seed": seed,
        "assignment": assignment,
        "fold_sizes": {str(k): sum(1 for v in assignment.values() if v == k) for k in range(folds)},
        "leakage_train_test_paper_overlap": train_test_overlap,
        "strata": {str(k): len(v) for k, v in groups.items()},
    }


def write_splits(splits: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(splits, ensure_ascii=False, indent=2), encoding="utf-8")
