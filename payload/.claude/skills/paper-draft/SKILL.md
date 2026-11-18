---
name: paper-draft
description: "Draft an MBA management/tax single-case thesis section by section from an approved outline, using only registered citations and registered results; unsupported claims become researcher questions, not text. Use for 起草论文、写初稿、成稿、分节写作、撰写全文、把大纲写成论文."
argument-hint: "[project folder, sections to draft]"
---

# Paper Draft（受限输入的分节写作 — MBA 案例论文）

只依据**已批准的大纲**写作。写作的输入被严格限定，这是防止编造企业数据与法规文号的主要手段：

| 允许的输入 | 用途 |
|---|---|
| `paper/outline.md`（C1 已通过） | 结构、主张清单、各章要点 |
| `Meta/citation-map.json`（`paper_tools.py cite list`） | **唯一允许引用的文献与法规**，用 `[@key]` |
| `Meta/results-ledger.json` | **唯一允许出现的测算数字**，用 `{{res:id}}`，保留小数位写 `{{res:id:3}}` |
| `Meta/style-guide.md`、`Templates/venues/*.md` | 文风、MBA 论文格式 |

## 步骤
0. `orchestrator.py status`：确认大纲关卡已通过；`paper_tools.py cite list` 看有哪些可引用的键，状态不是 verified/confirmed 的在正文里照常引用，但会在终检被挡，提醒研究者核验。
1. 逐章逐节写，一次一节（长节可派出 `paper-writer-agent`，一次一个，交接单按 `Templates/handoff.md`，只给上表所列文件的路径）。写入 `paper/draft.md`。
2. 每个分析/结果段落开头加注释 `<!-- claim: C3 -->`，说明它支撑哪条主张。措辞强度不得超过大纲里该主张允许的强度。
3. **数字**：只能写成 `{{res:id}}`。表里没有的企业财务数据、税负率、罚款金额不要写；不要心算、不要四舍五入后手写。
4. **引用与法规**：只能引 `[@key]`，key 必须在引文表里。想引的文献或税法文件不在表里时，写 `⟦问：需要引用…，请先登记⟧`，不要自己编 key、作者或文号。
5. **证据不足**：不要用“显然、众所周知、企业普遍存在”绕过；写 `⟦问：…⟧` 交研究者（补测算 / 降级为推测 / 删除）。**不新增分析、不补数据。**
6. 起草后依次运行并处理：
   - `paper_tools.py cite check paper/draft.md`（未知 key 为错误，未核验为警告）
   - `paper_tools.py results check paper/draft.md`（未知 id 为错误，未链接的统计量为警告，必须逐个处理）
   - `paper_tools.py questions paper/draft.md`（列出未回答的问题）
7. 生成 **主张—证据对照表**（C3 检查点用）：主张编号 → 正文位置 → 结果 id → 实际使用的措辞强度 → 是否超出大纲。

## 停点
`orchestrator.py artifact paper/draft.md` → `verify` → 向研究者汇报对照表、未核验引文、未回答的 `⟦问⟧`。**C3：等研究者表态后才推进。** 研究者在稿内用 `⟦答：…⟧` 回答，回答后再修改相应段落。

## 禁止
把单源访谈写成普遍规律；引用不在表里的文献或法规；写出不在登记簿里的企业财务/税务数字；用“据业内人士透露”之类无来源的断言；虚构优化方案的节税金额。
