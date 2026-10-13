[CmdletBinding()]
param(
    [string]$TaskDir = $env:CODEX_TASK_DIR,
    [string]$ReportDateBjt,
    [string]$GeneratorCommand = $env:US_MARKET_RECAP_COMMAND,
    [switch]$SkipGenerate
)

$ErrorActionPreference = 'Stop'

function Resolve-ChinaNow {
    $zone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
    return [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $zone)
}

function Invoke-ConfiguredGenerator {
    param(
        [Parameter(Mandatory = $false)][AllowEmptyString()][string]$Command,
        [Parameter(Mandatory = $true)][string]$DateBjt,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $env:REPORT_DATE_BJT = $DateBjt
    $env:CODEX_TASK_DIR = $Root
    $env:RECAP_OUTPUT_DIR = Join-Path $Root 'outputs'

    $trimmed = $Command.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw @"
No daily recap generator is configured.
Set US_MARKET_RECAP_COMMAND on the self-hosted runner to the existing local
generation command, or pass -GeneratorCommand. The command must create a Word
file named us_market_recap_${DateBjt}_BJT_us_<US_TRADE_DATE>_final.docx under
$($env:RECAP_OUTPUT_DIR) (or D:\codex\outputs\us_market_daily_recaps).
"@
    }

    $quoted = $trimmed.Trim('"')
    if (Test-Path -LiteralPath $quoted -PathType Leaf) {
        $extension = [IO.Path]::GetExtension($quoted).ToLowerInvariant()
        if ($extension -eq '.ps1') {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $quoted `
                -ReportDateBjt $DateBjt -TaskDir $Root
        } elseif ($extension -eq '.py') {
            & python.exe -u $quoted --report-date-bjt $DateBjt --task-dir $Root
        } else {
            throw "US_MARKET_RECAP_COMMAND must point to a .ps1 or .py file, or be a runnable command string: $Command"
        }
    } else {
        # The command string is deliberately opt-in and runs only on the
        # trusted self-hosted machine configured by the user.
        & cmd.exe /d /s /c $trimmed
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Daily recap generator failed with exit code $LASTEXITCODE."
    }
}

function Find-FreshReport {
    param(
        [Parameter(Mandatory = $true)][string]$DateBjt,
        [Parameter(Mandatory = $true)][DateTime]$StartedUtc,
        [Parameter(Mandatory = $true)][string[]]$Directories
    )

    $candidates = @()
    foreach ($directory in ($Directories | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) { continue }
        $pattern = "us_market_recap_${DateBjt}_BJT_us_*_final.docx"
        $candidates += Get-ChildItem -LiteralPath $directory -Filter $pattern -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTimeUtc -ge $StartedUtc.AddMinutes(-2) }
    }
    return $candidates | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($TaskDir)) {
    $TaskDir = Split-Path -Parent $PSScriptRoot
}
$TaskDir = (Resolve-Path -LiteralPath $TaskDir).Path
$taskOutput = Join-Path $TaskDir 'outputs'
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null

$nowBjt = Resolve-ChinaNow
if ([string]::IsNullOrWhiteSpace($ReportDateBjt)) {
    $ReportDateBjt = $nowBjt.ToString('yyyy-MM-dd')
}
if ($ReportDateBjt -notmatch '^\d{4}-\d{2}-\d{2}$') {
    throw "ReportDateBjt must use yyyy-MM-dd: $ReportDateBjt"
}

$startedUtc = [DateTime]::UtcNow
$sourceOutput = if ($env:RECAP_OUTPUT_DIR) { $env:RECAP_OUTPUT_DIR } else { 'D:\codex\outputs\us_market_daily_recaps' }
$searchDirectories = @($taskOutput, $sourceOutput, 'D:\codex\outputs\us_market_daily_recaps')

if (-not $SkipGenerate) {
    Invoke-ConfiguredGenerator -Command $GeneratorCommand -DateBjt $ReportDateBjt -Root $TaskDir
}

$report = Find-FreshReport -DateBjt $ReportDateBjt -StartedUtc $startedUtc -Directories $searchDirectories
if ($null -eq $report) {
    throw "No fresh Word report found for Beijing date $ReportDateBjt. Refusing to send a stale report to Feishu."
}

# Keep a local copy in the existing task folder even when the generator uses
# the skill's canonical D:\codex output directory.
$localReport = Join-Path $taskOutput $report.Name
if ((Resolve-Path -LiteralPath $report.FullName).Path -ne (Resolve-Path -LiteralPath $localReport -ErrorAction SilentlyContinue).Path) {
    Copy-Item -LiteralPath $report.FullName -Destination $localReport -Force
    $sourceMarkdown = [IO.Path]::ChangeExtension($report.FullName, '.md')
    if (Test-Path -LiteralPath $sourceMarkdown -PathType Leaf) {
        Copy-Item -LiteralPath $sourceMarkdown -Destination (Join-Path $taskOutput ([IO.Path]::GetFileName($sourceMarkdown))) -Force
    }
    $report = Get-Item -LiteralPath $localReport
}

$runUrl = ''
if ($env:GITHUB_SERVER_URL -and $env:GITHUB_REPOSITORY -and $env:GITHUB_RUN_ID) {
    $runUrl = "$($env:GITHUB_SERVER_URL)/$($env:GITHUB_REPOSITORY)/actions/runs/$($env:GITHUB_RUN_ID)"
}
$python = (Get-Command python.exe -ErrorAction Stop).Source
$sender = Join-Path $PSScriptRoot 'send_feishu_webhook.py'
$senderArgs = @('-u', $sender, '--report', $report.FullName, '--status', 'generated')
if ($runUrl) { $senderArgs += @('--run-url', $runUrl) }
& $python @senderArgs
if ($LASTEXITCODE -ne 0) {
    throw "Feishu notification failed with exit code $LASTEXITCODE."
}

$manifest = [ordered]@{
    report_date_bjt = $ReportDateBjt
    generated_at_bjt = (Resolve-ChinaNow).ToString('o')
    report_path = $report.FullName
    report_name = $report.Name
    run_url = $runUrl
}
$manifestPath = Join-Path $taskOutput 'latest_daily_recap.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output ($manifest | ConvertTo-Json -Depth 4 -Compress)
