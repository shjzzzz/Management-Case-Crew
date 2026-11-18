---
name: wiki-lint
description: "Health-check the research wiki: run the deterministic lint script, then review contradictions, stale claims and missing concept pages. Reports first; fixes only after approval. Use for 知识库体检、检查知识库、断链、孤立页、矛盾、过时内容."
argument-hint: "[optional: folder or topic to focus on]"
---

# Wiki Lint

## 流程
1. 读取 `Meta/purpose.md`、`Meta/index.md`、`Meta/review-queue.md`。
2. 运行确定性检查：`python .claude/scripts/wiki_lint.py lint --vault .`。它只扫描新增研究目录（`01-Research-Projects`、`03-Literature`、`04-Theories`、`05-Methods`、`08-Research-Notes`、`09-Writing`），**不扫描库内原有的税法笔记**。检查项：frontmatter、`sources[]` 可解析、断链、孤立页、index 覆盖。
3. 语义检查（模型完成，必须逐条给出证据位置）：
   - 页面之间的**矛盾**（同一问题不同结论、同一数据不同口径）；
   - **过时**：新来源是否已取代旧主张；法规是否已修订/废止；
   - 被多次提到却没有独立页面的概念；
   - 可通过补充检索填补的数据或文献缺口；
   - `Meta/review-queue.md` 中长期 open 的事项。
4. 输出报告：错误 / 警告 / 语义问题 / 建议的下一步（含值得追问的新问题与可补充的来源）。
5. **默认不修改任何页面。** 研究者批准具体项后再改；改动逐条说明。
6. 在 `Meta/research-log.md` 追加：`## [YYYY-MM-DD] lint | 范围`，附错误与警告计数。

## 规则
- 不删除、不移动页面；孤立页只提示，不自动处理。
- 无法确认是矛盾还是口径差异时，记入 `Meta/review-queue.md`，不要擅自判定。
