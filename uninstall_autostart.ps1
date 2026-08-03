$ErrorActionPreference = "Stop"

$TaskName = "FreelanceBot-Dashboard"

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Tarefa removida: $TaskName"
} else {
    Write-Output "Tarefa nao encontrada: $TaskName"
}

$StartupDir = [Environment]::GetFolderPath("Startup")
$StartupFile = Join-Path $StartupDir "FreelanceBot-Dashboard.cmd"
if (Test-Path -LiteralPath $StartupFile) {
    Remove-Item -LiteralPath $StartupFile -Force
    Write-Output "Atalho de inicializacao removido: $StartupFile"
}
