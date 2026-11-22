[CmdletBinding()]
param([Parameter(Mandatory)][string]$VaultPath)
$ErrorActionPreference = "Stop"
$VaultPath = [System.IO.Path]::GetFullPath($VaultPath)
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot "tools\manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$agents = @($manifest.agents)
$skills = @($manifest.skills)
$errors = @()
function Get-Front([string]$Path) {
    $t = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ($t -notmatch '(?s)^---\r?\n(.*?)\r?\n---') { return $null }
    $h = @{}
    foreach ($l in $Matches[1] -split '\r?\n') { if ($l -match '^([\w-]+):\s*(.*)$') { $h[$Matches[1]] = $Matches[2].Trim('"') } }
    $h
}
function Test-Files([string[]]$Paths) {
    foreach ($m in $Paths) { if (-not (Test-Path (Join-Path $VaultPath $m))) { $script:errors += "缺少文件: $m" } }
}
function Test-Defs([string]$Root) {
    $validAccess = "raw","redacted","verified_only"
    $validTask = "open-ended","outcome-gradable"
    foreach ($a in $agents) {
        $p = Join-Path $VaultPath "$Root\agents\$a.md"
        if (-not (Test-Path $p)) { $script:errors += "缺少 agent: $Root\agents\$a.md"; continue }
        $f = Get-Front $p
        if (-not $f -or $f.name -ne $a -or -not $f.description) { $script:errors += "agent frontmatter 无效: $Root\agents\$a.md" }
        if ($f -and ($validAccess -notcontains $f.data_access_level -or $validTask -notcontains $f.task_type)) { $script:errors += "agent 缺少或无效的 data_access_level/task_type: $Root\agents\$a.md" }
    }
    foreach ($s in $skills) {
        $p = Join-Path $VaultPath "$Root\skills\$s\SKILL.md"
        if (-not (Test-Path $p)) { $script:errors += "缺少 skill: $Root\skills\$s"; continue }
        $f = Get-Front $p
        if (-not $f -or $f.name -ne $s -or -not $f.description) { $script:errors += "skill frontmatter 无效（name 须等于目录名）: $Root\skills\$s" }
        if ($f -and ($validAccess -notcontains $f.data_access_level -or $validTask -notcontains $f.task_type)) { $script:errors += "skill 缺少或无效的 data_access_level/task_type: $Root\skills\$s" }
    }
}

# 按已安装的内容判断平台
$hasClaude = (Test-Path (Join-Path $VaultPath ".claude\skills")) -or (Test-Path (Join-Path $VaultPath "CLAUDE.md"))
$hasAgents = (Test-Path (Join-Path $VaultPath ".agents\skills")) -or (Test-Path (Join-Path $VaultPath "AGENTS.md"))
if (-not ($hasClaude -or $hasAgents)) { $errors += "未发现任何平台的安装（.claude/ 或 .agents/）" }

Test-Files @($manifest.meta_required | ForEach-Object { $_ -replace '/', '\' })
foreach ($d in @($manifest.required_dirs | ForEach-Object { $_ -replace '/', '\' })) { if (-not (Test-Path (Join-Path $VaultPath $d))) { $errors += "缺少目录: $d" } }

if ($hasClaude) {
    Test-Defs ".claude"
    Test-Files @($manifest.claude_required | ForEach-Object { $_ -replace '/', '\' })
    $rc = Join-Path $VaultPath "CLAUDE.md"
    if (-not (Test-Path $rc) -or (Get-Content $rc -Raw) -notmatch [regex]::Escape("@.claude/MANAGEMENT-CASE-RESEARCH.md")) { $errors += "根 CLAUDE.md 未 import MANAGEMENT-CASE-RESEARCH.md" }
    $sj = Join-Path $VaultPath ".claude\settings.json"
    if (Test-Path $sj) {
        $st = [IO.File]::ReadAllText($sj)
        foreach ($h in @($manifest.hooks_claude)) {
            if ($st -match [regex]::Escape($h) -and -not (Test-Path (Join-Path $VaultPath ".claude\hooks\$h"))) { $errors += "settings.json 引用了 hook 但文件缺失: $h" }
        }
    }
    $claudeCli = Get-Command claude -ErrorAction SilentlyContinue
    if ($claudeCli -and (Test-Path (Join-Path $VaultPath ".claude"))) {
        $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        $vOut = (& $claudeCli.Source plugin validate (Join-Path $VaultPath ".claude") 2>&1 | Out-String).Trim()
        $vRc = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        if ($vRc -ne 0) { $errors += "claude plugin validate 未通过: $vOut" }
    }
}
if ($hasAgents) {
    Test-Defs ".agents"
    Test-Files @($manifest.agents_required | ForEach-Object { $_ -replace '/', '\' })
    $am = Join-Path $VaultPath "AGENTS.md"
    if (-not (Test-Path $am)) { $errors += "缺少根 AGENTS.md" }
    else {
        $bytes = [IO.File]::ReadAllBytes($am).Length
        if ([IO.File]::ReadAllText($am) -notmatch "ERC:BEGIN") { $errors += "AGENTS.md 中没有 Management Case Crew / Economics Research Crew 区块" }
        if ($bytes -gt 24000) { $errors += "AGENTS.md 为 $bytes 字节，超过 Antigravity 规则文件上限 24000（超出部分会被截断）" }
    }
    $hj = Join-Path $VaultPath ".agents\hooks.json"
    if (Test-Path $hj) {
        $ht = [IO.File]::ReadAllText($hj)
        try { $null = $ht | ConvertFrom-Json } catch { $errors += ".agents\hooks.json 不是有效 JSON" }
        foreach ($h in @($manifest.hooks_agy)) {
            if ($ht -match [regex]::Escape($h) -and -not (Test-Path (Join-Path $VaultPath ".agents\hooks\$h"))) { $errors += "hooks.json 引用了 hook 但文件缺失: $h" }
        }
    }
}
if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Host " x $_" -ForegroundColor Red }; exit 1 }
$where = @(); if ($hasClaude) { $where += "Claude Code(.claude)" }; if ($hasAgents) { $where += "Antigravity/Codex(.agents + AGENTS.md)" }
Write-Host "结构检查通过（$($agents.Count) agents, $($skills.Count) skills；平台：$($where -join '、')）。仍需在各 CLI 中确认可识别（Claude：/agents、/skills）。" -ForegroundColor Green
