# Management Case Research Crew

面向管理学单一案例研究（包含税法合规、偷漏税治理与税收筹划方向，适用于 MBA 工商管理硕士学位论文与案例分析）的研究环境扩展，支持 Claude Code、Antigravity CLI（`agy`）与 Codex CLI。

## 设计
- 7 个研究 Subagents、14 个 Skills（含 `/research-pipeline` 研究总协调与质量闭环，以及 `/case-design-audit`、`/case-data-analysis`、`/tax-policy-analysis`、`/ingest-source`、`/query-wiki`、`/wiki-lint` 等）、研究规范与 MBA 论文模板。
- 路由规则与角色映射见 [docs/USAGE.md](docs/USAGE.md) 第 4 节。
- 借鉴 llm_wiki 的“可积累 wiki”思路（purpose / index / log / 两步摄入 / lint）与 My-Brain-Is-Full-Crew 的 hooks 强制执行、安装器回归测试。
- 不覆盖已有 `CLAUDE.md`、`.mcp.json`、`.claude/settings.json`；不安装 MCP、不启用上游 Hooks。
- 上游框架（My-Brain-Is-Full-Crew）为**可选**：加 `-WithUpstream` 才会克隆并在隔离目录构建。

## 安装
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -WhatIf   # 先预演
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki"           # 仅安装本扩展（默认 -Platform auto）
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -Platform all       # 指定平台：auto | claude | agy | codex | all
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -WithHooks            # 可选：安装 hooks（合并 settings.json）
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -Update               # 升级：差异文件生成 .new，不覆盖
.\Test-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki"
```
脚本只新增文件，已存在的文件一律跳过并列出；改动前备份 `CLAUDE.md`、`.mcp.json`、`.claude/settings.json`、`AGENTS.md`、`.agents/hooks.json` 到 `_erc-backups/<时间戳>/`。

### 编排层（Research Director）
`/research-pipeline` 通过 `.claude/scripts/orchestrator.py` 维护项目状态 `01-Research-Projects/<项目>/STATE.json` 和派出日志 `Meta/run-ledger.jsonl`（只通过脚本修改）：`init / status / next / artifact / verify / gate / fail / recover / enforce / log`。阶段定义在 `.claude/pipeline-stages.json`，交接模板在 `Templates/handoff.md`。
- **关卡只由研究者决定：** 脚本需要 `--note`；`gate` 命令经 hook 触发权限提示，研究者确认后才执行。
- **Claude Code 下的强制（`-WithHooks`）：** 不能派出后续阶段的 Agent、重试（每个 Agent 每阶段最多 2 次）用尽后不能再派、同时运行数不得超过阶段上限（默认 1，S3 为 2，硬上限 3）；直接编辑 `STATE.json` / 账本会被拦。

### MBA 案例论文写作与人机协作（S8–S12）
- 流程：大纲 `/paper-outline`（内置 `Templates/venues/venue-mba-thesis-cn.md` 模板）→ 引文与法规 `/literature-review` → 成稿 `/paper-draft` → 精修 `/paper-refine`（最多 3 轮，改进才接受）→ 终检；每步有研究者检查点 C1–C5，规则见 `Meta/collaboration-protocol.md`。
- `paper_tools.py`：引文表（Crossref 联网核验；中文文献与税法文件标为人工核验，法规须写发文机关、文号与生效日期；`--offline` 或 `ERC_OFFLINE=1` 可关闭）、结果登记簿（正文财务/税负数字写成 `{{res:id}}`）、精修判定、`report` 指标。
- 稿内标记：引用 `[@key]`、数字 `{{res:id}}`、AI 提问 `⟦问：…⟧`、研究者回答 `⟦答：…⟧`。

### 多平台（自适应）
`-Platform auto`（默认）检测本机已安装的 `claude`、`agy`、`codex`，只为检测到的平台生成文件；都没检测到时安装 Claude Code 版。`payload/.claude/` 是唯一源，其他平台的文件在安装时生成（需要 python）。

| 平台 | 规则 | Skills | Agents | Hooks（`-WithHooks`） |
|---|---|---|---|---|
| Claude Code | `CLAUDE.md` + `.claude/MANAGEMENT-CASE-RESEARCH.md` | `.claude/skills/` | `.claude/agents/` | `.claude/settings.json` |
| Antigravity（agy） | 根 `AGENTS.md` 中带标记的区块（自包含，≤24 KB） | `.agents/skills/` | `.agents/agents/`（subagent） | `.agents/hooks.json` 的 `economics-research-crew` 键 |
| Codex CLI | 同上 `AGENTS.md` | `.agents/skills/` | `.agents/agents/` 作为角色说明读取 | 无（原始材料保护仅靠规则文本） |

`.\Sync-AgentsMd.ps1` 以库里当前的 `CLAUDE.md` 为准重新生成 `AGENTS.md` 区块，保持两者一致。

## 用法
`/research-question` `/literature-review` `/theory-modeling` `/tax-policy-analysis` `/case-design-audit` `/case-data-analysis` `/academic-review` `/ingest-source` `/query-wiki` `/wiki-lint` `/paper-outline` `/paper-draft` `/paper-refine` `/research-pipeline`

## 规范摘要
原始数据与来源只读；不删除文件；不虚构文献/法条/处罚文号/企业财务数据；单一案例须建立证据链与三角验证；严格区分合法税收筹划与偷漏税边界；税法核验时效。

## 验证流程
1. `Test-ManagementCaseCrew.ps1`：文件存在、frontmatter 合法（name/description）、agent 名与文件名一致、根 CLAUDE.md 含 import、`AGENTS.md` ≤ 24,000 字节。
2. 回归测试：`powershell -NoProfile -File tests\run.ps1` 与 `pwsh -NoProfile -File tests\run.ps1`（全部在临时目录进行）。
