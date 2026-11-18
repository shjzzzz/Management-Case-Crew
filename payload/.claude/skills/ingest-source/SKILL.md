---
name: ingest-source
description: "Ingest one source (paper, report, legal document, data note) into the research wiki in two steps: analyze first, write only after the researcher approves. Use for 摄入文献、入库、把这篇论文加入知识库、处理 _sources 里的文件."
argument-hint: "[path to a file under 03-Literature/_sources/]"
---

# Ingest Source

一次只处理一个来源。分两步：先分析（不写任何文件），经研究者确认后再写入。

## 前置
1. 读取 `Meta/purpose.md`（方向）、`Meta/index.md`（已有页面）、`Meta/source-registry.md`（已登记来源）。`purpose.md` 未填写时，提醒研究者并按“方向未定”处理，不要替他编造。
2. 来源文件必须位于 `03-Literature/_sources/`。若在别处，请研究者自行放入；**不得移动、改名或修改原始来源**。
3. 计算哈希：`python .claude/scripts/wiki_lint.py hash <文件> --vault .`。输出 `ALREADY REGISTERED` 时说明已摄入，除非研究者明确要求重新摄入，否则停止。

## 第一步：分析（不写任何文件）
1. 完整阅读来源。读不到全文（只有摘要、扫描质量差、受限）时如实说明，不得用摘要推断细节。
2. 抽取：研究问题、理论/机制、数据与样本、变量、识别策略、主要结果、稳健性、局限；每个主张附页码/表/节。法规类来源抽取：发文机关、文号、发布日期、生效日期、废止/修订状态、适用范围。
3. 与已有知识比对（先读 index，再读相关页面）：列出**矛盾与张力**——两侧主张各自附来源，不要擅自裁决。
4. 列出拟写入的改动清单：新建哪些页面、更新哪些已有页面的哪一段（逐条一句话）。
5. 列出“未核实项”和“需要研究者判断的事项”。

**输出以上分析后停止，等待研究者确认或调整。**

## 第二步：写入（确认后）
1. 用 `Templates/literature-note.md` 新建文献笔记，frontmatter 必须包含：`type`、`title`、`sources`（指向 `_sources` 里的文件路径）、`sha256`、`updated`、`verification`（verified | unverified）。
2. 更新已有页面时只追加或修改相关段落，保留原文，不整页重写；每处改动在页面末尾“更新记录”注明日期与来源。
3. 矛盾：在相关页面并列写出两侧主张与各自引用；同时记入 `Meta/review-queue.md`（状态 open）。
4. 更新 `Meta/index.md`（每页一行）。
5. 在 `Meta/source-registry.md` 登记该来源（含 SHA256、访问日期）。
6. 在 `Meta/research-log.md` 追加：`## [YYYY-MM-DD] ingest | 标题`，下附改动页面清单。
7. 运行 `python .claude/scripts/wiki_lint.py lint --vault .`，把结果告知研究者；错误必须先修再收尾。

## 规则
- 不虚构文献、DOI、页码、法条。无法核实一律标 `unverified`。
- 区分来源事实、你的解释、研究者的假说。
- 单个来源通常会触及多个页面，但每次写入范围以研究者确认的清单为准。
- 涉及个人信息或受限数据的来源，不得发送到外部服务。
