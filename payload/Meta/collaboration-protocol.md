---
type: collaboration-protocol
status: default
updated: YYYY-MM-DD
---

# 人机协作协议

> 研究者对学术判断负最终责任；AI 负责结构化协作、可追溯执行与机械核验。本协议为默认版本，研究者可修改，修改后在 `Meta/decisions.md` 记一条。

## 1. 自治等级（A0–A3）
| 等级 | 含义 | 典型操作 |
|---|---|---|
| A0 只读/整理 | AI 可独立完成，不改研究定稿 | 读文献/知识库、运行只读脚本、体检知识库、汇总进度与报告 |
| A1 起草 | AI 可独立起草，随时可被研究者覆盖 | 文献/案例卡草稿、大纲草稿、分节初稿、精修版本 `vN.md`、润色稿 `polished.md`（须通过 `polish check`） |
| A2 需确认 | 必须等研究者明确表态后才写入/推进 | 通过阶段关卡（`gate`）、人工确认引文/法源（`cite confirm`）、接受精修/润色为 `final.md`、写入 wiki 定稿与结项回流页 |
| A3 AI 不得做 | 无论如何均由研究者本人决定 | 拍板案例选择与归因/定性措辞强度；编造或“补全”文献、法条、企业财报数据、访谈原话、测算结果；决定是否送审/投稿；最终接受或拒绝盲审意见；修改 `06-Data/raw` 或 `03-Literature/_sources`；以“降 AIGC/过检测”为目的改写 |

## 2. 论文阶段检查点（C1–C5）
| 检查点 | 对应阶段 | 研究者确认事项 |
|---|---|---|
| C1 | S8 论文大纲 | 论证脊柱、主张清单（每条含 `res:id` 与措辞上限）、MBA 案例章节与对策布局、文献簇与图表叙事分工 |
| C2 | S9 引文与法规 | `Meta/citation-map.json` 中每条文献与税法文号的核验状态（verified/confirmed）与三层定位锚点 `locator` |
| C3 | S10 成稿 | 主张—证据—测算数字对照表、大纲主张覆盖度、案例事实/理论解释/对策边界是否清晰 |
| C4 | S11 精修（+ 可选 `/paper-polish`） | 版本轨迹、按基线清单复核后的剩余 Fatal/Major、转入 `Meta/review-queue.md` 的“需新分析/补充证据”清单；若做语言润色，确认 `polish check` 全过 |
| C5 | S12 终检 | `cite check --strict`、`results check`、`claim check --strict`、`questions`、7 类 AI 失效模式清零、`paper/ai-disclosure.md` 审定、结项知识回流确认 |

关卡通过 `orchestrator.py gate` 记录（Claude Code 下触发权限提示），必须附带 `--note` 写明研究者的决定与理由。

## 3. 稿内沟通与追溯标记
- AI 提问：`⟦问：…⟧`；研究者回答：紧随其后写 `⟦答：…⟧`。存在未回答问题将阻断 S8/S12 校验。
- 引用：`[@key]`（必须在 `Meta/citation-map.json`）；结果数字：`{{res:id}}` 或 `{{res:id:3}}`（必须在 `Meta/results-ledger.json`）；结果段落主张锚点：`<!-- claim: Cn -->`。
- 证据不足时写 `⟦问：…⟧`，绝不写空洞结论或编造访谈/财报细节。

## 4. 评审口径与记录披露
- **评审口径**：初评产出带编号清单（`F1…`、`M1…`、`m1…`）与 5 维 1–10 分（`ident` 案例设计严谨度 / `contrib` 理论与实践贡献 / `inst` 税法与制度准确度 / `consist` 证据链与测算一致性 / `write` 写作与规范）；复评按基线清单逐条复核（`--carried-*`/`--new-*`），尽量由同一 `academic-reviewer` 实例执行以保口径一致。
- **决策与披露**：`Meta/decisions.md` 只记研究者的关键学术决定，AI 恢复上下文时先读；`Meta/run-ledger.jsonl` 用于终检起草 `paper/ai-disclosure.md`，实际披露方式以培养单位 MBA 论文规范或目标期刊要求及研究者判断为准。
