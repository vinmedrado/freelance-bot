param(
    [switch]$OpenBrowser,
    [switch]$SkipChrome
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

if (-not $env:WEBAPP_HOST) {
    $env:WEBAPP_HOST = "0.0.0.0"
}
if (-not $env:WEBAPP_PORT) {
    $env:WEBAPP_PORT = "5050"
}
if (-not $env:CHROME_CDP_URL) {
    $env:CHROME_CDP_URL = "http://127.0.0.1:9222"
}

$LogsDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$PythonCandidates = @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path $Root "venv\Scripts\python.exe"),
    "python"
)

$Python = $null
foreach ($Candidate in $PythonCandidates) {
    if ($Candidate -eq "python") {
        $Python = $Candidate
        break
    }
    if (Test-Path -LiteralPath $Candidate) {
        $Python = $Candidate
        break
    }
}

if (-not $Python) {
    throw "Python nao encontrado. Crie .venv ou venv, ou deixe python no PATH."
}

function Find-ChromeExe {
    $Candidates = @(
        $env:CHROME_EXE_PATH,
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    )

    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate)) {
            return $Candidate
        }
    }

    return $null
}

function Test-ChromeDebug {
    try {
        $VersionUrl = "$($env:CHROME_CDP_URL.TrimEnd('/'))/json/version"
        Invoke-WebRequest -Uri $VersionUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Ensure-ChromeDebug {
    if ($SkipChrome) {
        return
    }
    if (Test-ChromeDebug) {
        return
    }

    $ChromeExe = Find-ChromeExe
    if (-not $ChromeExe) {
        Add-Content -Path (Join-Path $LogsDir "watchdog.log") -Value "[$(Get-Date -Format s)] Chrome nao encontrado. Defina CHROME_EXE_PATH no .env."
        return
    }

    $ChromeProfile = Join-Path $Root ".chrome_bot_profile"
    New-Item -ItemType Directory -Force -Path $ChromeProfile | Out-Null

    Start-Process `
        -FilePath $ChromeExe `
        -ArgumentList @(
            "--remote-debugging-port=9222",
            "--remote-debugging-address=127.0.0.1",
            "--user-data-dir=$ChromeProfile",
            "--disable-gpu",
            "--disable-gpu-sandbox",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            "about:blank"
        ) `
        -WindowStyle Minimized | Out-Null

    Start-Sleep -Seconds 3
}

$Url = "http://127.0.0.1:$($env:WEBAPP_PORT)"
$Opened = $false

while ($true) {
    $Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LogFile = Join-Path $LogsDir "dashboard_$Stamp.log"
    $ErrFile = Join-Path $LogsDir "dashboard_$Stamp.err.log"

    if ($OpenBrowser -and -not $Opened) {
        Start-Job -ScriptBlock {
            param($TargetUrl)
            Start-Sleep -Seconds 5
            Start-Process $TargetUrl
        } -ArgumentList $Url | Out-Null
        $Opened = $true
    }

    Ensure-ChromeDebug

    Add-Content -Path $LogFile -Value "[$(Get-Date -Format s)] starting dashboard on $Url"
    Add-Content -Path $LogFile -Value "[$(Get-Date -Format s)] python: $Python"
    $Process = Start-Process `
        -FilePath $Python `
        -ArgumentList @("-u", "webapp.py") `
        -WorkingDirectory $Root `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError $ErrFile
    $ExitCode = $Process.ExitCode
    Add-Content -Path $LogFile -Value "[$(Get-Date -Format s)] dashboard exited with code $ExitCode; restarting in 5 seconds"
    if ((Test-Path -LiteralPath $ErrFile) -and ((Get-Item -LiteralPath $ErrFile).Length -gt 0)) {
        Add-Content -Path $LogFile -Value "[$(Get-Date -Format s)] stderr:"
        Get-Content -Path $ErrFile | Add-Content -Path $LogFile
    }
    Start-Sleep -Seconds 5
}
