# 流水线 vs 计划书 v3：科学一致性审查

> 审查对象：`/root/faudit/` 实际代码与 `runs/full`、`runs/smoke2` 产物；对照 `研究计划书_v3_银标准.md`。
> 结论先行：**旧 `runs/full` 是 pre-audit pilot；新的 `runs/full_auto` 已由 `run_pipeline.py` 全自动驱动 S0–S9，正在跑。**它有真实银标准、真实模型输出、真实指标，但主终点、五折、训练/Verifier、Q5–Q7、污染探针尚未全部落地。下面逐项列出，已修的写“已修”，未修的写“未实现”，不把 stub 说成完成。

## 1. 审查方法

- 逐行读 `pipeline/{common,rules,llm,silver,metrics}.py`、`run_pilot.py`；对照计划书 §3–§10。
- 读 `runs/smoke2/` 的 `silver_v1.0.jsonl`、`silver_sources.jsonl`、`pred_eval.jsonl`、`metrics_eval.json`。
- 用新写的 `posthoc_audit.py` 在 smoke2 上重算，验证修复路径。
- 未使用人工标注；所有判断可追到文件与行号/产物。

## 2. 逐项一致性表

| # | 计划书要求 | 实现状态 | 证据 | 处置 |
|---|---|---|---|---|
| 1 | 82 摘要 + 24–28 全文 | **目标不可达**：82 摘要 + **20** 全文；4 个本地 PDF 是错误页（pypdf `invalid pdf header`），4 个未取回 | `docs.jsonl` 102 行；`refs/pdf/*.pdf` 探测 | 计划书已按实测改为 20；不再声称 24–28 |
| 2 | 银标准四源：规则 + Llama + Ministral + 综述抽取 X | **部分**：full run 只用了 R/A/B；X 只在 `reconsensus.py` 中实现 | `silver_sources.jsonl` 无 review 源；`reconsensus.load_review_extraction` | 已修代码；full run 后需用 X 重算 |
| 3 | ≥2 源一致才算 high | **已实现** | `silver.consensus_field`；`reconsensus.consensus_doc` | — |
| 4 | 多值集合表决 | **v1 不一致**：`_agree_values` 会丢掉第二源独有的值 | `silver.py:_agree_values` | **已修**：`reconsensus._cluster_values` 按 support 聚类，保留全部高支持值 |
| 5 | 条件元组（buffer/温度/方法/时间点/路线） | **v1 不一致**：共识与指标都忽略 context | `silver.py`；`metrics.value_scores` | **已修**：`_merge_context` + `audit_metrics._context_match`，报 `context_f1` |
| 6 | 逐字 quote 门 | **已实现**；分块后改用块并集 | `silver._validate_source`；`common.quote_valid` | **已修**：增加 `quote_valid_relaxed`（骨架匹配），同时报 exact 与 skeleton |
| 7 | 缺席门 + 否定句拦截 | **部分**：缺席门有；否定句无 | `consensus_field`；`common.is_negated` | **已修**：`is_negated` 接入 silver/reconsensus；结构化 absence_evidence |
| 8 | QA Q1–Q8 | **部分**：Q1–Q4/Q8 已实现；**Q5/Q6/Q7 未跑**（代码 `qa_extra.py`） | `silver_qa`；`reconsensus.qa_v2` | Q3/Q4 已修；Q5–Q7 未实现，状态必须写 `not_run` |
| 9 | 16 字段 | **已实现** | `common.FIELDS` | — |
| 10 | T1 三分类 macro-F1 | **已实现**；但 full run 的 `metrics_eval` 用了全部字段 | `metrics.field_presence` | **已修**：`audit_metrics.evaluate_v2(confidence="high")`；主分析只看 high |
| 11 | T2 集合 F1 + 条件 | **v1 不一致**：只比 value/unit，忽略 context；多值只算单值命中 | `metrics.value_scores` | **已修**：`audit_metrics.value_scores` 集合匹配 + `context_f1` |
| 12 | T3 quote 合法率 / 幻觉率 | **已实现**；但 exact 会受分块解码空白影响 | `metrics.evaluate` | **已修**：exact + skeleton 两列并报 |
| 13 | T4 缺席理由 Jaccard | **未实现** | — | **已修**：`failure.analyze` 报 `absence_jaccard_mean` |
| 14 | 5 折论文级交叉验证 | **已实现协议**：S5 每折训练、S6 每折 OOF 推理、S8 逐折 OOF；smoke2 单折验证 | `run_pipeline.py` S5/S6/S8；`train_qlora.py --fold` | full_auto 将跑 5 折 7B |
| 15 | E0–E9 实验矩阵 | **E0/E1/E4/E7 可跑**（smoke2 验证）；E2/E3/E8/E9 未跑 | `run_pipeline.py` S5/S6/S7；smoke2 metrics | 14B/跨规模/商业 API 未接入 |
| 16 | Verifier 独立性 I0–I3 | **单一级已实现/验证**；四级因子未跑 | `verifier.py`；smoke2 `pred_verified.jsonl` | 需 I0/I1/I2/I3 四组对照 |
| 17 | 污染/记忆化 P1–P4 | **未跑**：代码 `probes.py` 已写 | — | 需模型重跑；当前 full run 占用 GPU |
| 18 | 失败模式 12 类自动编码 | **未实现** | — | **已修**：`failure.py` 确定性 12 类 + 例 |
| 19 | S0 预注册哈希闸门 | **已执行**：`full_auto` S0 done（hash match） | `runs/full_auto/manifest.json` | 旧 `runs/full` 仍标 pre-audit pilot |
| 20 | S3/S4/S8/S9 | **已实现并有 orchestrator**：S3 splits、S4 prompt sha、S8 high/OOF/失败分类、S9 checksums | `run_pipeline.py`；smoke2 已验证 | — |
| 21 | S5 QLoRA 训练 | **per-fold 已接入**：每折一个 adapter，训练只用该折训练论文 | `run_pipeline.py` S5；`train_qlora.py --splits/--fold` | 0.5B smoke；7B 由 full_auto 执行 |
| 22 | S7 独立 Verifier | **orchestrator 已接入，full_auto 将自动跑** | `run_pipeline.py` S7；`verifier.py` | 待 full_auto 执行；失败会标 failed |
| 23 | 发布许可分层 | **未实现** | — | S9 release 只含标注/指标/报告，不含出版商文本；正式发布包未做 |
| 24 | 自动化后台 + 状态 | **部分**：setsid 后台；status 只有 start/silver_done/done | `run_pilot.write_status` | 未修：缺每 stage 心跳；可加 |

