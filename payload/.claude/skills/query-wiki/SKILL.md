---
name: query-wiki
description: "Answer a research question from the accumulated wiki with citations, separating wiki-sourced claims from inference, and offer to file the answer back as a note. Use for 知识库里有什么、库里有哪些证据、根据知识库回答、查一下我们已有的文献."
argument-hint: "[question]"
---

# Query Wiki

## 流程
1. 读取 `Meta/purpose.md` 与 `Meta/index.md`；据 index 选出相关页面，再读页面本身。必要时用检索补充，但不要在 `.claude`、`_vendor`、`_erc-*`、`06-Data`、`07-Code` 中找税法笔记。
2. 回答结构：
   - **结论**（先给答案）；
   - **依据**：每条主张标 `[[页面]]` 与其 `sources` 中的原始来源（页码/表/节）；
   - **推断**：明确标出哪些是你基于依据的推理、不是来源明说的；
   - **未核实/冲突**：引用 `verification: unverified` 的页面或存在矛盾时必须指出；
   - **知识库没有覆盖的部分**：直接说“库中没有”，建议 `/literature-review` 或 `/ingest-source`。
3. 法规类结论注明发文机关、文号、生效与废止状态；库内资料不等于现行有效，需提示核验。
4. 回答完成后询问是否把它存为 `08-Research-Notes/` 下的笔记（frontmatter：`type: query`、`sources`、`updated`、`verification`）。**得到同意才写**，写后更新 `Meta/index.md` 并在 `Meta/research-log.md` 追加 `## [YYYY-MM-DD] query | 问题`。

## 规则
- 不用常识补库里没有的事实并冒充库内结论。
- 回答不得声称“文献一致认为”，除非 index/页面确实支持，并给出这些页面。
