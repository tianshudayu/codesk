Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$venvPython = Join-Path $projectRoot ".venv\\Scripts\\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment not found. Create it first with 'python -m venv .venv'."
}

Push-Location $projectRoot
try {
    & $venvPython -m pip install -r requirements.txt
    & $venvPython -m PyInstaller --noconfirm --clean remote_coding_assist.spec
}
finally {
    Pop-Location
}