## 3. 关键科学问题（按严重度）

### P0：full run 的“主终点”不是计划书的主终点

计划书 §3.2/§8.1 规定主分析只用 **high-confidence 银标准**；`run_pilot.py` 的 `metrics_eval.json` 在全部字段上算，且银标准 v1 的 consensus 会丢多值、忽略 context。**因此 `metrics_eval.json` 不能当论文主结果**。

另一个已修问题：第一次 run 的严格 quote 门在写 `silver_sources.jsonl` 前丢掉了部分分块解码造成的空白差异值。`posthoc_audit.py --rebuild-cache` 从 `runs/*/cache/*.json` 的原始模型输出重建 sources，再由 `reconsensus` 用 relaxed 门复核；smoke2 已重建 102 行（有 cache 的文档）。

已修：`audit_metrics.evaluate_v2(confidence="high")` 在 smoke2 上给出（2 文档；5 折 OOF：规则 0.950、Qwen2.5-7B 0.835）：

| 系统 | 置信度 | macro-F1 | 覆盖 | Tier-1 |
|---|---|---|---|---|
| 规则 | high | 0.964 | 0.719 | 见 `runs/smoke2/audit/audit_metrics.json` |
| Qwen2.5-7B | high | 0.786 | 0.719 | 同上 |

（2 文档，仅验证路径；不是科学结论。）

### P1：银标准 v1 的多值与 context 缺陷

`silver._agree_values` 从第一源出发，只保留与第二源匹配的值；第二源独有的值被丢掉。对 Kd/%ID/g 这类天然多值字段，这会系统性低估。`context` 完全没进共识。已用 `reconsensus.py` 重算为 `silver_v2.jsonl`；full run 完成后必须用它重评。

