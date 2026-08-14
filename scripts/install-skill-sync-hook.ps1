$ErrorActionPreference = 'Stop'
$repoRoot = (git rev-parse --show-toplevel).Trim()
$hookDir = Join-Path $repoRoot '.githooks'
New-Item -ItemType Directory -Force -Path $hookDir | Out-Null
git -C $repoRoot config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) { throw '无法设置 Git hooks 路径。' }
Write-Host '已启用 skill 自动同步钩子。以后提交包含 skills/ 改动时，会自动推送到 LingxiSkills/main。'
