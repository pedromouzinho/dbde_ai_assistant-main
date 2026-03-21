# Auditoria Infraestrutura Azure — 21 de Março 2026

> **Subscription**: Azure subscription 1 (`84949c46-...`)
> **Tenant**: `5d89951c-...` (bcpcorp.net)
> **Resource Group**: `rg-MS_Access_Chabot` — Sweden Central
> **App Version**: 8.0.0 (Fase H)
> **Validado live em**: 2026-03-21

---

## 1. Inventário de Recursos (22 recursos)

| Recurso | Tipo | SKU/Tier | Região |
|---------|------|----------|--------|
| `millennium-ai-assistant` | App Service (Linux, Python 3.12) | P1v3 | Sweden Central |
| `millennium-ai-assistant-worker` | App Service (Linux, Python 3.12) | P1v3 (partilhado) | Sweden Central |
| `plan-dbde-v2` | App Service Plan | P1v3, 2 workers | Sweden Central |
| `dbdeaccessstorage` | Storage Account | Standard_RAGRS | Sweden Central |
| `ms-access-chabot-resource` | AI Services (OpenAI + Foundry) | S0 | Sweden Central |
| `dbde-pii` | Text Analytics | S | Sweden Central |
| `dbde-doc-intel` | Document Intelligence | S0 | Sweden Central |
| `dbde-content-safety` | Content Safety | S0 | Sweden Central |
| `dbde-speech` | Speech Services | S0 | Sweden Central |
| `dbdeacessrag` | AI Search | Free (legacy) | Sweden Central |
| `dbdeacessrag-basic` | AI Search (**em uso**) | Basic | Sweden Central |
| `dbde-ai-vault` | Key Vault | Standard | Sweden Central |
| `cosmosdbrgmsaccesschabot84949c` | Cosmos DB | Standard, Session | Sweden Central |
| `millennium-ai-assistant` | Application Insights | 90d retention | Sweden Central |
| `dbde-ai-logs` | Log Analytics Workspace | — | Sweden Central |
| `dbde-access-agent` | Automation Account | — | Sweden Central |
| `dbde-access-agent/Ingestion_Daily` | Automation Runbook | — | Sweden Central |

---

## 2. Model Deployments (AI Services)

| Deployment | Modelo | TPM | RPM | Uso em produção |
|-----------|--------|-----|-----|-----------------|
| `gpt-4-1-dz` | gpt-4.1 (DataZone) | 87K | 87 | `LLM_TIER_FAST`, `LLM_TIER_VISION` |
| `gpt-4-1-mini-dz` | gpt-4.1-mini (DataZone) | 229K | 229 | `LLM_FALLBACK`, Speech prompt primary |
| `gpt-5-mini-dz` | gpt-5-mini | 30K | 30 | Default standard **apenas se Anthropic não estiver configurado** (não é o caso em produção) |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | 100K | 100 | **`LLM_TIER_STANDARD`** (override ativo: `anthropic:sonnet`) |
| `claude-opus-4-6` | Claude Opus 4.6 | 100K | 100 | `LLM_TIER_PRO` (`anthropic:opus`) |
| `text-embedding-3-small` | text-embedding-3-small | 500K | 500 | Embeddings RAG |
| `cohere-rerank-v4-fast` | Cohere Rerank v4 | 3K | 3 | Post-retrieval rerank |
| `model-router` | model-router | 50K | 50 | Desactivado (`MODEL_ROUTER_ENABLED=false`) |
| `dbde_access_chatbot` | gpt-4o | 50K | 50 | **LEGACY — sem referência em app settings** |

### Hierarquia LLM efectiva em produção

```
Standard (default) → anthropic:sonnet (Claude Sonnet 4.6, via Azure Foundry)
Fast               → azure_openai:gpt-4-1-dz (DataZone, EU)
Pro                → anthropic:opus (Claude Opus 4.6, via Azure Foundry)
Vision             → azure_openai:gpt-4-1-dz (DataZone, multimodal)
Fallback           → azure_openai:gpt-4-1-mini-dz (DataZone, EU)
Speech prompt      → azure_openai:gpt-4-1-mini-dz (primary), anthropic:sonnet (fallback)
```