### P1：S0 没有闸住 full run

`run_pilot.py` 没有检查 `prereg.json`。full run 在协议未冻结的情况下启动，这是流程违规。已加 `posthoc_audit` S0 校验；**full run 只能标为 pilot**。下一轮必须用带 S0 的入口启动。

### P2：训练/Verifier 只有代码，没有 full 结果

`train_qlora.py` 是真实训练器（0.5B smoke 通过，loss=2.07，adapter 已保存）；`verifier.py` 是真实 Verifier（待 smoke）。但 full run 的 E4/E7 没有跑，论文不能声称“微调/独立 Verifier 有效”。

### P2：QA Q5–Q7 未跑

Q5 稳定性、Q6 诱饵、Q7 外部 AutoPK 锚未实现/未跑。按计划书 §4.5，未跑必须写 `not_run`，不能写成 PASS。当前 `silver_qa_v2.json` 只覆盖 Q1–Q4/Q8。

### P3：8 篇出版商 PDF 未纳入

计划书 §4.1 目标 24–28 全文；当前 20。需 pypdf 解析 + 逐篇许可核。未做。

## 4. 已修改的文件

| 文件 | 修改 | 验证 |
|---|---|---|
| `pipeline/reconsensus.py` | 多值聚类、context 合并、结构化缺席证据、否定句、Q3/Q4/Q8、综述 X 源、manifest | smoke2 跑通，`silver_v2` 2 行 |
| `pipeline/audit_metrics.py` | high/medium/all 分层、Tier 1/2/3、context F1、集合 F1、coverage、doc all-or-nothing、exact/skeleton quote | smoke2 六组指标 |
| `pipeline/splits.py` | 5 折论文级、按 fulltext/year 分层、泄漏检查 | smoke2 `leakage=0` |
| `pipeline/failure.py` | 12 类确定性错误分类 + T4 Jaccard | smoke2：absence_contradiction 4、fabrication 1、Jaccard 0.5 |
| `pipeline/common.py` | `is_negated`、`quote_valid_relaxed`、skeleton | 单元手测 |
| `posthoc_audit.py` | S0/S2b/S3/S4/S8/S9、stages.json、release checksums | smoke2 `stages.json`：S0/S1/S2b/S3/S4/S6/S8/S9 done；S5/S7 not_run |
| `train_qlora.py` | 真实 field-conditioned QLoRA；0.5B smoke | adapter 已保存；7B 未跑 |
| `verifier.py` | 真实独立 Verifier（Qwen2.5-Coder-7B） | smoke 待跑 |

## 4.5 第二轮：全自动编排

新增 `run_pipeline.py`，把 S0–S9 串成无人值守流水线：

- S0 哈希闸门 → S1 语料 → S2a 银标准（缓存续跑）→ S2b 重建 sources + QA + 覆盖率闸门 → S3 5 折 splits → S4 prompt 哈希 → S5 QLoRA → S6 adapter 推理 → S7 Verifier → S8 high-confidence/5 折/失败分类 → S9 release checksums。
- `--detach` 后台启动；`manifest.json`/`status.json`/`logs/` 逐 stage 记录；失败标 `failed`，闸门标 `blocked`，不静默。
- 当前 `runs/full_auto`：S0/S1 done，S2a 复用 `runs/full/cache` 继续。
- 旧 `runs/full` 只作 cache 来源，不再引用其 `metrics_eval.json`。
- **5 折协议已修正**：S5 每折训练、S6 每折 OOF 推理、S8 逐折 OOF；此前的“一个模型训全部再算 OOF”是测试标签泄漏，已消除。
- 47 篇 cache 的银标准 high 覆盖实测约 **0.80**（Tier-1 0.801 / Tier-2 0.805 / Tier-3 0.670），S2b 的 0.40 闸门不会误拦。
- orchestrator 已在 smoke2 上验证 **S2b/S3/S4/S5/S6/S7/S8/S9**：S5 0.5B adapter 生成、S6 adapter 推理 2 篇、S7 Coder-7B 验证 1 篇、S8 输出 E0/E1/E4 与 5 折 OOF、S9 checksums。S0/S1/S2a 在 `full_auto` 中已跑/正在跑。

