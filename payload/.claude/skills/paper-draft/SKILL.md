---
name: paper-draft
description: "Draft an MBA management case thesis or case paper section by section from an approved outline using strictly constrained inputs (registered citations and registered results only); unsupported claims become researcher questions. Use for 起草论文、写初稿、成稿、分节写作、撰写全文、把大纲写成论文."
argument-hint: "[project folder, sections to draft]"
data_access_level: verified_only
task_type: open-ended
---

# Paper Draft（S10：受限输入的 MBA 案例论文分节成稿）

## 1. 目标与边界
仅依据 **C1 已批准的大纲**分节起草正文。通过**严格限定输入源**从机械层面杜绝幻觉：
| 唯一允许的输入 | 约束规则 |
|---|---|
| `paper/outline.md`（C1 已通过） | 结构、主张清单（含措辞强度上限）、各节要点 |
| `Meta/citation-map.json`（`paper_tools.py cite list`） | **唯一允许引用的文献与税法文号**，写作 `[@key]` |
| `Meta/results-ledger.json` | **唯一允许出现的核心财务/税负/对标数字**，写作 `{{res:id}}` 或 `{{res:id:2}}` |
| `Meta/style-guide.md`、`Meta/constraints.md`、`Templates/venues/*.md` | 文风锚定、术语表、培养单位/期刊规范 |

## 2. 前置读取
- 运行 `python .claude/scripts/orchestrator.py status` 确认 S8/S9 关卡已通过；运行 `python .claude/scripts/paper_tools.py cite list` 查看可用键（未核验条目须提醒研究者人工核验）。
- 读取 `Meta/style-guide.md` 与 `Meta/constraints.md` 完成文风与术语校准。

## 3. 核心流程、分节规程与委派
- **委派授权**：长节起草可派出隔离上下文的 `paper-writer-agent`（一次一个，按 `Templates/handoff.md` 交接，只给上表 4 类文件路径）。
1. **逐节写作**（一次一节，写入 `01-Research-Projects/<项目>/paper/draft.md`）：
   - 严格区分**案例事实描述**、**管理理论解释**与**规范性治理/筹划建议**；
   - 每个核心结果/诊断段落开头加 `<!-- claim: Cn -->`，措辞强度严禁超过 `paper/outline.md` 对应主张上限；
   - 财务与税负数字只用 `{{res:id}}` 并交代口径与同业基准；文献与法规只用 `[@key]`（带 `locator` 防 L3 错配）；缺失证据或需企业内部细节写 `⟦问：…⟧`，绝不编造访谈原话或数据。
2. **成稿机械审计与质检**（每节或全稿完成后依次运行）：
   - `python .claude/scripts/paper_tools.py cite check paper/draft.md`
   - `python .claude/scripts/paper_tools.py results check paper/draft.md`
   - `python .claude/scripts/paper_tools.py claim check paper/draft.md`
   - `python .claude/scripts/paper_tools.py questions paper/draft.md`
3. **生成主张—证据对照表**（C3 检查点用）：主张编号 → 正文节/段 → 结果 id → 实际措辞强度 → 是否符合大纲上限 → 覆盖状态。

## 4. 产出与停点（C3 检查点）
- 运行 `python .claude/scripts/orchestrator.py artifact paper/draft.md` 与 `verify`。
- 向研究者汇报主张—证据对照表、主张覆盖度、未核验引文与未回答 `⟦问⟧`。**C3 检查点：等研究者表态并在稿内写 `⟦答：…⟧` 后再修改或推进。**

## 5. 硬性禁止
禁止超出证据上限作强归因；禁止引用不在 `citation-map.json` 的文献或法条；禁止手写不在 `results-ledger.json` 的核心数字；禁止编造访谈引语或无来源断言；禁止替研究者做 A3 决策。
