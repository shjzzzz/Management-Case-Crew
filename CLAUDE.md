# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Management Case Crew（开发仓库）

这是**安装包源码**，不是研究库。`payload/` 由安装器装进用户的 Obsidian 库；`payload/CLAUDE.template.md` 是装给库的模板，不是本文件。

## 目录
- `payload/`：必装内容（17 个 Skill、7 个 Agent、Meta、Templates、hooks、scripts）。
- `tools/`（单一清单 `manifest.json`、跨平台安装 CLI `mcc_cli.py`、多平台构建器 `build_platform.py`、hooks 合并器、ARS 追踪）、`tests/`、`docs/`、`README.md`。

## 验证（改动后必跑，两个宿主都要过）
- `pwsh -NoProfile -File tests\run.ps1`
- `powershell -NoProfile -File tests\run.ps1`
- 支持按节调试：`pwsh -NoProfile -File tests\run.ps1 -Section 10,12`（省略 `-Section` 时全量运行）。

## 规则
- 改 `payload/` 里 Skill / Agent / Meta / Hook 的数量或名称，须先更新单一清单 `tools/manifest.json`，再同步 `README.md`、`docs/USAGE.md`、`tests/run.ps1` 的数字。
- 新增第三方 Skill 前先确认许可证；仅 MIT 等允许再分发的可进 `payload/`，并附 LICENSE。
- 行尾：`*.sh`、`*.py` 用 LF；`.ps1` 保留 BOM。
- 不要提交 `_erc-backups/`、`tasks/`；push 前需经用户确认。

## 常用命令
- 安装到库（预演不写入）：`.\Install-ManagementCaseCrew.ps1 -VaultPath <库> -WhatIf`；常用开关 `-ProjectName`（写入库 CLAUDE.md 标题，默认目录名）、`-Platform auto|claude|agy|codex|all`、`-WithHooks`、`-Update`（差异写 `.new`，不覆盖）。
- 跨平台等价入口：`./install.sh --vault <库> ...` 或 `python tools/mcc_cli.py install|test|sync|check-ars`。
- 校验已安装的库：`.\Test-ManagementCaseCrew.ps1 -VaultPath <库>`。
- 同步 AGENTS.md 的 ERC 区块：`.\Sync-AgentsMd.ps1 -VaultPath <库> [-Check]`。
- `tests/refmgr_selftest.py <库>/.claude/scripts/paper_tools.py <库>`：离线测 EndNote/Zotero 交换。
- `tests/routing_eval.py --vault <一次性库>`：**消耗 Claude Code 额度**，只在用户明确要求时运行。

## 架构（需跨文件理解）
- **单一事实来源**：`payload/.claude/` 是内容正本，`tools/manifest.json` 是安装/校验清单正本（供 `Install-ManagementCaseCrew.ps1`、`Test-ManagementCaseCrew.ps1`、`tools/mcc_cli.py` 共用）。`tools/build_platform.py` 从正本生成 agy / Codex 的 `.agents/`（脚本路径改写）与 `AGENTS.erc.md`，不要手改生成物。
- **三条安装路径**：`Install-ManagementCaseCrew.ps1`（PS 5.1/7）与 `tools/mcc_cli.py`（Python）实现同一套逻辑，行为必须一致；`install.sh` 只是 `mcc_cli.py` 的封装。改安装行为须两处同改。
- **知识地图引擎**：`payload/.claude/scripts/wiki_lint.py map` 是唯一事实来源，生成完整版 `Meta/folder-map.md` 与 `Meta/link-map.md`，并把精简双地图写入 `CLAUDE.md` 与 `AGENTS.md` 的 `<!-- ERC:MAP:BEGIN/END -->` 区块（守住 24,000 字节上限）。
- **hooks 合并**：`payload/.claude/settings.hooks.json` 是片段，经 `tools/merge_hooks.py` 幂等并入用户 `settings.json`（按脚本文件名判重，不覆盖其他键）；Windows 用 `python`，macOS/Linux 自适应 `python3`。
