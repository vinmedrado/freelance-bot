$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "FreelanceBot-Dashboard"
$Script = Join-Path $Root "start_dashboard_forever.ps1"

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Script nao encontrado: $Script"
}

try {
    $Action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""

    $LogonTrigger = New-ScheduledTaskTrigger -AtLogOn

    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Days 3650)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $LogonTrigger `
        -Settings $Settings `
        -Description "Mantem o dashboard Flask do freelance_bot ativo em 0.0.0.0:5050." `
        -Force | Out-Null

    Start-ScheduledTask -TaskName $TaskName
    Write-Output "Tarefa instalada e iniciada: $TaskName"
} catch {
    $StartupDir = [Environment]::GetFolderPath("Startup")
    $StartupFile = Join-Path $StartupDir "FreelanceBot-Dashboard.cmd"
    $Content = @"
@echo off
start "FreelanceBot Watchdog" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$Script"
"@
    Set-Content -Path $StartupFile -Value $Content -Encoding ASCII
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""
    Write-Output "Sem permissao para registrar tarefa. Atalho de inicializacao criado: $StartupFile"
}

Write-Output "Notebook: http://127.0.0.1:5050"
Write-Output "Celular na mesma rede: http://IP_DO_NOTEBOOK:5050"
