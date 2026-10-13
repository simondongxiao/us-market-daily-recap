$ErrorActionPreference = 'Continue'
$taskDir = 'C:\Users\Administrator\Documents\Codex\2026-08-10\us-market-daily-recap'
$logDir = Join-Path $taskDir 'outputs\scheduler_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("run_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
try {
    Start-Transcript -Path $log -Force | Out-Null
    $env:CODEX_TASK_DIR = $taskDir
    $env:FEISHU_WEBHOOK_URL = [Environment]::GetEnvironmentVariable('FEISHU_WEBHOOK_URL', 'Machine')
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $taskDir 'scripts\run_daily_recap.ps1') -TaskDir $taskDir
    $code = $LASTEXITCODE
} catch {
    Write-Error $_
    $code = 1
} finally {
    Stop-Transcript | Out-Null
}
exit $code