### 4.6 第二轮最严重发现：E4 的测试标签泄漏

旧 S5 只训练**一个** adapter，训练集包含全部论文；S8 再用 5 折 OOF 评测。这样 test fold 的银标准标签在训练时已经被模型看过，E4 的 OOF 数字是**泄漏后的**，不能作为泛化估计。

这不是“实现不完整”，而是**实现与计划书的 5 折协议直接矛盾**。已修：

- S5：`train_qlora.py --splits --fold k`，每折只用 `assignment != k` 的论文训练；5 个 adapter。
- S6：`adapter k` 只预测 fold k 的论文；汇总为 `pred_finetuned.jsonl` 的 OOF。
- S8：E4 的 5 折 OOF 与全量指标；E7 只覆盖 30 篇时，额外算 `E4_on_verified_subset` 做同集合比较。
- 结论：在 `full_auto` 跑完 5 折之前，**不得引用任何 E4/E7 数字**。

## 5. 当前运行状态

- `runs/full_auto`：`run_pipeline.py` 全自动跑 S0–S9；S0/S1 已过，S2a 正在复用 cache 继续。
- `runs/full`：旧 pilot，已停止；只作 cache 来源，**不是最终结果**。
- `runs/smoke2/audit/`：已用新指标重算，可作为“路径已验证”的证据，不能作为论文结果。
- `runs/train_smoke/`：0.5B QLoRA smoke，`train_loss 0.0` 是长度掩码问题的旧产物；已修 `max_len=4096`，待重跑确认 loss>0。
- `runs/smoke2/verified/`：Verifier smoke 若完成，会出现在此。

## 6. 必须做的下一步（按顺序）

1. 等 `runs/full` 完成；不要用 `metrics_eval.json` 当主结果。
2. 跑 `python3 posthoc_audit.py --run runs/full --out runs/full/audit`，得到 `silver_v2` + high-confidence 主指标 + 失败分类 + splits + release。
3. 检查 S0：若 `freeze_report.json` 失败，说明 full run 启动时的协议已变；full run 只能作 pilot。
4. 跑 7B `train_qlora.py`（full silver；1 epoch 先验），再跑 `verifier.py`（20 篇），用 `audit_metrics` 比较 E4/E7。
5. 补 Q5/Q6/Q7；Q7 若无 AutoPK 数据，写 `not_available`，不写 PASS。
6. 补 P1–P4 污染探针（至少 10 篇样本）。
7. 8 篇 PDF 解析，把全文从 20 提到 24–28。
8. 用带 S0/S3/S5/S7 的入口重跑正式 run；当前 `run_pilot.py` 只保留为 pilot 工具。

## 7. 一句话结论

**代码路径是真实的，但 full run 不是计划书的正式实验**：它是 pre-audit pilot。主终点、五折、训练、Verifier、Q5–Q7、污染探针、8 篇 PDF 都还没有完成；已修的部分（多值/context/高置信过滤/splits/失败分类/S0/S9）可以在 full run 完成后立即重算。把 `metrics_eval.json` 当论文结果，就是虚假实现；本文档明确禁止这一点。

## 8. full_auto 收口结果（2026-11-16 10:12Z）与致命问题

`full_auto` 的 S0–S9 全部 `done`，但**结果不能直接用**。我检查了 `audit_metrics.json` 和原始 `pred_finetuned.jsonl`，发现两个致命问题：

### 8.1 指标被“缺席”主导

| 系统 | macro-F1（presence） | value-F1 | quote(skeleton) | quote(exact) | high 覆盖 |
|---|---|---|---|---|---|
| E0 规则 | 0.998 | 0.571 | 1.000 | 1.000 | 0.850 |
| E1 zero-shot（30 篇） | 0.976 | **0.000** | 0.625 | 0.406 | 0.810 |
| E4 5 折 OOF | 0.990 | **0.000** | None | None | 0.850 |
| E7 verified | 0.985 | **0.000** | None | None | 0.838 |

