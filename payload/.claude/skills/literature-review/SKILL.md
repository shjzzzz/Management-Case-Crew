---
name: literature-review
description: "Conduct a source-grounded management, corporate governance and tax-law literature review, debate-structured matrix, Kumar (2020) gap taxonomy and citation registration with three-layer locator anchors. Use for 文献综述、梳理文献、国内外研究现状、研究缺口、文献矩阵、找文献、Zotero、EndNote."
argument-hint: "[topic, question or scope]"
data_access_level: redacted
task_type: open-ended
---

# Literature Review（S2 / S9：证据驱动文献梳理与引文锚点登记）

## 1. 目标与边界
产出**按争论/理论框架/治理机制演进组织**的管理学与财税文献矩阵与精确缺口，而非逐篇罗列摘要；在 S9 阶段协同 `paper_tools.py cite` 完成带三层定位锚点（`locator`）的引文与法源表建设。**绝不编造文献或法条，绝不用摘要替代全文证据。**

## 2. 前置读取
- 先读本地知识库：`Meta/purpose.md`、`Meta/constraints.md`、`Meta/index.md`、`Meta/link-map.md`（沿枢纽页与 `03-Literature/` 检索已有文献卡），再决定外部检索范围。
- 若处于论文 S9 阶段，先读 `paper/outline.md` 第 4 节 `citation_hints` 与 `Meta/citation-map.json`（`python .claude/scripts/paper_tools.py cite list`）。

## 3. 核心流程与委派规则
- **委派授权**：长篇文献检索、逐篇抽取与矩阵比对可派出 `literature-agent`（按 `Templates/handoff.md` 交接，一次一个）。
1. **界定检索协议**：明确主题、时间跨度、语种、纳入/排除标准，记录检索日期、数据库与检索词。
2. **多源检索与分级筛选**：优先一手法规/监管文书、国内外管理学与财税核心期刊、权威案例库，明确区分同行评审期刊、工作论文、案例报告与新闻评论。
3. **逐篇方法论抽取**（禁止只看摘要下结论）：研究问题、管理框架、案例/样本、财务/税负指标、研究方法与三角验证、核心发现与局限；读不到全文时显式标注“仅摘要/未获全文”。
4. **按争论簇构建矩阵**（直接服务 S8 `/paper-outline`）：划分为 2–4 个微观文献簇，每簇明确代表文献与共识/分歧、局限假设及与本案例的桥接。
5. **识别真实缺口与竞争解释**：按 §3a 的“研究缺口分类表”逐类登记，区分“没人写过”与“既有框架/案例未解决的真实管理与涉税痛点”。
6. **三层定位锚点与引文登记（含 Zotero / EndNote 交换）**：
   - 已有 `03-Literature/*.md` 文献卡：优先运行 `python .claude/scripts/paper_tools.py cite from-note <卡片路径>` 桥接入库。
   - 已在 **Zotero / EndNote** 中管理的文献：导出 RIS / BibTeX / CSL-JSON（本机 Zotero 也可用 `cite zotero` 直接拉取），先 `paper_tools.py cite import <文件> --dry-run` 预览再正式导入（`--attach [--pdf-dir DIR]` 复制 PDF 到 `03-Literature/_sources/`）。导入条目一律 `unverified`（中文为 `manual`），须核对原文或由研究者 `cite confirm` 后才能引用。定稿后可用 `cite ris|csl|bib -o` 导出。
   - 新增引文：`python .claude/scripts/paper_tools.py cite add --key <k> --title "…" --year Y [--doi D] --locator "…" --claim-scope "…"`；中文文献加 `--type chinese`，税法文件加 `--type legal --doc-no "…" --effective YYYY-MM-DD`，均须研究者核对原文后执行 `cite confirm`。

## 3a. 研究缺口分类表（据 Kumar 2020, *Journey through research gaps*）
**表 A：缺口分类表**（八类各占一行；无证据填“未发现”，不硬凑）

| 缺口类型 | 判定问题 | 已知（过往知识 + 引文 + locator） | 未知 / 所需知识 | 过往发现的弱点 | 张力类型（表 B，无则“—”） | 现有研究是否已解决 | 本案例如何填补（交 S3） | 证据状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Population 案例/样本 | 哪些行业、企业类型、所有制或税制时期未被覆盖？ | | | | | | | |
| Concepts 概念 | 核心概念（合规/激进避税/偷漏税/内控）界定或口径不一？ | | | | | | | |
| Perspectives 视角 | 缺哪类主体或管理视角（如只看税法不看内控治理）？ | | | | | | | |
| Theory 理论 | 管理理论机制或竞争解释缺失？ | | | | | | | |
| Analysis 分析 | 业财税联动分析、税负测算或异质性维度缺失？ | | | | | | | |
| Implication 启示 | 合规筹划与治理方案的可落地性与保障机制未验证？ | | | | | | | |
| Methods 方法 | 数据来源、测算口径、质性编码或对标方法有局限？ | | | | | | | |
| Methodology 方法论 | 案例研究设计或证据三角验证存在根本局限？ | | | | | | | |

**表 B：张力表**（Inconsistency 不一致 / Controversy 争议 / Conflict 冲突 / Contradiction 矛盾）

| 张力类型 | 一侧主张（来源 + locator） | 另一侧主张（来源 + locator） | 可能原因（情境、制度、口径、框架） | 对应表 A 缺口行 |
| --- | --- | --- | --- | --- |
| | | | | |

**表 C：缺口到框架的收口**：现有研究共用框架 → 本案例拟采用/修正的管理分析框架（注明由表 A 哪几行推出）。已核实的张力同步记入 `Meta/review-queue.md`（状态 `open`），不替研究者裁决。

## 4. 产出与知识回流
- 输出：检索记录、争论簇文献矩阵、研究缺口分类表（表 A/B/C）、未核实清单；经确认后按 `Templates/literature-note.md` 沉淀至 `03-Literature/`，更新 `Meta/index.md`、`Meta/log.md` 并运行 `wiki_lint.py map` 刷新双地图。

## 5. 硬性禁止
严禁编造作者/标题/年份/DOI/法规文号；严禁把摘要当作全文细节（防 L3 错配）；严禁无定位锚点支撑强主张。
