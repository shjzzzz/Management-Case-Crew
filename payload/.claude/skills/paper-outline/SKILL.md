---
name: paper-outline
description: "Turn frozen single-case research outputs (case protocol, financial/tax results ledger, triangulation matrix) into a structured MBA thesis / management case paper outline with an Argument Spine: claim list, chapter plan, literature clusters and table storytelling plan. Use for 论文大纲、论文框架、论文结构、写作大纲、主张清单、MBA论文大纲."
argument-hint: "[project folder, target venue template]"
data_access_level: verified_only
task_type: open-ended
---

# Paper Outline（S8：MBA 管理案例论文论证脊柱与大纲设计）

## 1. 目标与边界
把已经冻结的 S1–S7 研究产物变成**可机械核查的论文架构**。大纲不写正文，只锁定五件事：核心主张与措辞边界、引言问题导入蓝图、管理诊断与合规筹划章节映射、文献与法规布局、待研究者裁决项（`⟦问：…⟧`）。**不写正文、不在此登记引文、不新增测算。**

## 2. 前置读取（不满足就停下说明）
- 检查项目已有 `PROJECT.md`、冻结的 `analysis-plan.md`（含三角验证矩阵与措辞上限）、`analysis-log.md`，以及已登记的 `Meta/results-ledger.json`（运行 `python .claude/scripts/paper_tools.py report` 核查）。若结果登记簿为空，暂停并提示先在 S5 登记核心财务/税负结果。
- 读取 `Meta/purpose.md`、`Meta/decisions.md`、`Meta/constraints.md`、`Meta/style-guide.md`、`Meta/mechanism-library.md`，以及研究者指定的学位论文/期刊规范（如 `Templates/venues/venue-mba-thesis-cn.md`）。

## 3. 核心架构设计流程
1. **主张清单（Claim List）——全稿机械校验基线**：
   - 每条一行：`C编号 | 主张 | 类型（描述/机制/因果/政策含义）| 证据（结果登记簿 id / 证据链）| 允许的措辞强度 | 局限与边界`。
   - 措辞强度不得高于 `analysis-plan.md` 与 `/case-design-audit` 冻结上限；**无证据支撑的主张标“无证据”**，禁止直接入稿，改写为 `⟦问：…⟧` 交研究者裁决。
2. **引言与问题导入蓝图**：明确现实/行业涉税痛点 → 单一案例典型性 → 管理框架与多源证据 → 核心定量诊断（锚定 `{{res:…}}`）→ 边际贡献与实践价值 → 章节路线图。
3. **章节与论证脊柱映射**（贴合 MBA 案例论文结构：绪论 → 文献综述与理论/税法基础 → 案例企业概况与涉税财务现状 → 涉税风险与管理问题诊断及成因剖析 → 合法税收筹划与内控治理优化方案 → 实施保障、局限与结论）：
   - 诊断章节必须实现“管理框架维度 × 多源证据链 × 财务/税负测算 `{{res:id}}`”深度咬合，杜绝“理论与案例两张皮”；
   - 对策章节每条方案必须对应前文已查明的具体成因，并标明税法依据、商业实质前提与预期改善测算口径。
4. **文献与法规布局**：划分 2–4 个微观文献簇，列出全部 `citation_hints`（`作者（确切标题）` 或 `待检索：<描述>`；法规写发文机关、文号与生效日），交 S9 `/literature-review` 与 `paper_tools.py cite` 登记。
5. **图表叙事计划**：一表一问——每张表/图注明编号、回答的核心问题、对应主张、来源 `res:id` 与口径注释。

## 4. 产出与停点（C1 检查点）
- 按 `Templates/paper-outline.md` 写入 `01-Research-Projects/<项目>/paper/outline.md`。
- 运行 `python .claude/scripts/orchestrator.py artifact <路径>` 与 `verify`；向研究者汇报主张清单、无证据主张与未决 `⟦问⟧`。**C1 检查点：等研究者表态后再推进至 S9/S10。**

## 5. 硬性禁止
禁止在本 Skill 写正文段落；禁止凭记忆登记引文或猜法规文号；禁止把无证据猜想包装为核心主张；禁止新增测算分析。
