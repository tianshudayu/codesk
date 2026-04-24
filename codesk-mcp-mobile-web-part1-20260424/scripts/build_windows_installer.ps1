param(
  [string]$CloudUrl = "https://codesk.lensseekapp.com",
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = (Get-Command python -ErrorAction Stop).Source
}
if (-not $OutputDir) {
  $OutputDir = Join-Path $RepoRoot ".dist\windows"
}
$BuildRoot = Join-Path $RepoRoot ".build\windows"
$WorkRoot = Join-Path $BuildRoot "work"
$TmpRoot = Join-Path $BuildRoot "tmp"
$PayloadDir = Join-Path $TmpRoot "payload"
$ClientPayload = Join-Path $PayloadDir "client"
$DistRoot = Join-Path $BuildRoot "dist"
$DesktopSyncRoot = Join-Path $RepoRoot "desktop_sync"
$IExpressRoot = Join-Path $TmpRoot "iexpress"

Remove-Item -Recurse -Force $BuildRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $ClientPayload, $WorkRoot, $DistRoot, $OutputDir, $IExpressRoot | Out-Null

& $Python -m pip install --disable-pip-version-check pyinstaller pyinstaller-hooks-contrib PySide6 segno | Out-Host
if (Test-Path (Join-Path $DesktopSyncRoot "requirements.txt")) {
  & $Python -m pip install -r (Join-Path $DesktopSyncRoot "requirements.txt") | Out-Host
}

$ClientAssets = Join-Path $RepoRoot "clients\windows"
Copy-Item (Join-Path $ClientAssets "requirements.txt") $ClientPayload -Force
Copy-Item (Join-Path $ClientAssets "BUILDING.txt") $ClientPayload -Force
Copy-Item (Join-Path $RepoRoot "scripts\setup_codex_cli.ps1") $ClientPayload -Force

$InstallerConfig = @{
  cloudUrl = $CloudUrl
}
$InstallerConfig | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PayloadDir "installer-config.json") -Encoding UTF8

Push-Location $RepoRoot
try {
  & $Python -m PyInstaller --noconfirm --clean --onefile --console --name "codesk-agent" --paths $RepoRoot --distpath $DistRoot --workpath (Join-Path $WorkRoot "agent") "$RepoRoot\scripts\windows_agent_entry.py"
  & $Python -m PyInstaller --noconfirm --clean --onefile --console --name "codesk-desktop-sync" --paths $DesktopSyncRoot --distpath $DistRoot --workpath (Join-Path $WorkRoot "desktop-sync") --add-data "$DesktopSyncRoot\app\static;app\static" "$DesktopSyncRoot\run_remote_assist.py"
  & $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name "codesk-tray" --hidden-import "PySide6.QtSvgWidgets" --paths $RepoRoot --distpath $DistRoot --workpath (Join-Path $WorkRoot "tray") "$RepoRoot\clients\windows\codesk_tray.py"

  Copy-Item (Join-Path $DistRoot "codesk-agent.exe") $ClientPayload -Force
  Copy-Item (Join-Path $DistRoot "codesk-desktop-sync.exe") $ClientPayload -Force
  Copy-Item (Join-Path $DistRoot "codesk-tray.exe") $ClientPayload -Force
}
finally {
  Pop-Location
}

$PayloadZip = Join-Path $OutputDir "Codesk-Setup-Payload.zip"
Compress-Archive -Path (Join-Path $PayloadDir "*") -DestinationPath $PayloadZip -Force

$IExpressScript = Join-Path $IExpressRoot "windows_installer_payload.ps1"
$IExpressConfig = Join-Path $IExpressRoot "installer-config.json"
$SedPath = Join-Path $IExpressRoot "codesk-installer.sed"
$IExpressExe = Join-Path $env:SystemRoot "System32\\iexpress.exe"
$TargetExe = Join-Path $OutputDir "Codesk-Setup.exe"

Copy-Item (Join-Path $RepoRoot "scripts\windows_installer_payload.ps1") $IExpressScript -Force
Copy-Item (Join-Path $PayloadDir "installer-config.json") $IExpressConfig -Force

$TargetExeSed = $TargetExe -replace "\\", "\\"
$IExpressRootSed = $IExpressRoot -replace "\\", "\\"
$Sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$TargetExeSed
FriendlyName=Codesk installer
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File windows_installer_payload.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$IExpressRootSed\
[SourceFiles0]
%FILE0%=
%FILE1%=
[Strings]
FILE0=windows_installer_payload.ps1
FILE1=installer-config.json
"@
$Sed | Set-Content -LiteralPath $SedPath -Encoding ASCII
& $IExpressExe /N $SedPath | Out-Host
if (-not (Test-Path $TargetExe)) {
  throw "IExpress did not produce Codesk-Setup.exe."
}
Write-Host "Built Codesk installer at $(Join-Path $OutputDir 'Codesk-Setup.exe')"