presence macro-F1 高，是因为银标准里绝大多数字段是 `not_reported`；模型判“缺席”就能拿高分。**value-F1 = 0.0 才是这个任务的真问题**：模型没有抽出可比的值。把 0.99 写成“审计性能”是虚假实现。

### 8.2 E4 的原始输出不是干净的抽取

`pred_finetuned.jsonl` 的 `raw` 里出现 `confidence`、`provenance`、`context_complete` —— 这些是**银标准目标对象的元数据**，不是抽取结果。旧训练目标把整段 silver field 原样喂给模型，模型学会了复制/编造 provenance；加上 1400 token 截断，很多 JSON 解析失败，`fields` 全变成 `not_reported`。E4 的 0.990 是“全判缺席”的假高分。

### 8.3 已做的修复

- `train_qlora.py`：训练目标只保留 `{status, values[{value,unit,quote,context}], absence_evidence}`，去掉 confidence/provenance/context_complete/n_values/conflicting_sources。
- `LLM` 推理 `max_new_tokens` 从 900 提到 1200。
- `common.values_match` 增加英文数词归一（“three” ↔ 3），修 valency 这类 word/number 不匹配。
- 5 折防泄漏已实现：S5 每折只用训练论文，S6 每折 OOF。

### 8.4 还没解决的科学问题

- **主终点选错**：presence macro-F1 在“缺席主导”的语料上会饱和；应改为 **value set-F1（或 value+context F1）为主、presence 为次**，否则论文会报一个 0.99 的假象。
- **0.5B clean-target smoke 仍会输出 schema 片段**（如 value=`nM/uM`、quote 空）；7B 是否学会干净抽取，必须重跑 S5–S9 才能知道。
- **E1 value-F1=0** 不全是格式问题：需要逐字段对一对，确认是 unit/value 解析还是模型真抽错。
- Q5–Q7、P1–P4、E2/E3/E8/E9、Verifier I0–I3 仍未接入。

### 8.5 结论

**当前 full_auto 的 S0–S9 自动化是成功的；科学结果是不成立的。** 在 S5–S9 用 clean target 重跑、并把主终点改成 value-F1 之前，不得引用 0.99/0.976/0.990/0.985 作为论文结果。

## 9. 点火结果：QLoRA 在当前语料上不可行，改点 zero-shot + Verifier

### 9.1 7B clean-target 诊断

- full silver 的 fold0 训练集只有 **9 个含 positive high 字段的文档**（positive-only 模式）；非 positive 模式 ~65 个，但绝大多数字段是 `not_reported`。
- 7B QLoRA（40 例、1 epoch）在 S0_abs 输出合法 JSON 但全 `not_reported`；在 S24_full（金标准 Kd=28 nM）仍全 `not_reported`。
- positive-only 9 例 adapter 输出**丢了字段键**（只输出 `{"status":"reported","values":[...]}`），`norm_source` 无法按键取值。
- 结论：**在 102 文档 / 5 折 / 每折 ~50–65 例的规模上，7B QLoRA 学不到值抽取；继续跑 5 折只会得到“全判缺席”的 0.99 假高分。**

### 9.2 已点火：zero-shot + Verifier

- `full_auto` 的 S0–S4 已完成，银标准 `silver_v2`、splits、prompt 哈希都在。
- 现用 `configs/full_zeroshot.yaml`：`train.enabled=false`，S6 用 Qwen2.5-7B zero-shot 跑 102 文档，写 `pred_zero_shot.jsonl`；S7 用 Coder-7B 验证 30 篇；S8 报 E0/E1/E7，主终点 value-F1。
- 当前 PID `96078`，stage `S6_infer`，fold 0/5。
- QLoRA 不删：保留为 **exploratory / negative result**；论文若报 E4，必须报 value-F1 与“全判缺席”的失败模式，不能报 presence 0.99。

### 9.3 主终点已改

`研究计划书_v3_银标准.md` §3.2/§5.1/§8.1 已把主终点从 presence macro-F1 改为 **T2 value set-F1（high-confidence reported）**；presence 只作次要。原因是 presence 在缺席主导语料上会饱和。

## 10. 最新收口（2026-11-17 00:57Z）

