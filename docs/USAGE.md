# 使用说明

本说明面向已把本扩展安装到研究库（下称 Vault，例如 `D:\Economicresearchwiki`）的使用者。安装步骤见 [README](../README.md)。

## 1. 它是什么
一组放进 Claude Code 项目的配置：
- **6 个 Subagent**（`.claude/agents/`）：各有职责与证据标准的专业角色。
- **11 个 Skill**（`.claude/skills/`）：固定流程，用 `/名称` 触发。
- **项目规则**（`CLAUDE.md` + `.claude/ECONOMICS-RESEARCH.md`）：每次会话自动加载。
- **规范与模板**（`Meta/`、`Templates/`）：研究方向（`purpose`）、目录（`index`）、研究日志、待审队列、来源登记、研究标准，以及文献/数据/分析模板。
- **脚本与 hooks**（`.claude/scripts/`、`.claude/hooks/`）：知识库体检脚本；可选的原始数据保护与 frontmatter 校验。

它不包含计量软件，也不会自动跑回归；它约束 Claude 如何组织、检查和记录研究工作。

## 2. 开始一次会话
```powershell
Set-Location D:\Economicresearchwiki
claude
```
首次使用先做只读检查：
```text
请读取 CLAUDE.md、.claude/ECONOMICS-RESEARCH.md、Meta/vault-map.md、Meta/research-standards.md。
只检查配置与目录，不修改知识库。报告已发现的 Agent、Skills、路径与潜在冲突。
```
再用 `/agents` 确认 6 个 Agent，`/skills` 确认 11 个 Skill。

## 3. Skill 速查
| 命令 | 何时用 | 产出 |
|---|---|---|
| `/research-question <主题>` | 题目还是一个主题，没有可检验的问题 | ≤3 个候选问题、可行性评估、推荐一个 |
| `/literature-review <范围>` | 需要有来源的文献梳理 | 检索记录、文献矩阵、研究缺口、未核实清单 |
| `/theory-modeling <机制>` | 需要把机制写成模型 | 设定、假设、逐步推导、比较静态、可检验推论 |
| `/tax-policy-analysis <政策>` | 税制、征管、遵从、归宿问题 | 法源与有效性、机制、效率与分配、待官方确认项 |
| `/causal-inference-audit <设计>` | 设计 DID/IV/RDD 前后审查识别 | estimand、假设、威胁、检验、可用的因果措辞 |
| `/econometric-analysis <任务>` | 数据审计、实现与复现回归 | 分析计划、代码、样本核算、日志 |
| `/academic-review <稿件/设计>` | 投稿或汇报前挑刺 | Fatal / Major / Minor 分级意见 |
| `/ingest-source <文件>` | 把 `03-Literature/_sources/` 里的一个来源摄入 wiki | 先输出分析并等你确认；确认后写文献笔记、更新 index/日志/登记 |
| `/query-wiki <问题>` | 基于已积累的 wiki 回答 | 带引用的回答，区分依据与推断，可回存为笔记 |
| `/wiki-lint` | 知识库体检 | 断链/孤立页/溯源/index 覆盖 + 矛盾与过时检查报告 |
| `/research-pipeline <主题或项目>` | 完整推进一个研究、继续上次的研究 | 先给阶段计划并等你同意；之后逐阶段推进，每阶段停在关卡，含 Reviewer 质量闭环 |

例：
```text
/causal-inference-audit 研究金税四期上线对企业税收遵从的影响，处理组为首批试点地区企业，双向固定效应 DID
```

## 4. 路由：Claude 如何决定用什么
1. 概念性短问题 → 直接回答。
2. 单项研究任务 → 先调用对应 Skill（Skill 描述里有中文触发词，例如“文献综述”“识别策略”“复现论文”）。
3. 完整研究、多阶段、“继续上次的研究” → `/research-pipeline`。
4. Agent 由 Skill 或 pipeline 在内部派出，一次一个；调用 Skill 即视为你同意它派出其指定的 Agent。Skill 之外，只有你点名时才派。
5. 在本库内，本项目 Skill 优先于范围重叠的全局插件技能；你点名其他技能时以你为准。

