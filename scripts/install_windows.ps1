$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

function Require-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Host "缺少 $Name。" -ForegroundColor Red
        Write-Host $InstallHint
        exit 1
    }
}

Set-Location $RepoRoot

Require-Command "py" "请安装 Python 3.11+，或从 https://www.python.org/downloads/windows/ 安装并勾选 Add python.exe to PATH。"
Require-Command "ffmpeg" "请安装 FFmpeg。可使用 winget install Gyan.FFmpeg，或安装后把 ffmpeg 加入 PATH。"
Require-Command "node" "请安装 Node.js 22 LTS: https://nodejs.org/"
Require-Command "npm" "请重新安装 Node.js，并确认 npm 已加入 PATH。"

if (-not (Test-Path $PythonExe)) {
    py -3 -m venv $VenvDir
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -e $RepoRoot
& npm ci --prefix (Join-Path $RepoRoot "core/infra/motion") --omit=dev --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw "Motion runtime installation failed." }
Write-Host "HTML 动画需要 Chrome；非标准安装位置请设置 AIGC_BROWSER_PATH。"

if (-not (Test-Path (Join-Path $RepoRoot ".env")) -and (Test-Path (Join-Path $RepoRoot ".env.example"))) {
    Copy-Item (Join-Path $RepoRoot ".env.example") (Join-Path $RepoRoot ".env")
    Write-Host "已生成 .env，请填入 API 密钥。"
}



& $PythonExe -m core.dependency_check --repo-root $RepoRoot

Write-Host ""
Write-Host "安装完成。启动程序：" -ForegroundColor Green
Write-Host ".\.venv\Scripts\python.exe -m cli"