- `full_auto` 的 zero-shot 路径 S6 已完成（102 文档），S7 verifier 因 30 篇全文本太慢被手动停止，S8 已用新的 **high+medium 正例** 重算。
- 最终可用数字：
  - **E0 规则**：presence 0.998，**value-F1 0.571**，quote 1.000，coverage 0.850。
  - **E1 zero-shot**：presence 0.975，**value-F1 0.029**，quote 0.600（exact 0.440），coverage 0.850。
  - **E4 QLoRA**：失效（全判缺席），已归档 `audit_qlora_broken/`，不作结果。
  - **E7 Verifier**：未完成（30 篇全文本太慢，被停止）；不报数字。
- **关键发现**：high-confidence 的 **reported** 字段实例只有 **13**；high+medium reported 为 **204**。主终点已改为 high+medium 正例上的 value-F1，high-only 作敏感性；否则 n=13 没有统计意义。
- **科学结论（初步）**：这个任务上“判缺席”很容易（presence≈0.98），**抽值很难**（value-F1≈0.03）。这正好支撑论文的 “Auditing What Is Absent” 框架：审计仪器能做的是缺席审计，不是自动值抽取。不要把 presence 0.98 写成抽取性能。

## 11. 第二轮修复：两阶段值抽取与 Verifier 5 篇可行性

### 11.1 两阶段值抽取（item 2）

`value_extract.py`：先按字段关键词抽候选句（每条字段 ≤3 句），再用 Qwen2.5-7B 做**字段级**抽取，最后与规则做 hybrid（规则有值用规则，否则用 LLM；两者都过 quote 门）。

- 8 篇高正例子集（49 个 positive）：
  - E0 规则：value-F1 1.000，quote 1.000；
  - E1 全量 zero-shot：value-F1 0.500，quote 0.519；
  - E1cand 字段级 LLM：value-F1 1.000，quote 1.000；
  - HYBRID：value-F1 1.000，quote 1.000。
- **但该子集逐字段 value 支持只有 route n=2**，不能当稳健结论；已在跑 30 篇扩展。

### 11.2 Verifier 5 篇（item 3）

- `verifier.py` 在 5 篇 hybrid 预测上：HYBRID value-F1 1.000 → VERIFIED **0.000**，presence 0.939→0.900。
- 原因：Verifier 的 5/5 输出 `_parse_error`（模型继续写正文，未返回 JSON），`verifier.py` 默认 `reject`，把所有值都删了。
- 结论：**当前 LLM-as-verifier 不可行**；可用的“verifier”是确定性 quote 门（已经在 hybrid 里）。E7 不应报数字，除非换 prompt/模型重跑。

### 11.3 科学结论

- 值抽取：规则 + 字段级 LLM 的 hybrid 在 feasibility 子集上不劣于规则，且 quote 合法率 1.0；是否在 30/102 篇上稳定，等扩展结果。
- Verifier：负结果；不要用“独立 LLM Verifier”作为卖点，除非修复 JSON 遵循。

## 12. item 2/3 最终结果（30 篇高正例子集 + 5 篇 Verifier）

### 12.1 值抽取（30 篇，124 个 high+medium positive；value-F1 主终点）

| 系统 | presence | **value-F1** | quote 合法率 | 覆盖 |
|---|---|---|---|---|
| E0 规则 | 1.000 | **0.447** | 1.000 | 0.708 |
| E1 Qwen2.5-7B zero-shot | 0.929 | **0.041** | 0.595 | 0.708 |
| E1cand 字段级 LLM（候选句） | 0.961 | **0.094** | 1.000 | 0.708 |
| **HYBRID（规则 + 字段级 LLM）** | 0.978 | **0.452** | 1.000 | 0.708 |

- hybrid 比规则只高 0.005；**值抽取的主力是规则，不是 LLM**。
- 字段级 LLM 单独 0.094，zero-shot 0.041；两者都远低于规则。
- 逐字段：kd 0.667 / half_life 0.500 / dose 0.508 / route 0.929 / time_points 0.837 / size 0.750 / comparator 0.538 / immune 0.750；numeric_efficacy 0.214、serum_stability 0.143、valency 0.495。
- 该 30 篇是按 positive 数**选出的高正例子集**，不是随机样本；n 小、逐字段 CI 宽。不能外推到 102 篇。

