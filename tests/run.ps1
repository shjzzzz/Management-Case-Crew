[CmdletBinding()]
param(
    # 可选节号过滤（如 -Section 11,17,18）；省略时全量运行全部节
    [string[]]$Section = @()
)
# Regression tests for the Economics Research Crew installer, hooks and lint.
# Run under each host you care about:
#   powershell -NoProfile -File tests\run.ps1   (Windows PowerShell 5.1)
#   pwsh -NoProfile -File tests\run.ps1         (PowerShell 7)
$ErrorActionPreference = "Stop"
$script:TotalSw = [System.Diagnostics.Stopwatch]::StartNew()
$script:SecSw = $null; $script:CurSec = $null
$secFilter = @($Section | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ })
if ($secFilter.Count -gt 0) {
    $deps = @{
        "2"=@("1"); "5"=@("1"); "7"=@("1"); "8"=@("1"); "9"=@("1");
        "13"=@("10","12"); "14"=@("10","12","13")
    }
    $expanded = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($s in $secFilter) {
        [void]$expanded.Add($s)
        if ($deps.ContainsKey($s)) { foreach ($d in $deps[$s]) { [void]$expanded.Add($d) } }
    }
    $secFilter = @($expanded)
}
function Begin-Sec([string]$Id, [string]$Title) {
    if ($script:CurSec -and $script:SecSw) {
        $script:SecSw.Stop()
        Write-Host ("  [{0}] done in {1:N2}s" -f $script:CurSec, $script:SecSw.Elapsed.TotalSeconds) -ForegroundColor DarkGray
    }
    if ($secFilter.Count -gt 0 -and ($secFilter -notcontains $Id.ToLower())) {
        $script:CurSec = $null; return $false
    }
    $script:CurSec = $Id
    $script:SecSw = [System.Diagnostics.Stopwatch]::StartNew()
    Write-Host "[$Id] $Title"
    return $true
}
$pkg = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $pkg "Install-ManagementCaseCrew.ps1"
$checker = Join-Path $pkg "Test-ManagementCaseCrew.ps1"
$payload = Join-Path $pkg "payload"
$py = (Get-Command python -ErrorAction Stop).Source
$enc = [System.Text.UTF8Encoding]::new($false)
# Windows PowerShell 5.1 pipes to native programs in ASCII by default; force UTF-8 so Chinese test input survives
$OutputEncoding = $enc
$shell = (Get-Process -Id $PID).Path
$script:pass = 0; $script:fail = 0

function Get-Sha([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $fs = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite); try { return [BitConverter]::ToString($sha.ComputeHash($fs)).Replace("-","") } finally { $fs.Dispose() } } finally { $sha.Dispose() }
}
function Ok([bool]$cond, [string]$name) {
    if ($cond) { $script:pass++; Write-Host "  PASS $name" -ForegroundColor Green }
    else { $script:fail++; Write-Host "  FAIL $name" -ForegroundColor Red }
}
function New-Vault { $d = Join-Path ([IO.Path]::GetTempPath()) ("erc-test-" + [guid]::NewGuid().ToString("N").Substring(0,8)); New-Item -ItemType Directory $d | Out-Null; $d }
function Run-Install([string]$Vault, [string[]]$Extra = @()) {
    $ErrorActionPreference = "Continue"
    if ($Extra -notcontains "-Platform") { $Extra = @("-Platform","claude") + $Extra }
    & $shell -NoProfile -File $installer -VaultPath $Vault @Extra *> $null
    return $LASTEXITCODE
}
function Run-Check([string]$Vault) { $ErrorActionPreference = "Continue"; & $shell -NoProfile -File $checker -VaultPath $Vault *> $null; return $LASTEXITCODE }
function Snapshot([string]$Vault) {
    Get-ChildItem -LiteralPath $Vault -Recurse -File -Force | Where-Object { $_.FullName -notmatch '_erc-backups' } |
        Sort-Object FullName | ForEach-Object { $_.FullName.Substring($Vault.Length) + ":" + (Get-Sha $_.FullName) }
}
function Hook([string]$Script, [hashtable]$Data) {
    $ErrorActionPreference = "Continue"
    $json = $Data | ConvertTo-Json -Depth 5 -Compress
    $json | & $py -X utf8 (Join-Path $payload ".claude\hooks\$Script") 2>$null
    return $LASTEXITCODE
}

Write-Host "Host: $($PSVersionTable.PSVersion)  python: $(& $py --version)"

# --- 1. fresh install -------------------------------------------------------
if (Begin-Sec "1" "fresh install") {
$v = New-Vault
Ok ((Run-Install $v) -eq 0) "install exit 0"
Ok ((Run-Check $v) -eq 0) "checker exit 0"
$skillCount = (Get-ChildItem (Join-Path $v ".claude\skills") -Directory).Count
$agentCount = (Get-ChildItem (Join-Path $v ".claude\agents") -Filter *.md).Count
Ok ($skillCount -eq 17) "17 skills (got $skillCount)"
Ok ($agentCount -eq 7) "7 agents (got $agentCount)"
Ok (Test-Path (Join-Path $v ".claude\skills\thu-digitizer\SKILL.md")) "built-in plot/table skills installed by default"
$extraSkillDirs = if (Test-Path (Join-Path $pkg "payload-extras\skills")) { @(Get-ChildItem (Join-Path $pkg "payload-extras\skills") -Directory) } else { @() }
if ($extraSkillDirs.Count -gt 0) {
$vx = New-Vault
Ok ((Run-Install $vx @("-WithExtras")) -eq 0) "install -WithExtras exit 0"
Ok ((Get-ChildItem (Join-Path $vx ".claude\skills") -Directory).Count -eq (17 + $extraSkillDirs.Count)) "-WithExtras adds only the extras on top of the 17 core skills"
Ok (-not (Test-Path (Join-Path $vx ".mcp.json"))) "-WithExtras installs no MCP config"
}
$mapRe = '(?s)<!-- ERC:MAP:BEGIN.*?<!-- ERC:MAP:END -->'
$tpl = ([IO.File]::ReadAllText((Join-Path $payload "CLAUDE.template.md")).Replace("`r`n","`n").Replace("{{PROJECT_NAME}}", (Split-Path -Leaf $v)) -replace $mapRe,"MAP").TrimEnd()
$got = ([IO.File]::ReadAllText((Join-Path $v "CLAUDE.md")).Replace("`r`n","`n") -replace $mapRe,"MAP").TrimEnd()
Ok ($got -eq $tpl) "root CLAUDE.md equals template (UTF-8, no mojibake)"
Ok (Test-Path (Join-Path $v "03-Literature\_sources")) "_sources dir created"

# --- 2. idempotent ----------------------------------------------------------
}
if (Begin-Sec "2" "idempotent") {
$before = Snapshot $v
Ok ((Run-Install $v) -eq 0) "second install exit 0"
$after = Snapshot $v
Ok ((($before -join "`n") -eq ($after -join "`n"))) "no file changed on re-install"

# --- 3. existing Chinese CLAUDE.md preserved ---------------------------------
}
if (Begin-Sec "3" "existing CLAUDE.md preserved") {
$v3 = New-Vault
$orig = "# 我的 CLAUDE`n中文内容：税收遵从`n"
[IO.File]::WriteAllText((Join-Path $v3 "CLAUDE.md"), $orig, $enc)
Ok ((Run-Install $v3) -eq 0) "install exit 0"
$c = [IO.File]::ReadAllText((Join-Path $v3 "CLAUDE.md"), $enc).Replace("`r`n","`n")
Ok ($c.StartsWith($orig)) "original Chinese content preserved byte-for-byte"
Ok (([regex]::Matches($c, [regex]::Escape("@.claude/MANAGEMENT-CASE-RESEARCH.md"))).Count -eq 1) "import appended once"
Run-Install $v3 | Out-Null
$c2 = [IO.File]::ReadAllText((Join-Path $v3 "CLAUDE.md"), $enc).Replace("`r`n","`n")
Ok ($c2 -eq $c) "re-run does not duplicate import"
Ok ((Get-ChildItem (Join-Path $v3 "_erc-backups") -Recurse -Filter CLAUDE.md).Count -ge 1) "backup of CLAUDE.md written"

# --- 4. -WhatIf writes nothing ------------------------------------------------
}
if (Begin-Sec "4" "-WhatIf") {
$v4 = New-Vault
Ok ((Run-Install $v4 @("-WhatIf")) -eq 0) "WhatIf exit 0"
Ok ((Get-ChildItem -LiteralPath $v4 -Force).Count -eq 0) "WhatIf left vault empty"

# --- 5. -Update writes .new, never overwrites -------------------------------
}
if (Begin-Sec "5" "-Update") {
$skill = Join-Path $v ".claude\skills\research-question\SKILL.md"
[IO.File]::AppendAllText($skill, "`nLOCAL EDIT`n", $enc)
$edited = (Get-Sha $skill)
Ok ((Run-Install $v @("-Update")) -eq 0) "update exit 0"
Ok ((Get-Sha $skill) -eq $edited) "edited file not overwritten"
Ok (Test-Path "$skill.new") ".new copy created for differing file"
$newCount = (Get-ChildItem $v -Recurse -Filter *.new -Force | Where-Object { $_.Name -ne "CLAUDE.md.new" }).Count
Ok ($newCount -eq 1) "only the differing file got a .new (got $newCount)"
Ok (-not (Test-Path (Join-Path $v "CLAUDE.md.new"))) "no CLAUDE.md.new when root CLAUDE.md equals template"
$v5 = New-Vault
[IO.File]::WriteAllText((Join-Path $v5 "CLAUDE.md"), "# old`n@.claude/MANAGEMENT-CASE-RESEARCH.md`n", $enc)
Run-Install $v5 @("-Update") | Out-Null
Ok ((Test-Path (Join-Path $v5 "CLAUDE.md.new")) -and ([IO.File]::ReadAllText((Join-Path $v5 "CLAUDE.md"), $enc)).StartsWith("# old")) "-Update writes CLAUDE.md.new, keeps CLAUDE.md"

# --- 6. -WithHooks merge ------------------------------------------------------
}
if (Begin-Sec "6" "-WithHooks") {
$v6 = New-Vault
New-Item -ItemType Directory (Join-Path $v6 ".claude") | Out-Null
$sj = Join-Path $v6 ".claude\settings.json"
[IO.File]::WriteAllText($sj, '{"permissions":{"allow":["Bash(ls)"]}}', $enc)
Ok ((Run-Install $v6 @("-WithHooks")) -eq 0) "install -WithHooks exit 0"
$st = [IO.File]::ReadAllText($sj, $enc) | ConvertFrom-Json
Ok ($st.permissions.allow[0] -eq "Bash(ls)") "existing permissions preserved"
Ok ($null -ne $st.hooks.PreToolUse -and $null -ne $st.hooks.PostToolUse) "hooks present"
$h1 = (Get-Sha $sj)
Run-Install $v6 @("-WithHooks") | Out-Null
Ok ((Get-Sha $sj) -eq $h1) "second merge is idempotent"
Ok ((Run-Check $v6) -eq 0) "checker exit 0 with hooks"
Ok ($st.hooks.PreToolUse[0].matcher -match "PowerShell") "PreToolUse matcher covers PowerShell tool"
# upgrade path: an old install whose matcher lacks PowerShell gets widened, not duplicated
$old = '{"hooks":{"PreToolUse":[{"matcher":"Write|Edit|Bash","hooks":[{"type":"command","command":"python x/protect_raw.py"}]}]}}'
[IO.File]::WriteAllText($sj, $old, $enc)
Run-Install $v6 @("-WithHooks") | Out-Null
$st2 = [IO.File]::ReadAllText($sj, $enc) | ConvertFrom-Json
$prot = @($st2.hooks.PreToolUse | Where-Object { ($_ | ConvertTo-Json -Depth 5) -match "protect_raw" })
Ok ($prot.Count -eq 1 -and $prot[0].matcher -match "PowerShell") "old matcher widened without duplicating hook"
# without -WithHooks, settings.json is never touched
$v6b = New-Vault
New-Item -ItemType Directory (Join-Path $v6b ".claude") | Out-Null
$sjb = Join-Path $v6b ".claude\settings.json"
[IO.File]::WriteAllText($sjb, '{"a":1}', $enc)
Run-Install $v6b | Out-Null
Ok (([IO.File]::ReadAllText($sjb, $enc)) -eq '{"a":1}') "settings.json untouched without -WithHooks"
# invalid JSON is refused and left untouched
$v6c = New-Vault
New-Item -ItemType Directory (Join-Path $v6c ".claude") | Out-Null
$sjc = Join-Path $v6c ".claude\settings.json"
[IO.File]::WriteAllText($sjc, '{not json', $enc)
$rc = Run-Install $v6c @("-WithHooks")
Ok ($rc -ne 0 -and ([IO.File]::ReadAllText($sjc, $enc)) -eq '{not json') "invalid settings.json refused, untouched"

# --- 7. protect_raw hook ------------------------------------------------------
}
if (Begin-Sec "7" "protect_raw hook") {
$rawDir = Join-Path $v "06-Data\raw"
$existing = Join-Path $rawDir "a.csv"
[IO.File]::WriteAllText($existing, "x,y`n1,2`n", $enc)
$proc = Join-Path $v "06-Data\processed\out.csv"
Ok ((Hook "protect_raw.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path=(Join-Path $rawDir "new.csv")}}) -eq 0) "Write NEW raw file allowed"
Ok ((Hook "protect_raw.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path=$existing}}) -eq 2) "Write EXISTING raw file blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Edit"; cwd=$v; tool_input=@{file_path=$existing}}) -eq 2) "Edit raw file blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Edit"; cwd=$v; tool_input=@{file_path="06-Data/raw/a.csv"}}) -eq 2) "Edit via relative path blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path="03-Literature/_sources/p.pdf"}}) -eq 0) "Write NEW source allowed"
Ok ((Hook "protect_raw.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path=$proc}}) -eq 0) "Write processed allowed"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="rm 06-Data/raw/a.csv"}}) -eq 2) "Bash rm raw blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="Remove-Item .\06-Data\raw\a.csv"}}) -eq 2) "PowerShell Remove-Item raw blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="echo x > 06-Data/raw/a.csv"}}) -eq 2) "Bash redirect into raw blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="cp /tmp/x.csv 06-Data/raw/"}}) -eq 2) "Bash cp into raw blocked"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="head -3 06-Data/raw/a.csv"}}) -eq 0) "Bash read of raw allowed"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="cp 06-Data/raw/a.csv 06-Data/processed/a.csv"}}) -eq 0) "Bash copy FROM raw allowed"
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v; tool_input=@{command="rm tmp.txt"}}) -eq 0) "unrelated rm allowed"
Ok ((Hook "protect_raw.py" @{tool_name="PowerShell"; cwd=$v; tool_input=@{command="Remove-Item .\06-Data\raw\a.csv"}}) -eq 2) "PowerShell TOOL Remove-Item raw blocked"
Ok ((Hook "protect_raw.py" @{tool_name="PowerShell"; cwd=$v; tool_input=@{command="Get-Content .\06-Data\raw\a.csv"}}) -eq 0) "PowerShell TOOL read raw allowed"
"not json" | & $py -X utf8 (Join-Path $payload ".claude\hooks\protect_raw.py") 2>$null
Ok ($LASTEXITCODE -eq 0) "malformed input fails open"

