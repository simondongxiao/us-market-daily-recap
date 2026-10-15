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
        $defaultGenerator = Join-Path $Root 'scripts\generate_daily_recap.py'
        if (Test-Path -LiteralPath $defaultGenerator -PathType Leaf) {
            $trimmed = $defaultGenerator
        } else {
            throw @"
No daily recap generator is configured.
Set US_MARKET_RECAP_COMMAND on the self-hosted runner to the existing local
generation command, or add scripts\generate_daily_recap.py. The command must
create a Word file named us_market_recap_${DateBjt}_BJT_us_<US_TRADE_DATE>_final.docx
under $($env:RECAP_OUTPUT_DIR) (or D:\codex\outputs\us_market_daily_recaps).
"@
        }
    }

    $quoted = $trimmed.Trim('"')
    if (Test-Path -LiteralPath $quoted -PathType Leaf) {
        $extension = [IO.Path]::GetExtension($quoted).ToLowerInvariant()
        if ($extension -eq '.ps1') {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $quoted `
                -ReportDateBjt $DateBjt -TaskDir $Root
        } elseif ($extension -eq '.py') {
            $runnerPython = if (Test-Path -LiteralPath 'D:\python\python.exe' -PathType Leaf) {
                'D:\python\python.exe'
            } else {
                (Get-Command python.exe -ErrorAction Stop).Source
            }
            & $runnerPython -u $quoted --report-date-bjt $DateBjt --task-dir $Root
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
$manifestPath = Join-Path $taskOutput 'latest_daily_recap.json'

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
$audit = [ordered]@{
    status = 'running'
    report_date_bjt = $ReportDateBjt
    started_at_bjt = (Resolve-ChinaNow).ToString('o')
    task_dir = $TaskDir
    generator_command = $GeneratorCommand
    output_directories = $searchDirectories
    stages = [ordered]@{
        generation = [ordered]@{ status = 'pending' }
        word_validation = [ordered]@{ status = 'pending' }
        html_validation = [ordered]@{ status = 'pending' }
        consistency_validation = [ordered]@{ status = 'pending' }
        dedupe_check = [ordered]@{ status = 'pending' }
        github_upload = [ordered]@{ status = 'pending' }
        pages_verification = [ordered]@{ status = 'pending' }
        feishu_notification = [ordered]@{ status = 'pending' }
        delivery_state = [ordered]@{ status = 'pending' }
    }
}
$report = $null
$publishInfo = $null
$currentStage = 'initialization'

function Save-Audit {
    $audit.updated_at_bjt = (Resolve-ChinaNow).ToString('o')
    $audit | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

function Set-AuditStage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$Detail = ''
    )
    $entry = [ordered]@{ status = $Status; at_bjt = (Resolve-ChinaNow).ToString('o') }
    if ($Detail) { $entry.detail = $Detail }
    $audit.stages[$Name] = $entry
    Save-Audit
}

try {
    Save-Audit
    Write-Output "Report date (BJT): $ReportDateBjt"
    Write-Output "Generator command: $GeneratorCommand"
    Write-Output "Output root: $($env:RECAP_OUTPUT_DIR)"

    if (-not $SkipGenerate) {
        $currentStage = 'generation'
        Invoke-ConfiguredGenerator -Command $GeneratorCommand -DateBjt $ReportDateBjt -Root $TaskDir
        Set-AuditStage -Name 'generation' -Status 'success'
    } else {
        Set-AuditStage -Name 'generation' -Status 'skipped'
    }

    $currentStage = 'word_validation'
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
        $sourceHtml = [IO.Path]::ChangeExtension($report.FullName, '.html')
        if (Test-Path -LiteralPath $sourceHtml -PathType Leaf) {
            Copy-Item -LiteralPath $sourceHtml -Destination (Join-Path $taskOutput ([IO.Path]::GetFileName($sourceHtml))) -Force
        }
        $report = Get-Item -LiteralPath $localReport
    }
    if ($report.Length -le 0) { throw "Word report is empty: $($report.FullName)" }
    $audit.report_path = $report.FullName
    $audit.report_name = $report.Name
    if ($report.Name -notmatch "^us_market_recap_${ReportDateBjt}_BJT_us_(?<trade>\d{4}-\d{2}-\d{2})_final\.docx$") {
        throw "Report filename does not contain a valid US trade date: $($report.Name)"
    }
    $usTradeDate = $Matches.trade
    Set-AuditStage -Name 'word_validation' -Status 'success' -Detail "$($report.Length) bytes; US trade date $usTradeDate"

    $currentStage = 'html_validation'
    $htmlPath = [IO.Path]::ChangeExtension($report.FullName, '.html')
    if (-not (Test-Path -LiteralPath $htmlPath -PathType Leaf)) { throw "HTML report is missing: $htmlPath" }
    $htmlItem = Get-Item -LiteralPath $htmlPath
    if ($htmlItem.Length -le 1000) { throw "HTML report is unexpectedly small: $htmlPath ($($htmlItem.Length) bytes)" }
    $audit.html_path = $htmlPath
    Set-AuditStage -Name 'html_validation' -Status 'success' -Detail "$($htmlItem.Length) bytes"

    $python = if (Test-Path -LiteralPath 'D:\python\python.exe' -PathType Leaf) {
        'D:\python\python.exe'
    } else {
        (Get-Command python.exe -ErrorAction Stop).Source
    }
    $validator = Join-Path $PSScriptRoot 'validate_recap_consistency.py'
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) { throw "Consistency validator is missing: $validator" }
    $dataRoot = @(
        (Join-Path $sourceOutput $ReportDateBjt),
        (Join-Path (Split-Path -Parent $report.FullName) $ReportDateBjt),
        (Join-Path $TaskDir "outputs\$ReportDateBjt")
    ) | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'source_audit.json') -PathType Leaf } | Select-Object -First 1
    $previousHtml = Get-ChildItem -Path @((Join-Path $TaskDir 'reports'), $taskOutput, $sourceOutput) -Filter 'us_market_recap_*_final.html' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne $htmlPath -and $_.Name -notmatch "_${ReportDateBjt}_BJT_" } |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    $currentStage = 'consistency_validation'
    $validationArgs = @('-u', $validator, '--report', $report.FullName, '--html', $htmlPath, '--report-date-bjt', $ReportDateBjt, '--us-trade-date', $usTradeDate)
    if ($dataRoot) { $validationArgs += @('--source-root', $dataRoot) }
    if ($previousHtml) { $validationArgs += @('--previous-html', $previousHtml.FullName) }
    $validationLines = @(& $python @validationArgs)
    if ($LASTEXITCODE -ne 0) { throw "Report consistency validation failed: $($validationLines | Select-Object -Last 1)" }
    $consistency = (($validationLines | Select-Object -Last 1) | ConvertFrom-Json)
    $audit.consistency = $consistency
    $consistencyDetail = 'ok'
    if ($consistency.warnings.Count -gt 0) { $consistencyDetail = "data_quality_warning; $($consistency.warnings -join '; ')" }
    Set-AuditStage -Name 'consistency_validation' -Status 'success' -Detail $consistencyDetail

    $wordHash = (Get-FileHash -LiteralPath $report.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $htmlHash = (Get-FileHash -LiteralPath $htmlPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $contentVersion = "$($wordHash):$($htmlHash)"
    $audit.content_version = $contentVersion
    $stateScript = Join-Path $PSScriptRoot 'delivery_state.py'
    if (-not (Test-Path -LiteralPath $stateScript -PathType Leaf)) { throw "Delivery state script is missing: $stateScript" }
    $currentStage = 'dedupe_check'
        $stateCheckLines = @(& $python -u $stateScript check --report-date-bjt $ReportDateBjt --us-trade-date $usTradeDate --content-version $contentVersion)
    if ($LASTEXITCODE -ne 0) {
        $audit.dedupe_warning = ($stateCheckLines -join ' ')
        Set-AuditStage -Name 'dedupe_check' -Status 'unavailable' -Detail 'state lookup failed; continuing with delivery and recording the condition'
        $stateCheck = [pscustomobject]@{ duplicate = $false; has_success_for_report_date = $false }
    } else {
        $stateCheck = (($stateCheckLines | Select-Object -Last 1) | ConvertFrom-Json)
        $audit.dedupe = $stateCheck
        $dedupeDetail = 'new or revised content'
        if ($stateCheck.duplicate) { $dedupeDetail = 'duplicate delivery suppressed' }
        Set-AuditStage -Name 'dedupe_check' -Status 'success' -Detail $dedupeDetail
    }
    $runUrl = ''
    if ($env:GITHUB_SERVER_URL -and $env:GITHUB_REPOSITORY -and $env:GITHUB_RUN_ID) {
        $runUrl = "$($env:GITHUB_SERVER_URL)/$($env:GITHUB_REPOSITORY)/actions/runs/$($env:GITHUB_RUN_ID)"
    }
    if ($stateCheck.duplicate) {
        $matched = $stateCheck.matched
        $audit.status = 'deduplicated'
        $audit.html_url = $matched.html_url
        $audit.word_url = $matched.word_url
        $audit.run_url = $runUrl
        $audit.deduplicated_from = $matched.run_url
        Set-AuditStage -Name 'github_upload' -Status 'skipped' -Detail 'same report content already sent'
        Set-AuditStage -Name 'pages_verification' -Status 'skipped' -Detail 'same report content already verified'
        Set-AuditStage -Name 'feishu_notification' -Status 'skipped' -Detail 'same report content already sent'
        Set-AuditStage -Name 'delivery_state' -Status 'success' -Detail 'existing sent state reused'
        Save-Audit
        Write-Output ($audit | ConvertTo-Json -Depth 8 -Compress)
        exit 0
    }

    $notificationStatus = if ($stateCheck.has_success_for_report_date) { 'revision' } else { 'generated' }
    $currentStage = 'github_upload'
    $publisher = Join-Path $PSScriptRoot 'publish_report_to_github.py'
    if (-not (Test-Path -LiteralPath $publisher -PathType Leaf)) { throw "Publisher is missing: $publisher" }
    $publishArgs = @('-u', $publisher, '--report', $report.FullName)
    $publishLines = @(& $python @publishArgs)
    if ($LASTEXITCODE -ne 0) { throw "GitHub report publication failed with exit code $LASTEXITCODE." }
    $publishInfo = (($publishLines | Select-Object -Last 1) | ConvertFrom-Json)
    if (-not $publishInfo.html_url -or -not $publishInfo.word_url) { throw 'Publisher returned incomplete public URLs.' }
    Set-AuditStage -Name 'github_upload' -Status 'success' -Detail "$($publishInfo.word_url)"
    $currentStage = 'pages_verification'
    if (-not $publishInfo.pages_verified) { throw 'Publisher did not verify the public Pages URL.' }
    $audit.html_url = $publishInfo.html_url
    $audit.word_url = $publishInfo.word_url
    $audit.pages = $publishInfo.pages
    Set-AuditStage -Name 'pages_verification' -Status 'success' -Detail "$($publishInfo.html_url)"
    Write-Output ($publishInfo | ConvertTo-Json -Depth 8 -Compress)

    $sender = Join-Path $PSScriptRoot 'send_feishu_webhook.py'
    if (-not (Test-Path -LiteralPath $sender -PathType Leaf)) { throw "Feishu sender is missing: $sender" }
    $senderArgs = @('-u', $sender, '--report', $report.FullName, '--status', $notificationStatus, '--github-url', $publishInfo.html_url, '--word-url', $publishInfo.word_url)
    if ($runUrl) { $senderArgs += @('--run-url', $runUrl) }
    $currentStage = 'feishu_notification'
    & $python @senderArgs
    $feishuExit = $LASTEXITCODE
    if ($feishuExit -eq 2) {
        $audit.delivery_status = 'UNKNOWN_DELIVERY'
        Set-AuditStage -Name 'feishu_notification' -Status 'unknown_delivery' -Detail 'network/response ambiguity; retry is allowed'
        throw 'Feishu notification returned UNKNOWN_DELIVERY.'
    }
    if ($feishuExit -ne 0) { throw "Feishu notification failed with exit code $feishuExit." }
    Set-AuditStage -Name 'feishu_notification' -Status 'success'

    $currentStage = 'delivery_state'
    $recordArgs = @('-u', $stateScript, 'record', '--report-date-bjt', $ReportDateBjt, '--us-trade-date', $usTradeDate, '--content-version', $contentVersion, '--html-url', $publishInfo.html_url, '--word-url', $publishInfo.word_url, '--status', 'sent')
    if ($runUrl) { $recordArgs += @('--run-url', $runUrl) }
    $recorded = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        & $python @recordArgs | Out-Null
        if ($LASTEXITCODE -eq 0) { $recorded = $true; break }
        Start-Sleep -Seconds ([math]::Min(8, 2 * $attempt))
    }
    if (-not $recorded) { throw 'Delivery was sent but persistent sent-state recording failed.' }
    Set-AuditStage -Name 'delivery_state' -Status 'success' -Detail 'sent state persisted to GitHub'

    $audit.status = 'success'
    $audit.report_date_bjt = $ReportDateBjt
    $audit.generated_at_bjt = (Resolve-ChinaNow).ToString('o')
    $audit.run_url = $runUrl
    Save-Audit
    Write-Output ($audit | ConvertTo-Json -Depth 8 -Compress)
} catch {
    $audit.status = 'failed'
    $audit.error = $_.Exception.Message
    $audit.failure_phase = $currentStage
    if ($audit.stages.Contains($currentStage) -and $audit.stages[$currentStage].status -eq 'pending') {
        $audit.stages[$currentStage] = [ordered]@{ status = 'failed'; at_bjt = (Resolve-ChinaNow).ToString('o'); detail = $audit.error }
    }
    if ($report) { $audit.report_path = $report.FullName; $audit.report_name = $report.Name }
    Save-Audit
    Write-Error "Daily recap pipeline failed: $($_.Exception.Message)"
    exit 1
}
