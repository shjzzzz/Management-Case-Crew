---
name: paper-outline
description: "Turn frozen single-case outputs (case design, tax-law check, financial/ETR results) into an MBA management/tax case thesis outline: claim list with evidence, chapter plan, literature layout, table/figure plan. Use for 论文大纲、论文框架、论文结构、写作大纲、主张清单、MBA论文大纲."
argument-hint: "[project folder, target thesis/journal template]"
---

# Paper Outline（MBA 单一案例论文架构：先有大纲，再写正文）

目标：把已经冻结的研究产物变成**可检查的 MBA 案例论文架构**。大纲不写正文，只回答：我主张什么、证据在哪、各章写什么、理论与案例如何咬合、哪些地方还要研究者决定。

## 0. 前提（不满足就停下说明）
- 有 `PROJECT.md`、冻结的案例分析计划、分析日志，且**测算/编码结果已登记**：`python .claude/scripts/paper_tools.py results ...`。结果登记簿 `Meta/results-ledger.json` 为空时，不写诊断与测算章节，只写到“案例概况与研究设计”，并提示先登记结果。
- 读 `Meta/purpose.md`、`Meta/style-guide.md`、`Meta/mechanism-library.md`，以及目标模板（默认 `Templates/venues/venue-mba-thesis-cn.md`）。各高校 MBA 学位论文具体格式要求以研究者核对培养单位官网后的为准，不凭记忆。

## 1. 主张清单（Claim list）——大纲的核心
每条主张一行：`C编号 | 主张 | 类型（事实描述 / 成因诊断 / 税法合规界定 / 优化对策）| 证据：结果登记簿 id 或三角验证来源 | 允许的措辞强度 | 局限`。
- 单一来源（未三角验证）的主张，措辞强度必须降级为“初步发现/访谈反映”，不得写成确凿结论。
- **没有登记结果或明确来源支撑的主张，标“无证据”，不得进入正文当作结论**；写成 `⟦问：…⟧` 交研究者决定（补测算、降级为推测，或删除）。
- 机制类主张对照 `Meta/mechanism-library.md`：每个机制要有案例证据对应；找不到就如实写“仅为解释性推测”。

## 2. MBA 案例论文标准结构（按模板调整）
1. **绪论**：研究背景（行业与税收监管环境）、研究意义（理论与实践）、研究内容与方法、技术路线图、可能创新点。
2. **文献综述与理论基础**：国内外相关研究（偷漏税治理/税收筹划/税务风险内控）、核心概念界定、管理学分析框架（如 COSO/委托代理/业财税融合）及税法制度背景。
3. **案例企业概况与涉税现状**：企业简介、业务模式与组织架构、近年财务与税负指标（`{{res:id}}`）、涉税事件/筹划需求还原。
4. **问题诊断与成因分析**（核心章）：依据管理学分析框架逐维诊断，结合三角验证证据（财务/ETR 测算 + 同业对标 + 访谈/制度）剖析偷漏税诱因或筹划痛点，明确税法边界。
5. **优化方案与实施保障**（MBA 核心价值）：针对性整改/合法税收筹划方案（含税负对比测算与合法性校验）+ 组织、制度、业财税信息化与风控保障措施。
6. **结论与展望**：研究结论、管理启示、单一案例外部效度局限与未来研究方向。

每章写：本章要回答的问题、对应主张编号、要点（**指向具体来源**，如“用 `{{res:etr.2023}}` 报告案例企业有效税率并与行业均值 `{{res:etr.peer}}` 对比”）。子节要成对出现，不留孤立子节。

## 3. 文献与法规布局
- **引文提示 `citation_hints`**：每个核心理论、案例研究方法（如 Yin）、财务指标口径、涉税法规都要有提示。格式 `作者（确切标题）`；法规写**发文机关 + 文号 + 生效日期**；不确定时写 `待检索：<描述>`，**禁止猜作者或文号**。
- 这些提示是 `/literature-review` 与 `paper_tools.py cite add` 的输入；大纲阶段**不登记引文**。

## 4. 图表计划
每个表/图一行：编号、目的、来源结果 id、需要的口径说明与注释。

## 5. 输出与停点
- 用 `Templates/paper-outline.md` 写到 `01-Research-Projects/<项目>/paper/outline.md`。
- 在流程中：`orchestrator.py artifact <路径>`，`verify`，然后向研究者汇报：主张清单（逐条含证据与措辞强度）、无证据主张、未决 `⟦问⟧`。**C1 检查点：等研究者表态后才推进。**
- 不要在本 Skill 里写正文、不要登记引文、不要新增分析。
