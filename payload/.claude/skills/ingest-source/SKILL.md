---
name: ingest-source
description: "Ingest one source (paper, case report, annual report, tax penalty notice, legal document) into the research wiki in two steps: analyze first, write only after the researcher approves; cross-link concept pages and prepare cite_key for paper writing. Use for 摄入文献、入库、把这篇论文或案例资料加入知识库、处理 00-Inbox（及 _sources）里的文件."
argument-hint: "[path to a file under 00-Inbox/ or 03-Literature/_sources/]"
data_access_level: raw
task_type: open-ended
---

# Ingest Source（两步摄入：原始来源 → 复利知识库）

## 1. 目标与边界
一次只处理一个原始来源，严格分两步执行：**先分析并停下等研究者确认，确认后再写入**。不仅生成孤立文献/案例卡，更推动跨文献概念页（`04-Theories/`、`05-Methods/`、`MOC/`）复利生长，并预置 `cite_key` 桥接论文引文表。

## 2. 前置检查
1. 读取 `Meta/purpose.md`（未填则提醒并按“方向未定”处理）、`Meta/index.md`、`Meta/link-map.md`、`Meta/source-registry.md`、`Meta/constraints.md`（研究者纠正，必须遵守）、`Meta/aliases.csv`（建概念页前先查别名，已有规范名则并入而非新建）。
2. 核实待摄入来源位于默认入口 `00-Inbox/`（亦兼容已归档的 `03-Literature/_sources/`）。若研究者仅提供文件名，优先在 `00-Inbox/` 下查找；**不得移动、改名、修改或删除原始文件**。
3. 计算哈希去重：`python .claude/scripts/wiki_lint.py hash <文件> --vault .`。若返回 `ALREADY REGISTERED`，停止并告知，除非研究者明确要求重新摄入。

## 3. 核心两步流程
### 第一步：分析（不写任何文件，输出后必须停止等待确认）
1. **全文通读**：读不到全文（仅摘要、扫描不清、受限）须如实说明，不得用摘要推断细节。
2. **结构化抽取**：
   - 学术文献/案例报告：研究问题、管理框架、案例/样本、财务/税负口径、研究方法与三角验证、核心发现与局限；附三层定位锚点（页码/表/图/条款），拟定规范英文 `cite_key` 与 `claim_scope`。
   - 法规/税务稽查文书：发文机关、文号、发布日期、生效日期、废止/修订状态、适用范围、违法定性与行刑衔接要点。
   - 企业年报/内部资料：主体、会计年度、报表口径、关键财务/税负事实与附注页码。
3. **跨库比对与知识复利评估**：查 `Meta/index.md` 与 `Meta/link-map.md`，找出可关联的已有文献卡、理论框架页（`04-Theories/`）和方法页（`05-Methods/`）；并列写出**矛盾与张力**，绝不擅自裁决。
4. **拟改动清单**：新建哪张卡片、建议在哪些已有页面追加双链或对照段落。
5. **未核实项与待研究者判断项**。

**输出以上分析后立即停下，等待研究者确认或调整范围。**

### 第二步：写入（仅在确认后执行）
1. 按 `Templates/literature-note.md` 写入 `03-Literature/`，frontmatter 必填：`type: literature`、`cite_key`、`title`、`locator`、`claim_scope`、`sources`、`sha256`、`updated`、`verification`（`verified | unverified`）。
2. 更新已确认触及的 `04-Theories/`、`05-Methods/` 或 `MOC/` 页面：只追加相关段落与 `[[双链]]`，不整页重写；文末“更新记录”注明日期与来源。
3. 矛盾处理：在相关页面并列写出两侧主张与来源，同时记入 `Meta/review-queue.md`（状态 `open`）。
4. 更新 `Meta/index.md`（每页一行，附 `cite_key`）、在 `Meta/source-registry.md` 登记 SHA256 与访问日期、在 `Meta/log.md` 追加 `## [YYYY-MM-DD] ingest | 标题`。
5. 若研究者同意同时进入论文引文表，运行 `python .claude/scripts/paper_tools.py cite from-note <卡片路径>`（中文/法规条目提醒人工 `cite confirm`）。
6. 运行 `python .claude/scripts/wiki_lint.py map --vault .` 刷新双地图，再运行 `python .claude/scripts/wiki_lint.py lint --vault .`；有错误必须修完再收尾。

## 4. 产出与知识回流
- 新增/更新的 Tier 1 知识页、更新后的 `index`/`source-registry`/`log`、刷新后的两张地图与 lint 报告。

## 5. 硬性禁止
禁止跳过确认直接写文件；禁止修改、移动或删除 `00-Inbox/` 或 `03-Literature/_sources/` 中的原始文件；禁止编造 DOI/页码/法条/财务数据；禁止擅自裁决来源矛盾；禁止把未公开企业/个人信息外发外部服务。
