[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$VaultPath = "D:\ManagementCaseWiki",
    [switch]$WithUpstream,
    [switch]$WithHooks,
    [switch]$Update,
    [string]$RepoUrl = "",
    # auto：检测本机已安装的 claude / agy / codex，只为检测到的平台生成文件（都没检测到则装 Claude 版）
    [ValidateSet("auto","claude","agy","codex","all")]
    [string]$Platform = "auto"
)
$ErrorActionPreference = "Stop"

function Get-Sha([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $fs = [IO.File]::OpenRead($Path); try { return [BitConverter]::ToString($sha.ComputeHash($fs)).Replace("-","") } finally { $fs.Dispose() } } finally { $sha.Dispose() }
}
$script:Pending = @()
function Copy-NoOverwrite([string]$Source, [string]$Destination) {
    if (-not (Test-Path $Source)) { return }
    foreach ($f in Get-ChildItem -LiteralPath $Source -Recurse -File -Force | Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' }) {
        $rel = $f.FullName.Substring($Source.TrimEnd('\').Length).TrimStart('\')
        $dest = Join-Path $Destination $rel
        if (Test-Path $dest) {
            if ($Update -and ((Get-Sha $f.FullName) -ne (Get-Sha $dest))) {
                $new = "$dest.new"
                if ($PSCmdlet.ShouldProcess($new, "写入差异副本")) { Copy-Item -LiteralPath $f.FullName -Destination $new -Force }
                $script:Pending += "$dest.new"
                Write-Host "  有差异 -> $rel.new" -ForegroundColor Cyan
            } elseif (-not $Update) {
                Write-Host "  跳过(已存在): $rel" -ForegroundColor Yellow
            }
            continue
        }
        if ($PSCmdlet.ShouldProcess($dest, "复制")) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
            Copy-Item -LiteralPath $f.FullName -Destination $dest
        }
    }
}

$VaultPath = [System.IO.Path]::GetFullPath($VaultPath)
if (-not (Test-Path $VaultPath -PathType Container)) { throw "知识库目录不存在：$VaultPath" }
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $packageRoot "payload"
if (-not (Test-Path $payload)) { throw "未找到 payload 目录，请完整解压安装包。" }
$claudeDir = Join-Path $VaultPath ".claude"

# 0. 平台
$detected = @("claude","agy","codex" | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue })
$platforms = @(switch ($Platform) {
    "auto" { if ($detected.Count -gt 0) { $detected } else { "claude" } }
    "all"  { "claude","agy","codex" }
    default { $Platform }
})
$doClaude = $platforms -contains "claude"
$doAgents = ($platforms -contains "agy") -or ($platforms -contains "codex")
Write-Host ("平台：{0}（-Platform {1}；本机检测到：{2}）" -f ($platforms -join ", "), $Platform, $(if ($detected) { $detected -join ", " } else { "无" })) -ForegroundColor Cyan
if ($doAgents -and -not (Get-Command python -ErrorAction SilentlyContinue)) { throw "为 agy/Codex 生成文件需要 python 在 PATH 中。" }

# 1. 备份
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $VaultPath "_erc-backups\$stamp"
foreach ($rel in @("CLAUDE.md", ".mcp.json", ".claude\settings.json", "AGENTS.md", ".agents\hooks.json")) {
    $src = Join-Path $VaultPath $rel
    if (Test-Path $src -PathType Leaf) {
        $dst = Join-Path $backupDir $rel
        if ($PSCmdlet.ShouldProcess($src, "备份到 $dst")) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
            Copy-Item -LiteralPath $src -Destination $dst
        }
    }
}

