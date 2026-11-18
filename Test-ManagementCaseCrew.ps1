[CmdletBinding()]
param([string]$VaultPath = "D:\ManagementCaseWiki")
$ErrorActionPreference = "Stop"
$VaultPath = [System.IO.Path]::GetFullPath($VaultPath)
$agents = "literature-agent","theory-agent","tax-policy-agent","case-data-agent","case-design-agent","academic-reviewer","paper-writer-agent"
$skills = "research-question","literature-review","theory-modeling","tax-policy-analysis","case-design-audit","case-data-analysis","academic-review","ingest-source","query-wiki","wiki-lint","research-pipeline","paper-outline","paper-draft","paper-refine"
$errors = @()
function Get-Front([string]$Path) {
    $t = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ($t -notmatch '(?s)^---\r?\n(.*?)\r?\n---') { return $null }
    $h = @{}
    foreach ($l in $Matches[1] -split '\r?\n') { if ($l -match '^([\w-]+):\s*(.*)$') { $h[$Matches[1]] = $Matches[2].Trim('"') } }
    $h
}
function Test-Defs([string]$Root) {
    foreach ($a in $agents) {
        $p = Join-Path $VaultPath "$Root\agents\$a.md"
        if (-not (Test-Path $p)) { $script:errors += "缺少 agent: $Root\agents\$a.md"; continue }
        $f = Get-Front $p
        if (-not $f -or $f.name -ne $a -or -not $f.description) { $script:errors += "agent frontmatter 无效: $Root\agents\$a.md" }
    }
    foreach ($s in $skills) {
        $p = Join-Path $VaultPath "$Root\skills\$s\SKILL.md"
        if (-not (Test-Path $p)) { $script:errors += "缺少 skill: $Root\skills\$s"; continue }
        $f = Get-Front $p
        if (-not $f -or $f.name -ne $s -or -not $f.description) { $script:errors += "skill frontmatter 无效（name 须等于目录名）: $Root\skills\$s" }
    }
}

# 按已安装的内容判断平台
$hasClaude = (Test-Path (Join-Path $VaultPath ".claude\skills")) -or (Test-Path (Join-Path $VaultPath "CLAUDE.md"))
$hasAgents = (Test-Path (Join-Path $VaultPath ".agents\skills")) -or (Test-Path (Join-Path $VaultPath "AGENTS.md"))
if (-not ($hasClaude -or $hasAgents)) { $errors += "未发现任何平台的安装（.claude/ 或 .agents/）" }

foreach ($m in "Meta\purpose.md","Meta\index.md","Meta\review-queue.md","Meta\vault-map.md","Meta\research-standards.md","Meta\source-registry.md","Meta\research-log.md") {
    if (-not (Test-Path (Join-Path $VaultPath $m))) { $errors += "缺少文件: $m" }
}
foreach ($d in "06-Data\raw","06-Data\processed","07-Code") { if (-not (Test-Path (Join-Path $VaultPath $d))) { $errors += "缺少目录: $d" } }

if ($hasClaude) {
    Test-Defs ".claude"
    foreach ($m in ".claude\MANAGEMENT-CASE-RESEARCH.md",".claude\scripts\wiki_lint.py",".claude\scripts\orchestrator.py",".claude\scripts\paper_tools.py",".claude\hooks\validate_paper.py",".claude\pipeline-stages.json","Templates\handoff.md","Templates\paper-outline.md","Meta\collaboration-protocol.md") { if (-not (Test-Path (Join-Path $VaultPath $m))) { $errors += "缺少文件: $m" } }
    $rc = Join-Path $VaultPath "CLAUDE.md"
    if (-not (Test-Path $rc) -or (Get-Content $rc -Raw) -notmatch [regex]::Escape("@.claude/MANAGEMENT-CASE-RESEARCH.md")) { $errors += "根 CLAUDE.md 未 import MANAGEMENT-CASE-RESEARCH.md" }
    $sj = Join-Path $VaultPath ".claude\settings.json"
    if (Test-Path $sj) {
        $st = [IO.File]::ReadAllText($sj)
        foreach ($h in "protect_raw.py","validate_frontmatter.py","routing_hint.py","orchestrator_guard.py","orchestrator_record.py") {
            if ($st -match [regex]::Escape($h) -and -not (Test-Path (Join-Path $VaultPath ".claude\hooks\$h"))) { $errors += "settings.json 引用了 hook 但文件缺失: $h" }
        }
    }
}
if ($hasAgents) {
    Test-Defs ".agents"
    foreach ($m in ".agents\scripts\wiki_lint.py",".agents\scripts\orchestrator.py",".agents\scripts\paper_tools.py",".agents\pipeline-stages.json") {
        if (-not (Test-Path (Join-Path $VaultPath $m))) { $errors += "缺少文件: $m" }
    }
    $am = Join-Path $VaultPath "AGENTS.md"
    if (-not (Test-Path $am)) { $errors += "缺少根 AGENTS.md" }
    else {
        $bytes = [IO.File]::ReadAllBytes($am).Length
        if ([IO.File]::ReadAllText($am) -notmatch "ERC:BEGIN") { $errors += "AGENTS.md 中没有 Economics Research Crew 区块" }
        if ($bytes -gt 24000) { $errors += "AGENTS.md 为 $bytes 字节，超过 Antigravity 规则文件上限 24000（超出部分会被截断）" }
    }
    $hj = Join-Path $VaultPath ".agents\hooks.json"
    if (Test-Path $hj) {
        try { $null = [IO.File]::ReadAllText($hj) | ConvertFrom-Json } catch { $errors += ".agents\hooks.json 不是有效 JSON" }
        $ht = [IO.File]::ReadAllText($hj)
        foreach ($h in "protect_raw.py","routing_hint.py") {
            if ($ht -match [regex]::Escape($h) -and -not (Test-Path (Join-Path $VaultPath ".agents\hooks\$h"))) { $errors += "hooks.json 引用了 hook 但文件缺失: $h" }
        }
    }
}
if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Host " x $_" -ForegroundColor Red }; exit 1 }
$where = @(); if ($hasClaude) { $where += "Claude Code(.claude)" }; if ($hasAgents) { $where += "Antigravity/Codex(.agents + AGENTS.md)" }
Write-Host "结构检查通过（$($agents.Count) agents, $($skills.Count) skills；平台：$($where -join '、')）。仍需在各 CLI 中确认可识别（Claude：/agents、/skills）。" -ForegroundColor Green
