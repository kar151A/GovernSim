$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Run-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
if (-not (Test-Path '.venv\Scripts\python.exe')) { Run-Checked 'py' @('-3.12', '-m', 'venv', '.venv') }
$PythonExe = Join-Path (Get-Location) '.venv\Scripts\python.exe'
Run-Checked $PythonExe @('scripts\bootstrap.py')
Run-Checked $PythonExe @('-m', 'pip', 'install', '-r', 'backend\requirements.txt')
Push-Location frontend
try {
    Run-Checked 'npm.cmd' @('ci', '--no-fund', '--no-audit')
    Run-Checked 'npm.cmd' @('run', 'build')
} finally { Pop-Location }
Write-Host 'Open http://localhost:8000 and copy a token from .local-keys.txt.'
Run-Checked $PythonExe @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8000')