想确保走某个流程，直接输入 `/技能名` 最可靠。

**角色映射（你的方案中的 8 个角色加 Director）**

| 角色 | 由谁承担 |
|---|---|
| Research Director | `/research-pipeline`（阶段、关卡、质量闭环） |
| 01 文献研究 | `/literature-review`、`literature-agent`、`/ingest-source` |
| 02 理论建模 | `/theory-modeling`、`theory-agent` |
| 03 数据工程 | `/econometric-analysis`、`econometrics-agent` |
| 04 计量分析 | `/econometric-analysis`、`econometrics-agent`；识别审查由 `/causal-inference-audit`、`causal-inference-agent` 负责 |
| 05 税收研究 | `/tax-policy-analysis`、`tax-policy-agent` |
| 06 代码复现 | `/econometric-analysis` 的“复现与代码审计模式” |
| 07 学术写作 | **不在本项目范围内**：由主会话完成，遵守证据与汇报规则；可按需使用你已安装的写作类技能 |
| 08 学术审稿 | `/academic-review`、`academic-reviewer`（独立上下文） |

质量闭环：研究 Agent 提方案 → `econometrics-agent` 执行 → `academic-reviewer` 质疑 → Director 与你决定是否接受；有致命问题不得接受。

## 4b. 调用 Agent
Claude 会按 `.claude/ECONOMICS-RESEARCH.md` 的分派规则，在任务确实专业化、可并行或需要独立审查时委派。也可以直接点名：
```text
请用 academic-reviewer 审查 01-Research-Projects/XXX/draft.md，只列致命问题和重要问题。
```
| Agent | 职责 | 工具权限 |
|---|---|---|
| literature-agent | 检索、抽取、比较文献 | 读、搜、联网 |
| theory-agent | 模型推导与机制 | 读、写、编辑 |
| tax-policy-agent | 税法、征管、归宿 | 读、搜、联网 |
| econometrics-agent | 数据审计、估计、复现 | 读、写、编辑、Bash |
| causal-inference-agent | 识别与稳健性设计 | 读、搜、联网、写 |
| academic-reviewer | 对抗式审稿 | 只读、联网 |

只有 econometrics-agent 能执行 Bash；reviewer 不能写文件，避免“边审边改”。

## 5. 推荐工作流
1. `/research-question` 定题 → 把确认后的问题写入 `01-Research-Projects/<项目>/`（用 `Templates/research-project.md`）。
2. `/literature-review` → 文献笔记放 `03-Literature/`（`Templates/literature-note.md`）。
3. `/theory-modeling`、`/tax-policy-analysis` → 机制与制度背景放 `04-Theories/`、`08-Research-Notes/`。
4. 数据入 `06-Data/raw`（只读），在 `06-Data/metadata` 建数据卡（`Templates/dataset-card.md`）。
5. `/causal-inference-audit` 先审设计，再用 `Templates/analysis-plan.md` 写分析计划。
6. `/econometric-analysis` 执行；日志用 `Templates/analysis-log.md`，代码放 `07-Code/`。
7. `/academic-review` 独立审查；按意见修改后再定稿。
8. 每次重要工作在 `Meta/research-log.md` 记一行；新来源登记到 `Meta/source-registry.md`。

不要跳过第 5 步：能跑出回归不等于识别成立。

## 6. 知识库维护（可积累的 wiki）
思路借鉴 llm_wiki：不是每次从原始文献重新检索，而是让知识库随摄入和提问不断积累。三层：**原始来源**（`03-Literature/_sources/`，不可变）→ **wiki 页面**（文献笔记、理论、方法、综合，由 Claude 与你共同维护）→ **规则**（`CLAUDE.md`）。

