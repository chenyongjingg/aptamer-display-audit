# Human-adjudicated label cleaning (2026-11-18)

This document supersedes the headline numbers in `CONFIRMATORY_RESULTS.md` for the manuscript. The raw confirmatory run remains archived; the cleaned analysis is the manuscript's analysis set.

## What was audited

- 50 instances from the frozen `silver_v2`: 33 positives (Tier 1/2/3 = 20/8/5) and 17 high-confidence absences (7/6/4).
- One author without clinical training, blind to silver labels, using written field definitions.
- For positives: status, value + unit, and whether a verbatim sentence contains the value.

## Agreement before cleaning

| Metric | Result |
|---|---|
| Status agreement | 36/50 = 72.0% (κ = 0.480) |
| Positive agreement (status + value + quote) | 18/33 = 54.5% (95% CI 38.0–70.2) |
| Absence agreement | 17/17 = 100% |

Most disagreements were silver labels that stored qualitative strings (`significant`, `high`), wrong-field values (payload per particle, sequence length) or fold changes. Two values were corrected (valency 1→4; serum stability 800-fold→72 h).

## Cleaning

- 59 non-conforming values removed; positives 206 → 147.
- High-confidence field instances 1,390 (85.2%) → 1,445 (88.5%).
- Tier coverage 91.8 / 88.1 / 77.0.

## Recomputed metrics

| System | Value set-F1 (95% CI) | Presence | Quote |
|---|---|---|---|
| E0 rules | 0.382 (0.293–0.499) | 0.987 | 1.000 |
| E1 Qwen2.5-7B zero-shot | 0.048 (0.015–0.092) | 0.967 | 0.600 |
| HYBRID | 0.415 (0.317–0.543) | 0.976 | 1.000 |

Paired: HYBRID−E0 +0.034 (0.004–0.081); HYBRID−E1 +0.380 (0.272–0.487).
Stratified: full texts 0.646 vs abstracts 0.266.
Tier 1/2/3: 0.497 / 0.162 / 0.590; Tier1−Tier2 +0.335 (0.143–0.556), opposite to the pre-registered direction.
Cross-family (40 docs): Qwen zero-shot 0.070 vs Ministral 0.218; hybrid 0.415 vs 0.485 (presence 0.976 vs 0.851).

## Interpretation

The anchor is a cleaning instrument, not a gold standard. The manuscript reports the raw 54.5% positive agreement, the single non-clinician reviewer, and the fact that value-F1 is agreement with a cleaned machine consensus rather than accuracy against expert truth.

Machine-readable: `results/cleaned_20261118.json`, `results/cleaned_20261118_full.json`.