# 2. 可选：上游框架，隔离构建，只取 agents/skills/references
$importLines = @()
if ($WithUpstream) {
    if (-not $RepoUrl) { throw "-WithUpstream 需要同时指定 -RepoUrl（上游 My-Brain-Is-Full-Crew 的 Git 地址）。" }
    foreach ($c in "git","bash.exe","jq") { if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { throw "缺少命令：$c" } }
    $repoPath  = Join-Path $VaultPath "_vendor\My-Brain-Is-Full-Crew"
    $stagePath = Join-Path $VaultPath "_erc-staging"
    if (Test-Path $stagePath) { throw "临时目录已存在：$stagePath，请先检查后手动移走。" }
    if (-not (Test-Path (Join-Path $repoPath ".git"))) {
        if (Test-Path $repoPath) { throw "$repoPath 已存在但不是 Git 仓库。" }
        if ($PSCmdlet.ShouldProcess($RepoUrl, "git clone")) {
            git clone --depth 1 $RepoUrl $repoPath
            if ($LASTEXITCODE -ne 0) { throw "git clone 失败" }
        }
    }
    $launch = Join-Path $repoPath "scripts\launchme.sh"
    if ((Test-Path $launch) -and $PSCmdlet.ShouldProcess($stagePath, "构建上游 Crew")) {
        Write-Host "请先人工审阅 $launch 的参数；下面的 --platform/--target 参数未经本包验证。" -ForegroundColor Yellow
        $cyg = (Get-Command cygpath.exe -ErrorAction Stop).Source
        $ru = (& $cyg -u $repoPath).Trim(); $su = (& $cyg -u $stagePath).Trim()
        & (Get-Command bash.exe).Source -lc "cd '$ru' && bash scripts/launchme.sh --platform claude-code --target '$su'"
        if ($LASTEXITCODE -ne 0) { throw "上游构建失败；知识库未被改动。" }
        foreach ($d in "agents","skills","references") {
            Copy-NoOverwrite (Join-Path $stagePath ".claude\$d") (Join-Path $claudeDir $d)
        }
        $disp = Join-Path $stagePath "CLAUDE.md"
        $dispDest = Join-Path $claudeDir "MBIFC-DISPATCHER.md"
        if ((Test-Path $disp) -and -not (Test-Path $dispDest)) {
            # 仅保存供参考，不自动 import：上游 dispatcher 要求“只用上游 Agent、绝不直接回答”，会与本项目路由冲突。
            Copy-Item $disp $dispDest
            Write-Host "上游 dispatcher 已保存为 .claude/MBIFC-DISPATCHER.md，未自动 import（与本项目路由规则冲突）。" -ForegroundColor Yellow
        }
    }
}
$importLines += "@.claude/MANAGEMENT-CASE-RESEARCH.md"

# 3. 本扩展
if ($doClaude) { Copy-NoOverwrite (Join-Path $payload ".claude") $claudeDir }
Copy-NoOverwrite (Join-Path $payload "Meta") (Join-Path $VaultPath "Meta")
Copy-NoOverwrite (Join-Path $payload "Templates") (Join-Path $VaultPath "Templates")

# 3a. agy / Codex：由 payload/.claude 生成 .agents/ 与 AGENTS.md 区块（先生成到临时目录，再不覆盖地复制）
if ($doAgents) {
    $builder = Join-Path $packageRoot "tools\build_platform.py"
    $stage = Join-Path ([IO.Path]::GetTempPath()) ("erc-platform-" + $stamp)
    $agentPlats = @($platforms | Where-Object { $_ -ne "claude" }) -join ","
    & python -X utf8 $builder build $payload $stage --platforms $agentPlats
    if ($LASTEXITCODE -ne 0) { throw "生成 agy/Codex 文件失败；知识库未被改动。" }
    try {
        Copy-NoOverwrite (Join-Path $stage ".agents") (Join-Path $VaultPath ".agents")
        $agentsMd = Join-Path $VaultPath "AGENTS.md"
        if ($PSCmdlet.ShouldProcess($agentsMd, "新建或追加 Economics Research Crew 区块")) {
            $mergeArgs = @("merge-agents-md", $agentsMd, (Join-Path $stage "AGENTS.erc.md"))
            if ($Update) { $mergeArgs += "--update" }
            $r = (& python -X utf8 $builder @mergeArgs | Out-String).Trim()
            if ($LASTEXITCODE -ne 0) { throw "AGENTS.md 合并失败。" }
            if ($r -eq "pending") { $script:Pending += "$agentsMd.new" }
            if ($r -eq "stale") { Write-Host "  AGENTS.md 中的区块不是最新版；用 -Update 生成 AGENTS.md.new 供比对。" -ForegroundColor Yellow }
        }
        if ($WithHooks -and ($platforms -contains "agy")) {
            $agyHooks = Join-Path $VaultPath ".agents\hooks.json"
            if ($PSCmdlet.ShouldProcess($agyHooks, "合并 agy hooks（仅 economics-research-crew 键）")) {
                & python -X utf8 $builder merge-agy-hooks $agyHooks (Join-Path $stage "hooks.erc.json")
                if ($LASTEXITCODE -ne 0) { throw "agy hooks 合并失败；hooks.json 未被改动。" }
            }
        }
    } finally {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 3b. 可选：hooks（修改 settings.json，需 -WithHooks；已在步骤 1 备份）
if ($WithHooks -and $doClaude) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "-WithHooks 需要 python 在 PATH 中。" }
    $merge = Join-Path $packageRoot "tools\merge_hooks.py"
    $snippet = Join-Path $payload ".claude\settings.hooks.json"
    $settingsFile = Join-Path $claudeDir "settings.json"
    if ($PSCmdlet.ShouldProcess($settingsFile, "合并 hooks")) {
        & python -X utf8 $merge $settingsFile $snippet
        if ($LASTEXITCODE -ne 0) { throw "hooks 合并失败；settings.json 未被改动。" }
    }
}

