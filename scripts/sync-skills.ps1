param(
    [string]$SourceRoot = (Join-Path (git rev-parse --show-toplevel) 'skills'),
    [string]$TargetRoot = '',
    [string]$Repository = 'https://github.com/LingXi-Org/LingxiSkills.git',
    [string]$Branch = 'main',
    [string]$CommitMessage = '',
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Invoke-Git([string[]]$Arguments, [string]$WorkingDirectory) {
    & git -C $WorkingDirectory @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') 执行失败，退出码：$LASTEXITCODE"
    }
}

$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$temporaryTarget = $false

if ([string]::IsNullOrWhiteSpace($TargetRoot)) {
    $TargetRoot = Join-Path $env:TEMP ('LingxiSkills-sync-' + [guid]::NewGuid().ToString('N'))
    $temporaryTarget = $true
    Write-Host "克隆目标仓库到临时目录：$TargetRoot"
    & git clone --branch $Branch $Repository $TargetRoot
    if ($LASTEXITCODE -ne 0) { throw "无法克隆目标仓库：$Repository" }
} else {
    $TargetRoot = (Resolve-Path -LiteralPath $TargetRoot).Path
    $remote = (& git -C $TargetRoot remote get-url origin).Trim()
    if ($LASTEXITCODE -ne 0 -or $remote -ne $Repository) {
        throw "TargetRoot 不是指定的 LingxiSkills 仓库：$TargetRoot"
    }
    Invoke-Git @('switch', $Branch) $TargetRoot
    Invoke-Git @('pull', '--ff-only', 'origin', $Branch) $TargetRoot
}

try {
    $targetSkills = Join-Path $TargetRoot 'skills'
    New-Item -ItemType Directory -Force -Path $targetSkills | Out-Null

    $sourceFiles = @(Get-ChildItem -LiteralPath $SourceRoot -Recurse -File | Where-Object {
        $_.FullName -notmatch '\\(__pycache__|\.pytest_cache)\\' -and $_.Extension -ne '.pyc'
    })
    if ($sourceFiles.Count -eq 0) { throw "本地没有找到任何 skill：$SourceRoot" }
    $sourceRelative = @{}
    foreach ($file in $sourceFiles) {
        $relative = $file.FullName.Substring($SourceRoot.Length + 1)
        $sourceRelative[$relative] = $true
        Write-Host "同步 $relative"
        if (-not $DryRun) {
            $destination = Join-Path $targetSkills $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
        }
    }

    if (-not $DryRun) {
        $targetFiles = @(Get-ChildItem -LiteralPath $targetSkills -Recurse -File)
        foreach ($file in $targetFiles) {
            $relative = $file.FullName.Substring($targetSkills.Length + 1)
            if (-not $sourceRelative.ContainsKey($relative)) {
                Write-Host "删除远端多余文件 $relative"
                Remove-Item -LiteralPath $file.FullName -Force
            }
        }
        Get-ChildItem -LiteralPath $targetSkills -Recurse -Directory |
            Sort-Object FullName -Descending |
            Where-Object { @(Get-ChildItem -LiteralPath $_.FullName -Force).Count -eq 0 } |
            Remove-Item -Force
    }

    if ($DryRun) {
        Write-Host 'DryRun 完成，未写入、提交或推送。'
        return
    }

    $status = & git -C $TargetRoot status --short -- skills
    if ($LASTEXITCODE -ne 0) { throw '无法读取目标仓库状态。' }
    if ([string]::IsNullOrWhiteSpace(($status -join "`n"))) {
        Write-Host '目标仓库已经是最新，无需提交。'
        return
    }

    Invoke-Git @('add', '--', 'skills') $TargetRoot
    if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
        $CommitMessage = 'sync skills from LingxiLearn'
    }
    Invoke-Git @('commit', '-m', $CommitMessage) $TargetRoot
    Invoke-Git @('push', 'origin', "$Branch`:$Branch") $TargetRoot
    Write-Host "Skill 已提交并推送到 $Repository ($Branch)。"
} finally {
    if ($temporaryTarget -and (Test-Path -LiteralPath $TargetRoot)) {
        Remove-Item -LiteralPath $TargetRoot -Recurse -Force
    }
}
