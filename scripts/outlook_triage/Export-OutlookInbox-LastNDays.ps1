[CmdletBinding()]
param(
    [int]$DaysBack = 7,
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
    -Mode "LastNDays" `
    -DaysBack $DaysBack `
    -MailboxDisplayName $MailboxDisplayName `
    -MaxCount $MaxCount `
    -BodyMaxLength $BodyMaxLength `
    -SubjectContains $SubjectContains `
    -SenderContains $SenderContains `
    -OutputPath $OutputPath `
    -OutputDirectory $OutputDirectory `
    -OpenFolder:$OpenFolder
