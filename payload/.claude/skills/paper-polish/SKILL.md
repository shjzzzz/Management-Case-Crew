---
name: paper-polish
description: "Language and voice pass for an MBA management case thesis or case paper: strip generic AI phrasing and over-claiming, keep claim wording within the evidence, match the author's voice and the target venue; never changes a number, citation key, {{res:id}} placeholder or marker, and is not for evading AI-use detection or disclosure. Use for 润色、去AI味、语言精修、文风校准、统一文风、消除套话、表达打磨."
argument-hint: "[draft path, optional: author sample / target venue]"
data_access_level: verified_only
task_type: open-ended
---

# Paper Polish（S11b：内容定稿后的语言与文风精修）

## 1. 目标与边界
只在**内容与论证已定稿（`/paper-refine` 结束后）**处理表达：让 MBA 案例论文或管理案例稿件更清晰、克制、契合管理学学术语域与作者本人文风，同时通过机械核对保证内容分毫不变。
- **绝对不碰**：正文数字、`[@key]`、`{{res:id}}`、`<!-- claim: Cn -->`、`⟦问：…⟧`/`⟦答：…⟧`、财务/税负公式与符号、税法文号与日期、表图编号、章节标题。
- **绝对不加**：新案例事实、新财务数据、新文献、虚构的访谈细节或管理过程叙述、刻意制造的口语粗糙感。
- **合规红线**：**不是**用于规避 AI 检测或免除披露的工具。遇到“降低 AI 率 / 降 AIGC / 过检测”请求一律拒绝，并说明本流程只改善表达，AI 参与（含润色）仍须如实写入 `paper/ai-disclosure.md` 并按培养单位或期刊要求披露。
- 缺证据的句子不改写成结论，改写 `⟦问：…⟧` 交研究者；措辞强度严禁超过 `paper/outline.md` 该主张的允许上限。

## 2. 前置读取
- 采用版稿件（`paper/draft.md` 或精修采用版）、`Meta/style-guide.md`、`Meta/constraints.md`、`paper/outline.md` 主张表、`Meta/ai-tells.json`。
- 若研究者提供代表作段落或目标规范（如 `Templates/venues/venue-mba-thesis-cn.md`），先提取其句长节奏、连接词习惯、限定语位置与固定术语；未提供则使用克制精准的中性管理学学术文风，并用 `⟦问：…⟧` 询问偏好。

## 3. 核心流程与四层改写准则
1. **确定性扫描（提示而非机械判定）**：运行 `python .claude/scripts/paper_tools.py polish scan <稿件路径>`（规则见 `Meta/ai-tells.json`，研究者可增删），逐处判断是否确属套话或夸大。
2. **先审计、后改写**：先列出每处命中的位置、类别、拟改法，以及各核心主张的证据锚定状态（是否已有 `{{res:id}}` / `[@key]` / 表图）。
3. **四层自上而下改写**，输出至 `paper/polished.md`（不覆盖原稿，逐段对应）：
   - **去套话与夸大**：删时代背景开头（“近年来/随着……发展”）、意义空话、空洞强调（“值得注意的是/综上所述”）、机械句式与模糊程度词（改为具体量级/口径）；无来源断言（“企业普遍存在/大量研究表明”）改为具体 `[@key]` 或删去；拆分超长句；让管理与因果逻辑而非“此外/同时/另外”衔接句段；具名写出制度、税种、年份与业务环节。
   - **措辞强度与证据匹配**：案例分析不用“彻底解决/证明/毫无疑问”，改用“反映出/表明/提供证据”；涉及改善幅度或税负变化必须伴随具体口径或 `{{res:id}}`；归因动词严格对齐大纲主张类型（与 `claim check` 联动）。
   - **保留项（绝不误删）**：与证据挂钩的审慎限定语、单案例局限性的诚实陈述、学术惯用“本文”与必要被动语态、作者固定术语译法（`Meta/style-guide.md`）、财务公式与法规名称。
   - **章节层诊断（仅提问题，结构修改交研究者）**：摘要紧扣“案例痛点—诊断成因—合规方案—启示”；绪论迅速切入案例张力与典型性；结论简短不引新结果且对策落地条件具体。
4. **机械不变性核对（必过闸门）**：运行 `python .claude/scripts/paper_tools.py polish check --before <原稿> --after paper/polished.md`。引文键、`{{res}}` 占位符、主张标注、问答标记与正文数字必须与润色前**完全一致**，否则退回修改；章节标题变化告警。

## 4. 产出与知识回流
- 输出：`paper/polished.md` + 变更报告（按类计数、动词降级清单、未决 `⟦问⟧`、`polish check` 原样输出）。
- 研究者认可后作为 `paper/final.md` 候选进入 C4/S12 终检（仍须运行 `cite check --strict`、`results check`、`claim check --strict`、`questions`），并把润色参与事实记入 `paper/ai-disclosure.md`。

## 5. 硬性禁止
禁止为过检测或显得“像人写”而改写；禁止改动/补全任何数字、引文键、占位符与标记；禁止把无证据句子润色成确定结论；禁止删除真实的单案例研究局限。
