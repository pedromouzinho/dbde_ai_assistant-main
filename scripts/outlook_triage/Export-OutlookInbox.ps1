[CmdletBinding()]
param(
    [ValidateSet("Unread", "All", "Today", "LastNDays", "DateRange")]
    [string]$Mode = "Unread",
    [string]$MailboxDisplayName,
    [Nullable[datetime]]$StartDate,
    [Nullable[datetime]]$EndDate,
    [int]$DaysBack = 7,
    [int]$MaxCount = 250,
    [int]$BodyMaxLength = 4000,
    [string]$SubjectContains,
    [string]$SenderContains,
    [string]$OutputPath,
    [string]$OutputDirectory,
    [switch]$OpenFolder
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common-OutlookInboxExport.ps1")

if ($Mode -eq "DateRange") {
    if (-not $PSBoundParameters.ContainsKey("StartDate") -or -not $PSBoundParameters.ContainsKey("EndDate")) {
        throw "No modo DateRange tens de indicar -StartDate e -EndDate."
    }

    if ($EndDate -lt $StartDate) {
        throw "EndDate nao pode ser anterior a StartDate."
    }
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Get-DbdeDefaultOutputPath -Mode $Mode -OutputDirectory $OutputDirectory
}

$outlook = Get-DbdeOutlookApplication
$namespace = Get-DbdeOutlookNamespace -OutlookApp $outlook
$inbox = Get-DbdeOutlookInboxFolder -Namespace $namespace -MailboxDisplayName $MailboxDisplayName

$rows = Get-DbdeInboxExportRows `
    -InboxFolder $inbox `
    -Mode $Mode `
    -StartDate $StartDate `
    -EndDate $EndDate `
    -DaysBack $DaysBack `
    -MaxCount $MaxCount `
    -BodyMaxLength $BodyMaxLength `
    -SubjectContains $SubjectContains `
    -SenderContains $SenderContains

if ($rows.Count -eq 0) {
    throw "Nao encontrei emails na Inbox com os filtros pedidos."
}

$finalPath = Export-DbdeRowsToCsv -Rows $rows -OutputPath $OutputPath
Write-DbdeExportSummary -OutputPath $finalPath -RowCount $rows.Count -Mode $Mode

if ($OpenFolder) {
    $folderPath = Split-Path -Parent $finalPath
    if (-not [string]::IsNullOrWhiteSpace($folderPath)) {
        Start-Process explorer.exe $folderPath
    }
}