# --- 8. validate_frontmatter hook ---------------------------------------------
}
if (Begin-Sec "8" "validate_frontmatter hook") {
$good = Join-Path $v "08-Research-Notes\good.md"
$bad = Join-Path $v "08-Research-Notes\bad.md"
$tab = Join-Path $v "08-Research-Notes\tab.md"
New-Item -ItemType Directory (Split-Path $good) -Force | Out-Null
[IO.File]::WriteAllText($good, "---`ntype: query`n---`n# ok`n", $enc)
[IO.File]::WriteAllText($bad, "---`ntype: query`n# no closing`n", $enc)
[IO.File]::WriteAllText($tab, "---`ntype: query`n`tx: 1`n---`n", $enc)
Ok ((Hook "validate_frontmatter.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path=$good}}) -eq 0) "valid frontmatter passes"
Ok ((Hook "validate_frontmatter.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path=$bad}}) -eq 2) "missing closing --- reported"
Ok ((Hook "validate_frontmatter.py" @{tool_name="Write"; cwd=$v; tool_input=@{file_path=$tab}}) -eq 2) "tab in frontmatter reported"

Remove-Item -LiteralPath $good,$bad,$tab -Force

# --- 8b. routing_hint hook (offline) ----------------------------------------
}
if (Begin-Sec "8b" "routing_hint hook") {
function Hint([string]$Prompt) {
    $ErrorActionPreference = "Continue"
    $json = @{prompt=$Prompt} | ConvertTo-Json -Compress
    $out = $json | & $py -X utf8 (Join-Path $payload ".claude\hooks\routing_hint.py") 2>$null
    return ($out -join " ")
}
Ok ((Hint "帮我梳理税收遵从的国内外文献，找出研究缺口") -match "/literature-review") "literature intent -> /literature-review"
Ok ((Hint "单一案例如何做好三角验证与建构效度") -match "/case-design-audit") "case design intent -> /case-design-audit"
Ok ((Hint "我想完整做一个研究并推进") -match "/research-pipeline") "project intent -> /research-pipeline"
Ok ((Hint "固定效应和随机效应的核心区别是什么") -eq "") "conceptual question -> no hint"
Ok ((Hint "/literature-review 税收遵从") -eq "") "explicit slash command -> no hint"
# Hosts run hooks as plain `python script.py` (no -X utf8). On Chinese Windows python would decode
# stdin as GBK and no Chinese trigger would ever match; the scripts must read UTF-8 bytes themselves.
function HintPlain([string]$Json) {
    $ErrorActionPreference = "Continue"
    $out = $Json | & $py (Join-Path $payload ".claude\hooks\routing_hint.py") 2>$null
    return ($out -join " ")
}
Ok ((HintPlain (@{prompt="帮我梳理税收遵从的国内外文献"} | ConvertTo-Json -Compress)) -match "/literature-review") "Chinese prompt matches without -X utf8 (Claude host)"
Ok ((HintPlain (@{hookEventName="PreInvocation"; invocationNum=0; lastUserInput="单一案例如何做好三角验证与建构效度"} | ConvertTo-Json -Compress)) -match "case-design-audit") "Chinese prompt matches without -X utf8 (agy host)"

# --- 9. wiki_lint ---------------------------------------------------------------
}
if (Begin-Sec "9" "wiki_lint") {
$lint = Join-Path $v ".claude\scripts\wiki_lint.py"
$lit = Join-Path $v "03-Literature"
[IO.File]::WriteAllText((Join-Path $lit "_sources\a.pdf"), "pdf", $enc)
[IO.File]::WriteAllText((Join-Path $lit "good.md"), "---`ntype: literature`nsources: [03-Literature/_sources/a.pdf]`nverification: verified`n---`nsee [[other]]`n", $enc)
[IO.File]::WriteAllText((Join-Path $lit "other.md"), "---`ntype: literature`nsources: [https://doi.org/10.1/x]`nverification: unverified`n---`nback to [[good]]`n", $enc)
[IO.File]::WriteAllText((Join-Path $v "Meta\index.md"), "---`ntype: index`n---`n[[good]] [[other]]`n", $enc)
& $py -X utf8 $lint lint --vault $v *> $null
Ok ($LASTEXITCODE -eq 0) "clean wiki exit 0"
[IO.File]::WriteAllText((Join-Path $lit "broken.md"), "---`ntype: literature`nsources: [03-Literature/_sources/missing.pdf]`nverification: verified`n---`n[[nonexistent]]`n", $enc)
[IO.File]::WriteAllText((Join-Path $lit "nofm.md"), "---`ntype: literature`n# no closing`n", $enc)
$out = (& $py -X utf8 $lint lint --vault $v --json) -join "`n"
Ok ($LASTEXITCODE -eq 1) "defects give exit 1"
$j = $out | ConvertFrom-Json
Ok (@($j.findings | Where-Object { $_.check -eq "link" }).Count -ge 1) "broken wikilink found"
Ok (@($j.findings | Where-Object { $_.check -eq "sources" -and $_.level -eq "error" }).Count -ge 1) "unresolvable source found"
Ok (@($j.findings | Where-Object { $_.check -eq "frontmatter" -and $_.level -eq "error" }).Count -ge 1) "unclosed frontmatter found"
Ok (@($j.findings | Where-Object { $_.check -eq "orphan" }).Count -ge 1) "orphan page found"
Ok (@($j.findings | Where-Object { $_.check -eq "orphan" -and $_.file -match "good|other" }).Count -eq 0) "pages linked from index/notes are not orphans"
Ok (@($j.findings | Where-Object { $_.file -match "nofm" -and $_.check -eq "frontmatter" -and $_.level -eq "warning" }).Count -eq 0) "no follow-on warnings after frontmatter error"
$legacy = Join-Path $v "旧税法笔记.md"
[IO.File]::WriteAllText($legacy, "[[ghost]] no frontmatter", $enc)
$out2 = (& $py -X utf8 $lint lint --vault $v --json) -join "`n"
Ok (-not ($out2 -match "旧税法笔记")) "legacy notes outside scope are not scanned"
$h = & $py -X utf8 $lint hash (Join-Path $lit "_sources\a.pdf") --vault $v
Ok ($LASTEXITCODE -eq 0 -and ($h -join " ") -match "sha256: [0-9a-f]{64}") "hash prints sha256 for new source"
$hex = ((($h -join " ") -replace '.*sha256: ([0-9a-f]{64}).*','$1'))
Add-Content -LiteralPath (Join-Path $v "Meta\source-registry.md") -Value "| SRC-X | a.pdf | | | | $hex | |" -Encoding UTF8
& $py -X utf8 $lint hash (Join-Path $lit "_sources\a.pdf") --vault $v *> $null
Ok ($LASTEXITCODE -eq 10) "registered source detected (exit 10)"

# --- 10. multi-platform (agy / Codex) -----------------------------------------
}
if (Begin-Sec "10" "multi-platform") {
$v10 = New-Vault
Ok ((Run-Install $v10 @("-Platform","all","-WithHooks")) -eq 0) "all-platform install exit 0"
Ok ((Run-Check $v10) -eq 0) "checker passes for all platforms"
Ok ((Test-Path (Join-Path $v10 "CLAUDE.md")) -and (Test-Path (Join-Path $v10 ".claude\skills"))) "Claude files present"
$sk = @(Get-ChildItem (Join-Path $v10 ".agents\skills") -Directory)
Ok ($sk.Count -eq 17) ".agents has 17 skills (got $($sk.Count))"
$badName = @($sk | Where-Object { ([IO.File]::ReadAllText((Join-Path $_.FullName "SKILL.md"), $enc)) -notmatch ("(?m)^name:\s*" + [regex]::Escape($_.Name) + "\s*$") })
Ok ($badName.Count -eq 0) "every SKILL.md name equals its folder"
$ag = @(Get-ChildItem (Join-Path $v10 ".agents\agents") -Filter *.md)
Ok ($ag.Count -eq 7 -and @($ag | Where-Object { ([IO.File]::ReadAllText($_.FullName, $enc)) -notmatch "(?m)^subagent: true" }).Count -eq 0) "7 agy subagents with subagent: true"
$am = [IO.File]::ReadAllText((Join-Path $v10 "AGENTS.md"), $enc)
Ok ([IO.File]::ReadAllBytes((Join-Path $v10 "AGENTS.md")).Length -le 24000) "AGENTS.md within 24,000 bytes"
Ok ($am -match "ERC:BEGIN" -and $am -notmatch "(?m)^@\.claude/" -and $am -match "\.agents/scripts/wiki_lint\.py" -and $am -notmatch "Skill 工具") "AGENTS.md self-contained, paths and wording rewritten"
Ok (-not (@(Get-ChildItem (Join-Path $v10 ".agents\skills") -Recurse -Filter *.md | Where-Object { ([IO.File]::ReadAllText($_.FullName, $enc)) -match "\.claude/" }).Count)) "no .claude/ paths left in .agents skills"
$hj = [IO.File]::ReadAllText((Join-Path $v10 ".agents\hooks.json"), $enc) | ConvertFrom-Json
Ok ($null -ne $hj.'economics-research-crew'.PreToolUse -and $null -ne $hj.'economics-research-crew'.PreInvocation) "agy hooks.json has our key with PreToolUse + PreInvocation"
& $py -X utf8 (Join-Path $v10 ".agents\scripts\wiki_lint.py") lint --vault $v10 *> $null
Ok ($LASTEXITCODE -eq 0) "generated wiki_lint runs on a fresh vault (and skips .agents/)"
$before10 = Snapshot $v10
Ok ((Run-Install $v10 @("-Platform","all","-WithHooks")) -eq 0) "all-platform re-install exit 0"
Ok ((($before10 -join "`n") -eq ((Snapshot $v10) -join "`n"))) "no file changed on all-platform re-install"

# existing AGENTS.md / hooks.json are preserved
$v10b = New-Vault
New-Item -ItemType Directory (Join-Path $v10b ".agents") | Out-Null
[IO.File]::WriteAllText((Join-Path $v10b "AGENTS.md"), "# 我的规则`n保留这一行`n", $enc)
[IO.File]::WriteAllText((Join-Path $v10b ".agents\hooks.json"), '{"mine":{"Stop":[{"command":"echo hi"}]}}', $enc)
Ok ((Run-Install $v10b @("-Platform","agy","-WithHooks")) -eq 0) "agy install over existing files exit 0"
$am2 = [IO.File]::ReadAllText((Join-Path $v10b "AGENTS.md"), $enc)
Ok ($am2.StartsWith("# 我的规则`n保留这一行") -and $am2 -match "ERC:BEGIN") "existing AGENTS.md kept, block appended"
$hj2 = [IO.File]::ReadAllText((Join-Path $v10b ".agents\hooks.json"), $enc) | ConvertFrom-Json
Ok ($null -ne $hj2.mine -and $null -ne $hj2.'economics-research-crew') "existing hooks.json key kept, ours added"
Ok (-not (Test-Path (Join-Path $v10b "CLAUDE.md")) -and -not (Test-Path (Join-Path $v10b ".claude"))) "agy-only install leaves no Claude files"
Ok (@(Get-ChildItem (Join-Path $v10b "_erc-backups") -Recurse -File -Filter AGENTS.md).Count -eq 1) "existing AGENTS.md backed up"
# -Update with a stale block -> AGENTS.md.new, original untouched
[IO.File]::WriteAllText((Join-Path $v10b "AGENTS.md"), $am2.Replace("路由规则", "路由规则（旧）"), $enc)
$shaOld = Get-Sha (Join-Path $v10b "AGENTS.md")
Ok ((Run-Install $v10b @("-Platform","agy","-Update")) -eq 0) "agy -Update exit 0"
Ok ((Get-Sha (Join-Path $v10b "AGENTS.md")) -eq $shaOld -and (Test-Path (Join-Path $v10b "AGENTS.md.new"))) "stale block -> AGENTS.md.new, original untouched"
Ok (([IO.File]::ReadAllText((Join-Path $v10b "AGENTS.md.new"), $enc)).StartsWith("# 我的规则")) "AGENTS.md.new keeps user content"

# Codex-only: shared files, no agy hooks
$v10c = New-Vault
Ok ((Run-Install $v10c @("-Platform","codex","-WithHooks")) -eq 0) "codex install exit 0"
Ok ((Run-Check $v10c) -eq 0) "checker passes for codex"
Ok ((Test-Path (Join-Path $v10c "AGENTS.md")) -and -not (Test-Path (Join-Path $v10c ".agents\hooks.json")) -and -not (Test-Path (Join-Path $v10c ".agents\hooks"))) "codex: AGENTS.md, no agy hooks"

# CLAUDE.md <-> AGENTS.md sync
$syncer = Join-Path $pkg "Sync-AgentsMd.ps1"
function Run-Sync([string]$Vault, [string[]]$Extra = @()) { $ErrorActionPreference = "Continue"; & $shell -NoProfile -File $syncer -VaultPath $Vault @Extra *> $null; return $LASTEXITCODE }
Ok ((Run-Sync $v10 @("-Check")) -eq 0) "fresh install: CLAUDE.md and AGENTS.md are in sync"
$cm = Join-Path $v10 "CLAUDE.md"
[IO.File]::WriteAllText($cm, ([IO.File]::ReadAllText($cm, $enc).TrimEnd() + "`n`n## 我的补充规则`n- 同步测试标记 XYZ123`n"), $enc)
Ok ((Run-Sync $v10 @("-Check")) -eq 1) "after editing CLAUDE.md: -Check reports out of sync"
$shaAm = Get-Sha (Join-Path $v10 "AGENTS.md")
Ok ((Get-Sha (Join-Path $v10 "AGENTS.md")) -eq $shaAm) "-Check does not write"
Ok ((Run-Sync $v10) -eq 0) "sync exit 0"
Ok (([IO.File]::ReadAllText((Join-Path $v10 "AGENTS.md"), $enc)) -match "XYZ123") "edit propagated into AGENTS.md block"
Ok ((Test-Path (Join-Path $v10 "AGENTS.md.bak")) -and ((Run-Sync $v10 @("-Check")) -eq 0)) "backup written; now in sync"
Ok ((Run-Sync $v10b) -eq 0 -and ([IO.File]::ReadAllText((Join-Path $v10b "AGENTS.md"), $enc)).StartsWith("# 我的规则")) "sync keeps user content outside the block"

# agy hook input shapes
function AgyHook([string]$Script, [string]$Json) {
    $ErrorActionPreference = "Continue"
    $out = $Json | & $py -X utf8 (Join-Path $payload ".claude\hooks\$Script") 2>$null
    return (($out -join " ") + "|rc=$LASTEXITCODE")
}
$rawf = Join-Path $v10 "06-Data\raw\p.csv"; [IO.File]::WriteAllText($rawf, "a", $enc)
$jp = { param($tool,$args2) (@{toolCall=@{name=$tool; args=$args2}; cwd=$v10} | ConvertTo-Json -Depth 5 -Compress) }
Ok ((AgyHook "protect_raw.py" (& $jp "edit_file" @{Path=$rawf; Target="a"; Replacement="b"})) -match '"decision": "deny".*\|rc=0') "agy edit_file on raw -> deny JSON"
Ok ((AgyHook "protect_raw.py" (& $jp "write_file" @{Path=$rawf; Content="x"})) -match '"decision": "deny"') "agy write_file overwriting raw -> deny"
Ok ((AgyHook "protect_raw.py" (& $jp "write_file" @{Path=(Join-Path $v10 "06-Data\raw\new.csv"); Content="x"})) -match '^\{"decision":"ask"\}\|rc=0') "agy write_file creating new raw file -> ask (normal flow)"
Ok ((AgyHook "protect_raw.py" (& $jp "run_command" @{CommandLine="del 06-Data\raw\p.csv"})) -match '"decision": "deny"') "agy run_command deleting raw -> deny"
Ok ((AgyHook "protect_raw.py" (& $jp "read_file" @{Path=$rawf})) -match '^\{"decision":"ask"\}') "agy read_file -> ask (never allow)"
Ok ((AgyHook "protect_raw.py" '{"toolCall":broken') -match '^\{"decision":"ask"\}\|rc=0') "agy malformed input -> neutral JSON"
$pi0 = @{hookEventName="PreInvocation"; invocationNum=0; lastUserInput="帮我梳理税收遵从的国内外文献"} | ConvertTo-Json -Compress
$pi1 = @{hookEventName="PreInvocation"; invocationNum=1; lastUserInput="帮我梳理税收遵从的国内外文献"} | ConvertTo-Json -Compress
$pi2 = @{hookEventName="PreInvocation"; invocationNum=0; lastUserInput="固定效应是什么"} | ConvertTo-Json -Compress
Ok ((AgyHook "routing_hint.py" $pi0) -match 'injectSteps.*literature-review') "agy PreInvocation first call -> injected hint"
Ok ((AgyHook "routing_hint.py" $pi1) -match '^\{\}\|rc=0') "agy later invocation in same turn -> {}"
Ok ((AgyHook "routing_hint.py" $pi2) -match '^\{\}\|rc=0') "agy conceptual question -> {}"

# --- 11. orchestration layer ------------------------------------------------------
}
if (Begin-Sec "11" "orchestration layer") {
$v11 = New-Vault
Ok ((Run-Install $v11 @("-Platform","claude","-WithHooks")) -eq 0) "install with hooks exit 0"
Ok ((Run-Check $v11) -eq 0) "checker passes (orchestrator files + hook files present)"
$st = [IO.File]::ReadAllText((Join-Path $v11 ".claude\settings.json"), $enc) | ConvertFrom-Json
Ok ($null -ne $st.hooks.SubagentStart -and $null -ne $st.hooks.SubagentStop -and ($st.hooks.PreToolUse | ConvertTo-Json -Depth 6) -match "orchestrator_guard") "settings.json has guard + SubagentStart/Stop recorders"
$orc = Join-Path $v11 ".claude\scripts\orchestrator.py"
function Orc([string[]]$A) { $ErrorActionPreference = "Continue"; & $py -X utf8 $orc --vault $v11 @A *> $null; return $LASTEXITCODE }
function OrcOut([string[]]$A) {
    $ErrorActionPreference = "Continue"
    $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc   # python prints UTF-8; decode it as such
    try { return ((& $py -X utf8 $orc --vault $v11 @A 2>&1) -join "`n") } finally { [Console]::OutputEncoding = $prev }
}
function Guard([string]$Tool, [hashtable]$In) {
    $ErrorActionPreference = "Continue"
    $json = @{tool_name=$Tool; tool_input=$In; cwd=$v11} | ConvertTo-Json -Depth 5 -Compress
    $out = $json | & $py (Join-Path $v11 ".claude\hooks\orchestrator_guard.py") 2>$null
    return "$(($out -join ' '))|rc=$LASTEXITCODE"
}
Ok ((Guard "Agent" @{subagent_type="academic-reviewer"}) -match "rc=0") "no active project -> agent dispatch allowed"
Ok ((Orc @("init","01-Research-Projects\demo")) -eq 0) "init creates STATE.json"
Ok ((Orc @("init","01-Research-Projects\demo")) -ne 0) "init refuses to re-initialise"
Ok ((Orc @("gate","--decision","pass","--note","x")) -eq 1) "gate pass blocked while S1 has no artifact"
Ok ((Orc @("gate","--decision","pass")) -ne 0) "gate without --note refused"
[IO.File]::WriteAllText((Join-Path $v11 "Meta\q.md"), "question", $enc)
Ok ((Orc @("artifact","Meta\q.md")) -eq 0) "artifact registered"
Ok ((Orc @("artifact","..\..\outside.md")) -ne 0) "artifact outside vault refused"
Ok ((Orc @("gate","--decision","pass","--note","研究者确认问题")) -eq 0) "S1 gate passes with artifact + note"
Ok ((OrcOut @("status")) -match "当前阶段：S2") "now at S2"
# guard: ordering, retries, concurrency, gate prompt, protected files
Ok ((Guard "Agent" @{subagent_type="academic-reviewer"}) -match "rc=2") "skip ahead to reviewer (S6) at S2 -> blocked"
Ok ((Guard "Agent" @{subagent_type="Explore"}) -match "rc=0") "non-pipeline agent -> allowed"
Orc @("recover") | Out-Null
Ok ((Guard "Agent" @{subagent_type="literature-agent"}) -match "rc=0") "S2 literature-agent -> allowed"
Ok ((Guard "Agent" @{subagent_type="literature-agent"}) -match "rc=2") "second concurrent dispatch (limit 1) -> blocked"
Ok ((Orc @("recover")) -eq 0 -and ((Guard "Agent" @{subagent_type="literature-agent"}) -match "rc=0")) "recover frees stale pending dispatch"
Orc @("recover") | Out-Null
1..3 | ForEach-Object { Orc @("fail","--agent","literature-agent","--reason","timeout") | Out-Null }
Ok ((Guard "Agent" @{subagent_type="literature-agent"}) -match "rc=2") "retry budget used up -> blocked"
Ok ((Orc @("gate","--decision","revise","--note","研究者要求重做")) -eq 0 -and ((Guard "Agent" @{subagent_type="literature-agent"}) -match "rc=0")) "researcher revise resets retry budget"
Ok ((Guard "Bash" @{command="python .claude/scripts/orchestrator.py gate --decision pass --note ok"}) -match "permissionDecision.*ask") "gate via Bash forces a permission prompt"
Ok ((Guard "PowerShell" @{command="python .claude\scripts\orchestrator.py gate --decision pass --note ok"}) -match "permissionDecision.*ask") "gate via PowerShell forces a permission prompt"
Ok ((Guard "Bash" @{command="python .claude/scripts/orchestrator.py status"}) -match "^\|rc=0") "status via Bash not prompted"
Ok ((Guard "Edit" @{file_path=(Join-Path $v11 "01-Research-Projects\demo\STATE.json")}) -match "rc=2") "direct edit of STATE.json blocked"
Ok ((Guard "Write" @{file_path=(Join-Path $v11 "Meta\run-ledger.jsonl")}) -match "rc=2") "direct write of run-ledger blocked"
Ok ((Guard "Write" @{file_path=(Join-Path $v11 "Meta\note.md")}) -match "rc=0") "ordinary write not affected"
# the block reason is Chinese and must reach the host as UTF-8 (default Windows stderr codec is GBK)
$chkPy = Join-Path ([IO.Path]::GetTempPath()) ("erc-chk-" + [guid]::NewGuid().ToString("N").Substring(0,8) + ".py")
[IO.File]::WriteAllText($chkPy, @"
import subprocess, sys, json
inp = json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "academic-reviewer"}, "cwd": sys.argv[2]}).encode("utf-8")
p = subprocess.run([sys.executable, sys.argv[1]], input=inp, capture_output=True)
print("OK" if p.returncode == 2 and "不能跳阶段" in p.stderr.decode("utf-8") else "BAD")
"@, $enc)
$chkOut = & $py $chkPy (Join-Path $v11 ".claude\hooks\orchestrator_guard.py") $v11
Remove-Item -LiteralPath $chkPy -Force
Ok ($chkOut -eq "OK") "block reason reaches host as readable UTF-8"
Ok ((Orc @("recover")) -eq 0 -and (Orc @("enforce","off")) -eq 0 -and ((Guard "Agent" @{subagent_type="academic-reviewer"}) -match "rc=0")) "enforce off -> skip ahead allowed (still recorded)"
Orc @("enforce","on") | Out-Null
$null = "{broken" | & $py (Join-Path $v11 ".claude\hooks\orchestrator_guard.py") 2>$null
Ok ($LASTEXITCODE -eq 0) "malformed hook input fails open"
# recorder + ledger
$rec = @{hook_event_name="SubagentStart"; agent_type="literature-agent"; agent_id="a1"; cwd=$v11} | ConvertTo-Json -Compress
$rec | & $py (Join-Path $v11 ".claude\hooks\orchestrator_record.py") 2>$null
$rec2 = @{hook_event_name="SubagentStop"; agent_type="literature-agent"; agent_id="a1"; cwd=$v11; last_assistant_message="完成"} | ConvertTo-Json -Compress
$rec2 | & $py (Join-Path $v11 ".claude\hooks\orchestrator_record.py") 2>$null
$ledger = [IO.File]::ReadAllText((Join-Path $v11 "Meta\run-ledger.jsonl"), $enc)
Ok ($ledger -match '"event": "start"' -and $ledger -match '"event": "stop"' -and $ledger -match '"event": "gate"' -and $ledger -match '"event": "fail"') "ledger records start/stop/gate/fail"
Ok ($ledger -notmatch "完成") "ledger does not store agent message content"
# stage rules: S4 needs an analysis plan; return resets later stages
$j = (OrcOut @("status","--json")) | ConvertFrom-Json
Ok ($j.stage -eq "S2") "state survives (S2)"
foreach ($pair in @(@("S2","Meta\lit.md"),@("S3","Meta\mech.md"))) {
    [IO.File]::WriteAllText((Join-Path $v11 $pair[1]), "x", $enc)
    Orc @("artifact",$pair[1]) | Out-Null
    Orc @("gate","--decision","pass","--note","ok") | Out-Null
}
Ok ((OrcOut @("status")) -match "当前阶段：S4") "S2 and S3 passed -> S4"
[IO.File]::WriteAllText((Join-Path $v11 "Meta\design.md"), "x", $enc); [IO.File]::WriteAllText((Join-Path $v11 "Meta\other.md"), "x", $enc)
Orc @("artifact","Meta\design.md","Meta\other.md") | Out-Null
Ok ((Orc @("verify")) -eq 1) "S4 verify fails without an analysis-plan artifact"
[IO.File]::WriteAllText((Join-Path $v11 "Meta\analysis-plan.md"), "x", $enc)
Orc @("artifact","Meta\analysis-plan.md") | Out-Null
Ok ((Orc @("verify")) -eq 0) "S4 verify passes with analysis-plan"
Orc @("gate","--decision","pass","--note","ok") | Out-Null
Orc @("gate","--decision","return","--to","S2","--note","退回补文献") | Out-Null
$j = (OrcOut @("status","--json")) | ConvertFrom-Json
Ok ($j.stage -eq "S2" -and $j.stages.S4.status -eq "pending" -and $j.stages.S3.status -eq "pending") "return --to S2 resets later stages"
Ok ((Orc @("gate","--decision","return","--to","S6","--note","x")) -ne 0) "return to a later stage refused"
Ok ((Orc @("gate","--decision","stop","--note","研究者决定停止")) -eq 0 -and ((OrcOut @("status")) -match "状态：stopped")) "stop ends the project"
Ok ((Guard "Agent" @{subagent_type="academic-reviewer"}) -match "rc=0") "stopped project no longer enforces"
# bytecode caches in the package must not be copied into a user's vault
$cache = Join-Path $payload ".claude\scripts\__pycache__"
New-Item -ItemType Directory -Force $cache | Out-Null
[IO.File]::WriteAllText((Join-Path $cache "x.pyc"), "x", $enc)
$v11c = New-Vault
$null = Run-Install $v11c @("-Platform","claude")
Remove-Item -LiteralPath $cache -Recurse -Force
Ok (@(Get-ChildItem $v11c -Recurse -Force -Directory -Filter __pycache__ -ErrorAction SilentlyContinue).Count -eq 0) "installer does not copy __pycache__"
# agy / Codex get the script + stages file
$v11b = New-Vault
Ok ((Run-Install $v11b @("-Platform","all")) -eq 0 -and (Test-Path (Join-Path $v11b ".agents\scripts\orchestrator.py")) -and (Test-Path (Join-Path $v11b ".agents\pipeline-stages.json"))) "agy/Codex install includes orchestrator + stages"
& $py -X utf8 (Join-Path $v11b ".agents\scripts\orchestrator.py") --vault $v11b init 01-Research-Projects\demo *> $null
Ok ($LASTEXITCODE -eq 0) ".agents orchestrator runs (finds .agents/pipeline-stages.json)"
$sk = [IO.File]::ReadAllText((Join-Path $v11b ".agents\skills\research-pipeline\SKILL.md"), $enc)
Ok ($sk -match "\.agents/scripts/orchestrator\.py" -and $sk -notmatch "\.claude/scripts") "agy research-pipeline skill points to .agents/scripts"

# --- 12. paper architecture (paper_tools, stages S8-S12, validate_paper) -------------
}
if (Begin-Sec "12" "paper architecture") {
$v12 = New-Vault
Ok ((Run-Install $v12 @("-Platform","all","-WithHooks")) -eq 0 -and (Run-Check $v12) -eq 0) "install + checker pass with paper files"
$pt = Join-Path $v12 ".claude\scripts\paper_tools.py"
$mock = Join-Path $v12 "mock.json"
$mockObj = [ordered]@{ "title:example study of tax salience" = @(@{doi="10.9999/example.001"; title="Example Study of Tax Salience"; year=2009; venue="Example Journal"; authors=@("A. Author")}) ;
    "doi:10.0/wrong" = @(@{doi="10.0/wrong"; title="Some Other Paper"; year=2001; venue="X"; authors=@()}) }
[IO.File]::WriteAllText($mock, ($mockObj | ConvertTo-Json -Depth 6), $enc)
function PT([string[]]$A) { $ErrorActionPreference = "Continue"; $env:ERC_CROSSREF_MOCK = $mock; $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try { $o = ((& $py -X utf8 $pt --vault $v12 @A 2>&1) -join "`n"); return "$o|rc=$LASTEXITCODE" } finally { [Console]::OutputEncoding = $prev; Remove-Item Env:\ERC_CROSSREF_MOCK -ErrorAction SilentlyContinue } }
Ok ((PT @("cite","add","--key","author2009","--title","Example Study of Tax Salience","--year","2009")) -match "verified") "cite add: matching Crossref record -> verified"
Ok ((PT @("cite","add","--key","bad1","--title","Example Study of Tax Salience","--year","2009","--doi","10.0/wrong")) -match "mismatch") "cite add: DOI pointing to another title -> mismatch"
Ok ((PT @("cite","add","--key","ghostpaper","--title","Totally Invented Paper","--year","2015")) -match "unverified") "cite add: unknown work -> unverified"
Ok ((PT @("cite","add","--key","zh1","--title","某中文文献","--type","chinese")) -match "manual") "Chinese literature -> manual"
Ok ((PT @("cite","add","--key","law1","--title","某通知","--type","legal")) -match "文号") "legal source without doc number refused"
Ok ((PT @("cite","add","--key","law1","--title","某通知","--type","legal","--doc-no","X号","--effective","2020-01-01")) -match "manual") "legal source with doc number and date accepted (manual)"
Ok ((PT @("cite","add","--key","off1","--title","Example Study of Tax Salience","--offline")) -match "unverified") "--offline never queries Crossref"
Ok ((PT @("cite","confirm","--key","zh1")) -match "rc=1") "confirm without --note refused"
Ok ((PT @("cite","confirm","--key","zh1","--note","已在知网核对原文")) -match "已由研究者确认") "researcher confirm works with note"
$res = Join-Path $v12 "06-Data\processed\t.csv"
New-Item -ItemType Directory -Force (Split-Path $res) | Out-Null
[IO.File]::WriteAllText($res, "row,coef`nDID,-0.12345`n", $enc)
Ok ((PT @("results","import","06-Data\processed\t.csv","--prefix","t2")) -match "已登记 1") "results import registers cells"
Ok ((PT @("results","register","--id","n","--value","1000","--source","06-Data\processed\t.csv")) -match "n = 1000") "results register with source"
$dr = Join-Path $v12 "01-Research-Projects\demo\paper"
New-Item -ItemType Directory -Force $dr | Out-Null
$d1 = Join-Path $dr "draft.md"
[IO.File]::WriteAllText($d1, "系数为 {{res:t2.DID.coef:3}}，样本 {{res:n}} [@author2009; @zh1]。`n⟦问：是否加机制检验？⟧`n", $enc)
Ok ((PT @("cite","check",$d1)) -match "rc=0") "cite check passes when all keys are in the table"
Ok ((PT @("results","check",$d1)) -match "错误 0") "results check passes for registered ids"
Ok ((PT @("questions",$d1)) -match "rc=1") "unanswered researcher question detected"
Ok ((PT @("results","render",$d1,"-o",(Join-Path $dr "r.md"))) -match "rc=0" -and ([IO.File]::ReadAllText((Join-Path $dr "r.md"), $enc) -match "系数为 -0\.123，")) "render fills placeholders with requested decimals"
$d2 = Join-Path $dr "bad.md"
[IO.File]::WriteAllText($d2, "引用 [@nobody2000]，数字 {{res:nope}}，另有 0.045 与 12.5% 未链接。`n", $enc)
$o = PT @("cite","check",$d2); Ok ($o -match "rc=1" -and $o -match "nobody2000") "unknown citation key is an error"
$o = PT @("results","check",$d2); Ok ($o -match "rc=1" -and $o -match "nope" -and $o -match "没有链接") "unknown result id is an error; bare statistics warned"
Ok ((PT @("cite","check",$d1,"--strict")) -match "rc=0") "--strict passes when every cited work is verified or confirmed"
# source change makes a result stale
[IO.File]::WriteAllText($res, "row,coef`nDID,-0.99`n", $enc)
Ok ((PT @("results","check",$d1)) -match "已变化") "changed source file flags stale results"
# refinement rule
Ok ((PT @("--project","demo","refine","start",$d1)) -match "v0") "refine start snapshots v0"
$vd = Join-Path $dr "versions"
foreach ($n in "v1","v2") { Copy-Item (Join-Path $vd "v0.md") (Join-Path $vd "$n.md") }
Ok ((PT @("--project","demo","refine","record","--version","v0","--fatal","1","--major","4","--scores","a=5,b=6")) -match "baseline") "baseline recorded"
Ok ((PT @("--project","demo","refine","record","--version","v1","--fatal","1","--major","2","--scores","a=6,b=6")) -match "复评必须按基线清单") "re-review with direct counts is refused (baseline only)"
Ok ((PT @("--project","demo","refine","record","--version","v1","--carried-fatal","1","--carried-major","2","--scores","a=6,b=6")) -match "accept") "fewer Major (checklist) -> accept"
Ok ((PT @("--project","demo","refine","record","--version","v2","--carried-fatal","1","--new-fatal","1","--carried-major","1","--scores","a=7,b=7")) -match "revert") "new Fatal -> revert even if scores rise"
Ok ((PT @("--project","demo","refine","status")) -match "当前采用：v1") "current version stays v1 after revert"
Copy-Item (Join-Path $vd "v0.md") (Join-Path $vd "v3.md")
Ok ((PT @("--project","demo","refine","record","--version","v3","--carried-fatal","0","--carried-major","1","--new-major","0","--scores","a=7,b=7")) -match "v3：accept") "checklist counts (carried+new) accepted when issues are resolved"
[IO.File]::WriteAllText((Join-Path $dr "worklog-v9.md"), "未改动：[@zzz] 与 {{res:zzz}}`n", $enc)
Ok ((PT @("--project","demo","report")) -notmatch "不在表中 [1-9]") "report ignores worklogs and versions"
# refinement rule: regressions found in review (Fatal down but Major up, bad counts, dimension mismatch)
$dr2 = Join-Path $v12 "01-Research-Projects\demo2\paper"
New-Item -ItemType Directory -Force $dr2 | Out-Null
[IO.File]::WriteAllText((Join-Path $dr2 "draft.md"), "draft`n", $enc)
$null = PT @("--project","demo2","refine","start",(Join-Path $dr2 "draft.md"))
foreach ($n in "v1","v2","v3") { Copy-Item (Join-Path $dr2 "versions\v0.md") (Join-Path $dr2 "versions\$n.md") }
Ok ((PT @("--project","demo2","refine","record","--version","v0","--fatal","2","--major","2","--scores","a=5,b=5")) -match "baseline") "demo2 baseline recorded"
Ok ((PT @("--project","demo2","refine","record","--version","v1","--carried-fatal","1","--carried-major","3","--scores","a=5,b=5")) -match "不能超过基线") "carried above baseline is refused"
Ok ((PT @("--project","demo2","refine","record","--version","v1","--carried-fatal","1","--carried-major","2","--new-major","-1","--scores","a=5,b=5")) -match "不能为负") "negative count is refused"
Ok ((PT @("--project","demo2","refine","record","--version","v1","--fatal","1","--major","1","--carried-fatal","0","--carried-major","0")) -match "只能二选一") "direct and checklist counts together are refused"
$o = PT @("--project","demo2","refine","record","--version","v1","--carried-fatal","1","--carried-major","2","--new-major","3","--scores","a=5,b=5")
Ok ($o -match "v1：revert") "Fatal down but Major up -> revert"
$o = PT @("--project","demo2","refine","record","--version","v2","--carried-fatal","2","--carried-major","1","--scores","a=5")
Ok ($o -match "v2：revert" -and $o -match "评分维度不一致") "missing score dimension -> revert (cannot compare)"
# ARS-inspired L3 claim-source alignment & locator anchors
Ok ((PT @("cite","add","--key","loc1","--title","Tax Salience","--locator","p.112, Table 3","--claim-scope","US state panel","--offline")) -match "unverified") "cite add accepts --locator and --claim-scope"
$o_claim = PT @("claim","check",$d1)
Ok ($o_claim -match "anchorless" -and $o_claim -match "缺少 <!-- claim:") "claim check flags anchorless citation and untagged result block"
Ok ((PT @("claim","check",$d1,"--strict")) -match "rc=1") "claim check --strict fails on anchorless citation"
[IO.File]::WriteAllText((Join-Path $dr "outline.md"), "| C1 | 税收征管强化与逃税率负相关 | 相关 | ATT | {{res:t2.DID.coef}} | 仅相关性 | 样本期短 |`n", $enc)
$d3 = Join-Path $dr "aligned.md"
[IO.File]::WriteAllText($d3, "<!-- claim: C1 -->`n研究发现系数为 {{res:t2.DID.coef:3}} [@loc1]。`n", $enc)
Ok ((PT @("claim","check",$d3,"--strict")) -match "rc=0") "claim check --strict passes with locator and aligned causal wording"
$d4 = Join-Path $dr "overstated.md"
[IO.File]::WriteAllText($d4, "<!-- claim: C1 -->`n税收征管强化显著降低了逃税率 {{res:t2.DID.coef:3}} [@loc1]。`n", $enc)
Ok ((PT @("claim","check",$d4,"--strict")) -match "rc=1" -and (PT @("claim","check",$d4,"--strict")) -match "OVERSTATED") "claim check --strict flags causal verb overstatement against outline"
$rv = [IO.File]::ReadAllText((Join-Path $dr2 "reviews.json"), $enc) | ConvertFrom-Json
Ok ($rv.rounds[0].method -eq "direct" -and $rv.rounds[1].method -eq "checklist" -and $rv.rounds[1].carried.major -eq 2 -and $rv.current -eq "v0") "method labels recorded; reverts keep v0 as current"
# protection + hook
function G2([string]$Tool, [hashtable]$In) { $ErrorActionPreference = "Continue"
    $json = @{tool_name=$Tool; tool_input=$In; cwd=$v12} | ConvertTo-Json -Depth 5 -Compress
    $out = $json | & $py (Join-Path $v12 ".claude\hooks\orchestrator_guard.py") 2>$null; return "$(($out -join ' '))|rc=$LASTEXITCODE" }
Ok ((G2 "Write" @{file_path=(Join-Path $v12 "Meta\citation-map.json")}) -match "rc=2") "direct write of citation-map.json blocked"
Ok ((G2 "Edit" @{file_path=(Join-Path $v12 "Meta\results-ledger.json")}) -match "rc=2") "direct edit of results-ledger.json blocked"
Ok ((G2 "Bash" @{command="python .claude/scripts/paper_tools.py cite confirm --key a --note x"}) -match "permissionDecision.*ask") "cite confirm via Bash forces a permission prompt"
Ok ((G2 "Bash" @{command="python .claude/scripts/paper_tools.py cite zotero-note k --user 1 --yes"}) -match "permissionDecision.*ask") "zotero-note --yes (write to Zotero) forces a permission prompt"
Ok (-not ((G2 "Bash" @{command="python .claude/scripts/paper_tools.py cite zotero-note k --user 1"}) -match "permissionDecision")) "zotero-note preview (no --yes) does not prompt"
Ok ((G2 "Bash" @{command="python .claude/scripts/paper_tools.py cite list"}) -match "^\|rc=0") "cite list not prompted"
function VP([string]$File) { $ErrorActionPreference = "Continue"
    $json = @{tool_name="Write"; tool_input=@{file_path=$File}; cwd=$v12} | ConvertTo-Json -Depth 5 -Compress
    $out = $json | & $py (Join-Path $v12 ".claude\hooks\validate_paper.py") 2>&1; return "$(($out -join ' '))|rc=$LASTEXITCODE" }
Ok ((VP $d2) -match "rc=2" -and (VP $d2) -match "nobody2000") "validate_paper warns on unknown citation key in a draft"
Ok ((VP $d1) -match "rc=0") "validate_paper silent on a clean draft"
Ok ((VP (Join-Path $v12 "Meta\note.md")) -match "rc=0") "validate_paper ignores non-paper files"
# stage definitions
$cfg = [IO.File]::ReadAllText((Join-Path $v12 ".claude\pipeline-stages.json"), $enc) | ConvertFrom-Json
Ok (($cfg.stages.id -join ",") -eq "S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11,S12") "stages S1..S12 defined"
# stage S10 verify uses the citation check
$orc12 = Join-Path $v12 ".claude\scripts\orchestrator.py"
function O12([string[]]$A) { $ErrorActionPreference = "Continue"; $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try { $o = ((& $py -X utf8 $orc12 --vault $v12 @A 2>&1) -join "`n"); return "$o|rc=$LASTEXITCODE" } finally { [Console]::OutputEncoding = $prev } }
$null = O12 @("init","01-Research-Projects\demo")
$stFile = Join-Path $v12 "01-Research-Projects\demo\STATE.json"
$stj = [IO.File]::ReadAllText($stFile, $enc) | ConvertFrom-Json
$stj.stage = "S10"; $stj.stages.S10.status = "in_progress"; foreach ($i in 1..9) { $stj.stages."S$i".status = "passed" }
[IO.File]::WriteAllText($stFile, ($stj | ConvertTo-Json -Depth 8), $enc)
$null = O12 @("artifact","01-Research-Projects\demo\paper\bad.md")
Ok ((O12 @("verify")) -match "不在引文表中|rc=1") "S10 verify fails for a draft with unknown citation key"
# routing
function Hint([string]$P) { $j = @{prompt=$P} | ConvertTo-Json -Compress; $b = $enc.GetBytes($j)
    $psi = New-Object Diagnostics.ProcessStartInfo $py, ("`"" + (Join-Path $v12 ".claude\hooks\routing_hint.py") + "`""); $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.UseShellExecute = $false; $psi.StandardOutputEncoding = $enc
    $pr = [Diagnostics.Process]::Start($psi); $pr.StandardInput.BaseStream.Write($b, 0, $b.Length); $pr.StandardInput.Close(); $o = $pr.StandardOutput.ReadToEnd(); $pr.WaitForExit(); return $o }
Ok ((Hint "把大纲写成论文初稿") -match "paper-draft") "routing: draft request -> paper-draft"
Ok ((Hint "写论文大纲和主张清单") -match "paper-outline") "routing: outline request -> paper-outline"
Ok ((Hint "按审稿意见修改稿件") -match "paper-refine") "routing: revise request -> paper-refine"
# agy build includes new pieces
Ok ((Test-Path (Join-Path $v12 ".agents\skills\paper-draft\SKILL.md")) -and (Test-Path (Join-Path $v12 ".agents\agents\paper-writer-agent.md"))) "agy gets paper skills and agent"
Ok ((Get-Item (Join-Path $v12 "AGENTS.md")).Length -le 24000) "AGENTS.md still within 24000 bytes"

# two maps: folder map + wikilink map, embedded in CLAUDE.md and AGENTS.md
$lintPy = Join-Path $v12 ".claude\scripts\wiki_lint.py"
$builderPy = Join-Path $pkg "tools\build_platform.py"
function LM([string[]]$A) { $ErrorActionPreference = "Continue"; return ((& $py -X utf8 $lintPy @A 2>&1) -join "`n") + "|rc=$LASTEXITCODE" }
function MapBlock([string]$File) { $t = [IO.File]::ReadAllText($File, $enc).Replace("`r`n","`n"); $m = [regex]::Match($t, "(?s)<!-- ERC:MAP:BEGIN.*?<!-- ERC:MAP:END -->"); return $m.Value }
Ok ((Test-Path (Join-Path $v12 "Meta\folder-map.md")) -and (Test-Path (Join-Path $v12 "Meta\link-map.md"))) "install generates folder-map and link-map"
$cb = MapBlock (Join-Path $v12 "CLAUDE.md"); $ab = MapBlock (Join-Path $v12 "AGENTS.md")
Ok ($cb -match "文件夹地图" -and $cb -match "双链地图" -and $cb -notmatch "尚未生成") "CLAUDE.md carries both maps (generated, not placeholder)"
Ok ($cb.Length -gt 0 -and $cb -eq $ab) "AGENTS.md carries the identical map block"
$lit = Join-Path $v12 "03-Literature"; $legacy = Join-Path $v12 "00-Inbox\old-tax"
New-Item -ItemType Directory -Force $legacy | Out-Null
[IO.File]::WriteAllText((Join-Path $lit "alpha.md"), "---`ntype: literature`n---`n链接 [[beta]] 与 [[ghost]] 与 [[图.base]]`n", $enc)
[IO.File]::WriteAllText((Join-Path $lit "beta.md"), "---`ntype: literature`n---`n回链 [[alpha]]`n", $enc)
[IO.File]::WriteAllText((Join-Path $legacy "law1.md"), "旧税法 [[alpha]] [[law2]]`n", $enc)
[IO.File]::WriteAllText((Join-Path $legacy "law2.md"), "旧税法二`n", $enc)
$r1 = LM @("map","--vault",$v12)
$lm = [IO.File]::ReadAllText((Join-Path $v12 "Meta\link-map.md"), $enc)
Ok ($r1 -match "link-map.md: written" -and $lm -match "alpha" -and $lm -match "beta") "map: research pages enter the wikilink graph"
Ok ($lm -match "ghost" -and $lm -notmatch "图\.base") "map: broken link listed; non-page link (.base) ignored"
$adj = [regex]::Match($lm, "(?s)## 邻接表.*?## 无入链页").Value
Ok ($lm -match "旧资料" -and $lm -match "00-Inbox" -and $adj -notmatch "law1" -and $adj -notmatch "law2") "map: legacy notes summarised per folder, not in the graph"
$ab2 = MapBlock (Join-Path $v12 "AGENTS.md")
Ok ($ab2 -match "alpha" -and $ab2 -eq (MapBlock (Join-Path $v12 "CLAUDE.md")) -and $ab2 -ne $ab) "map: compact block refreshed in both files and still identical"
$r2 = LM @("map","--vault",$v12)
Ok ($r2 -notmatch "written|updated|drift" -and $r2 -match "rc=0") "map: second run changes nothing (deterministic)"
Ok ((LM @("map","--vault",$v12,"--check")) -match "rc=0") "map --check: no drift right after generating"
[IO.File]::WriteAllText((Join-Path $lit "gamma.md"), "---`ntype: literature`n---`n[[alpha]]`n", $enc)
Ok ((LM @("map","--vault",$v12,"--check")) -match "drift.*rc=1|rc=1") "map --check: drift after a new note"
$null = LM @("map","--vault",$v12)
Ok ((Get-Item (Join-Path $v12 "AGENTS.md")).Length -le 24000) "AGENTS.md within 24000 bytes after map refresh"
Ok ((& $py -X utf8 $builderPy sync-vault $v12 --check 2>&1) -match "in-sync") "sync-vault --check: AGENTS.md block still in sync with CLAUDE.md after map"
[IO.File]::WriteAllText((Join-Path $v12 "04-Theories\alpha.md"), "---`ntype: theory`n---`n同名页`n", $enc)
Ok ((LM @("lint","--vault",$v12)) -match "duplicate") "lint warns about duplicate page names"
Remove-Item (Join-Path $v12 "04-Theories\alpha.md") -Force

# language polish: scan lists tells; check proves protected content is unchanged
$pd = Join-Path $v12 "01-Research-Projects\demo\paper"
New-Item -ItemType Directory -Force $pd | Out-Null
$orig = Join-Path $pd "p0.md"; $good = Join-Path $pd "p1.md"; $bad = Join-Path $pd "p2.md"
[IO.File]::WriteAllText($orig, "近年来，数字征管受到了广泛关注。本文证明了遵从提高 {{res:t1.coef}}，样本 3,936 家 [@a2020]。`n", $enc)
[IO.File]::WriteAllText($good, "数字征管能否改变遵从？本文发现遵从提高 {{res:t1.coef}}，样本 3,936 家 [@a2020]。`n", $enc)
[IO.File]::WriteAllText($bad, "数字征管能否改变遵从？本文发现遵从提高 {{res:t1.coef}}，样本 3,900 家 [@a2020]。`n", $enc)
Ok ((PT @("polish","scan",$orig)) -match "套话开头" -and (PT @("polish","scan",$orig)) -match "措辞强于证据") "polish scan flags a formulaic opener and an over-claiming verb"
Ok ((PT @("polish","check","--before",$orig,"--after",$good)) -match "通过") "polish check passes when only wording changed"
Ok ((PT @("polish","check","--before",$orig,"--after",$bad)) -match "正文数字" -and (PT @("polish","check","--before",$orig,"--after",$bad)) -match "rc=1") "polish check fails when a number changed"
Ok ((Hint "帮我润色这一节的表达") -match "paper-polish") "routing: polish request -> paper-polish"
Ok ((Hint "帮我从这张论文图里提取图中数据") -match "thu-digitizer") "routing: digitize request -> thu-digitizer"
Ok ((Hint "帮我做一张期刊配图，多子图带误差棒") -match "scientific-visualization") "routing: figure request -> scientific-visualization"
Ok ((Hint "帮我检查DID识别是否成立") -notmatch "scientific-visualization") "routing: plot route does not shadow causal audit"
Remove-Item Env:\ERC_CROSSREF_MOCK -ErrorAction SilentlyContinue

# --- 13. architecture, wiki isolation & argument spine upgrades ---------------
}
if (Begin-Sec "13" "architecture & spine upgrades") {
# 13a. checker verifies all 17 skills (including paper-polish & 2 MIT plot skills)
$chkText = ((& $shell -NoProfile -File $checker -VaultPath $v12 2>&1) -join "`n")
Ok ($LASTEXITCODE -eq 0 -and $chkText -match "17 skills") "checker reports and validates all 17 skills"
# 13b. pure agy & codex installs generate folder-map / link-map via .agents/scripts/wiki_lint.py
Ok ((Test-Path (Join-Path $v10b "Meta\folder-map.md")) -and (Test-Path (Join-Path $v10b "Meta\link-map.md"))) "agy-only install generates both maps"
Ok ((MapBlock (Join-Path $v10b "AGENTS.md")) -notmatch "尚未生成") "agy-only AGENTS.md map block refreshed"
Ok ((Test-Path (Join-Path $v10c "Meta\folder-map.md")) -and (MapBlock (Join-Path $v10c "AGENTS.md")) -notmatch "尚未生成") "codex-only install generates maps and refreshes AGENTS.md"
# 13c. de-duplicated AGENTS.md has comfortable headroom below 24,000 bytes
$freshAgyBytes = (Get-Item (Join-Path $v10c "AGENTS.md")).Length
Ok ($freshAgyBytes -le 17500) "de-duplicated AGENTS.md <= 17,500 bytes (got $freshAgyBytes)"
# 13d. multi-project wiki_lint isolation (PROJECT.md vs paper/ sub-artifacts & versions/)
$v13 = New-Vault
Ok ((Run-Install $v13 @("-Platform","claude")) -eq 0) "v13 fresh install exit 0"
$lint13 = Join-Path $v13 ".claude\scripts\wiki_lint.py"
$pt13 = Join-Path $v13 ".claude\scripts\paper_tools.py"
foreach ($pn in "projA","projB") {
    $pdir = Join-Path $v13 "01-Research-Projects\$pn"
    New-Item -ItemType Directory -Force (Join-Path $pdir "paper\versions") | Out-Null
    [IO.File]::WriteAllText((Join-Path $pdir "PROJECT.md"), "---`ntype: research-project`nupdated: 2026-11-19`n---`n# $pn`n", $enc)
    [IO.File]::WriteAllText((Join-Path $pdir "paper\draft.md"), "草稿正文（无 frontmatter，不应报孤立/重名/缺索引）`n", $enc)
    [IO.File]::WriteAllText((Join-Path $pdir "paper\versions\v0.md"), "旧版本快照 [[ghost_in_snapshot]]`n", $enc)
}
[IO.File]::WriteAllText((Join-Path $v13 "Meta\index.md"), "---`ntype: index`n---`n- [[projA/PROJECT]]`n- [[projB/PROJECT]]`n", $enc)
& $py -X utf8 $lint13 map --vault $v13 *> $null
$l13Out = (& $py -X utf8 $lint13 lint --vault $v13 --json) -join "`n"
$l13Rc = $LASTEXITCODE
$l13j = $l13Out | ConvertFrom-Json
Ok ($l13Rc -eq 0 -and $l13j.errors -eq 0 -and $l13j.warnings -eq 0) "multi-project lint: 0 errors, 0 warnings (PROJECT.md + paper/ + versions/)"
$lm13 = [IO.File]::ReadAllText((Join-Path $v13 "Meta\link-map.md"), $enc)
Ok ($lm13 -notmatch "draft\.md" -and $lm13 -notmatch "v0\.md" -and $lm13 -notmatch "ghost_in_snapshot") "link-map excludes paper drafts and version snapshots"
# broken wikilink inside paper/draft.md is still caught as an error
[IO.File]::WriteAllText((Join-Path $v13 "01-Research-Projects\projA\paper\draft.md"), "引用不存在页 [[broken_in_draft]]`n", $enc)
$l13b = (& $py -X utf8 $lint13 lint --vault $v13 --json) -join "`n"
Ok ($LASTEXITCODE -eq 1 -and $l13b -match "broken_in_draft") "broken wikilink in paper/draft.md still caught"
# 13e. paper_tools cite from-note bridges 03-Literature cards into citation-map.json
$noteEn = Join-Path $v13 "03-Literature\chetty2009.md"
$noteZh = Join-Path $v13 "03-Literature\tax_cn_2024.md"
[IO.File]::WriteAllText($noteEn, "---`ntype: literature`ncite_key: chetty2009salience`ntitle: Salience and Taxation`nauthors: [Raj Chetty, Adam Looney]`nyear: 2009`njournal: AER`ndoi: 10.1257/aer.99.4.1145`nlocator: p.1146, Table 2`nclaim_scope: US grocery stores`n---`n# 笔记`n", $enc)
[IO.File]::WriteAllText($noteZh, "---`ntype: literature`ncite_key: zhang2024tax`ntitle: 税收征管数字化与企业税收遵从`nauthors: [张三]`nyear: 2024`njournal: 经济研究`nlocator: 第45页, 表3`nclaim_scope: 中国上市公司`n---`n# 笔记`n", $enc)
function PT13([string[]]$A) { $ErrorActionPreference = "Continue"; $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try { return ((& $py -X utf8 $pt13 --vault $v13 @A 2>&1) -join "`n") + "|rc=$LASTEXITCODE" } finally { [Console]::OutputEncoding = $prev } }
$fnOut = PT13 @("cite","from-note",$noteEn,$noteZh,"--offline")
Ok ($fnOut -match "chetty2009salience -> unverified" -and $fnOut -match "zhang2024tax -> manual" -and $fnOut -match "共桥接登记 2 条") "cite from-note bridges EN/ZH literature notes with locators"
$cm13 = [IO.File]::ReadAllText((Join-Path $v13 "Meta\citation-map.json"), $enc) | ConvertFrom-Json
Ok ($cm13.entries.chetty2009salience.locator -eq "p.1146, Table 2" -and $cm13.entries.zhang2024tax.type -eq "chinese") "bridged citations retain locator and detected type"
# 13f. claim check: coverage warning + expanded non-causal restriction ("与……一致") + report coverage
$p13 = Join-Path $v13 "01-Research-Projects\projA\paper"
[IO.File]::WriteAllText((Join-Path $p13 "outline.md"), "| C1 | 机制检验 | 机制 | ATT | res:m1 | 与威慑机制一致 | 局限 |`n| C2 | 异质性发现 | 描述 | — | res:h1 | 仅描述 | 局限 |`n", $enc)
$null = PT13 @("results","register","--id","m1","--value","0.08")
[IO.File]::WriteAllText((Join-Path $p13 "draft.md"), "<!-- claim: C1 -->`n征管数字化显著提高了企业遵从 {{res:m1}} [@chetty2009salience]。`n", $enc)
$cc13 = PT13 @("--project","projA","claim","check",(Join-Path $p13 "draft.md"),"--strict")
Ok ($cc13 -match "OVERSTATED" -and $cc13 -match "C2 尚未在正文") "claim check catches mechanism-consistent overstatement and uncovered outline claim C2"
$rep13 = PT13 @("--project","projA","report","--json")
Ok ($rep13 -match '"claims_defined": 2' -and $rep13 -match '"claims_covered": 1') "report --json outputs claims_defined and claims_covered"

# --- 14. ARS v3.24.4 patterns, upstream tracker & cross-platform installer ---
}
if (Begin-Sec "14" "ARS v3.24.4 patterns, upstream tracker & cross-platform CLI") {
# 14a. honest null for results register (--no-source-reason)
$hn1 = PT13 @("results","register","--id","conf1","--value","0.15","--no-source-reason","税务保密机房脱敏汇总")
Ok ($hn1 -match "诚实空值" -and $hn1 -match "rc=0") "results register accepts --no-source-reason honest null"
$sfile14 = Join-Path $v13 "06-Data\processed\s14.csv"
New-Item -ItemType Directory -Force (Split-Path $sfile14) | Out-Null
[IO.File]::WriteAllText($sfile14, "a,b`n1,2`n", $enc)
$hnBad = PT13 @("results","register","--id","conf2","--value","0.2","--source","06-Data\processed\s14.csv","--no-source-reason","conflict")
Ok ($hnBad -match "不能同时提供" -and $hnBad -match "rc=1") "results register rejects --source + --no-source-reason together"
# 14b. paper_tools review verify (NFC quote check + suggested-references Crossref check)
$rvDraft = Join-Path $p13 "rv_draft.md"
$rvRep = Join-Path $p13 "rv_report.md"
$rvMock = Join-Path $v13 "rv_mock.json"
[IO.File]::WriteAllText($rvMock, (@{ "title:example study of tax salience" = @(@{doi="10.9999/ex.1"; title="Example Study of Tax Salience"; year=2009; venue="AER"; authors=@("A. Author")}) } | ConvertTo-Json -Depth 6), $enc)
[IO.File]::WriteAllText($rvDraft, "本文发现征管数字化提高了小微企业增值税申报遵从率，并在样本期内保持稳健。`n", $enc)
[IO.File]::WriteAllText($rvRep, "意见 M1：稿件称「本文发现征管数字化提高了小微企业增值税申报遵从率」，但未检验预期效应。`n意见 M2：稿件称「作者在附表九中剔除了全部制造业样本」，这是误读。`n``````yaml suggested-references`n- title: Example Study of Tax Salience`n  year: 2009`n- title: Totally Hallucinated Tax Paper`n  year: 2025`n```````n", $enc)
$env:ERC_CROSSREF_MOCK = $rvMock
$rvOut = PT13 @("review","verify","--review",$rvRep,"--manuscript",$rvDraft,"--strict")
Remove-Item Env:\ERC_CROSSREF_MOCK -ErrorAction SilentlyContinue
Ok ($rvOut -match "UNVERIFIED_QUOTE" -and $rvOut -match "引述 1/2 匹配" -and $rvOut -match "verified.*Example Study" -and $rvOut -match "unverified.*Totally Hallucinated" -and $rvOut -match "rc=1") "review verify catches misquoted passage and hallucinated suggested reference"
# 14c. adaptive ARS upstream tracker (check_ars_updates.py)
$cau = Join-Path $pkg "tools\check_ars_updates.py"
$manCopy = Join-Path $v13 "upstream-ars.test.json"
Copy-Item (Join-Path $pkg "payload\Meta\upstream-ars.json") $manCopy
$mockSame = Join-Path $v13 "ars_same.json"
$mockNew = Join-Path $v13 "ars_new.json"
$manObj = [IO.File]::ReadAllText($manCopy, $enc) | ConvertFrom-Json
[IO.File]::WriteAllText($mockSame, (@{releases=@(@{tag=$manObj.last_audited_tag; published_at="2026-11-19"; name="current"; body=""}); commits=@(@{sha=$manObj.last_audited_sha + "0000"; date="2026-11-20"; message="baseline"})} | ConvertTo-Json -Depth 6), $enc)
[IO.File]::WriteAllText($mockNew, (@{releases=@(@{tag="v3.25.0"; published_at="2026-12-01"; name="New reviewer panel & citation check"; body="Adds citation locator rule and stakeholder audit"}, @{tag=$manObj.last_audited_tag; published_at="2026-11-19"; name="old"; body=""}); commits=@(@{sha="deadbeef1234"; date="2026-12-01"; message="feat(reviewer): improve frame-lock check"}, @{sha="cafe00001234"; date="2026-12-01"; message="docs: add zotero adapter note"}, @{sha=$manObj.last_audited_sha + "0000"; date="2026-11-20"; message="baseline"})} | ConvertTo-Json -Depth 6), $enc)
$prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
$cSame = (& $py -X utf8 $cau check --manifest $manCopy --mock $mockSame 2>&1) -join "`n"; $rcSame = $LASTEXITCODE
$repOut = Join-Path $v13 "ars-brief.md"
$cNew = (& $py -X utf8 $cau check --manifest $manCopy --mock $mockNew --out $repOut 2>&1) -join "`n"; $rcNew = $LASTEXITCODE
$cMark = (& $py -X utf8 $cau mark-audited --manifest $manCopy --tag v3.25.0 --sha deadbeef 2>&1) -join "`n"; $rcMark = $LASTEXITCODE
[Console]::OutputEncoding = $prev
Ok ($rcSame -eq 0 -and $cSame -match "已是最新") "check_ars_updates: up-to-date returns exit 0"
Ok ($rcNew -eq 2 -and (Test-Path $repOut) -and $cNew -match "reviewer_audit" -and $cNew -match "zotero_jsonschema_adapters") "check_ars_updates: new release returns exit 2, maps ERC modules and filters excluded items"
Ok ($rcMark -eq 0 -and ([IO.File]::ReadAllText($manCopy, $enc)) -match '"v3\.25\.0"') "check_ars_updates: mark-audited updates manifest baseline"
# 14d. cross-platform Python CLI (tools/mcc_cli.py): Win11 + simulated macOS (python3 hooks)
$cli = Join-Path $pkg "tools\mcc_cli.py"
$v14 = New-Vault
$ErrorActionPreference = "Continue"
& $py -X utf8 $cli install --vault $v14 --platform all --with-hooks --target-os macos --python-cmd python3 *> $null
$rc14i = $LASTEXITCODE
& $py -X utf8 $cli test --vault $v14 *> $null
$rc14t = $LASTEXITCODE
& $py -X utf8 $cli sync --vault $v14 --check *> $null
$rc14s = $LASTEXITCODE
Ok ($rc14i -eq 0 -and $rc14t -eq 0 -and $rc14s -eq 0) "mcc_cli.py install/test/sync pass for full platform + hooks"
$sj14 = [IO.File]::ReadAllText((Join-Path $v14 ".claude\settings.json"), $enc)
$hj14 = [IO.File]::ReadAllText((Join-Path $v14 ".agents\hooks.json"), $enc)
Ok ($sj14 -match 'python3 .*protect_raw\.py' -and $hj14 -match 'python3 hooks/protect_raw\.py') "macOS mode adapts Claude and agy hook commands to python3"
Ok (Test-Path (Join-Path $pkg "install.sh")) "macOS/Linux install.sh launcher present"

# --- 15. EndNote / Zotero exchange (cite import | ris | csl | zotero) --------------------
}
if (Begin-Sec "15" "reference-manager exchange") {
$v15 = New-Vault
Ok ((Run-Install $v15) -eq 0) "v15 fresh install exit 0"
Ok (Test-Path (Join-Path $v15 ".claude\scripts\refmgr.py")) "refmgr.py installed with the scripts"
$ErrorActionPreference = "Continue"
$selftest = Join-Path $pkg "tests\refmgr_selftest.py"
$stOut = & $py -X utf8 $selftest (Join-Path $v15 ".claude\scripts\paper_tools.py") $v15 2>&1
foreach ($ln in $stOut) {
    $m = [regex]::Match([string]$ln, '^\s+(PASS|FAIL) (.+)$')
    if ($m.Success) { Ok ($m.Groups[1].Value -eq "PASS") ("refmgr: " + $m.Groups[2].Value) }
}
Ok ($LASTEXITCODE -eq 0) "refmgr selftest exit 0"

# --- 16. logic hardening regressions -----------------------------------------
}
if (Begin-Sec "16" "logic hardening regressions") {
$v16 = New-Vault
Ok ((Run-Install $v16 @("-Platform","all","-WithHooks")) -eq 0) "v16 all-platform install exit 0"
$orc16 = Join-Path $v16 ".claude\scripts\orchestrator.py"
$pt16 = Join-Path $v16 ".claude\scripts\paper_tools.py"
$lint16 = Join-Path $v16 ".claude\scripts\wiki_lint.py"
function O16([string[]]$A) { $ErrorActionPreference = "Continue"; $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try { return ((& $py -X utf8 $orc16 --vault $v16 @A 2>&1) -join "`n") + "|rc=$LASTEXITCODE" } finally { [Console]::OutputEncoding = $prev } }
function PT16([string[]]$A) { $ErrorActionPreference = "Continue"; $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try { return ((& $py -X utf8 $pt16 --vault $v16 @A 2>&1) -join "`n") + "|rc=$LASTEXITCODE" } finally { [Console]::OutputEncoding = $prev } }
function G16([string]$Tool, [hashtable]$In) { $ErrorActionPreference = "Continue"
    $json = @{tool_name=$Tool; tool_input=$In; cwd=$v16} | ConvertTo-Json -Depth 5 -Compress
    $out = $json | & $py (Join-Path $v16 ".claude\hooks\orchestrator_guard.py") 2>$null; return "$(($out -join ' '))|rc=$LASTEXITCODE" }
# 16a. protect_raw chained & named -Destination bypasses
Ok ((Hook "protect_raw.py" @{tool_name="Bash"; cwd=$v16; tool_input=@{command="cp /tmp/x.csv 06-Data/raw/ && echo ok"}}) -eq 2) "protect_raw blocks chained cp into raw"
Ok ((Hook "protect_raw.py" @{tool_name="PowerShell"; cwd=$v16; tool_input=@{command="Copy-Item -Destination 06-Data/raw/a.csv -Path x.csv"}}) -eq 2) "protect_raw blocks Copy-Item -Destination raw"
Ok ((Hook "protect_raw.py" @{tool_name="PowerShell"; cwd=$v16; tool_input=@{command="Copy-Item -Path 06-Data/raw/a.csv -Destination 06-Data/processed/a.csv"}}) -eq 0) "protect_raw allows Copy-Item FROM raw to processed"
# 16b. orchestrator_guard spaced --vault paths
Ok ((G16 "Bash" @{command='python .claude/scripts/orchestrator.py --vault "D:\My Vault" gate --decision pass --note ok'}) -match "permissionDecision.*ask") "guard prompts for gate with spaced --vault"
Ok ((G16 "Bash" @{command='python .claude/scripts/paper_tools.py --vault "D:\My Vault" cite confirm --key k1 --note ok'}) -match "permissionDecision.*ask") "guard prompts for cite confirm with spaced --vault"
# 16c. validate_frontmatter & validate_paper boundaries
$agBad = Join-Path $v16 ".agents\bad.md"; [IO.File]::WriteAllText($agBad, "---`nx: 1`n# unclosed`n", $enc)
Ok ((Hook "validate_frontmatter.py" @{tool_name="Write"; cwd=$v16; tool_input=@{file_path=$agBad}}) -eq 0) "validate_frontmatter skips .agents/"
Remove-Item -LiteralPath $agBad -Force
$p16 = Join-Path $v16 "01-Research-Projects\p1\paper"
New-Item -ItemType Directory -Force (Join-Path $p16 "versions") | Out-Null
$vSnap = Join-Path $p16 "versions\v0.md"; [IO.File]::WriteAllText($vSnap, "引用 [@ghost] {{res:ghost}}`n", $enc)
$wLog = Join-Path $p16 "worklog-v1.md"; [IO.File]::WriteAllText($wLog, "引用 [@ghost] {{res:ghost}}`n", $enc)
$lcBad = Join-Path $p16 "bad.md"; [IO.File]::WriteAllText($lcBad, "引用 [@ghost]`n", $enc)
function VP16([string]$File) { $ErrorActionPreference = "Continue"; $json = @{tool_name="Write"; tool_input=@{file_path=$File}; cwd=$v16} | ConvertTo-Json -Depth 5 -Compress
    $null = $json | & $py (Join-Path $v16 ".claude\hooks\validate_paper.py") 2>$null; return $LASTEXITCODE }
Ok ((VP16 $vSnap) -eq 0 -and (VP16 $wLog) -eq 0) "validate_paper skips versions/ and worklog- files"
Ok ((VP16 ($lcBad.Replace("01-Research-Projects", "01-research-projects"))) -eq 2) "validate_paper matches project path case-insensitively"
# 16d. orchestrator unknown --stage, artifact --remove, and cross-project verify
$null = O16 @("init","01-Research-Projects\p1")
Ok ((O16 @("verify","--stage","S99")) -match "未知阶段|rc=1") "orchestrator verify rejects unknown stage"
$badArt = Join-Path $p16 "bad.md"; $goodArt = Join-Path $p16 "ok.md"; [IO.File]::WriteAllText($goodArt, "ok`n", $enc)
$null = O16 @("artifact",$badArt); $null = O16 @("artifact",$badArt,"--remove"); $null = O16 @("artifact",$goodArt)
Ok ((O16 @("verify")) -match "rc=0") "orchestrator artifact --remove clears mistakenly registered artifact"
# cross-project claims_aligned: p2 is newest active, p1 verified explicitly at S12 uses p1's outline
$null = O16 @("init","01-Research-Projects\p2")
$p2dir = Join-Path $v16 "01-Research-Projects\p2\paper"; New-Item -ItemType Directory -Force $p2dir | Out-Null
[IO.File]::WriteAllText((Join-Path $p16 "outline.md"), "| C1 | 关联 | 相关 | ATT | res:r1 | 仅相关性 | 局限 |`n", $enc)
[IO.File]::WriteAllText((Join-Path $p2dir "outline.md"), "| C9 | 其他 | 因果 | ATT | res:r9 | 因果 | 局限 |`n", $enc)
$null = PT16 @("cite","add","--key","k16","--title","Tax","--locator","p.1","--offline")
$null = PT16 @("cite","confirm","--key","k16","--note","ok")
$null = PT16 @("results","register","--id","r1","--value","0.5","--no-source-reason","test")
$p1Final = Join-Path $p16 "final.md"
[IO.File]::WriteAllText($p1Final, "<!-- claim: C1 -->`n`n结果 {{res:r1}} 与征管相关 [@k16]。`n", $enc)
$null = O16 @("--project","p1","artifact",$p1Final,"--stage","S12")
Ok ((O16 @("--project","p1","verify","--stage","S12")) -match "rc=0") "orchestrator cross-project verify S12 checks p1 outline (not active p2) and binds blank-line claim tag"
# 16e. paper_tools edge cases: forthcoming year, short zh title, bibtex --, Chinese CSV, non-.md render, bare_stats heading, case-insensitive OVERSTATED, report latest manuscript, polish frontmatter
$m16 = Join-Path $v16 "mock16.json"
[IO.File]::WriteAllText($m16, (@{"title:forthcoming tax study"=@(@{doi="10.1/f";title="Forthcoming Tax Study";year=2026;venue="AER";authors=@("A")})} | ConvertTo-Json -Depth 5), $enc)
$env:ERC_CROSSREF_MOCK = $m16
Ok ((PT16 @("cite","add","--key","forth26","--title","Forthcoming Tax Study","--year","forthcoming")) -match "verified") "cite add handles non-integer year (forthcoming) without crashing"
Remove-Item Env:\ERC_CROSSREF_MOCK -ErrorAction SilentlyContinue
$zhShort = Join-Path $v16 "03-Literature\shui.md"
[IO.File]::WriteAllText($zhShort, "---`ntype: literature`ncite_key: shui2024`ntitle: 税法学`nyear: 2024`n---`n", $enc)
Ok ((PT16 @("cite","from-note",$zhShort,"--offline")) -match "shui2024 -> manual") "cite from-note classifies short 3-char Chinese title as manual"
$zhCsv = Join-Path $v16 "06-Data\processed\zh.csv"
New-Item -ItemType Directory -Force (Split-Path $zhCsv) | Out-Null
[IO.File]::WriteAllText($zhCsv, "模型,系数,标准误`n基准回归,-0.12,0.03`n稳健性,-0.11,0.04`n", $enc)
Ok ((PT16 @("results","import",$zhCsv,"--prefix","cn")) -match "已登记 4.*rc=0") "results import handles Chinese CSV row/column headers"
$txtIn = Join-Path $p16 "raw.txt"; [IO.File]::WriteAllText($txtIn, "值 {{res:r1}}`n", $enc)
Ok ((PT16 @("results","render",$txtIn)) -match "raw\.txt\.rendered.*rc=0" -and ([IO.File]::ReadAllText($txtIn, $enc) -match "\{\{res:r1\}\}")) "results render on non-.md writes .rendered without overwriting input"
$hdFile = Join-Path $p16 "hd.md"; [IO.File]::WriteAllText($hdFile, "---`nversion: 1.2`n---`n## 3.1 识别策略`n正文无裸统计 {{res:r1}}。`n", $enc)
Ok ((PT16 @("results","check",$hdFile)) -match "警告 0") "bare_stats ignores YAML frontmatter and markdown heading numbers"
$enOver = Join-Path $p16 "en_over.md"; [IO.File]::WriteAllText($enOver, "<!-- claim: C1 -->`n`nEnforcement Causes higher compliance {{res:r1}} [@k16].`n", $enc)
Ok ((PT16 @("--project","p1","claim","check",$enOver,"--strict")) -match "(?s)OVERSTATED.*rc=1") "claim check binds blank-line claim tag and catches capitalized Causes"
[IO.File]::WriteAllText((Join-Path $p16 "draft.md"), "旧草稿 {{res:r1}} ⟦问：旧问题⟧`n", $enc)
$rep16 = (PT16 @("--project","p1","report","--json")) -replace '\|rc=\d+$',''
$rj16 = $rep16 | ConvertFrom-Json
Ok ($rj16.open_questions -eq 0 -and $rj16.numbers_linked -eq 1 -and $rj16.manuscript -match "final\.md") "report measures only latest manuscript (final.md), no double-counting or stale draft questions"
$pf0 = Join-Path $p16 "pf0.md"; $pf1 = Join-Path $p16 "pf1.md"
[IO.File]::WriteAllText($pf0, "---`nupdated: 2026-11-20`n---`n结果 {{res:r1}} [@k16]。`n", $enc)
[IO.File]::WriteAllText($pf1, "---`nupdated: 2026-11-21`n---`n估计结果 {{res:r1}} [@k16]。`n", $enc)
Ok ((PT16 @("polish","check","--before",$pf0,"--after",$pf1)) -match "通过.*rc=0") "polish check ignores YAML frontmatter date changes"
# 16f. wiki_lint code-block wikilink skip, multi-project index & link-map isolation
foreach ($pn in "p1","p2") {
    [IO.File]::WriteAllText((Join-Path $v16 "01-Research-Projects\$pn\PROJECT.md"), "---`ntype: research-project`n---`n# $pn`n示例 ``[[not_a_real_link]]```n", $enc)
}
[IO.File]::WriteAllText((Join-Path $v16 "Meta\index.md"), "---`ntype: index`n---`n- [[p1/PROJECT]]`n- [[shui]]`n", $enc)
& $py -X utf8 $lint16 map --vault $v16 *> $null
$l16Out = (& $py -X utf8 $lint16 lint --vault $v16 --json) -join "`n"
$l16j = $l16Out | ConvertFrom-Json
Ok (@($l16j.findings | Where-Object { $_.msg -match "not_a_real_link" }).Count -eq 0) "wiki_lint ignores wikilinks inside inline code"
Ok (@($l16j.findings | Where-Object { $_.file -match "p2/PROJECT" -and $_.check -eq "index" }).Count -eq 1) "wiki_lint flags unindexed p2/PROJECT even when p1/PROJECT is indexed"
$lm16 = [IO.File]::ReadAllText((Join-Path $v16 "Meta\link-map.md"), $enc)
Ok ($lm16 -match "01-Research-Projects/p2/PROJECT\.md") "link-map correctly marks unlinked p2/PROJECT as orphan (no bleed from p1/PROJECT)"
# 16g. check_ars_updates mixed release, merge_hooks python prefix upgrade, sync-vault total size cap, erc_cli missing agy hook
$mockMix = Join-Path $v16 "ars_mix.json"
$manObj16 = [IO.File]::ReadAllText((Join-Path $pkg "payload\Meta\upstream-ars.json"), $enc) | ConvertFrom-Json
[IO.File]::WriteAllText($mockMix, (@{releases=@(@{tag="v3.99.0"; published_at="2026-12-09"; name="Reviewer & Zotero"; body="Improves reviewer panel and zotero adapter"}); commits=@()} | ConvertTo-Json -Depth 6), $enc)
$mixOut = (& $py -X utf8 (Join-Path $pkg "tools\check_ars_updates.py") check --mock $mockMix --json 2>&1) -join "`n"
Ok ($LASTEXITCODE -eq 2 -and ($mixOut | ConvertFrom-Json).relevant_count -eq 1) "check_ars_updates keeps mixed release with relevant keywords instead of excluding it"
$mhPy = Join-Path $pkg "tools\merge_hooks.py"
$sj16 = Join-Path $v16 ".claude\settings.json"
& $py -X utf8 $mhPy $sj16 (Join-Path $payload ".claude\settings.hooks.json") --python-cmd python3 *> $null
Ok (([IO.File]::ReadAllText($sj16, $enc)) -match 'python3 .*protect_raw\.py') "merge_hooks upgrades existing hook python prefix to python3"
$origAg = [IO.File]::ReadAllText((Join-Path $v16 "AGENTS.md"), $enc)
[IO.File]::WriteAllText((Join-Path $v16 "AGENTS.md"), ("x" * 10000) + "`n" + $origAg, $enc)
[IO.File]::AppendAllText((Join-Path $v16 "CLAUDE.md"), "`n- trigger sync`n", $enc)
& $py -X utf8 (Join-Path $pkg "tools\build_platform.py") sync-vault $v16 *> $null
Ok ($LASTEXITCODE -ne 0) "sync-vault refuses when total AGENTS.md (custom + block) exceeds 24,000 bytes"
Remove-Item -LiteralPath (Join-Path $v16 ".agents\hooks\protect_raw.py") -Force
& $py -X utf8 (Join-Path $pkg "tools\mcc_cli.py") test --vault $v16 *> $null
Ok ($LASTEXITCODE -ne 0) "mcc_cli test catches missing hook referenced in .agents/hooks.json"

# --- 17. Claude Code CLI 2.1.x adaptation ------------------------------------
}
if (Begin-Sec "17" "Claude Code CLI 2.1.x adaptation") {
$v17 = New-Vault
Ok ((Run-Install $v17 @("-Platform","claude","-WithHooks")) -eq 0) "v17 claude+hooks install exit 0"
$sj17 = [IO.File]::ReadAllText((Join-Path $v17 ".claude\settings.json"), $enc) | ConvertFrom-Json
Ok ($null -ne $sj17.hooks.SessionStart -and $sj17.hooks.SessionStart[0].hooks[0].timeout -eq 10 -and $sj17.hooks.PreToolUse[0].hooks[0].timeout -eq 10) "settings.json has SessionStart hook and timeout=10"
# upgrade path backfills missing timeout on existing hook
$oldNoTimeout = '{"hooks":{"PreToolUse":[{"matcher":"Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell","hooks":[{"type":"command","command":"python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect_raw.py\""}]}]}}'
[IO.File]::WriteAllText((Join-Path $v17 ".claude\settings.json"), $oldNoTimeout, $enc)
& $py -X utf8 (Join-Path $pkg "tools\merge_hooks.py") (Join-Path $v17 ".claude\settings.json") (Join-Path $payload ".claude\settings.hooks.json") *> $null
$sj17b = [IO.File]::ReadAllText((Join-Path $v17 ".claude\settings.json"), $enc) | ConvertFrom-Json
Ok ($sj17b.hooks.PreToolUse[0].hooks[0].timeout -eq 10 -and $null -ne $sj17b.hooks.SessionStart) "merge_hooks backfills timeout=10 and adds SessionStart"
# session_context.py: unfilled purpose.md -> warns; filled purpose + no active project -> silent; active project + compact -> restores stage
function SC17([hashtable]$In) {
    $ErrorActionPreference = "Continue"
    $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try {
        $json = $In | ConvertTo-Json -Depth 5 -Compress
        return (($json | & $py (Join-Path $v17 ".claude\hooks\session_context.py") 2>$null) -join "`n")
    } finally { [Console]::OutputEncoding = $prev }
}
$scInit = SC17 @{cwd=$v17; source="startup"}
Ok ($scInit -match '"hookEventName":\s*"SessionStart"' -and $scInit -match 'purpose\.md') "session_context reports unfilled Meta/purpose.md on startup"
[IO.File]::WriteAllText((Join-Path $v17 "Meta\purpose.md"), "---`ntype: purpose`n---`n# 研究方向`n税收征管数字化与企业遵从`n", $enc)
Ok ((SC17 @{cwd=$v17; source="startup"}).Trim() -eq "") "session_context stays silent when purpose filled and no active project"
& $py -X utf8 (Join-Path $v17 ".claude\scripts\orchestrator.py") --vault $v17 init 01-Research-Projects\demo17 *> $null
$scComp = SC17 @{cwd=$v17; source="compact"}
Ok ($scComp -match 'ERC 压缩后状态恢复' -and $scComp -match 'demo17' -and $scComp -match 'S1') "session_context restores active project stage after compaction"
# subagent CLI 2.1.x metadata: econometrics PowerShell tool + read-only disallowedTools + effort levels
$ecAg = [IO.File]::ReadAllText((Join-Path $v17 ".claude\agents\case-data-agent.md"), $enc)
$rvAg = [IO.File]::ReadAllText((Join-Path $v17 ".claude\agents\academic-reviewer.md"), $enc)
Ok ($ecAg -match 'PowerShell' -and $ecAg -match '(?m)^effort:\s*medium' -and $rvAg -match '(?m)^disallowedTools:.*PowerShell' -and $rvAg -match '(?m)^effort:\s*high') "agents declare PowerShell tool, disallowedTools and effort levels"
# native Claude Code CLI validator (strict mode) when claude is installed
$claudeBin = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeBin) {
    $ErrorActionPreference = "Continue"
    & $claudeBin.Source plugin validate --strict (Join-Path $v17 ".claude") *> $null
    Ok ($LASTEXITCODE -eq 0) "claude plugin validate --strict passes on installed .claude"
}

}
# --- 18. optimization, SSOT manifest & performance invariants -----------------
if (Begin-Sec "18" "optimization & SSOT invariants") {
$manPath = Join-Path $pkg "tools\manifest.json"
Ok (Test-Path $manPath) "tools/manifest.json exists"
$man = [IO.File]::ReadAllText($manPath, $enc) | ConvertFrom-Json
$diskAgents = @(Get-ChildItem (Join-Path $payload ".claude\agents") -Filter *.md | ForEach-Object { $_.BaseName } | Sort-Object)
$diskSkills = @(Get-ChildItem (Join-Path $payload ".claude\skills") -Directory | ForEach-Object { $_.Name } | Sort-Object)
$diskHooks  = @(Get-ChildItem (Join-Path $payload ".claude\hooks") -Filter *.py | ForEach-Object { $_.Name } | Sort-Object)
Ok ((($man.agents | Sort-Object) -join ",") -eq ($diskAgents -join ",")) "manifest.agents matches payload/.claude/agents"
Ok ((($man.skills | Sort-Object) -join ",") -eq ($diskSkills -join ",")) "manifest.skills matches payload/.claude/skills"
Ok ((($man.hooks_claude | Sort-Object) -join ",") -eq ($diskHooks -join ",")) "manifest.hooks_claude matches payload/.claude/hooks"
$missingMeta = @($man.meta_required | Where-Object { -not (Test-Path (Join-Path $payload ($_ -replace '/', '\'))) })
Ok ($missingMeta.Count -eq 0) "all manifest.meta_required files exist in payload"
# context slimming: AGENTS.erc.md block stays well under 13,500 bytes (leaving >10 KB headroom below 24 KB limit)
$blkBytes = [int](& $py -X utf8 -c "import sys; sys.path.insert(0, sys.argv[1]); import build_platform as bp; print(len(bp.build_rules_block(sys.argv[2]).encode('utf-8')))" (Join-Path $pkg "tools") $payload)
Ok ($blkBytes -le 13500) "slimmed AGENTS.erc.md block <= 13,500 bytes (got $blkBytes)"
# lightweight validate_paper catches both unknown [@key] and unknown {{res:id}}
$v18 = New-Vault
Ok ((Run-Install $v18 @("-Platform","claude")) -eq 0) "v18 install exit 0"
$p18 = Join-Path $v18 "01-Research-Projects\demo18\paper"
New-Item -ItemType Directory -Force $p18 | Out-Null
$d18 = Join-Path $p18 "draft.md"
[IO.File]::WriteAllText($d18, "测试引用 [@missing_k] 与缺失结果 {{res:missing_r}}。`n", $enc)
$prevEap18 = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$vp18Out = ((@{tool_name="Write"; tool_input=@{file_path=$d18}; cwd=$v18} | ConvertTo-Json -Depth 5 -Compress) | & $py (Join-Path $v18 ".claude\hooks\validate_paper.py") 2>&1) -join "`n"
$vp18Rc = $LASTEXITCODE
$ErrorActionPreference = $prevEap18
Ok ($vp18Rc -eq 2 -and $vp18Out -match "missing_k" -and $vp18Out -match "missing_r") "lightweight validate_paper catches unknown citation and unknown result"
# refmgr O(N) dup index & single-walk pdf index match unindexed semantics
$rmCheck = & $py -X utf8 -c @"
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])
import refmgr
entries = {
    'a2020': {'title': 'Tax Compliance in China', 'year': '2020', 'doi': '10.1000/abc'},
    'b2021': {'title': 'Platform Economy', 'year': '2021', 'doi': None},
}
idx = refmgr.build_dup_index(entries)
r1 = {'title': 'Other', 'year': '2020', 'doi': 'https://doi.org/10.1000/ABC'}
r2 = {'title': 'Platform Economy!', 'year': '2021', 'doi': None}
r3 = {'title': 'Platform Economy!', 'year': '2022', 'doi': None}
assert refmgr.find_duplicate(r1, entries, idx) == 'a2020'
assert refmgr.find_duplicate(r2, entries, idx) == 'b2021'
assert refmgr.find_duplicate(r3, entries, idx) is None
with tempfile.TemporaryDirectory() as td:
    sub = os.path.join(td, 'sub', 'deep')
    os.makedirs(sub)
    fp = os.path.join(sub, 'paper.pdf')
    open(fp, 'wb').write(b'%PDF')
    pidx = refmgr.build_pdf_index(td)
    assert refmgr.resolve_pdf(['internal-pdf://x/paper.pdf'], td, td, pidx) == os.path.abspath(fp)
print('OK')
"@ (Join-Path $payload ".claude\scripts")
Ok ($rmCheck -eq "OK") "refmgr indexed duplicate detection and PDF lookup match semantics"
# protect_raw UTF-8 stderr on Windows
$prChk = & $py -c @"
import json, subprocess, sys
inp = json.dumps({'tool_name': 'Edit', 'tool_input': {'file_path': '06-Data/raw/a.csv'}, 'cwd': sys.argv[2]}).encode('utf-8')
p = subprocess.run([sys.executable, sys.argv[1]], input=inp, capture_output=True)
print('OK' if p.returncode == 2 and 'BLOCKED by protect_raw' in p.stderr.decode('utf-8') else 'BAD')
"@ (Join-Path $payload ".claude\hooks\protect_raw.py") $v18
Ok ($prChk -eq "OK") "protect_raw writes readable UTF-8 stderr"
}

if ($script:CurSec -and $script:SecSw) {
    $script:SecSw.Stop()
    Write-Host ("  [{0}] done in {1:N2}s" -f $script:CurSec, $script:SecSw.Elapsed.TotalSeconds) -ForegroundColor DarkGray
}
$script:TotalSw.Stop()

# --- cleanup + summary ----------------------------------------------------------
foreach ($d in $v,$vx,$v3,$v4,$v5,$v6,$v6b,$v6c,$v10,$v10b,$v10c,$v11,$v11b,$v11c,$v12,$v13,$v14,$v15,$v16,$v17,$v18) { if ($d -and (Test-Path $d) -and $d.StartsWith([IO.Path]::GetTempPath())) { Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue } }
Write-Host ""
Write-Host ("passed: {0}  failed: {1}  elapsed: {2:N2}s" -f $script:pass, $script:fail, $script:TotalSw.Elapsed.TotalSeconds) -ForegroundColor $(if ($script:fail) { "Red" } else { "Green" })
if ($script:fail) { exit 1 }