# 4. 根 CLAUDE.md 仅追加缺失的 import
$rootClaude = Join-Path $VaultPath "CLAUDE.md"
$enc = [System.Text.UTF8Encoding]::new($false)
if (-not $doClaude) {
    # 未选择 Claude Code：不创建、不修改 CLAUDE.md
} elseif (-not (Test-Path $rootClaude)) {
    if ($PSCmdlet.ShouldProcess($rootClaude, "新建")) {
        $tpl = Join-Path $payload "CLAUDE.template.md"
        $body = if (Test-Path $tpl) { [IO.File]::ReadAllText($tpl, $enc).TrimEnd() } else { "# Research Workspace" }
        $extra = @($importLines | Where-Object { $body -notmatch [regex]::Escape($_) })
        if ($extra.Count -gt 0) { $body += "`r`n`r`n" + ($extra -join "`r`n") }
        [IO.File]::WriteAllText($rootClaude, $body + "`r`n", $enc)
    }
} else {
    $existing = [IO.File]::ReadAllText($rootClaude, $enc)
    # -Update：模板有新版且与现有 CLAUDE.md 不同 -> 生成 CLAUDE.md.new 供人工合并（不覆盖）
    $tpl = Join-Path $payload "CLAUDE.template.md"
    if ($Update -and (Test-Path $tpl)) {
        $tplBody = [IO.File]::ReadAllText($tpl, $enc).Replace("`r`n","`n").TrimEnd()
        if ($existing.Replace("`r`n","`n").TrimEnd() -ne $tplBody) {
            $newRoot = "$rootClaude.new"
            if ($PSCmdlet.ShouldProcess($newRoot, "写入 CLAUDE.md 新版模板副本")) { [IO.File]::WriteAllText($newRoot, $tplBody + "`n", $enc) }
            $script:Pending += $newRoot
        }
    }
    $missing = @($importLines | Where-Object { $existing -notmatch [regex]::Escape($_) })
    if ($missing.Count -gt 0 -and $PSCmdlet.ShouldProcess($rootClaude, "追加 import")) {
        [IO.File]::WriteAllText($rootClaude, $existing.TrimEnd() + "`r`n`r`n" + ($missing -join "`r`n") + "`r`n", $enc)
    }
}

# 5. 研究目录（仅新建，不移动现有内容）
foreach ($d in "00-Inbox","01-Research-Projects","03-Literature","03-Literature\_sources","04-Theories","05-Methods",
               "06-Data\raw","06-Data\processed","06-Data\metadata","07-Code\python","07-Code\R","07-Code\stata",
               "08-Research-Notes","09-Writing","10-Archive","MOC") {
    $p = Join-Path $VaultPath $d
    if (-not (Test-Path $p) -and $PSCmdlet.ShouldProcess($p, "创建目录")) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}
if ($script:Pending.Count -gt 0) { Write-Host "以下文件与新版不同，已生成 .new 副本（未覆盖原文件），请人工比对后合并：" -ForegroundColor Cyan; $script:Pending | ForEach-Object { Write-Host "  $_" } }
$backupNote = if (Test-Path $backupDir) { "备份：$backupDir" } else { "无需备份（没有已存在的 CLAUDE.md/.mcp.json/settings.json/AGENTS.md/hooks.json）" }
Write-Host "完成。$backupNote 。请运行 Test-EconomicsResearchCrew.ps1。" -ForegroundColor Green
