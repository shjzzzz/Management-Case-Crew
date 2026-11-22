---
name: query-wiki
description: "Answer a management case or tax-law question from the accumulated wiki (and project decisions) with traceable citations, separating wiki-sourced facts from inference, and offer to file synthesis notes back into the wiki. Use for 知识库里有什么、库里有哪些证据、根据知识库回答、查一下我们已有的文献."
argument-hint: "[question]"
data_access_level: redacted
task_type: open-ended
---

# Query Wiki（沿图谱检索与证据综合）

## 1. 目标与边界
基于已积累的 Tier 1 知识库与项目决策记录回答研究问题，严格区分“库内一手依据”与“AI 推断”。**不用常识补齐库里不存在的事实，绝不冒充库内结论。**

## 2. 前置读取与检索顺序
1. 先读 `Meta/purpose.md`、`Meta/decisions.md`、`Meta/constraints.md`、`Meta/index.md` 与 `Meta/link-map.md`（优先锁定枢纽页与 `MOC/`）。
2. 从相关枢纽页和条目进入正文，再沿 `[[双链]]`（`Meta/link-map.md` 邻接表）向外展开 1–2 跳；若涉及在研案例项目进展，补充读取 `01-Research-Projects/<项目>/PROJECT.md`。
3. 必要时按目录检索库内既有旧税法笔记，**严禁**在 `.claude`、`.agents`、`_vendor`、`_erc-*`、`06-Data`、`07-Code` 中查找税法笔记。

## 3. 核心回答结构
1. **核心结论**：先给直接、克制的结论（不足以定论则直说“库内证据不足”）。
2. **库内依据（Fact）**：每条主张标明 `[[页面]]` 与其 `sources` 中的原始来源及定位锚点（页码/表/节/文号）；若用于论文写作准备，顺带列出各文献卡的 `cite_key`。
3. **综合推断（Inference）**：显式单独标注基于上述依据做出的归纳或演绎，说明适用条件，不与原文事实混写。
4. **未核实项与来源冲突**：引用 `verification: unverified` 页面或存在 `Meta/review-queue.md` 未决矛盾时必须标出；税法结论须注明发文机关、文号、生效/废止状态，并提醒本地资料不自动等于现行有效法。
5. **知识库盲区与下一步**：明确列出“库中没有覆盖的部分”，建议对应 `/literature-review` 或 `/ingest-source`。

## 4. 产出与知识回流
- 回答结束后询问研究者是否回存为笔记（一般问答 → `type: query`；跨文献/案例综合 → `type: synthesis`）。
- **经研究者同意才写入**；写入后更新 `Meta/index.md`、在 `Meta/log.md` 追加 `## [YYYY-MM-DD] query | 问题`（或 `synthesis`），并运行 `python .claude/scripts/wiki_lint.py map --vault .`。

## 5. 硬性禁止
禁止用模型常识填补库内缺口并包装为“库内已有证据”；禁止在未核对多页的情况下宣称“文献一致认为”；禁止未经同意擅自新建笔记。