- **先填 `Meta/purpose.md`**：研究方向、核心问题、范围边界。Claude 每次摄入和回答前都会读它；没填它会提醒你，不会替你编。
- **摄入**：把 PDF/剪藏放进 `03-Literature/_sources/`，运行 `/ingest-source 路径`。它先算 SHA256 去重，再输出分析（抽取、与已有页面的矛盾、拟改动清单、未核实项），**等你确认**后才写页面、更新 `Meta/index.md`、追加日志、登记来源。
- **提问**：`/query-wiki 问题`，先读 index 再读页面，回答区分“库内依据”和“推断”，并询问是否回存为 `08-Research-Notes/` 笔记。
- **体检**：`/wiki-lint`，先跑确定性脚本再做语义检查；默认只报告不修改。也可直接运行 `python .claude/scripts/wiki_lint.py lint --vault .`。扫描范围只含新增研究目录，**不扫描原有 Economicresearchwiki 税法笔记**。
- **日志**：`Meta/research-log.md` 条目以 `## [日期] 类型 | 标题` 开头，可用 `grep "^## \[" Meta/research-log.md | tail` 查看近期记录。
- **矛盾**：来源之间的冲突并列记录并进入 `Meta/review-queue.md`，由你裁决。
- 页面 frontmatter 约定：`type`、`sources`、`updated`、`verification`（verified | unverified）。

## 7. Hooks（可选，技术层面的保护）
安装时加 `-WithHooks`，会把两个 hook 合并进 `.claude/settings.json`（合并前备份；已有设置保留；重复运行不会重复添加；若 settings.json 不是合法 JSON 则拒绝并保持原样）。需要 PATH 中有 `python`。

| Hook | 时机 | 作用 |
|---|---|---|
| `protect_raw.py` | PreToolUse | 阻止修改 `06-Data/raw` 与 `03-Literature/_sources` 里**已存在**的文件（Write/Edit/NotebookEdit 精确拦截）；新建文件允许，便于导入新资料 |
| `validate_frontmatter.py` | PostToolUse | 写入 .md 后检查 frontmatter 是否闭合、有无 Tab，有问题时把提示反馈给 Claude 去修 |

**局限**：对 Bash 只是关键字启发式检查（`rm`/`mv`/`Remove-Item`/重定向/复制到目标等且命令里出现受保护路径），无法覆盖所有 shell 写法；hook 输入异常时放行（fail open）。它们是在提示约束之外多加的一层，不是沙箱，Git 与备份仍然需要。

## 8. 它会遵守的规则
- `06-Data/raw` 与 `03-Literature/_sources` 只读；衍生数据只写 `06-Data/processed`。
- 不删除、不移动、不重命名库内原有笔记，除非你明确同意。
- 不编造文献、DOI、法条、数据或结果；查不到就标“未核实”。
- 区分相关与因果，先说 estimand 与假设。
- 税法结论要给文号、日期、生效与废止状态。
- 涉及个人或受限数据，不外发。

这些主要是写在指令里的约束：模型可能出错。装了 hooks 后，原始数据与原始来源另有技术拦截（见第 7 节，有局限）；权限提示与 Git 仍是实际保险。重要结论请自行核对原始来源。

## 9. 自定义
- **改角色**：编辑 `.claude/agents/*.md`（`description` 决定何时被自动调用，`tools` 决定权限）。
- **加 Skill**：新建 `.claude/skills/<name>/SKILL.md`，frontmatter 需有 `name`（与目录同名）和 `description`。
- **改规则**：编辑 `CLAUDE.md` 或 `.claude/ECONOMICS-RESEARCH.md`。
- **改路径映射**：编辑 `Meta/vault-map.md`。
- 重装不会覆盖已改过的文件（已存在即跳过）；想拿回默认版本，先把旧文件改名再安装。

改完后运行 `Test-EconomicsResearchCrew.ps1` 检查结构。

## 9a. 编排层：状态、关卡、重试与记录
- 完整研究用 `/research-pipeline`。它会用 `orchestrator.py` 记录当前阶段、已登记的产物和你每次的关卡决定，所以中断后可以从 `STATE.json` 继续，不会重做已通过的阶段。
- 常用命令（在库根目录）：`python .claude/scripts/orchestrator.py status`（进度）、`next`（下一步与还缺什么）、`log -n 20`（最近的派出与决定）。
- **关卡由你决定。** Claude 汇报产物和关卡问题后会等你表态；它运行 `gate` 时 Claude Code 会弹出权限提示，请在确认你确实作出了该决定后再同意。
- Agent 失败：最多重试 2 次，之后停下向你报告；你决定“修改（revise）”后计数才清零。
- 如果被 hook 拦住而你确认是残留记录：`orchestrator.py recover`；要临时关闭拦截：`orchestrator.py enforce off`（仍会记录）。
- 派出 Agent 的交接单模板：`Templates/handoff.md`（只给产物路径，不给推理，保持独立审查）。