---

## 3. Storage Account (`dbdeaccessstorage`)

- **SKU**: Standard_RAGRS (read-access geo-redundant)
- **Replicação**: Sweden Central (primary) → Sweden South (secondary)
- **TLS**: 1.2 mínimo
- **Public blob access**: Disabled
- **Public network access**: Enabled, defaultAction=Allow (sem IP rules)
- **HTTPS only**: true

### Blob Containers (12)

| Container | Uso |
|-----------|-----|
| `upload-raw` | Ficheiros originais uploaded |
| `upload-text` | Texto extraído de ficheiros |
| `upload-chunks` | Chunks para embedding |
| `upload-artifacts` | Artefactos tabulares processados |
| `chat-tool-results` | Resultados de tools armazenados |
| `generated-files` | Ficheiros gerados pelo agente (TTL 30min) |
| `codexdeploy` | Pacotes de deployment |
| `appservice-backups` | Backups App Service |
| `diagnosticdata` | Dados de diagnóstico |
| `jsonmse` | Dados MSE legacy |
| `memorydumps` | Crash dumps |
| `state` | Estado da aplicação |

### Tables (21)

| Table | Uso |
|-------|-----|
| `Users` | Gestão de utilizadores |
| `Sessions` | Sessões ativas |
| `ChatHistory` | Histórico de conversas |
| `AuthState` | Estado de autenticação |
| `AuditLog` | Log de auditoria |
| `DataDictionary` | Dicionário de dados (uploads tabulares) |
| `UploadIndex` | Índice de ficheiros uploaded |
| `UploadJobs` | Fila de jobs de upload |
| `ExportJobs` | Fila de jobs de exportação |
| `RateLimits` | Rate limiting por utilizador |
| `TokenQuota` | Quotas de tokens por tier |
| `PromptRules` | Regras de prompt configuráveis |
| `feedback` | Feedback dos utilizadores |
| `ActiveInstances` | Instâncias ativas do worker |
| `IndexSyncState` | Estado de sync com AI Search |
| `UserStoryCurated` | User stories curadas para aprendizagem |
| `UserStoryDrafts` | Rascunhos de user stories |
| `UserStoryFeedback` | Feedback de user stories |
| `UserStoryKnowledgeAssets` | Knowledge base para story writer |
| `WriterProfiles` | Perfis de escrita |
| `examples` | Exemplos para few-shot |

---

## 4. Key Vault (`dbde-ai-vault`)

- **SKU**: Standard
- **Soft delete**: 90 dias
- **RBAC**: Enabled (sem access policies legacy)
- **Public network access**: Enabled
- **Purge protection**: Disabled

### Secrets (25 enabled)

**Ativos (19):**
`dbde-anthropic-foundry-key`, `dbde-appinsights-connection-string`, `dbde-appinsights-instrumentationkey`, `dbde-azure-openai-key`, `dbde-azure-speech-key`, `dbde-content-safety-key`, `dbde-devops-pat-v2`, `dbde-doc-intel-key`, `dbde-figma-access-token`, `dbde-jwt-secret`, `dbde-miro-access-token`, `dbde-pii-api-key`, `dbde-rerank-api-key`, `dbde-search-key`, `dbde-search-key-basic`, `dbde-storage-connection-string`, `dbde-storage-key`, `dbde-web-answers-api-key`, `dbde-web-search-api-key`

**Legacy/Duplicados (6):**
`claude-opus-key`, `dbde-devops-patoken`, `FIGMA-ACCESS-TOKEN`, `MIRO-ACCESS-TOKEN`, `STORAGE-CONNECTION-STRING`, `WEB-ANSWERS-API-KEY`

---

## 5. App Service — Main App (`millennium-ai-assistant`)

