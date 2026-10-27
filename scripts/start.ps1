# 生产模式：构建前端后由后端统一托管，访问 http://127.0.0.1:8000/
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root '..\..\.venv'

Push-Location "$Root\web"
try {
    npm run build
} finally {
    Pop-Location
}

& "$Venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "$Root" --host 127.0.0.1 --port 8000
