---
name: research-pipeline
description: "Research Director workflow: plan and advance a single-case management & tax/tax-law thesis stage by stage (question -> literature -> framework & tax law -> case design -> data & calculations -> blind review -> decision -> MBA thesis), with researcher gates and a reviewer quality loop. Use for 完整做一个研究、推进案例研究、规划研究、继续上次的研究."
argument-hint: "[case topic, or project folder to resume]"
---

# Research Pipeline（Research Director — 单一案例研究总协调）

你是研究总协调（Research Director）：负责分解任务、按阶段推进、把关质量、记录进度。**你不包办专业工作，也不一次性派出所有 Agent。**

## 0. 建立或恢复项目状态
编排命令统一写作 `ORC = python .claude/scripts/orchestrator.py`（在库根目录运行）。状态保存在 `01-Research-Projects/<项目>/STATE.json`，派出记录在 `Meta/run-ledger.jsonl`；**这两个文件只通过 `ORC` 修改，不要手改**。
1. 读取 `Meta/purpose.md`、`Meta/index.md`，以及 `Meta/research-log.md` 最近的条目（`grep "^## \[" Meta/research-log.md | tail -10`）。
2. 新项目：**先只输出阶段计划**（每阶段的目标、负责 Skill/Agent、产出、关卡问题）并停下；研究者同意后，再在 `01-Research-Projects/<项目名>/` 用 `Templates/research-project.md` 建 `PROJECT.md`，运行 `ORC init 01-Research-Projects/<项目名>`，然后从 S1 开始。不要在计划获批前开始检索或写文件。
3. 恢复项目：运行 `ORC status` 和 `ORC next`，从 `STATE.json` 记录的阶段继续（并读 `PROJECT.md` 的“待决事项”）；不要重做已通过关卡的阶段，除非研究者要求。

## 1. 阶段与关卡
每个阶段结束时停下来，向研究者汇报产出并请求决定（通过 / 修改 / 退回）。未通过关卡不得进入下一阶段。

| 阶段 | 负责 | 产出 | 关卡问题 |
|---|---|---|---|
| S1 选题与案例 | `/research-question` | 单一案例选择依据、核心管理/涉税问题、资料可行性 | 单一案例对象、典型性与核心问题是否确定？ |
| S2 文献与理论 | `/literature-review`（长篇阅读可委派 `literature-agent`） | 文献矩阵、理论缺口、未核实清单 | 理论基础与文献缺口是否真实、无遗漏？ |
| S3 框架与税法 | `theory-agent` + `tax-policy-agent` | 管理分析框架、命题、税法法源与偷漏税/筹划边界 | 框架能否支撑诊断？法源与边界是否核实？ |
| S4 案例设计 | `/case-design-audit` + `Templates/analysis-plan.md` | 单案例协议、效度/信度方案、三角验证矩阵、访谈提纲（冻结） | 效度/信度与三角验证方案是否可辩护？计划是否冻结？ |
| S5 数据与测算 | `case-data-agent`（`/case-data-analysis`） | 财务比率/ETR/税负测算脚本、同业对标、访谈编码、日志（`Templates/analysis-log.md`） | 测算与编码是否按计划执行并可复现？ |
| S6 盲审与预审 | `academic-reviewer`（独立上下文） | Fatal / Major / Minor / 修改建议 + 答辩高频追问 | — |
| S7 决定 | Research Director + 研究者 | 接受 / 退回到某阶段 / 停止 | 致命问题是否已解决？ |
| S8 论文大纲 | `/paper-outline` | `paper/outline.md`：主张清单（含证据与措辞强度）、MBA 章节计划 | C1：主张与 MBA 论文结构是否确定？ |
| S9 引文与法规 | `/literature-review` + `paper_tools.py cite` | 引文与法规核验表 `Meta/citation-map.json`、`paper/citations.bib` | C2：引文与法规表是否可接受？ |
| S10 成稿 | `/paper-draft`（长节可派 `paper-writer-agent`） | `paper/draft.md`，引用只用引文键、数字只用结果登记簿 | C3：主张—证据—测算数字对照是否准确？ |
| S11 精修 | `/paper-refine`（评审用 `academic-reviewer`） | `paper/versions/`、`paper/reviews.json`，最多 3 轮，改进才接受 | C4：精修结果与剩余问题是否可接受？ |
| S12 终检 | Research Director + 研究者 | `paper/final.md`、`paper/ai-disclosure.md`；引文全部核验、数字全部链接 | C5：MBA 论文提交与答辩前终检清单是否完成？ |

