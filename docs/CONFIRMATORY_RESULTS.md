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
**opposite** (0.441 > 0.287), so the pre-registered direction is **not supported**.
The paired tier difference is +0.154 with 95% CI [-0.031, 0.313] (p≈0.11), so the
data do **not** establish a tier gradient in either direction. Per-field detail (HYBRID):
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
| H4 | Tier-1 < Tier-2 | 0.4409 > 0.2868; Δ CI [-0.031, 0.313] | **not supported** |
| secondary | presence > 0.90 | 0.9903 | supported |

The failed pre-registered prediction is reported as a result, not repaired post hoc. The tier labels
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

## Robustness analyses (post-confirmatory, not pre-registered)

Run after the confirmatory freeze; reported as robustness, not as pre-registered
tests. Machine-readable: `results/robustness_20261117.json`.

### Uncertainty and paired comparisons (2000 document-level bootstrap)

| Quantity | Estimate | 95% CI |
|---|---|---|
| HYBRID value-F1 | 0.418 | [0.319, 0.525] |
| E0 rules | 0.397 | [0.297, 0.499] |
| E1 zero-shot | 0.030 | [0.012, 0.055] |
| HYBRID − E0 | +0.0217 | [0.0052, 0.0418] (p≈0.005) |
| HYBRID − E1 | +0.393 | [0.290, 0.488] |

The hybrid gain over rules is small, but its paired CI excludes zero.

### Silver leave-one-source-out

| Silver variant | E0 | E1 | HYBRID | coverage high |
|---|---|---|---|---|
| full (rules + Llama + Ministral where sampled) | 0.397 | 0.030 | 0.418 | 0.852 |
| drop Ministral (rules + Llama) | 0.423 | 0.028 | 0.442 | 0.847 |
| rules + Ministral only (B-sample subset) | 0.683 | 0.070 | 0.706 | 0.676 (subset) |

The ranking is unchanged; absolute values move with the label definition. The
B-only subset scores higher because consensus keeps only values both sources
support, so its positives are easier.

### Stratification

| Subset | E0 | E1 | HYBRID |
|---|---|---|---|
| abstracts (n=82) | 0.222 | 0.027 | 0.250 |
| full texts (n=20) | 0.657 | 0.044 | 0.669 |
| pre-2025 (n=77) | 0.449 | 0.031 | 0.465 |
| 2025+ (n=25) | 0.376 | 0.025 | 0.403 |

The instrument is far better on full texts. On abstracts — where the companion
review found Kd 0/82 and %ID/g 0/82 — even the hybrid reaches only 0.250; this
is the empirical boundary the paper should foreground.

### Cross-family replication

Zero-shot on a fixed 40-document subset (all 20 full texts + every fourth
abstract by doc_id), same prompt:

| Model | value-F1 | presence | quote valid |
|---|---|---|---|
| Qwen2.5-7B | 0.039 | 0.946 | 0.571 |
| Ministral-8B-Instruct-2410 | **0.251** | 0.943 | 0.750 |

Hybrid on all 102 documents:

| Model | value-F1 | presence | quote valid |
|---|---|---|---|
| Qwen2.5-7B | 0.418 | 0.990 | 1.000 |
| Ministral-8B | **0.487** | 0.869 | 1.000 |

Ministral hybrid on the 90 documents outside the silver-B sample is 0.530.
The 0.030 zero-shot figure is therefore a **Qwen2.5-7B-specific** result, not a
general property of zero-shot LLMs. Value extraction and absence detection
dissociate across models: Ministral extracts more values but over-reports
presence (0.869 vs 0.990), so neither model dominates both tasks.

### Prompt stability (Q5)

Paraphrased prompts, same documents and decoding:

| System | original | paraphrase | Δ |
|---|---|---|---|
| HYBRID (102 docs) | 0.418 | 0.414 | −0.004 |
| E1 zero-shot (40 docs) | 0.039 | 0.045 | +0.006 |

Both systems are insensitive to prompt wording at this effect size (|Δ| ≤ 0.006).

### Failure taxonomy (counts over eligible fields)

| Class | E0 rules | E1 zero-shot | HYBRID |
|---|---|---|---|
| false_absence | 103 | 164 | 93 |
| fabrication | 0 | 17 | 0 |
| absence_contradiction | 0 | 20 | 11 |
| wrong_value | 0 | 18 | 4 |
| multi_value | 29 | 0 | 30 |
| context_missing | 0 | 0 | 1 |

This supports H3: zero-shot errors are dominated by false absence and
fabrication, not by wrong values. The hybrid removes fabrication entirely (quote
gate) but leaves multi-value omissions.

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
