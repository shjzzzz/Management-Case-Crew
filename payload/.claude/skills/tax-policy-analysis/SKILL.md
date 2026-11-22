---
name: tax-policy-analysis
description: "Analyze Chinese tax law applicability, tax evasion vs. lawful tax planning boundaries, tax audit risk, administrative-criminal thresholds and legal conflict resolution from authoritative sources. Use for 税法、偷漏税、逃税、虚开发票、税务稽查、税收筹划、税务合规、增值税、企业所得税、个税、行刑衔接."
argument-hint: "[tax issue, transaction structure or policy rule]"
data_access_level: redacted
task_type: open-ended
---

# Tax Policy Analysis（S3：税法适用、偷漏税定性与合法筹划边界分析）

## 1. 目标与边界
基于中国权威税法法源，为管理案例中的涉税交易、风险事件或筹划方案建立严谨的法律基准，清晰划定**合法税收筹划**、**激进避税/纳税调整风险**与**违法偷漏税/虚开发票**（含行刑衔接）的三条红线。

## 2. 前置读取
- 读取 `Meta/purpose.md`、`Meta/decisions.md`、`Meta/constraints.md`、`Meta/vault-map.md` 与 `Meta/index.md`；若检索库内既有旧税法笔记，按目录检索且**不自动视为现行有效法规**（排除 `.claude`、`.agents`、`_vendor`、`_erc-*`、`06-Data`、`07-Code`）。

## 3. 核心流程与委派
- **委派授权**：复杂多税种冲突适用与法源核查可派出 `tax-policy-agent`（按 `Templates/handoff.md` 交接，一次一个）。
1. **锁定交易实质与税期**：拆解业务流、合同流、资金流、发票流（四流一致性）、纳税主体与涉税会计期间，不轻信“灵活用工/个体户/税收洼地”等表面包装。
2. **权威法源核验**：每条法源必须注明**发文机关、文号、发布日期、生效日期、修订/废止状态、适用范围**；无法对照官方原文核实的一律标 `unverified`；重要法条建议同步通过 `paper_tools.py cite add --type legal --doc-no "…" --effective YYYY-MM-DD` 入表。
3. **冲突适用与证据等级**：多文件冲突时严格遵循 `tax-policy-agent` 冲突处理顺序（税收法定 → 过渡条款 → 位阶 → 特别/普通 → 新/旧 → 实质重于形式），并标注证据等级（直接 / 部分 / 解释性）。
4. **违法定性与筹划边界**：对照《税收征收管理法》第 63 条（偷税）、《刑法》第 201 条（逃税罪）与第 205 条（虚开增值税专用发票罪）评估行刑衔接风险；所有合法筹划方案必须满足“真实商业实质 + 明确法定依据 + 事前/事中程序合规”。
5. **税负影响与合规约束**：明确税基、税率、扣除与优惠口径，将可量化测算参数交 S5 `/case-data-analysis`。

## 4. 产出与知识回流
- 输出：法源与现行效力表、违法/避税/合法筹划边界评估、行刑衔接风险提示、筹划实施合规要件与待官方确认清单；经确认可沉淀至 `03-Literature/` 或 `08-Research-Notes/` 并更新 `Meta/index.md`、`Meta/log.md`。

## 5. 硬性禁止
禁止编造文号、条款或生效日期；禁止把废止法规或地方口径宣传稿当现行法律；禁止为违法偷漏税或无商业实质虚开行为提供规避方案。