| Propriedade | Valor |
|------------|-------|
| Runtime | Python 3.12 (Linux) |
| Startup | `bash /home/site/wwwroot/startup.sh` |
| AlwaysOn | true |
| HTTPS Only | **true** |
| HTTP/2 | true |
| WebSockets | true |
| Health check | `/health` |
| Min TLS | 1.2 |
| FTP state | **AllAllowed** (ISSUE) |
| 32-bit | false |
| Identity | SystemAssigned |
| Custom domain | `dbdeai.pt` (SNI SSL) |
| IP restrictions | Allow all (frontend) |
| SCM restrictions | **IP whitelist + Deny all** |
| Client affinity | true |

---

## 6. App Service — Worker (`millennium-ai-assistant-worker`)

| Propriedade | Valor |
|------------|-------|
| Runtime | Python 3.12 (Linux) |
| Startup | `bash /home/site/wwwroot/startup_worker.sh` |
| Worker mode | `WORKER_MODE=both` (upload + export) |
| AlwaysOn | true |
| HTTPS Only | **false** (ISSUE) |
| HTTP/2 | true |
| WebSockets | false |
| Health check | **null** (ISSUE) |
| Min TLS | 1.2 |
| FTP state | FtpsOnly |
| 32-bit | **true** (ISSUE) |
| Identity | SystemAssigned |
| IP restrictions | Allow all |
| SCM restrictions | **Allow all** (ISSUE) |
| Client affinity | true |
| STORAGE_KEY | **Plaintext** (ISSUE) |

### Worker Architecture

O worker é um processo dedicado que corre `worker_entrypoint.py`:
- Com `WORKER_MODE=both`, lança **upload_worker.py** e **export_worker.py** em paralelo
- O main app tem `UPLOAD_INLINE_WORKER_RUNTIME_ENABLED=true` (processa uploads inline também)
- O worker tem `UPLOAD_INLINE_WORKER_RUNTIME_ENABLED=false` e `UPLOAD_DEDICATED_WORKER_ENABLED=false` — funciona via `worker_entrypoint.py`, não via inline runtime
- Exports: main app tem `EXPORT_DEDICATED_WORKER_ENABLED=false`, `EXPORT_INLINE_WORKER_ENABLED=false` — o worker dedicado trata de tudo

---

## 7. App Service Plan (`plan-dbde-v2`)

| Propriedade | Valor |
|------------|-------|
| SKU | P1v3 (PremiumV3) |
| Workers configurados | 2 |
| Sites hospedados | 2 (main + worker) |
| Max workers (autoscale) | 3 |
| Zone redundant | false |
| Elastic scale | false |

---

## 8. Autoscale (`plan-dbde-v2-autoscale`)

| Regra | Trigger | Ação | Cooldown |
|-------|---------|------|----------|
| CPU Scale Up | >70% avg (5min) | +1 instância | 5min |
| CPU Scale Down | <30% avg (10min) | -1 instância | 10min |
| Memory Scale Up | >80% avg (5min) | +1 instância | 5min |
| Memory Scale Down | <40% avg (10min) | -1 instância | 10min |

**Capacidade**: min=2, default=2, max=3

---

## 9. Monitoring & Alerting

### Application Insights
- **Retention**: 90 dias
- **Ingestion mode**: LogAnalytics
- **Workspace**: `dbde-ai-logs`

### Metric Alerts (4 configurados)

| Alert | Métrica | Threshold | Severidade | Enabled |
|-------|---------|-----------|------------|---------|
| `dbde-high-error-rate` | HTTP 5xx | >5 em 5min | Sev 2 | **Sim** |
| `dbde-high-latency` | Response time | >30s | Sev 3 | **Sim** |
| `dbde-health-failures` | Health check | failing | Sev 1 | **Sim** |
| `dbde-high-cpu` | CPU | >80% em 10min | Sev 3 | **Não** |

### Action Group (`dbde-ai-alerts`)
- **Email**: pedro.mousinho@millenniumbcp.pt
- **SMS**: nenhum
- **Webhook**: nenhum

---

## 10. Cosmos DB (`cosmosdbrgmsaccesschabot84949c`)

