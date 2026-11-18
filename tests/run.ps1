[CmdletBinding()]
param()
# Regression tests for the Economics Research Crew installer, hooks and lint.
# Run under each host you care about:
#   powershell -NoProfile -File tests\run.ps1   (Windows PowerShell 5.1)
#   pwsh -NoProfile -File tests\run.ps1         (PowerShell 7)
$ErrorActionPreference = "Stop"
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
    try { $fs = [IO.File]::OpenRead($Path); try { return [BitConverter]::ToString($sha.ComputeHash($fs)).Replace("-","") } finally { $fs.Dispose() } } finally { $sha.Dispose() }
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
Write-Host "[1] fresh install"
$v = New-Vault
Ok ((Run-Install $v) -eq 0) "install exit 0"
Ok ((Run-Check $v) -eq 0) "checker exit 0"
$skillCount = (Get-ChildItem (Join-Path $v ".claude\skills") -Directory).Count
$agentCount = (Get-ChildItem (Join-Path $v ".claude\agents") -Filter *.md).Count
Ok ($skillCount -eq 14) "14 skills (got $skillCount)"
Ok ($agentCount -eq 7) "7 agents (got $agentCount)"
$tpl = [IO.File]::ReadAllText((Join-Path $payload "CLAUDE.template.md")).Replace("`r`n","`n").TrimEnd()
$got = [IO.File]::ReadAllText((Join-Path $v "CLAUDE.md")).Replace("`r`n","`n").TrimEnd()
Ok ($got -eq $tpl) "root CLAUDE.md equals template (UTF-8, no mojibake)"
Ok (Test-Path (Join-Path $v "03-Literature\_sources")) "_sources dir created"

# --- 2. idempotent ----------------------------------------------------------
Write-Host "[2] idempotent"
$before = Snapshot $v
Ok ((Run-Install $v) -eq 0) "second install exit 0"
$after = Snapshot $v
Ok ((($before -join "`n") -eq ($after -join "`n"))) "no file changed on re-install"

# --- 3. existing Chinese CLAUDE.md preserved ---------------------------------
Write-Host "[3] existing CLAUDE.md preserved"
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
Write-Host "[4] -WhatIf"
$v4 = New-Vault
Ok ((Run-Install $v4 @("-WhatIf")) -eq 0) "WhatIf exit 0"
Ok ((Get-ChildItem -LiteralPath $v4 -Force).Count -eq 0) "WhatIf left vault empty"

# --- 5. -Update writes .new, never overwrites -------------------------------
Write-Host "[5] -Update"
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
Write-Host "[6] -WithHooks"
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
Write-Host "[7] protect_raw hook"
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
Write-Host "[8] validate_frontmatter hook"
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
Write-Host "[8b] routing_hint hook"
function Hint([string]$Prompt) {
    $ErrorActionPreference = "Continue"
    $json = @{prompt=$Prompt} | ConvertTo-Json -Compress
    $out = $json | & $py -X utf8 (Join-Path $payload ".claude\hooks\routing_hint.py") 2>$null
    return ($out -join " ")
}
Ok ((Hint "帮我梳理税收遵从的国内外文献，找出研究缺口") -match "/literature-review") "literature intent -> /literature-review"
Ok ((Hint "我的单一案例三角验证设计成立吗") -match "/case-design-audit") "case design intent -> /case-design-audit"
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
Ok ((HintPlain (@{hookEventName="PreInvocation"; invocationNum=0; lastUserInput="我的单一案例三角验证设计成立吗"} | ConvertTo-Json -Compress)) -match "case-design-audit") "Chinese prompt matches without -X utf8 (agy host)"

# --- 9. wiki_lint ---------------------------------------------------------------
Write-Host "[9] wiki_lint"
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
Write-Host "[10] multi-platform"
$v10 = New-Vault
Ok ((Run-Install $v10 @("-Platform","all","-WithHooks")) -eq 0) "all-platform install exit 0"
Ok ((Run-Check $v10) -eq 0) "checker passes for all platforms"
Ok ((Test-Path (Join-Path $v10 "CLAUDE.md")) -and (Test-Path (Join-Path $v10 ".claude\skills"))) "Claude files present"
$sk = @(Get-ChildItem (Join-Path $v10 ".agents\skills") -Directory)
Ok ($sk.Count -eq 14) ".agents has 14 skills (got $($sk.Count))"
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
[IO.File]::WriteAllText((Join-Path $v10b "AGENTS.md"), $am2.Replace("## 路由规则", "## 路由规则（旧）"), $enc)
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
Write-Host "[11] orchestration layer"
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
Write-Host "[12] paper architecture"
$v12 = New-Vault
Ok ((Run-Install $v12 @("-Platform","all","-WithHooks")) -eq 0 -and (Run-Check $v12) -eq 0) "install + checker pass with paper files"
$pt = Join-Path $v12 ".claude\scripts\paper_tools.py"
$mock = Join-Path $v12 "mock.json"
$mockObj = [ordered]@{ "title:salience and taxation theory and evidence" = @(@{doi="10.1257/aer.99.4.1145"; title="Salience and Taxation: Theory and Evidence"; year=2009; venue="AER"; authors=@("Raj Chetty")}) ;
    "doi:10.0/wrong" = @(@{doi="10.0/wrong"; title="Some Other Paper"; year=2001; venue="X"; authors=@()}) }
