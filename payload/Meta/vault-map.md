---
inbox: 00-Inbox
projects: 01-Research-Projects
resources: .
literature: 03-Literature
literature_raw: 03-Literature/_sources
theories: 04-Theories
methods: 05-Methods
data_raw: 06-Data/raw
data_processed: 06-Data/processed
data_metadata: 06-Data/metadata
code: 07-Code
notes: 08-Research-Notes
writing: 09-Writing
archive: 10-Archive
templates: Templates
meta: Meta
moc: MOC
---

# Vault Map（四层知识架构与 Meta 控制面）

## 四层知识流
1. **Tier 0 原始只读层（Immutable Sources）**
   - `00-Inbox/`：`/ingest-source` 默认待摄入原始来源入口（如企业年报、税务稽查通报、法规原文；摄入时不原地修改、移动或删除原始文件）。
   - `03-Literature/_sources/`：已归档原始文献 PDF / 处罚决定书 / 访谈纪要（只读，可新增、不得覆盖或修改）。
   - `06-Data/raw/`：原始数据（企业财报、纳税申报表、访谈逐字稿、问卷原始数据；只读，禁止任何原地清洗或覆盖）。
   - 库根目录既有笔记（既有税法/管理笔记，`resources: .`）：保持原位、不移动/重命名/批量改写，仅作本地参考资料，不自动视为现行有效法规或已核实结论。
2. **Tier 1 跨项目复利知识层（Compounding Wiki Graph）**
   - `03-Literature/`：结构化文献与案例卡（含 `cite_key` 与三层证据定位，可桥接 `Meta/citation-map.json`）。
   - `04-Theories/`：管理学分析框架与涉税激励/内控机制页（COSO、价值链、委托代理、业财税融合等）。
   - `05-Methods/`：单一案例研究设计（Yin 效度/信度、三角验证）与质性编码/财务税负测算方法页。
   - `08-Research-Notes/`：跨案例综合页（`type: synthesis`）、问答回存（`type: query`）与结项回流摘要。
   - `MOC/`：主题枢纽索引页（Map of Content）。
3. **Tier 2 项目执行与手稿层（Project Workspace，按项目隔离）**
   - `01-Research-Projects/<project>/`：
     - `PROJECT.md`：项目入口页（进 `Meta/index.md` 与双链图）。
     - `STATE.json`：阶段机读状态（仅由 `orchestrator.py` 维护）。
     - `analysis-plan.md`、`analysis-log.md`：预设案例分析/测算计划与执行日志。
     - `paper/`：该项目全部 MBA 论文/案例报告产物（`outline.md`、`draft.md`、`versions/`、`worklog-vN.md`、`reviews.json`、`polished.md`、`final.md`、`rebuttal-matrix.md`、`ai-disclosure.md`）。项目内部手稿与版本快照不进入全库双链图，避免多项目并行时的重名与孤立页噪音。
   - `06-Data/processed/` + `06-Data/metadata/`：衍生财务/税负测算表与数据卡（建议按 `<project>/` 分目录）。
   - `07-Code/{python,R,stata}/`：财务比率、有效税率（ETR）、税负测算与图表脚本。
4. **Tier 3 独立交付与归档层（Outputs & Archive）**
   - `09-Writing/`：**仅放非完整研究项目的独立文稿**（案例简报、教学案例、政策评论、答辩提纲），不与 `01-Research-Projects/<project>/paper/` 重叠。
   - `10-Archive/`：已结项案例项目归档。

## Meta 控制面（三类文件）
- **静态规范（研究者可编辑）**：`purpose.md`、`research-standards.md`、`collaboration-protocol.md`、`style-guide.md`、`mechanism-library.md`、`ai-tells.json`、`vault-map.md`。
- **协作账本（人机共同维护）**：`index.md`、`source-registry.md`、`log.md`、`review-queue.md`、`decisions.md`、`constraints.md`（研究者纠正）、`aliases.csv`（术语别名）。
- **脚本独占机读文件（禁止手改）**：`citation-map.json`、`results-ledger.json`（`paper_tools.py`）；`run-ledger.jsonl`（`orchestrator.py`）；`folder-map.md`、`link-map.md`（`wiki_lint.py map`，精简版嵌入 `CLAUDE.md`/`AGENTS.md` 的 `ERC:MAP` 区块）。

## 检索边界
- 检索库根目录既有笔记时排除 `.claude`、`.agents`、`_vendor`、`_erc-staging`、`_erc-backups`、`06-Data`、`07-Code`。
- 若本文件安装前已存在，安装器不会覆盖，请手动比对更新。
