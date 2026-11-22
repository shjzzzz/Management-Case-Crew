---
name: wiki-lint
description: "Health-check the research wiki: run deterministic lint and map refresh, check active paper report and project synthesis write-back, then audit contradictions, stale claims, missing concept pages and optional weekly review. Reports first; fixes only after approval. Use for 知识库体检、检查知识库、断链、孤立页、矛盾、过时内容、复盘."
argument-hint: "[optional: folder, topic, or '复盘']"
data_access_level: redacted
task_type: open-ended
---

# Wiki Lint（知识库确定性体检、语义审计与周期复盘）

## 1. 目标与边界
保障 Tier 1 跨项目知识库与项目入口页的结构健康、双链完整、溯源清晰与语义一致。**默认只报告不修改**，经研究者逐项批准后再执行修复。

## 2. 前置读取
- 读取 `Meta/purpose.md`、`Meta/index.md`、`Meta/review-queue.md`、`Meta/decisions.md`、`Meta/constraints.md`。

## 3. 核心体检流程
1. **确定性结构检查**：运行 `python .claude/scripts/wiki_lint.py lint --vault .`。
   - 扫描范围：Tier 1 知识目录（`03-Literature`、`04-Theories`、`05-Methods`、`08-Research-Notes`）、`01-Research-Projects/<项目>/PROJECT.md` 入口页与 `09-Writing` 独立文稿；**不扫描**库内既有旧税法笔记、`paper/versions/` 快照，且不把项目内部草稿误报为全库孤立页或重名页。
   - 核查项：frontmatter 完整性与语法、`sources[]` 路径可解析、断链、孤立页、`Meta/index.md` 覆盖、重名主干名、`Meta/aliases.csv` 别名冲突、双地图是否漂移。
2. **刷新两张地图**：运行 `python .claude/scripts/wiki_lint.py map --vault .`，同步更新 `Meta/folder-map.md`、`Meta/link-map.md` 以及 `CLAUDE.md`/`AGENTS.md` 中的 `ERC:MAP` 精简区块。
3. **项目与论文健康联动检查**（若库内存在活跃或近期结项项目）：
   - 运行 `python .claude/scripts/paper_tools.py report` 查看引文核验率、结果链接率、主张覆盖度与未答 `⟦问⟧` 数；
   - 检查已进入 S12 或结项的案例项目是否已把核心机制/综合结论回流至 `08-Research-Notes/`（`type: synthesis`）、`04-Theories/` 或 `05-Methods/`。
4. **语义级深度审计**（每条必须附具体页面与段落位置）：
   - **页面间矛盾**：同一涉税问题不同定性、同一企业财务/税负口径冲突；
   - **过时与失效**：中国税法条文、优惠政策或稽查标准是否已修订/废止；
   - **缺失概念页**：被多篇文献或案例反复引用却尚未独立建页的管理框架（`04-Theories/`）或案例/测算方法（`05-Methods/`）；
   - **缺失 `cite_key` / `locator`**：`03-Literature/` 中已核实但尚未补齐 `cite_key` 或三层锚点的文献/案例卡；
   - **长期积压**：`Meta/review-queue.md` 中长期 `open` 的待决项。

## 3b. 周期复盘模式（研究者要求“复盘”时）
读最近 7 天的 `Meta/run-ledger.jsonl` 与 `Meta/log.md`，找出：重复出现的失败原因、被反复退回的阶段、多次转入 `review-queue.md` 的同类事项、lint 报出的别名冲突。据此**只提议**对 Skill、`Meta/constraints.md`、`Meta/aliases.csv` 的修改，输出为 diff；由研究者逐条批准，复盘本身绝不写这些文件。

## 4. 产出与知识回流
- 输出结构化体检报告：**确定性错误 / 警告 / 项目与论文指标 / 语义问题 / 建议下一步**。
- 仅在研究者批准具体项后逐条修改；整理/体检结束后同步更新 `Meta/index.md` 并在 `Meta/log.md` 追加 `## [YYYY-MM-DD] lint | 范围`（附错误与警告计数）。

## 5. 硬性禁止
禁止未经批准自动改写、移动或删除任何页面；禁止把既有税法笔记纳入批量重构；无法确认是矛盾还是口径差异时记入 `Meta/review-queue.md`，严禁擅自裁决。
