[CmdletBinding()]
param(
    [string]$VaultPath = "D:\ManagementCaseWiki",
    [switch]$Check   # 只检查是否同步，不写文件（不同步时退出码 1）
)
# 以库里当前的 CLAUDE.md + .claude/MANAGEMENT-CASE-RESEARCH.md 为准，重新生成 AGENTS.md 中的 ERC 区块。
# 只改带标记的区块，区块之外的内容不动；写入前把原 AGENTS.md 另存为 AGENTS.md.bak。
$ErrorActionPreference = "Stop"
$builder = Join-Path $PSScriptRoot "tools\build_platform.py"
$vault = [IO.Path]::GetFullPath($VaultPath)
if ($Check) { & python -X utf8 $builder sync-vault $vault --check } else { & python -X utf8 $builder sync-vault $vault }
exit $LASTEXITCODE