[IO.File]::WriteAllText($mock, ($mockObj | ConvertTo-Json -Depth 6), $enc)
function PT([string[]]$A) { $ErrorActionPreference = "Continue"; $env:ERC_CROSSREF_MOCK = $mock; $prev = [Console]::OutputEncoding; [Console]::OutputEncoding = $enc
    try { $o = ((& $py -X utf8 $pt --vault $v12 @A 2>&1) -join "`n"); return "$o|rc=$LASTEXITCODE" } finally { [Console]::OutputEncoding = $prev; Remove-Item Env:\ERC_CROSSREF_MOCK -ErrorAction SilentlyContinue } }
Ok ((PT @("cite","add","--key","chetty2009","--title","Salience and Taxation: Theory and Evidence","--year","2009")) -match "verified") "cite add: matching Crossref record -> verified"
Ok ((PT @("cite","add","--key","bad1","--title","Salience and Taxation: Theory and Evidence","--year","2009","--doi","10.0/wrong")) -match "mismatch") "cite add: DOI pointing to another title -> mismatch"
Ok ((PT @("cite","add","--key","ghostpaper","--title","Totally Invented Paper","--year","2015")) -match "unverified") "cite add: unknown work -> unverified"
Ok ((PT @("cite","add","--key","zh1","--title","某中文文献","--type","chinese")) -match "manual") "Chinese literature -> manual"
Ok ((PT @("cite","add","--key","law1","--title","某通知","--type","legal")) -match "文号") "legal source without doc number refused"
Ok ((PT @("cite","add","--key","law1","--title","某通知","--type","legal","--doc-no","X号","--effective","2020-01-01")) -match "manual") "legal source with doc number and date accepted (manual)"
Ok ((PT @("cite","add","--key","off1","--title","Salience and Taxation: Theory and Evidence","--offline")) -match "unverified") "--offline never queries Crossref"
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
[IO.File]::WriteAllText($d1, "系数为 {{res:t2.DID.coef:3}}，样本 {{res:n}} [@chetty2009; @zh1]。`n⟦问：是否加机制检验？⟧`n", $enc)
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
$rv = [IO.File]::ReadAllText((Join-Path $dr2 "reviews.json"), $enc) | ConvertFrom-Json
Ok ($rv.rounds[0].method -eq "direct" -and $rv.rounds[1].method -eq "checklist" -and $rv.rounds[1].carried.major -eq 2 -and $rv.current -eq "v0") "method labels recorded; reverts keep v0 as current"
# protection + hook
function G2([string]$Tool, [hashtable]$In) { $ErrorActionPreference = "Continue"
    $json = @{tool_name=$Tool; tool_input=$In; cwd=$v12} | ConvertTo-Json -Depth 5 -Compress
    $out = $json | & $py (Join-Path $v12 ".claude\hooks\orchestrator_guard.py") 2>$null; return "$(($out -join ' '))|rc=$LASTEXITCODE" }
Ok ((G2 "Write" @{file_path=(Join-Path $v12 "Meta\citation-map.json")}) -match "rc=2") "direct write of citation-map.json blocked"
Ok ((G2 "Edit" @{file_path=(Join-Path $v12 "Meta\results-ledger.json")}) -match "rc=2") "direct edit of results-ledger.json blocked"
Ok ((G2 "Bash" @{command="python .claude/scripts/paper_tools.py cite confirm --key a --note x"}) -match "permissionDecision.*ask") "cite confirm via Bash forces a permission prompt"
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
Remove-Item Env:\ERC_CROSSREF_MOCK -ErrorAction SilentlyContinue

# --- cleanup + summary ----------------------------------------------------------
foreach ($d in $v,$v3,$v4,$v5,$v6,$v6b,$v6c,$v10,$v10b,$v10c,$v11,$v11b,$v11c,$v12) { if ($d -and (Test-Path $d) -and $d.StartsWith([IO.Path]::GetTempPath())) { Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue } }
Write-Host ""
Write-Host "passed: $script:pass  failed: $script:fail" -ForegroundColor $(if ($script:fail) { "Red" } else { "Green" })
if ($script:fail) { exit 1 }
