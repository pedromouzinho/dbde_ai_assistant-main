[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [datetime]$StartDate,
    [Parameter(Mandatory = $true)]
    [datetime]$EndDate,
    [string]$MailboxDisplayName,
    [int]$MaxCount = 500,
    [int]$BodyMaxLength = 4000,
    [string]$SubjectContains,
    [string]$SenderContains,
    [string]$OutputPath,
    [string]$OutputDirectory,
    [switch]$OpenFolder
)

$scriptPath = Join-Path $PSScriptRoot "Export-OutlookInbox.ps1"
& $scriptPath `
    -Mode "DateRange" `
    -StartDate $StartDate `
    -EndDate $EndDate `
    -MailboxDisplayName $MailboxDisplayName `
    -MaxCount $MaxCount `
    -BodyMaxLength $BodyMaxLength `
    -SubjectContains $SubjectContains `
    -SenderContains $SenderContains `
    -OutputPath $OutputPath `
    -OutputDirectory $OutputDirectory `
    -OpenFolder:$OpenFolder
