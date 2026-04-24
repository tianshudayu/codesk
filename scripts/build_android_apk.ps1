param(
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AndroidRoot = Join-Path $RepoRoot "android_app"
if (-not $OutputDir) {
  $OutputDir = Join-Path $RepoRoot ".dist\android"
}
$ToolRoot = Join-Path $RepoRoot ".tooling\gradle"
$GradleVersion = "8.7"
$GradleHome = Join-Path $ToolRoot "gradle-$GradleVersion"
$GradleZip = Join-Path $ToolRoot "gradle-$GradleVersion-bin.zip"

New-Item -ItemType Directory -Force -Path $ToolRoot, $OutputDir | Out-Null
if (-not (Test-Path (Join-Path $GradleHome "bin\gradle.bat"))) {
  Invoke-WebRequest -Uri "https://services.gradle.org/distributions/gradle-$GradleVersion-bin.zip" -OutFile $GradleZip -UseBasicParsing
  Expand-Archive -LiteralPath $GradleZip -DestinationPath $ToolRoot -Force
}

Push-Location $AndroidRoot
try {
  $Gradle = Join-Path $GradleHome "bin\gradle.bat"
  $ReleaseKeystore = $env:CODEX_ANDROID_KEYSTORE
  $ReleaseStorePassword = $env:CODEX_ANDROID_KEYSTORE_PASSWORD
  $ReleaseKeyAlias = $env:CODEX_ANDROID_KEY_ALIAS
  $ReleaseKeyPassword = $env:CODEX_ANDROID_KEY_PASSWORD

  $HasReleaseSigning = $ReleaseKeystore -and $ReleaseStorePassword -and $ReleaseKeyAlias -and $ReleaseKeyPassword
  if ($HasReleaseSigning) {
    & $Gradle assembleRelease `
      "-PcodeskReleaseStoreFile=$ReleaseKeystore" `
      "-PcodeskReleaseStorePassword=$ReleaseStorePassword" `
      "-PcodeskReleaseKeyAlias=$ReleaseKeyAlias" `
      "-PcodeskReleaseKeyPassword=$ReleaseKeyPassword"
  }
  else {
    & $Gradle assembleDebug
  }
}
finally {
  Pop-Location
}

$Candidates = @(
  (Join-Path $AndroidRoot "app\build\outputs\apk\debug\app-debug.apk"),
  (Join-Path $AndroidRoot "app\build\outputs\apk\release\app-release.apk"),
  (Join-Path $AndroidRoot "app\build\outputs\apk\release\app-release-unsigned.apk")
)
$Artifact = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Artifact) {
  throw "Android APK was not produced."
}

Copy-Item $Artifact (Join-Path $OutputDir "Codesk-Android.apk") -Force
Write-Host "Built Android APK at $(Join-Path $OutputDir 'Codesk-Android.apk')"
