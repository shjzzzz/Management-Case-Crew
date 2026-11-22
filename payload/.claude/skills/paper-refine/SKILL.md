---
name: paper-refine
description: "Refine an MBA management case thesis or paper draft through independent review rounds (F1/M1/m1 checklist + 5 scores, accept only on measurable improvement, else revert, max 3 rounds) and manage blind-review / advisor revisions via a traceability matrix. Use for 精修、修改稿、返修、R&R、按盲审或导师意见修改、多轮修改."
argument-hint: "[project folder / draft path]"
data_access_level: verified_only
task_type: open-ended
---

# Paper Refine（S11：清单复核精修闭环与盲审/导师返修）

## 1. 目标与边界
面向**内容与论证质量**的迭代精修：以“改稿回应弱点”为核心，通过独立盲审的编号问题清单与 5 维评分做**严格接受/回退控制**（最多 3 轮，所有版本留档），并支持外部盲审/导师修改意见的矩阵追溯。纯语言表达打磨在内容定稿后交给 `/paper-polish`。

## 2. 前置读取
- 确认 `paper/draft.md`（C3 已通过）、`paper/outline.md`、`Meta/style-guide.md`、`Meta/constraints.md`、`Meta/results-ledger.json`、`Meta/citation-map.json`。
- 若为外部盲审或导师意见返修，同时读入意见全文与 `Templates/rebuttal-matrix.md`。

## 3. 核心流程与委派规则
### 3.1 内部对抗精修循环（最多 3 轮，版本全保留）
0. **快照基线**：`python .claude/scripts/paper_tools.py refine start paper/draft.md` 生成 `paper/versions/v0.md` 与 `paper/reviews.json`。
1. **基线独立评审与审稿报告复核**：派出 `academic-reviewer`（独立上下文，一次一个，按 `Templates/handoff.md` **只给产物路径**）。输出已读文件清单 + 编号清单（`F1…`、`M1…`、`m1…` + 可选 `Advisory`）+ 5 维 1–10 分（`ident, contrib, inst, consist, write`）+ 建议文献块 + 框架锁定与 7 类 AI 失效核查。保存报告后运行 `python .claude/scripts/paper_tools.py review verify --review <报告> --manuscript paper/versions/v0.md` 核验引述与推荐文献，剔除误读或幻觉推荐后再动稿。
2. **登记基线**：`python .claude/scripts/paper_tools.py refine record --version v0 --fatal F --major M --minor m --scores ident=5,contrib=6,inst=6,consist=7,write=6`。
3. **针对性改稿**（写成 `paper/versions/v1.md`…`v3.md`，长篇修改可派 `paper-writer-agent`）：
   - 严守受限输入（`{{res:id}}`、`[@key]`），**不得擅自补测算或改原始数据**；
   - 评审要求新增财务测算/补充访谈/扩充对标样本的条目，逐条写入 `Meta/review-queue.md`（标“需要新分析/补采证据，待研究者决定”）；
   - 每轮写 `paper/worklog-vN.md` 记录回应的问题编号、修改位置与未处理原因。
4. **按基线清单复评与机械判优**：
   - 复评对照基线清单逐条标注 `已解决 / 部分解决 / 仍存在`（计入 `carried`）并单列新增问题（计入 `new`），尽量复用同一 `academic-reviewer` 实例。
   - `python .claude/scripts/paper_tools.py refine record --version vN --carried-fatal a --carried-major b --new-fatal c --new-major d --minor m --scores ident=...,contrib=...,inst=...,consist=...,write=...`。
   - 机械判定接受/回退：仅当 `Fatal ≤ 上版` 且（`Major < 上版` 或 `Major == 上版 且同维度总分 ≥ 上版`），且**维度完全一致、任一维度未降 ≥2 分**时接受；否则回退并回到当前采用版重新修改。
5. **停止条件**：用满 3 轮、Fatal 与 Major 均归零、或连续回退。运行 `python .claude/scripts/paper_tools.py refine status` 查看轨迹。

### 3.2 外部盲审 / 导师意见返修模式
按 `Templates/rebuttal-matrix.md` 建立 `paper/rebuttal-matrix.md`，逐条分类（直接改稿/澄清边界、需新增测算/补证据入 `review-queue.md`、有据反驳），绑定正文位置、证据锚点与复核状态。

## 4. 收尾与停点（C4 → 可选 `/paper-polish` → S12）
1. 提交简洁中文修改简报（版本轨迹、当前采用版、剩余 Fatal/Major、`review verify` 结果与转入 `review-queue.md` 清单）。
2. **内容定稿后，可选调用 `/paper-polish`** 做纯语言精修，必须通过 `polish check` 并经研究者认可。
3. 研究者确认采用版后复制为 `paper/final.md`；运行 `orchestrator.py artifact paper/reviews.json paper/final.md` 与 `verify`，等研究者表态再 `gate`。
4. **S12 终检准备**：运行 `cite check --strict`、`results check`、`claim check --strict`、`questions`，清零 7 类 AI 失效模式，起草 `paper/ai-disclosure.md`；结项后经研究者同意将核心发现回流至 `08-Research-Notes/`（`type: synthesis`）并刷新双地图。

## 5. 硬性禁止
禁止为拉高评分而弱化或删除单案例局限；禁止把“需新分析/补证据”悄悄当作已完成；禁止修改已登记数值；禁止替研究者接受或拒绝盲审意见（A3）。
