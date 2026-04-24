Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

$LogPath = Join-Path $env:TEMP "CodeskInstaller.log"
function Write-InstallLog {
    param([string]$Message)
    try {
        $line = "[{0}] {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Message
        Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    }
    catch {
    }
}

function Show-Message {
    param(
        [string]$Title,
        [string]$Message,
        [System.Windows.Forms.MessageBoxIcon]$Icon = [System.Windows.Forms.MessageBoxIcon]::Information
    )
    [System.Windows.Forms.MessageBox]::Show(
        $Message,
        $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        $Icon
    ) | Out-Null
}

$script:InstallForm = $null
$script:InstallLabel = $null

function Show-InstallProgress {
    param([string]$Message)
    if (-not $script:InstallForm) {
        $form = New-Object System.Windows.Forms.Form
        $form.Text = "Installing Codesk"
        $form.StartPosition = "CenterScreen"
        $form.Size = New-Object System.Drawing.Size(420, 150)
        $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
        $form.MaximizeBox = $false
        $form.MinimizeBox = $false
        $form.ControlBox = $false
        $form.TopMost = $true
        $form.BackColor = [System.Drawing.Color]::FromArgb(245, 245, 248)

        $label = New-Object System.Windows.Forms.Label
        $label.AutoSize = $false
        $label.Size = New-Object System.Drawing.Size(360, 40)
        $label.Location = New-Object System.Drawing.Point(24, 24)
        $label.Font = New-Object System.Drawing.Font("Segoe UI", 10)
        $label.TextAlign = [System.Drawing.ContentAlignment]::MiddleLeft

        $bar = New-Object System.Windows.Forms.ProgressBar
        $bar.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
        $bar.MarqueeAnimationSpeed = 24
        $bar.Size = New-Object System.Drawing.Size(360, 18)
        $bar.Location = New-Object System.Drawing.Point(24, 78)

        $form.Controls.Add($label)
        $form.Controls.Add($bar)
        $script:InstallForm = $form
        $script:InstallLabel = $label
        $form.Show()
    }

    if ($script:InstallLabel) {
        $script:InstallLabel.Text = $Message
    }
    [System.Windows.Forms.Application]::DoEvents()
}

function Close-InstallProgress {
    if ($script:InstallForm) {
        $script:InstallForm.Close()
        $script:InstallForm.Dispose()
    }
    $script:InstallForm = $null
    $script:InstallLabel = $null
}

function Stop-CodeskProcesses {
    foreach ($name in @("codesk-tray", "codesk-agent", "codesk-desktop-sync")) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "python*.exe" -and $_.CommandLine -like "*-m bridge.agent_main*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "cmd.exe" -and $_.CommandLine -like "*codex.cmd app-server*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Copy-WithRetry {
    param(
        [string]$Source,
        [string]$Destination,
        [int]$Retries = 20
    )
    $lastError = $null
    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            Copy-Item -LiteralPath $Source -Destination $Destination -Force
            return
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Unable to update $(Split-Path -Leaf $Destination): $($lastError.Exception.Message)"
}

function New-ShortcutFile {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory
    )
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Save()
}

$extractRoot = Join-Path $env:TEMP ("CodeskSetup-" + [Guid]::NewGuid().ToString("N"))
$payloadZip = Join-Path $extractRoot "payload.zip"

try {
    Write-InstallLog "Installer started."
    Show-InstallProgress "Preparing Codesk installer..."
    New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

    $configPath = Join-Path $PSScriptRoot "installer-config.json"
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw "Installer configuration is missing."
    }

    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $cloudUrl = [string]$config.cloudUrl
    if ([string]::IsNullOrWhiteSpace($cloudUrl)) {
        throw "Installer configuration is missing cloud URL."
    }
    $payloadUrl = ($cloudUrl.TrimEnd("/")) + "/api/downloads/windows-client/payload"
    Write-InstallLog "Downloading payload from $payloadUrl"
    Show-InstallProgress "Downloading Codesk components..."

    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($payloadUrl, $payloadZip)
    Write-InstallLog "Payload downloaded."
    Show-InstallProgress "Unpacking installer payload..."
    [System.IO.Compression.ZipFile]::ExtractToDirectory($payloadZip, $extractRoot)
    Write-InstallLog "Payload extracted."

    $clientPayload = Join-Path $extractRoot "client"
    if (-not (Test-Path -LiteralPath $clientPayload)) {
        throw "Installer payload is incomplete."
    }

    $installRoot = Join-Path $env:LOCALAPPDATA "Codesk"
    $clientRoot = Join-Path $installRoot "client"
    $agentRoot = Join-Path $installRoot "agent"
    $identityFile = Join-Path $agentRoot "cloud-agent.json"

    New-Item -ItemType Directory -Force -Path $installRoot, $clientRoot, $agentRoot | Out-Null

    Stop-CodeskProcesses
    Start-Sleep -Seconds 1
    Write-InstallLog "Stopped existing Codesk processes."
    Show-InstallProgress "Updating local Codesk runtime..."

    foreach ($item in Get-ChildItem -LiteralPath $clientPayload -Force) {
        $target = Join-Path $clientRoot $item.Name
        if ($item.PSIsContainer) {
            if (Test-Path -LiteralPath $target) {
                Remove-Item -LiteralPath $target -Recurse -Force
            }
            Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
        }
        else {
            Copy-WithRetry -Source $item.FullName -Destination $target
        }
    }

    $clientConfig = [ordered]@{
        cloudUrl     = $cloudUrl
        agentRoot    = $agentRoot
        identityFile = $identityFile
        installedAt  = (Get-Date).ToString("o")
    }

    $desktopSyncExe = Join-Path $clientRoot "codesk-desktop-sync.exe"
    if (Test-Path -LiteralPath $desktopSyncExe) {
        $clientConfig.desktopAutomationExe = $desktopSyncExe
    }

    $clientConfigPath = Join-Path $clientRoot "codesk-client.json"
    $clientConfig | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $clientConfigPath -Encoding UTF8
    Write-InstallLog "Client files copied and config written."

    $trayExe = Join-Path $clientRoot "codesk-tray.exe"
    if (-not (Test-Path -LiteralPath $trayExe)) {
        throw "codesk-tray.exe is missing from the installer payload."
    }

    $desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Codesk for Windows.lnk"
    $startupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "Codesk Tray.lnk"
    New-ShortcutFile -ShortcutPath $desktopShortcut -TargetPath $trayExe -WorkingDirectory $clientRoot
    New-ShortcutFile -ShortcutPath $startupShortcut -TargetPath $trayExe -WorkingDirectory $clientRoot
    Write-InstallLog "Shortcuts created."
    Show-InstallProgress "Starting Codesk for Windows..."

    Start-Process -FilePath $trayExe -WorkingDirectory $clientRoot
    Write-InstallLog "Tray launched."
}
catch {
    Write-InstallLog ("Installer failed: " + $_.Exception.Message)
    Close-InstallProgress
    if ($env:CODESK_INSTALLER_TEST -ne "1") {
        Show-Message -Title "Codesk installer" -Message ($_.Exception.Message + "`n`nLog: " + $LogPath) -Icon ([System.Windows.Forms.MessageBoxIcon]::Error)
    }
    exit 1
}
finally {
    Write-InstallLog "Installer finished."
    Close-InstallProgress
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
