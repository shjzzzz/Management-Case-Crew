# Management Case Crew

面向**管理学（含税法合规、偷漏税治理与税收筹划）单一案例研究与 MBA 学位论文**的 AI 研究协同套件，把 Obsidian 知识库升级为可复现、可核验、支持多平台（Claude Code / Antigravity / Codex）的案例研究工作区。

> **核心原则**：AI 是研究协作者，不是学术裁决者；绝不覆盖既有文件、绝不修改原始数据（`06-Data/raw`、`03-Literature/_sources`）、绝不虚构文献/法条/财报数字/访谈原话；所有阶段关卡与最终结论均由研究者拍板。

## 核心架构
- **四层知识架构 + Meta 控制面**：
  - **Tier 0 原始只读**：`00-Inbox/`、`03-Literature/_sources/`、`06-Data/raw/`、根目录既有税法/管理笔记（hook 保护只读）。
  - **Tier 1 复利知识图谱**：`03-Literature/`、`04-Theories/`、`05-Methods/`、`08-Research-Notes/`、`MOC/`。
  - **Tier 2 项目执行隔离**：`01-Research-Projects/<项目>/`（仅 `PROJECT.md` 进双链图，`paper/` 过程稿隔离）、`06-Data/{processed,metadata}/`、`07-Code/{python,R,stata}/`。
  - **Tier 3 交付归档**：`09-Writing/`（非完整项目的独立案例简报/讲义）、`10-Archive/`。
  - **Meta 控制面**：规范（`purpose`/`research-standards`/`collaboration-protocol`/`style-guide`/`mechanism-library`/`ai-tells.json`/`vault-map`）、账本（`index`/`log`/`source-registry`/`review-queue`/`decisions`/`constraints`/`aliases.csv`）、脚本独占机读文件（`citation-map.json`/`results-ledger.json`/`run-ledger.jsonl`/`folder-map.md`/`link-map.md`）。
- **两张自动生成地图（`wiki_lint.py map`）**：生成完整版 `Meta/folder-map.md`（文件夹地图）与 `Meta/link-map.md`（Obsidian 双链枢纽/邻接表/断链/孤立页/重名检测），并在 `CLAUDE.md` 与 `AGENTS.md` 中同步嵌入精简双地图（严守 24,000 字节上限）。
- **17 个 Skills + 7 个 Agents**：覆盖 S1–S12 全周期（选题 → 文献与 Kumar 缺口表 → 管理框架/税法底线 → 单案例设计与三角验证 → 财务/ETR 测算与质性编码 → MBA 盲审预审与 7 类 AI 失效闸门 → 大纲 → 引文与 EndNote/Zotero 交换 → 成稿 → 清单复核精修/返修 → `/paper-polish` 去 AI 味润色 → 终检与知识回流），并内置 MIT 许可的 `/scientific-visualization`（出版级图表）与 `/thu-digitizer`（年报/图表数据提取）。
- **单一事实清单与跨平台安装**：`tools/manifest.json` 驱动 Windows PowerShell（`Install-ManagementCaseCrew.ps1`）、Python CLI（`tools/mcc_cli.py`）与 macOS/Linux（`install.sh`）；`tools/build_platform.py` 由 `.claude/` 正本自动构建 `.agents/` 与 `AGENTS.md`。

## 快速开始

### Windows（PowerShell）
```powershell
# 预演安装（不写入）
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -Platform all -WithHooks -WhatIf

# 正式安装（可指定 -ProjectName 写入 CLAUDE.md 标题，默认取目录名）
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -Platform all -WithHooks

# 结构校验（含 frontmatter、data_access_level/task_type、24KB 上限与 hooks 检查）
.\Test-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki"

# 同步 CLAUDE.md 规则与地图到 AGENTS.md（加 -Check 仅校验不写入）
.\Sync-AgentsMd.ps1 -VaultPath "D:\ManagementCaseWiki"
```

### macOS / Linux / 跨平台 Python CLI
```bash
./install.sh --vault ~/ManagementCaseWiki --platform all --with-hooks
./install.sh test --vault ~/ManagementCaseWiki
./install.sh sync --vault ~/ManagementCaseWiki
```

### 升级已有知识库
```powershell
.\Install-ManagementCaseCrew.ps1 -VaultPath "D:\ManagementCaseWiki" -Platform all -WithHooks -Update
```
`-Update` 绝不覆盖已有文件：仅有差异的文件会生成 `*.new` 副本供人工比对合并，同时在 `_erc-backups/` 保留备份。

## 测试与验证
```powershell
# 全量测试（支持 -Section 1,10,17,18 按节调试）
powershell -NoProfile -File tests\run.ps1
pwsh -NoProfile -File tests\run.ps1
```
