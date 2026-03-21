Set-StrictMode -Version Latest

function Convert-DbdeSafeString {
    param(
        [AllowNull()]
        $Value
    )

    if ($null -eq $Value) {
        return ""
    }

    return [string]$Value
}

function Get-DbdeOutlookApplication {
    try {
        return New-Object -ComObject Outlook.Application
    } catch {
        throw "Nao foi possivel iniciar o Outlook via COM. Confirma que o Outlook desktop esta instalado e configurado nesta maquina."
    }
}

function Get-DbdeOutlookNamespace {
    param(
        [Parameter(Mandatory = $true)]
        $OutlookApp
    )

    try {
        return $OutlookApp.GetNamespace("MAPI")
    } catch {
        throw "Nao foi possivel obter o namespace MAPI do Outlook."
    }
}

function Get-DbdeOutlookInboxFolder {
    param(
        [Parameter(Mandatory = $true)]
        $Namespace,
        [string]$MailboxDisplayName
    )

    if (-not [string]::IsNullOrWhiteSpace($MailboxDisplayName)) {
        foreach ($store in $Namespace.Stores) {
            if ($store.DisplayName -ieq $MailboxDisplayName) {
                return $store.GetDefaultFolder(6)
            }
        }

        throw "Nao encontrei a mailbox '$MailboxDisplayName' no Outlook."
    }

    return $Namespace.GetDefaultFolder(6)
}

function Convert-DbdeSenderAddress {
    param(
        [Parameter(Mandatory = $true)]
        $MailItem
    )

    try {
        if ($MailItem.SenderEmailType -eq "EX" -and $MailItem.Sender) {
            $exchangeUser = $MailItem.Sender.GetExchangeUser()
            if ($exchangeUser -and -not [string]::IsNullOrWhiteSpace($exchangeUser.PrimarySmtpAddress)) {
                return [string]$exchangeUser.PrimarySmtpAddress
            }
        }
    } catch {
    }

    try {
        return (Convert-DbdeSafeString $MailItem.SenderEmailAddress)
    } catch {
        return ""
    }
}

function Convert-DbdeBodyText {
    param(
        [string]$Text,
        [int]$BodyMaxLength = 4000
    )

    $clean = Convert-DbdeSafeString $Text
    $clean = $clean -replace "`0", ""
    $clean = $clean -replace "`r`n", "`n"
    $clean = $clean -replace "`r", "`n"
    $clean = $clean.Trim()

    if ($BodyMaxLength -gt 0 -and $clean.Length -gt $BodyMaxLength) {
        $clean = $clean.Substring(0, $BodyMaxLength)
    }

    return $clean
}

function Get-DbdeAttachmentNames {
    param(
        [Parameter(Mandatory = $true)]
        $MailItem
    )

    $names = New-Object System.Collections.Generic.List[string]

    try {
        foreach ($attachment in $MailItem.Attachments) {
            $fileName = Convert-DbdeSafeString $attachment.FileName
            if (-not [string]::IsNullOrWhiteSpace($fileName)) {
                [void]$names.Add($fileName)
            }
        }
    } catch {
    }

    return ($names -join "; ")
}

function New-DbdeMessageInput {
    param(
        [hashtable]$Record
    )

    $bodyOneLine = Convert-DbdeSafeString $Record.Body
    $bodyOneLine = $bodyOneLine -replace "\s+", " "
    $bodyOneLine = $bodyOneLine -replace "\|", "/"
    $bodyOneLine = $bodyOneLine.Trim()

    return (
        "EntryID: {0} | StoreID: {1} | Subject: {2} | From: {3} | SenderName: {4} | ReceivedTime: {5} | Importance: {6} | Attachments: {7} | Body: {8}" -f
        $Record.EntryID,
        $Record.StoreID,
        $Record.Subject,
        $Record.From,
        $Record.SenderName,
        $Record.ReceivedTime,
        $Record.Importance,
        $Record.Attachments,
        $bodyOneLine
    )
}

