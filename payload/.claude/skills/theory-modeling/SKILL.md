---
name: theory-modeling
description: "Build and audit management analytical frameworks (COSO, ERM, value chain, agency theory, corporate governance, business-finance-tax integration), diagnostic indicators and competing causal propositions for single-case analysis. Use for 分析框架、理论框架、COSO、内部控制、价值链、委托代理、公司治理、业财税融合、机制分析."
argument-hint: "[case problem, management framework or mechanism]"
data_access_level: verified_only
task_type: open-ended
---

# Theory Modeling（S3：管理分析框架构建与竞争性机制推导）

## 1. 目标与边界
围绕 S1 确定的案例问题与 S2 识别的文献缺口，构建贴合案例情境的管理学分析框架与可观测诊断指标，并提出主成因链与竞争性解释，彻底避免“理论与案例两张皮”。

## 2. 前置读取
- 读取 `Meta/purpose.md`、`Meta/decisions.md`、`Meta/constraints.md`、`Meta/mechanism-library.md`（仅作候选起点，不是证据）、项目 `PROJECT.md` 与 S2 文献缺口表。

## 3. 核心流程与委派
- **委派授权**：复杂框架推导与多理论比选可派出 `theory-agent`（按 `Templates/handoff.md` 交接，一次一个）。
1. **框架选型与适配论证**：比较 2–3 个候选管理框架（如 COSO 五要素 vs 委托代理激励 vs 价值链与业财税融合），说明为何所选框架最贴合本案例的涉税/合规问题，并显式列出其适用边界以防框架锁定（Frame-Lock）。
2. **可观测诊断指标拆解**：将每个框架维度转化为具体的可观测信号（财务/ETR 偏离、合同/发票流断点、审批权限漏洞、绩效考核激励等）。
3. **主成因链与竞争性假说（H1..Hk）**：至少提出一条主解释链与一条竞争性解释（如“内控流程缺失导致的被动涉税违规” vs “高管短视业绩激励驱动的主动偷漏税/激进筹划”），写清两者在可观测证据上的排他性差异。
4. **下游证据需求映射**：逐项列出 S4 `/case-design-audit` 需要采集的财报附注、内部制度与访谈问题。

## 4. 产出与知识回流
- 输出：管理分析框架与适用边界、诊断指标表、竞争性命题清单与证据映射；通用理论框架经研究者同意可沉淀至 `04-Theories/` 并更新 `Meta/index.md`、`Meta/log.md` 与双地图。

## 5. 硬性禁止
禁止先下定论再裁剪案例事实；禁止把 `Meta/mechanism-library.md` 当成已验证结论；禁止构建与 S4/S5 证据采集脱节的空泛框架。
