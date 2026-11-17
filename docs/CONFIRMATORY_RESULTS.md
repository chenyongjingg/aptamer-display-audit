# Confirmatory results — 2026-11-17

Both confirmatory runs were frozen **before** inference and passed the S0
pre-registration hash gate. Aggregate metrics only; no publisher text.

- `prereg_zs_20261117` — E0 rules + E1 zero-shot (`prereg.json`, `configs/prereg_zs.yaml`)
- `hybrid_confirm` — hybrid rules + field-level LLM (`prereg_or.json`, `configs/prereg_or.yaml`)
- `or_confirm` — metrics over all three systems, temporal subsets, AutoPK reference

## Primary endpoint

Value set-F1 on high+medium reported fields; 102 documents (82 abstracts + 20 full
texts), 204 high+medium positive field instances, frozen `silver_v2`.

| System | presence macro-F1 | **value-F1** | quote valid | coverage high |
|---|---|---|---|---|
| E0 rules | 0.9979 | **0.3969** | 1.0000 | 0.8517 |
| E1 Qwen2.5-7B zero-shot | 0.9750 | **0.0298** | 0.6000 | 0.8517 |
| HYBRID (rules + field-level LLM) | 0.9903 | **0.4181** | 1.0000 | 0.8517 |

`n_high_fields` = 1,390 (16 fields × 102 documents, high-confidence silver subset).

## Temporal subsets

| System | 2025+ (n=25) | pre-2025 (n=77) |
|---|---|---|
| E1 zero-shot | 0.0249 | 0.0306 |
| HYBRID | 0.4027 | 0.4653 |

The ranking (hybrid ≫ rules ≫ zero-shot) is unchanged across the temporal split;
the hybrid gap between periods is within the expected sampling noise for n=25.

## Tier value-F1 and the pre-registered H4

Field-level value-F1 averaged within tier (fields with at least one high+medium
positive instance):

| Tier | Fields | E0 rules | E1 zero-shot | HYBRID |
|---|---|---|---|---|
| 1 — PK | 8 | 0.4176 | 0.0283 | 0.4409 |
| 2 — design | 4 | 0.2743 | 0.0250 | 0.2868 |
| 3 — comparator/immune | 2 | 0.5593 | 0.0455 | 0.5896 |

H4 predicted Tier-1 (PK) < Tier-2 (design). The observed direction is the
**opposite** (0.441 > 0.287): **H4 is falsified**. Per-field detail (HYBRID):
`time_points` 0.813 (19 docs), `route` 0.682 (22), `kd` 0.667 (3), `half_life`
0.500 (2), `dose` 0.452 (9), `serum_stability` 0.231 (13), `numeric_efficacy`
0.183 (31), `id_per_g` 0.000 (2); `size` 0.588 (17), `valency` 0.559 (40),
`linker_chemistry` 0.000 (2), `attachment` 0.000 (12); `immune` 0.788 (11),
`comparator` 0.391 (23).

## Hypothesis adjudication

| Hypothesis | Pre-specified | Observed | Verdict |
|---|---|---|---|
| H1 | zero-shot value-F1 < 0.10 | 0.0298 | supported |
| H2 | hybrid > 0.30 and > zero-shot | 0.4181 | supported |
| H3 | hybrid ≥ rules (non-inferior) | 0.4181 ≥ 0.3969 | supported |
| H4 | Tier-1 < Tier-2 | 0.4409 > 0.2868 | **falsified** |
| secondary | presence > 0.90 | 0.9903 | supported |

Falsifying H4 is reported as a result, not repaired post hoc. The tier labels
were fixed in `protocol.md` before the run; Tier-2 has only four fields and
`attachment`/`linker_chemistry` contribute two positive documents each, so the
Tier-2 estimate is fragile — but the pre-registered direction is what it is.

## External comparator (not rerun)

AutoPK (IEEE ICTAI 2025, doi:10.1109/ICTAI66417.2025.00051) reports human-labeled
table F1 0.92 (half-life) and 0.91 (clearance) on 605 tables. The 605 annotated
tables are **not publicly released** (the repository provides DOIs and code, not
tables/labels). The 100-table anchor therefore **cannot be rerun** without the
authors' data or new annotation, which this project does not perform. The
published metrics are cited as a task-level comparator only: structured PK tables
are near-solved; narrative preclinical text with conditionals and absence is
harder. No head-to-head claim is made.

## What is not in the confirmatory set

- Field-level verifier: exploratory, 5 documents, degraded value-F1 0.696 → 0.535.
- 7B QLoRA: exploratory negative (collapsed to absence); adapters archived;
  not bitwise reproducible (seed patch landed after the archived run).
- These are reported in `AUDIT_SUMMARY.md` and `results/value_experiments.json`.

## Artifacts

- `results/confirmatory_20261117.json` — machine-readable aggregate (this document).
- `results/value_experiments.json` — exploratory + confirmatory, side by side.
- Run directories (`runs/prereg_zs_20261117`, `runs/hybrid_confirm`, `runs/or_confirm`)
  are in the local snapshot; the public repo carries aggregates and manifests only.