function Test-DbdeMailItemMatchesFilters {
    param(
        [Parameter(Mandatory = $true)]
        $MailItem,
        [Parameter(Mandatory = $true)]
        [ValidateSet("Unread", "All", "Today", "LastNDays", "DateRange")]
        [string]$Mode,
        [Nullable[datetime]]$StartDate,
        [Nullable[datetime]]$EndDate,
        [int]$DaysBack = 7,
        [string]$SubjectContains,
        [string]$SenderContains
    )

    try {
        if ($MailItem.Class -ne 43) {
            return $false
        }
    } catch {
        return $false
    }

    try {
        $received = [datetime]$MailItem.ReceivedTime
    } catch {
        return $false
    }

    switch ($Mode) {
        "Unread" {
            try {
                if (-not [bool]$MailItem.UnRead) {
                    return $false
                }
            } catch {
                return $false
            }
        }
        "Today" {
            $effectiveStart = (Get-Date).Date
            $effectiveEnd = $effectiveStart.AddDays(1)
            if ($received -lt $effectiveStart -or $received -ge $effectiveEnd) {
                return $false
            }
        }
        "LastNDays" {
            $effectiveStart = (Get-Date).Date.AddDays(-1 * [Math]::Max($DaysBack, 1))
            if ($received -lt $effectiveStart) {
                return $false
            }
        }
        "DateRange" {
            if (-not $PSBoundParameters.ContainsKey("StartDate") -or -not $PSBoundParameters.ContainsKey("EndDate")) {
                throw "No modo DateRange tens de indicar StartDate e EndDate."
            }
            if ($received -lt $StartDate -or $received -gt $EndDate) {
                return $false
            }
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($SubjectContains)) {
        $subject = Convert-DbdeSafeString $MailItem.Subject
        if ($subject.IndexOf($SubjectContains, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            return $false
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($SenderContains)) {
        $senderText = @(
            (Convert-DbdeSafeString $MailItem.SenderName)
            [string](Convert-DbdeSenderAddress -MailItem $MailItem)
        ) -join " | "

        if ($senderText.IndexOf($SenderContains, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            return $false
        }
    }

    return $true
}

function Convert-DbdeMailItemToRecord {
    param(
        [Parameter(Mandatory = $true)]
        $MailItem,
        [Parameter(Mandatory = $true)]
        [string]$StoreId,
        [int]$BodyMaxLength = 4000
    )

    $body = Convert-DbdeBodyText -Text (Convert-DbdeSafeString $MailItem.Body) -BodyMaxLength $BodyMaxLength
    $attachments = Get-DbdeAttachmentNames -MailItem $MailItem
    $senderAddress = Convert-DbdeSenderAddress -MailItem $MailItem

    $record = [ordered]@{
        EntryID           = (Convert-DbdeSafeString $MailItem.EntryID)
        StoreID           = [string]$StoreId
        Subject           = (Convert-DbdeSafeString $MailItem.Subject)
        From              = $senderAddress
        SenderName        = (Convert-DbdeSafeString $MailItem.SenderName)
        To                = (Convert-DbdeSafeString $MailItem.To)
        CC                = (Convert-DbdeSafeString $MailItem.CC)
        ReceivedTime      = ([datetime]$MailItem.ReceivedTime).ToString("s")
        SentOn            = ([datetime]$MailItem.SentOn).ToString("s")
        Importance        = (Convert-DbdeSafeString $MailItem.Importance)
        Unread            = [string]([bool]($MailItem.UnRead))
        Categories        = (Convert-DbdeSafeString $MailItem.Categories)
        AttachmentCount   = [int]($MailItem.Attachments.Count)
        Attachments       = $attachments
        ConversationTopic = (Convert-DbdeSafeString $MailItem.ConversationTopic)
        ConversationID    = (Convert-DbdeSafeString $MailItem.ConversationID)
        Body              = $body
    }

    $record.MessageInput = New-DbdeMessageInput -Record $record
    return [pscustomobject]$record
}

function Get-DbdeInboxExportRows {
    param(
        [Parameter(Mandatory = $true)]
        $InboxFolder,
        [ValidateSet("Unread", "All", "Today", "LastNDays", "DateRange")]
        [string]$Mode = "Unread",
        [Nullable[datetime]]$StartDate,
        [Nullable[datetime]]$EndDate,
        [int]$DaysBack = 7,
        [int]$MaxCount = 250,
        [int]$BodyMaxLength = 4000,
        [string]$SubjectContains,
        [string]$SenderContains
    )

    $items = $InboxFolder.Items
    $items.Sort("[ReceivedTime]", $true)

    $storeId = Convert-DbdeSafeString $InboxFolder.StoreID
    $rows = New-Object System.Collections.Generic.List[object]

    foreach ($item in $items) {
        try {
            $matches = Test-DbdeMailItemMatchesFilters `
                -MailItem $item `
                -Mode $Mode `
                -StartDate $StartDate `
                -EndDate $EndDate `
                -DaysBack $DaysBack `
                -SubjectContains $SubjectContains `
                -SenderContains $SenderContains

            if (-not $matches) {
                continue
            }

            $record = Convert-DbdeMailItemToRecord -MailItem $item -StoreId $storeId -BodyMaxLength $BodyMaxLength
            [void]$rows.Add($record)

            if ($MaxCount -gt 0 -and $rows.Count -ge $MaxCount) {
                break
            }
        } catch {
            Write-Warning ("Falha ao processar um email da Inbox: {0}" -f $_.Exception.Message)
        }
    }

    return $rows
}

function Get-DbdeDefaultOutputPath {
    param(
        [string]$Mode = "Unread",
        [string]$OutputDirectory
    )

    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        $OutputDirectory = Join-Path $PSScriptRoot "exports"
    }

    if (-not (Test-Path $OutputDirectory)) {
        New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    }

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $safeMode = ($Mode -replace "[^A-Za-z0-9_-]", "_")
    return Join-Path $OutputDirectory ("outlook_inbox_{0}_{1}.csv" -f $safeMode.ToLowerInvariant(), $timestamp)
}

function Export-DbdeRowsToCsv {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IEnumerable]$Rows,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $parent = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $csv = $Rows | ConvertTo-Csv -NoTypeInformation
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllLines($OutputPath, $csv, $utf8Bom)
    return (Resolve-Path $OutputPath).Path
}

function Write-DbdeExportSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [int]$RowCount,
        [Parameter(Mandatory = $true)]
        [string]$Mode
    )

    Write-Host ""
    Write-Host "Export concluido." -ForegroundColor Green
    Write-Host ("Ficheiro: {0}" -f $OutputPath)
    Write-Host ("Modo: {0}" -f $Mode)
    Write-Host ("Emails exportados: {0}" -f $RowCount)
    Write-Host ""
    Write-Host "Proximo passo no DBDE:" -ForegroundColor Cyan
    Write-Host "1. Carregar o CSV na conversa."
    Write-Host "2. Pedir a triagem, por exemplo:"
    Write-Host '   "Classifica estes emails: marca como Urgente os que indiquem bloqueio operacional, Review os que peçam analise humana e Ignore newsletters."'
    Write-Host "3. Descarregar e executar o .ps1 de acoes que o DBDE gerar para o Outlook."
    Write-Host ""
}