## 9c. 论文写作：大纲、引文、成稿、精修
1. `/paper-outline` 产出 `paper/outline.md`（主张清单：每条主张的证据 id 与允许的措辞强度）。
2. 登记结果：`python .claude/scripts/paper_tools.py results import <csv> --prefix t2` 或 `results register`；登记引文：`cite add --key k --title "…" --year Y [--doi D]`，状态为 verified / mismatch / unverified / manual；`cite confirm` 由研究者人工确认（会触发权限提示）。
3. `/paper-draft` 只用引文表与结果登记簿写作；`cite check`、`results check`、`questions` 检查草稿。
4. `/paper-refine`：评审→修改→`refine record` 给出接受/回退，最多 3 轮；需要新分析的意见进入 `Meta/review-queue.md`。
5. `paper_tools.py report` 查看已核验引文率、数字链接率、未答问题数。

## 9b. 在 Antigravity（agy）或 Codex CLI 中使用
- 安装：`-Platform auto` 会自动为本机已有的 CLI 生成文件；也可用 `-Platform agy` / `codex` / `all` 指定。
- 规则在研究库根目录 `AGENTS.md` 的 `ERC:BEGIN … ERC:END` 区块里，内容与 `CLAUDE.md` 一致；Skills 在 `.agents/skills/`，Agent 说明在 `.agents/agents/`，脚本在 `.agents/scripts/`。
- 用法相同：直接用自然语言提问，或点名 Skill（如“用 literature-review 梳理……”）。agy 装了 `-WithHooks` 时，路由提示会在每轮第一次调用模型前注入。
- agy 的原始材料保护 hook 在不拦截时返回 `ask`（沿用 agy 正常审批流程），不会自动批准任何操作。
- Codex：未在本机运行测试；没有 hook，`06-Data/raw` 与 `03-Literature/_sources` 的只读规则只靠 `AGENTS.md` 文本约束。若 Codex 不支持子 Agent，Skill 会在主会话里按 `.agents/agents/<名称>.md` 的职责完成。
- 在库里改了 `CLAUDE.md` 或 `.claude/ECONOMICS-RESEARCH.md` 后，运行 `.\Sync-AgentsMd.ps1 -VaultPath <库>` 把改动同步进 `AGENTS.md` 区块（`-Check` 只检查不写；区块之外的内容不动，原文件另存 `AGENTS.md.bak`）。
- 修改 Skill 或规则时改 `payload/.claude/` 下的源文件，再用 `-Update` 重新生成；不要直接改 `.agents/` 或 `AGENTS.md` 区块。

## 10. 常见问题
- **`/agents` 看不到 Agent**：确认在 Vault 根目录启动 `claude`，且 `.claude/agents/` 下有文件；改动后重启会话。
- **安装脚本提示“跳过(已存在)”**：正常，说明保护了你已有的文件。想获取新版内容，用 `-Update`：已存在且有差异的文件会生成 `<文件>.new`（如 `SKILL.md.new`，不会被当作 Skill/Agent 加载），原文件不动，你人工比对合并。
- **怎么确认安装器没坏**：运行 `tests/run.ps1`（5.1 与 pwsh 7 各一次），覆盖安装、幂等、保留中文 CLAUDE.md、`-WhatIf`、`-Update`、`-WithHooks`、两个 hook 与 lint。
- **中文乱码**：用 UTF-8 打开；`.ps1` 已带 BOM，Windows PowerShell 5.1 与 pwsh 7 均可运行。
- **`-WithUpstream`**：需同时给 `-RepoUrl`；上游构建参数未经本项目验证，运行前请先读其 `launchme.sh`。
- **卸载**：本项目不提供自动卸载。按 `README` 列出的文件手动删除；安装前的 `CLAUDE.md` 等备份在 `_erc-backups/<时间戳>/`。
