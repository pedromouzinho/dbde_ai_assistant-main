# Outlook Inbox Triage Setup

Este diretório prepara a extração de emails diretamente da `Inbox` do Outlook desktop para alimentar a triagem no DBDE AI Assistant.

O fluxo pensado é este:

1. Exportar emails da Inbox para CSV com um dos scripts abaixo.
2. Carregar o CSV na conversa do DBDE.
3. Pedir a triagem dos emails com instruções claras.
4. Descarregar o pack gerado pelo DBDE.
5. Executar o `.ps1` de ações no Outlook que o DBDE devolver.

## O que os scripts exportam

Os CSVs saem num formato já alinhado com os tools de email do DBDE:

- `EntryID`
- `StoreID`
- `Subject`
- `From`
- `SenderName`
- `To`
- `CC`
- `ReceivedTime`
- `SentOn`
- `Importance`
- `Unread`
- `Categories`
- `AttachmentCount`
- `Attachments`
- `ConversationTopic`
- `ConversationID`
- `Body`
- `MessageInput`

`MessageInput` vai num formato de texto compatível com o parser interno do DBDE.

## Scripts disponíveis

- `Export-OutlookInbox.ps1`
  - script principal
  - modos: `Unread`, `All`, `Today`, `LastNDays`, `DateRange`

- `Export-OutlookInbox-Unread.ps1`
  - exporta emails não lidos da Inbox

- `Export-OutlookInbox-All.ps1`
  - exporta todos os emails da Inbox

- `Export-OutlookInbox-Today.ps1`
  - exporta os emails de hoje

- `Export-OutlookInbox-LastNDays.ps1`
  - exporta emails dos últimos `N` dias

- `Export-OutlookInbox-Period.ps1`
  - exporta emails entre duas datas

## Pré-requisitos

- Windows com Outlook desktop instalado e configurado
- PowerShell
- Outlook com a mailbox aberta

## Utilização rápida

### 1. Não lidos

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Export-OutlookInbox-Unread.ps1 -OpenFolder
```

### 2. Todos os emails

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Export-OutlookInbox-All.ps1 -MaxCount 500 -OpenFolder
```

### 3. Hoje

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Export-OutlookInbox-Today.ps1 -OpenFolder
```

### 4. Últimos 7 dias

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Export-OutlookInbox-LastNDays.ps1 -DaysBack 7 -OpenFolder
```

### 5. Período específico

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Export-OutlookInbox-Period.ps1 `
  -StartDate "2026-03-01 00:00:00" `
  -EndDate "2026-03-15 23:59:59" `
  -OpenFolder
```

### 6. Script principal

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Export-OutlookInbox.ps1 `
  -Mode DateRange `
  -StartDate "2026-03-01 00:00:00" `
  -EndDate "2026-03-31 23:59:59" `
  -MaxCount 300 `
  -SubjectContains "incidente" `
  -OpenFolder
```

## Parâmetros úteis

- `-MailboxDisplayName`
  - útil se tiveres várias mailboxes no Outlook
  - se não indicares nada, usa a Inbox por defeito do Outlook

- `-MaxCount`
  - limita o número de emails exportados
  - recomendado para não carregar CSVs gigantes na triagem

- `-BodyMaxLength`
  - controla o tamanho máximo do `Body` exportado por email

- `-SubjectContains`
  - filtra por texto no assunto

- `-SenderContains`
  - filtra por remetente ou nome do remetente

- `-OutputPath`
  - caminho final do CSV

- `-OutputDirectory`
  - diretório onde o CSV será criado

- `-OpenFolder`
  - abre a pasta do ficheiro exportado no fim

## Prompts recomendados no DBDE

### Triage simples

```text
Classifica estes emails: marca como Urgente os que indiquem bloqueio operacional, Review os que peçam análise humana e Ignore newsletters.
```

### Triage orientada a cliente

```text
Classifica estes emails: Urgente para incidentes ou pedidos com SLA hoje, FollowUp para temas com resposta necessária esta semana, FYI para informação sem ação.
```

### Triage para Outlook com ações

```text
Classifica estes emails e prepara ações para Outlook: Urgente -> flag today, Review -> category AI-Review, Ignore -> none.
```

## Resultado esperado do DBDE

Quando o DBDE classifica os emails, deves esperar um pack com:

- `.xlsx` com `Output`, `Actions` e `Config`
- `.csv` com as ações e labels
- `.json` de manifesto
- `.ps1` para aplicar as ações diretamente no Outlook

## Notas importantes

- estes scripts trabalham sempre sobre a `Inbox` do Outlook desktop
- não percorrem subpastas
- o `EntryID` e o `StoreID` são exportados para permitir que o DBDE devolva ações aplicáveis no Outlook
- se a Inbox for muito grande, usa `-MaxCount` ou um filtro por período