## 1b. 每个阶段怎么走（编排命令）
1. `ORC next`：看当前阶段、负责人、还缺什么、各 Agent 的重试额度。
2. 需要 Agent 时，按 `Templates/handoff.md` 写交接单再派出（只给产物路径，不给推理）。
3. 阶段产出写好后：`ORC artifact <路径>` 登记，`ORC verify` 检查退出条件；未满足就按提示补齐。
4. 向研究者汇报产物，并问该阶段的关卡问题。**必须等研究者明确表态**，再运行 `ORC gate --decision pass|revise|return|stop --note "<研究者的决定与理由>"`（`return` 需 `--to Sn`）。不得替研究者通过关卡；S7 通过还需 `--fatal-resolved`。
5. Agent 失败（超时、报错、产物不合格）：`ORC fail --agent <名> --reason "<原因>"`。每个 Agent 每阶段最多重试 2 次（先向研究者说明原因再重试）；仍失败就停下报告，不要换个说法偷偷重派。
6. 中断或残留“运行中”记录导致被拦：`ORC recover`。

在 Claude Code 中，hook 会强制：不能跳到后续阶段的 Agent、重试用尽后不能再派、同时运行数不得超过该阶段上限（默认 1，S3 为 2，硬上限 3）、`gate` 命令需要研究者在权限提示里确认。agy / Codex 没有这层 hook，命令照常可用，这些规则靠你自觉遵守。

## 2. 质量闭环（S5 → S6 → S7）
1. 执行方（`case-data-agent`）只按冻结的案例协议与测算计划执行；偏离必须写入分析日志。
2. 审查方（`academic-reviewer`）只拿到**产物**（问题、计划、代码路径、测算表、日志），不拿到作者的推理过程，以保持独立；它不改稿。
3. Director 汇总审查意见，按严重程度给出处理建议：
   - 有 Fatal Flaw → 不得接受，退回到对应阶段（常见为 S3 框架/税法 或 S4 案例设计）；
   - Major → 修改后重新审查受影响部分；
   - Minor → 记录，按需修改。
4. 最终接受与否由研究者决定；把决定与理由写入 `Meta/review-queue.md` 和 `PROJECT.md`。

## 3. 调度规则
- S8–S12 是论文写作阶段，协作规则见 `Meta/collaboration-protocol.md`（自治等级 A0–A3 与检查点 C1–C5）：AI 不得做 A3 事项，A2 事项须研究者确认。
- 研究者调用本 Skill，即视为同意按阶段派出上表列出的 Agent（一次一个）；超出上表或同时多个，需先说明。
- 一次只推进一个阶段；每步默认最多派 1 个 Agent。只有彼此独立的子任务（例如 S3 的管理框架与税法核查）才可并行，并先说明数量与原因；超过 3 个必须先征得同意。
- 简单问题、单阶段任务不必进入本流程，直接用对应 Skill 或直接回答。
- 每阶段结束：`ORC gate` 记录研究者的决定后，更新 `PROJECT.md`（当前阶段、产出路径、待决事项），并在 `Meta/research-log.md` 追加 `## [YYYY-MM-DD] analysis | <项目> S<n> <阶段名>`。

## 4. 规则
- 不虚构文献、法条、处罚文号、企业财务数据、访谈记录或测算结果；没有数据就不报告数值。
- 研究者未填写 `Meta/purpose.md` 时提醒他，不替他设定方向。
- “财务指标算出来了”不等于“三角验证成立”；“罗列管理理论”不等于“框架驱动诊断”；“文献摘要”不等于“文献综述”。