| Propriedade | Valor |
|------------|-------|
| Kind | GlobalDocumentDB |
| Consistency | Session |
| Free tier | false |
| Public access | Enabled |
| Location | Sweden Central (single region) |
| Capabilities | Nenhuma especial |

> **Nota**: Não foram encontradas referências a Cosmos DB no código da aplicação (config.py, imports). Este recurso pode estar a ser usado por outro sistema ou ser legacy. Requer validação.

---

## 11. AI Search

| Serviço | SKU | Status | Em uso |
|---------|-----|--------|--------|
| `dbdeacessrag` | Free | Running | **Não** (legacy) |
| `dbdeacessrag-basic` | Basic | Running | **Sim** (`SEARCH_SERVICE=dbdeacessrag-basic`) |

### Índices configurados
- `millennium-story-devops-index` (DEVOPS_INDEX, STORY_DEVOPS_INDEX)
- `millennium-story-knowledge-index` (OMNI_INDEX, STORY_KNOWLEDGE_INDEX)
- `millennium-story-examples-index` (STORY_EXAMPLES_INDEX)

---

## 12. Cognitive Services

| Serviço | Kind | Endpoint | Feature flag |
|---------|------|----------|-------------|
| `dbde-pii` | TextAnalytics | swedencentral.api.cognitive.microsoft.com | `PII_ENABLED=true` |
| `dbde-doc-intel` | FormRecognizer | swedencentral.api.cognitive.microsoft.com | `DOC_INTEL_ENABLED=true` |
| `dbde-content-safety` | ContentSafety | swedencentral.api.cognitive.microsoft.com | `PROMPT_SHIELD_ENABLED=true` |
| `dbde-speech` | SpeechServices | swedencentral | `AZURE_SPEECH_ENABLED=true` |

---

## 13. Config Overrides (código vs Azure)

| Config | Default no `config.py` | Override no Azure | Nota |
|--------|----------------------|-------------------|------|
| `SEARCH_SERVICE` | `dbdeacessrag` | `dbdeacessrag-basic` | Migrado para Basic |
| `DEVOPS_INDEX` | `millennium-devops-index` | `millennium-story-devops-index` | Renomeado |
| `OMNI_INDEX` | `millennium-omni-index` | `millennium-story-knowledge-index` | Renomeado |
| `STARTUP_FAIL_FAST` | `true` | `false` | Evita crash loop em produção |
| `UPLOAD_MAX_CONCURRENT_JOBS` | `8` | `4` | Conservador em P1v3 |
| `UPLOAD_TABULAR_DEEP_INGEST_MAX_MB` | `150` | `50` | Conservador |
| `UPLOAD_TABULAR_DEEP_INGEST_MAX_ROWS` | `500000` | `100000` | Conservador |
| `CHAT_BUDGET_PER_MINUTE` | `10` | `120` | 12x mais generoso em produção |
| `EXPORT_DEDICATED_WORKER_ENABLED` | `true` | `false` | Worker dedicado separado trata disto |
| `TOKEN_QUOTA_ENFORCEMENT_ENABLED` | `false` | não definido | **Intencional** — fase de rollout |
| `CHAT_RATE_LIMIT_ENFORCEMENT_ENABLED` | `false` | não definido | **Intencional** — fase de rollout |

---

## 14. Issues & Recomendações

### SEGURANCA — Corrigir imediatamente

| # | Sev | Issue | Recurso | Recomendação |
|---|-----|-------|---------|-------------|
| 1 | **CRIT** | STORAGE_KEY em plaintext nos app settings | Worker | Substituir por `@Microsoft.KeyVault(SecretUri=https://dbde-ai-vault.vault.azure.net/secrets/dbde-storage-key/)` |
| 2 | **ALTO** | httpsOnly=false | Worker | `az webapp update --name millennium-ai-assistant-worker --set httpsOnly=true` |
| 3 | **ALTO** | SCM/Kudu aberto a todos | Worker | Copiar IP restrictions do main app SCM |
| 4 | **ALTO** | ftpsState=AllAllowed | Main app | Mudar para `Disabled` (deploy via ZIP/Git) |
| 5 | **ALTO** | Sem health check | Worker | Configurar healthCheckPath (ou endpoint dedicado) |

