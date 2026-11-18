---
name: paper-refine
description: "Refine an MBA case thesis draft through independent blind-review rounds: review, revise by presentation, re-review, accept the revision only if it improved, otherwise revert; at most 3 rounds, researcher decides at the end. Use for 精修、修改稿、返修、按盲审意见修改、润色并审阅、多轮修改."
argument-hint: "[project folder / draft path]"
---

# Paper Refine（盲审级评审—修改—接受或回退）

借鉴“以修改代替回复信”：评审意见通过**改正文**来回应，而不是另写回复。接受规则看**问题数**，最终由研究者决定。

## 循环（最多 3 轮；每个版本都保留）
0. `paper_tools.py refine start paper/draft.md`：保存 `paper/versions/v0.md`。
1. **独立盲审**：派出 `academic-reviewer`（一次一个，独立上下文），**只给产物路径**：稿件、主张—证据对照表、结果登记簿清单、案例分析计划；不给你的推理。要求结构化输出：**带编号的问题清单**（F1…、M1…、m1…，每条一句话并指向稿件位置），以及 5 个维度的 1–10 分：`theory`（理论与案例融合度）、`taxlaw`（税法准确与合规边界）、`evidence`（证据三角验证与测算可追溯）、`action`（对策可落地性与保障）、`write`（MBA 写作规范）。
2. 登记基线（条数 = 清单条数）：`paper_tools.py refine record --version v0 --fatal F --major M --minor m --scores theory=5,taxlaw=6,evidence=6,action=6,write=6`。
3. **修改**，写成 `paper/versions/v1.md`（再下一轮 v2、v3）：
   - 用改正文回应弱点；评审的问题要在正文里自然回答。
   - 保留“优点”所在的段落，除非必须改动。
   - 数字仍只用 `{{res:id}}`，引用仍只用引文表里的键；**不得新增测算与数据**。
   - 评审要求的新测算、新访谈或同业对标：**不要忽略，也不要自己做**，逐条追加到 `Meta/review-queue.md`（标“需要新分析，待研究者决定”）。
   - 每轮写 `paper/worklog-vN.md`：回应了哪些弱点、整合了哪些答案、做了哪些改动。
4. 对新版本再次评审。**必须按基线清单逐条复核**（已解决 / 部分 / 仍存在），再单独列出**新增**问题，不要重新数一遍；最好用 `SendMessage` 让同一个 reviewer 复评以保持口径。登记：`paper_tools.py refine record --version v1 --carried-fatal a --carried-major b --new-fatal c --new-major d --minor m --scores ...`（仍存在与部分解决的计入 carried）。脚本给出**接受 / 回退**：
   - 接受条件：Fatal 数不增加，且 Major 数严格下降，或 Major 持平而总分不低于上一采用版；Fatal 下降但 Major 上升一律回退；任何维度下降 ≥2 分一律回退；两次评审的评分维度必须完全一致，否则无法比较、一律回退。
   - 复评只接受清单计数（`--carried-*`/`--new-*`），直接计数只用于基线；`carried` 不能超过基线条数，计数不能为负。
   - 回退时：当前采用版本不变，**回到该版本再改**，不要在被回退的版本上继续。
5. 停止：3 轮用完、Fatal 与 Major 都为 0，或连续回退。`paper_tools.py refine status` 查看轨迹。

## 收尾（C4 检查点）
- 向研究者汇报：版本轨迹、当前采用版本、剩余 Fatal/Major、进入 review-queue 的“需要新分析”清单。
- 研究者认可后，把采用版复制为 `paper/final.md`；`orchestrator.py artifact paper/reviews.json paper/final.md`，`verify`，等研究者表态再 `gate`。
- 终检（S12）前再运行 `cite check --strict`、`results check`、`questions`，并起草 `paper/ai-disclosure.md`：依据 `orchestrator.py log` 与 `Meta/run-ledger.jsonl` 列出 AI 参与的阶段与任务，交研究者审定后再用于提交或盲审。
- 成稿后经研究者同意，把“主张—证据对照”整理为 `type: synthesis` 的 wiki 页，链回文献笔记与结果表来源。

## 禁止
为让分数上升而弱化或删除真实的证据局限；把评审的“新分析”要求悄悄当作已完成；修改已登记的结果数值；替研究者接受或拒绝盲审意见。
