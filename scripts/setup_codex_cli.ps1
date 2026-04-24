[CmdletBinding()]
param(
    [string]$Version = "0.118.0",
    [string]$NpmRegistry = ""
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[setup-codex-cli] $Message"
}

function Require-Command {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$Name' was not found in PATH."
    }
    return $command.Source
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Label
    )
    Write-Step "$Label`: $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Test-CodexCommand {
    param([string]$CodexCmd)

    $checks = @(
        @("--help"),
        @("app-server", "--help")
    )

    foreach ($args in $checks) {
        try {
            & $CodexCmd @args *> $null
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        }
        catch {
            # Try the next help command before failing the whole setup.
        }
    }

    return $false
}

$node = Require-Command "node"
$npm = Require-Command "npm"

Write-Step "node: $(& $node --version)"
Write-Step "npm: $(& $npm --version)"

$prefix = (& $npm config get prefix).Trim()
Write-Step "npm prefix: $prefix"

$installArgs = @("install", "-g", "@openai/codex@$Version")
if ($NpmRegistry.Trim()) {
    $installArgs += @("--registry", $NpmRegistry.Trim())
}

Invoke-Checked -FilePath $npm -Arguments $installArgs -Label "npm install"

$codexCmd = Join-Path $env:APPDATA "npm\codex.cmd"
if (-not (Test-Path -LiteralPath $codexCmd)) {
    throw "Expected user-level Codex CLI was not found: $codexCmd"
}

Write-Step "codex command: $codexCmd"

if (-not (Test-CodexCommand -CodexCmd $codexCmd)) {
    throw "codex.cmd help check failed. Make sure the user-level npm install completed successfully."
}

Write-Step "success. Bridge can use: $codexCmd app-server"