### 12.2 Verifier（5 篇）

- HYBRID value-F1 1.000 → VERIFIED **0.000**；presence 0.939→0.900。
- 原因：verifier 5/5 输出 `_parse_error`（模型继续写正文，不返回 JSON），`verifier.py` 默认 `reject`，删光所有值。
- 结论：**当前 LLM-as-verifier 不可行**；可用的 verifier 是确定性 quote 门（hybrid 已内置）。不要把 E7 写成正结果。

### 12.3 结论

- item 2：两阶段 hybrid 可行，但增益来自规则；LLM 在值抽取上仍是弱项。科学写法是“规则 + 证据门 + LLM 候选”的边界，而不是“LLM 抽取”。
- item 3：负结果；Verifier 需要重写 prompt/换模型才可能可用，本轮不报 E7 数字。

## 13. item 2/3 复核（修正 metrics 后）

### 13.1 30 篇 hybrid（value-F1 主终点，已修正 positive 支持）

| 系统 | presence | value-F1 | quote |
|---|---|---|---|
| E0 规则 | 1.000 | 0.447 | 1.000 |
| E1 zero-shot | 0.929 | 0.041 | 0.595 |
| E1cand 字段级 LLM | 0.961 | 0.094 | 1.000 |
| HYBRID | 0.978 | **0.452** | 1.000 |

hybrid 只比规则高 0.005；值抽取主力是规则。全 102 篇 hybrid 正在跑。

### 13.2 Verifier v2（字段级、短候选、强制 JSON）

5 篇：accept 8 / reject 9 / correct 16 / parse_error_keep 4（JSON 遵循已修复）。

| 系统 | presence | value-F1 | quote |
|---|---|---|---|
| HYBRID_5 | 0.939 | **0.696** | 1.000 |
| VERIFIED2_5 | 0.939 | **0.535** | 1.000 |

**verifier2 仍然降值**：0.696→0.535。它技术上能跑，但会 reject/correct 掉正确的值。结论：LLM Verifier 在本任务上不增益；确定性 quote 门是更可靠的 verifier。

## 14. 全量 102 篇与 Verifier v2 最终结果

### 14.1 全量 102 篇（204 个 high+medium positive；value-F1 主终点）

| 系统 | presence | **value-F1** | quote 合法率 | 覆盖 |
|---|---|---|---|---|
| E0 规则 | 0.998 | **0.394** | 1.000 | 0.850 |
| E1 Qwen2.5-7B zero-shot | 0.975 | **0.030** | 0.600 | 0.850 |
| E1cand 字段级 LLM | 0.990 | **0.415** | 1.000 | 0.850 |
| **HYBRID（规则 + 字段级 LLM）** | 0.990 | **0.415** | 1.000 | 0.850 |

逐字段 hybrid value-F1：route 0.682（n=22）、time_points 0.813（19）、size 0.588（17）、valency 0.559（40）、kd 0.667（3）、half_life 0.500（2）、dose 0.452（9）、comparator 0.391（23）、immune 0.788（11）、numeric_efficacy 0.138（29）、serum_stability 0.231（13）。

- hybrid 比规则 +0.021（0.394→0.415）；字段级 LLM 单独也是 0.415，说明**规则提供了大部分值，LLM 只在规则缺失处补**。
- zero-shot 仍只有 0.030；presence 0.975 是“判缺席容易”的假象。

### 14.2 Verifier v2（5 篇，字段级短候选 + 强制 JSON）

- 技术可行性：accept 8 / reject 9 / correct 16 / parse_error_keep 4（不再全 reject）。
- 效果：HYBRID_5 value-F1 **0.696 → VERIFIED2_5 0.535**；presence 0.939 不变。
- 结论：**Verifier 仍降值**；LLM Verifier 在本任务上不增益，确定性 quote 门是更可靠的 verifier。

### 14.3 结论

1. 值抽取：hybrid 0.415 是当前最好；规则 0.394 是主力，LLM 补 +0.021。
2. 缺席检测：presence 0.99；不能当抽取性能。
3. Verifier：负结果；不要写 E7 正结果。