### OPERACIONAL — Planear a curto prazo

| # | Sev | Issue | Recomendação |
|---|-----|-------|-------------|
| 6 | **MED** | use32BitWorkerProcess=true no worker | Mudar para false — limita memória a ~2GB |
| 7 | **MED** | clientAffinityEnabled=true em ambos | Desativar — APIs stateless, prejudica load balancing |
| 8 | **MED** | Storage publicNetworkAccess=Enabled sem network rules | Adicionar IP rules ou service endpoints |
| 9 | **MED** | Cosmos DB sem referências no código | Validar se outro sistema usa; se não, eliminar para poupar custo |
| 10 | **MED** | Deployment `dbde_access_chatbot` (gpt-4o) legacy | Eliminar — 50K TPM não referenciado |
| 11 | **MED** | 6 secrets legacy no Key Vault | Desativar para reduzir ruído operacional |
| 12 | **MED** | SCM do main app tem 2 whitelists antigas | Rever IPs; remover os que já não são necessários |

### ARQUITECTURA — Planear a médio prazo

| # | Item | Estado atual | Recomendação |
|---|------|-------------|-------------|
| 13 | VNet integration | Nenhuma | Integrar ASP com VNet; service endpoints para Storage, Search, Cognitive Services |
| 14 | Private Endpoints | Nenhum | Após VNet, adicionar PE para Storage, Key Vault, AI Search |
| 15 | WAF / Front Door | Não encontrado nesta RG | Avaliar Azure Front Door com WAF para protecção DDoS e caching |
| 16 | Deployment slots | Nenhum | Criar slot de staging para zero-downtime deploys |
| 17 | Zone redundancy | Disabled no ASP | Avaliar upgrade para zone-redundant (requer recriação do plan) |
| 18 | Backup policy | Não configurado | Configurar backup automático do App Service |
| 19 | Search Free tier | Legacy (`dbdeacessrag`) | Baixa prioridade — Free tier não tem custo, mas eliminar reduz ruído |
| 20 | Autoscale notifications | Emails vazios no autoscale | Adicionar email ao action group do autoscale (alertas de scaling já vão para pedro.mousinho@millenniumbcp.pt via `dbde-ai-alerts`) |
| 21 | `dbde-high-cpu` alert disabled | Desativado | Avaliar reactivação com threshold ajustado |

---

## 15. Resumo Executivo

### O que está bem

- **Secrets management**: Main app usa Key Vault references para todos os 17 secrets sensíveis
- **HTTPS enforced** no main app com custom domain SSL (`dbdeai.pt`)
- **SCM restrito** por IP no main app (deny all + whitelist)
- **TLS 1.2** mínimo em todos os serviços
- **Autoscale** configurado com CPU + Memory (min=2, max=3)
- **Storage geo-redundante** (RAGRS: Sweden Central → Sweden South)
- **Application Insights** com 90 dias retenção + Log Analytics workspace
- **4 metric alerts** configurados com action group (3 ativos, 1 disabled)
- **Blob public access disabled** no Storage Account
- **Data residency EU**: todos os serviços em Sweden Central
- **Multi-provider LLM**: Azure OpenAI DataZone (EU) + Anthropic via Azure Foundry
- **Safety layers**: PII Shield, Prompt Shield, Content Safety — todos ativos
- **Worker dedicado** para processamento assíncrono (uploads + exports)

### O que precisa de fix imediato (5 items)

1. STORAGE_KEY em plaintext no worker → Key Vault ref
2. Worker httpsOnly → true
3. Worker SCM → restringir por IP
4. Main app FTP → Disabled
5. Worker health check → configurar

### O que precisa de planeamento (8 items)

1. Worker 32-bit → 64-bit
2. Client affinity → disabled
3. Storage network rules
4. VNet integration + Private Endpoints
5. Deployment slots
6. Cleanup de recursos legacy
7. Backup policy
8. Zone redundancy

---

*Relatório gerado em 2026-03-21. Validado live contra a infraestrutura Azure.*
