# DBDE AI Assistant — Azure Infra Handoff for Audit

## Date

2026-03-16

## Purpose

This document is meant to brief an external agent or auditor that does **not** have Azure CLI access. It captures the Azure-facing infrastructure, deployment shape, data stores, service dependencies, and the most important operational assumptions based on:

-   the repository source of truth in [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
-   deployment and infra scripts in [scripts/setup_azure_infra.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/setup_azure_infra.sh) and [scripts/apply_p1v3_safe_profile.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/apply_p1v3_safe_profile.sh)
-   app runtime wiring in [app.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/app.py), [storage.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/storage.py), [upload_worker.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/upload_worker.py), and [export_worker.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/export_worker.py)
-   recent deployment notes in [UPGRADE_TRACKER.md](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/UPGRADE_TRACKER.md)
-   publish metadata in `/Users/pedromousinho/Downloads/millennium-ai-assistant.PublishSettings`

## Confidence and Limits

This handoff is intentionally split into:

-   `Confirmed from code/repo`
-   `Last known operational intent`
-   `Not live-verified at capture time`

Reason: Azure CLI access expired during capture, so this document is highly useful for audit, but it should not be treated as a full live inventory of every current Azure resource property.

## Executive Summary

The application is a Python FastAPI web app deployed on Azure App Service, backed by Azure Table Storage and Azure Blob Storage, using Azure OpenAI, Azure AI Search, Azure DevOps, and optional Azure AI adjuncts such as Content Safety, PII detection, Document Intelligence, and Azure Speech.

The platform shape is:

1.  A primary web app named `millennium-ai-assistant`
2.  An App Service Plan named `plan-dbde-v2`
3.  A dedicated worker app pattern for async upload/export processing in the same plan
4.  One Azure Storage account, used for both Table and Blob persistence
5.  One Azure AI Search service, with both legacy and story-specific indexes
6.  One Key Vault intended to hold secrets
7.  Azure Monitor alerts and autoscale on the plan
8.  Optional custom domain `dbdeai.pt` in front of the Azure default hostname

## Subscription and Tenant

Confirmed from local Azure account context:

-   Subscription name: `Azure subscription 1`
-   Subscription ID: `84949c46-8ea6-4a10-bec4-2b49903aeb5b`
-   Tenant ID: `5d89951c-b62b-46bf-b261-910b5240b0e7`

## Resource Group

Last known and consistently referenced resource group:

-   Resource group: `rg-MS_Access_Chabot`

This is referenced in:

-   [scripts/setup_azure_infra.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/setup_azure_infra.sh)
-   [scripts/apply_p1v3_safe_profile.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/apply_p1v3_safe_profile.sh)
-   [scripts/deploy_swap.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/deploy_swap.sh)
-   [scripts/rollback.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/rollback.sh)

## App Service Topology

### Main web app

Confirmed identifiers:

-   App name: `millennium-ai-assistant`
-   Default public hostname: `https://millennium-ai-assistant.azurewebsites.net`
-   Publish SCM host: `millennium-ai-assistant.scm.azurewebsites.net`
-   Publish profile destination URL: `https://millennium-ai-assistant.azurewebsites.net`

Evidence:

-   `/Users/pedromousinho/Downloads/millennium-ai-assistant.PublishSettings`
-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)

### Worker app

Last known intended worker app:

-   App name: `millennium-ai-assistant-worker`

Evidence:

-   [scripts/apply_p1v3_safe_profile.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/apply_p1v3_safe_profile.sh)
-   [startup_worker.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/startup_worker.sh)
-   [worker_entrypoint.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/worker_entrypoint.py)

### App Service Plan

Last known intended plan:

-   Plan name: `plan-dbde-v2`
-   SKU family: `P1v3`

Last known operational note:

-   [UPGRADE_TRACKER.md](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/UPGRADE_TRACKER.md) records PremiumV3 P1v3 with autoscale
-   [scripts/apply_p1v3_safe_profile.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/apply_p1v3_safe_profile.sh) sets autoscale to `2/2/3`

### Runtime and startup

Confirmed from repo:

-   Runtime target: `PYTHON:3.12`
-   Main app startup file: `bash /home/site/wwwroot/startup.sh`
-   Worker app startup file: `bash /home/site/wwwroot/startup_worker.sh`

Evidence:

-   [scripts/apply_p1v3_safe_profile.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/apply_p1v3_safe_profile.sh)
-   [startup.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/startup.sh)
-   [startup_worker.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/startup_worker.sh)

## Domains and Exposure

### Known public entrypoints

-   `https://millennium-ai-assistant.azurewebsites.net`
-   `https://dbdeai.pt`

Evidence:

-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
-   [UPGRADE_TRACKER.md](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/UPGRADE_TRACKER.md)
-   tests for allowed origins in [tests/test_allowed_origins.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/tests/test_allowed_origins.py)

### Current frontend/backend serving pattern

The Azure Web App serves:

-   API routes from FastAPI
-   static frontend assets from `static/` and `static/dist/`

Evidence:

-   [app.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/app.py)

### Auth-exempt public routes

From the current code:

-   `/`
-   `/health`
-   `/api/info`
-   `/api/client-error`
-   `/docs`
-   `/openapi.json`
-   `/redoc`

Important note: - `/docs`, `/openapi.json`, and `/redoc` are currently auth-exempt in code, in [route_deps.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/route_deps.py) - this matters for audit because it exposes the API shape publicly unless separately blocked at edge or ingress

## Storage Layer

### Storage account

Confirmed default name from config:

-   Storage account: `dbdeaccessstorage`

Evidence:

-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)

### Storage usage model

The app uses the same storage account for:

-   Azure Table Storage
-   Azure Blob Storage

The app does not rely on local disk as source of truth for conversations or jobs. Table Storage is the persistence backbone.

Evidence:

-   [storage.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/storage.py)
-   [job_store.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/job_store.py)
-   [agent.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/agent.py)

### Blob containers

Confirmed default blob containers:

-   `upload-raw`
-   `upload-text`
-   `upload-chunks`
-   `upload-artifacts`
-   `chat-tool-results`
-   `generated-files`

Evidence:

-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
-   [storage.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/storage.py)

### Blob container purposes

-   `upload-raw`: original uploaded files
-   `upload-text`: extracted/plaintext representations
-   `upload-chunks`: semantic chunks for retrieval
-   `upload-artifacts`: tabular artifacts and processing outputs
-   `chat-tool-results`: tool result payloads and some story-lane payload blobs
-   `generated-files`: generated downloadable files plus metadata

### Azure Table Storage tables

Confirmed core tables ensured by runtime in [storage.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/storage.py):

-   `ChatHistory`
-   `Users`
-   `UploadJobs`
-   `UploadIndex`
-   `ExportJobs`
-   `RateLimits`
-   `TokenQuota`
-   `UserStoryFeedback`
-   `UserStoryCurated`
-   `UserStoryKnowledgeAssets`

Also used elsewhere in code:

-   `PromptRules`
-   `WriterProfiles`
-   `feedback`
-   `examples`
-   `DataDictionary`

### Table purposes

-   `ChatHistory`: persisted user conversations
-   `Users`: local app users, roles, activation, password hashes
-   `UploadJobs`: queued/running/completed upload jobs
-   `UploadIndex`: per-conversation searchable uploaded file index
-   `ExportJobs`: queued/running/completed export jobs
-   `RateLimits`: distributed rate limiting state
-   `TokenQuota`: per-tier quota state
-   `UserStoryFeedback`: user story lane feedback events
-   `UserStoryCurated`: promoted curated user stories
-   `UserStoryKnowledgeAssets`: knowledge assets used by story search/indexing
-   `PromptRules`: learning or active prompt governance rules
-   `WriterProfiles`: style/reference author profiles
-   `feedback`: generic product feedback
-   `examples`: example or evaluation-oriented rows
-   `DataDictionary`: tabular metadata dictionary

## Azure AI and Search Dependencies

### Azure OpenAI

Confirmed from config:

-   Endpoint comes from `AZURE_OPENAI_ENDPOINT`
-   Base URL comes from `AZURE_OPENAI_BASE_URL`
-   Chat deployment default: `gpt-4-1-dz`
-   Embedding deployment default: `text-embedding-3-small`
-   Vision tier default: `azure_openai:gpt-4-1-dz`

Operational model:

-   `fast` tier defaults to Azure OpenAI
-   `vision` tier defaults to Azure OpenAI
-   embeddings are always Azure OpenAI

Evidence:

-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
-   [llm_provider.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/llm_provider.py)

### Anthropic via Azure AI Foundry or direct API

The platform supports Anthropic as standard/pro tier if configured.

Operational implication:

-   `standard` often prefers `anthropic:sonnet`
-   `pro` defaults to `anthropic:opus`

Evidence:

-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
-   [llm_provider.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/llm_provider.py)

### Azure AI Search

Confirmed service name:

-   Search service: `dbdeacessrag`

Legacy indexes:

-   `millennium-devops-index`
-   `millennium-omni-index`
-   `millennium-examples-index`

Story-specific indexes:

-   `millennium-story-devops-index`
-   `millennium-story-knowledge-index`
-   `millennium-story-examples-index`

Operational nuance:

-   the code still supports legacy indexes
-   the story lane increasingly relies on the `story-*` indexes
-   fallback logic exists in search tooling for missing legacy indexes

Evidence:

-   [config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
-   [tools_knowledge.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/tools_knowledge.py)
-   [story_index_admin.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/story_index_admin.py)
-   setup/sync scripts under `scripts/setup_story_*` and `scripts/sync_story_*`

### Rerank service

Confirmed capability:

-   post-retrieval reranking is enabled by config via `RERANK_ENABLED`
-   default model is `cohere-rerank-v4-fast`

This is not an Azure-native primitive in the repo; it is consumed as an external rerank endpoint.

## Azure Adjacent Services

### Azure AI Language / PII Shield

Configured via:

-   `PII_ENDPOINT`
-   `PII_API_KEY`
-   `PII_ENABLED`

Used to mask or detect PII before some downstream calls.

### Azure AI Content Safety / Prompt Shield

Configured via:

-   `CONTENT_SAFETY_ENDPOINT`
-   `CONTENT_SAFETY_KEY`
-   `PROMPT_SHIELD_ENABLED`

Used in [prompt_shield.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/prompt_shield.py).

### Azure Document Intelligence

Configured via:

-   `DOC_INTEL_ENDPOINT`
-   `DOC_INTEL_KEY`
-   `DOC_INTEL_ENABLED`
-   `DOC_INTEL_MODEL`

Used during upload parsing for PDFs and document-like files.

### Azure Speech

Configured via:

-   `AZURE_SPEECH_ENABLED`
-   `AZURE_SPEECH_KEY`
-   `AZURE_SPEECH_REGION`
-   `AZURE_SPEECH_LANGUAGE`

Supports browser speech recognition token issuance and TTS.

## Azure DevOps Dependency

The app integrates with Azure DevOps for work item reading and creation.

Confirmed defaults:

-   Org: `ptbcp`
-   Project: `IT.DIT`

Credentials:

-   uses `DEVOPS_PAT`

Used for:

-   search and retrieval of work items
-   placement of user stories into epic/feature context
-   work item creation from the story lane

## Worker and Job Processing Model

### Upload processing

Upload jobs are persisted to `UploadJobs` and processed either:

-   inline in the web app, or
-   by the dedicated upload worker app

Evidence:

-   [app.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/app.py)
-   [upload_worker.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/upload_worker.py)

### Export processing

Export jobs are persisted to `ExportJobs` and processed either:

-   inline in the web app, or
-   by the dedicated export worker app

Evidence:

-   [app.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/app.py)
-   [export_worker.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/export_worker.py)

### Worker health model

The worker app uses:

-   [startup_worker.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/startup_worker.sh)
-   [worker_entrypoint.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/worker_entrypoint.py)
-   [worker_health_server.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/worker_health_server.py)

The intended shape is a dedicated worker-only App Service that still exposes a simple `/health`.

## Monitoring, Alerts, and Autoscale

### Key Vault

Last known intended vault:

-   `dbde-ai-vault`

### Monitor action group

Last known intended action group:

-   `dbde-ai-alerts`

### Metric alerts created by script

From [scripts/setup_azure_infra.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/setup_azure_infra.sh):

-   `dbde-high-error-rate`
-   `dbde-high-latency`
-   `dbde-health-failures`
-   `dbde-high-cpu`

### Autoscale

Last known operational intent from [scripts/apply_p1v3_safe_profile.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/apply_p1v3_safe_profile.sh):

-   autoscale resource name: `plan-dbde-v2-autoscale`
-   minimum instances: `2`
-   default instances: `2`
-   maximum instances: `3`

Historical repo note:

-   [UPGRADE_TRACKER.md](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/UPGRADE_TRACKER.md) earlier mentions autoscale `1-3`

Audit implication:

-   there may be drift between documented intent and currently applied Azure config
-   this should be verified in the Azure Portal

## Deployment Model

### Current known deployment paths

-   Zip Deploy / Web Deploy via App Service SCM
-   direct production deploy when no staging slot exists
-   optional slot-based deploy if a `staging` slot exists

Evidence:

-   `/Users/pedromousinho/Downloads/millennium-ai-assistant.PublishSettings`
-   [docs/DEPLOY_CHECKLIST.md](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/docs/DEPLOY_CHECKLIST.md)
-   [scripts/deploy_swap.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/deploy_swap.sh)
-   [scripts/rollback.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/scripts/rollback.sh)

### Important operational note

The existence of a staging slot is not guaranteed. The repo explicitly handles both modes:

-   slot-based deployment when slot exists
-   in-place deployment when it does not

For audit, this means rollback guarantees differ by environment state.

## Security-Relevant Infra Facts

### Secret-bearing mechanisms

Secrets are expected in:

-   App Service app settings
-   Key Vault
-   local publish settings file

Important note: - the publish settings file contains deployment credentials and should be treated as sensitive material - if this file was shared externally, rotate publish credentials

### Stateful security controls persisted in storage

-   JWT-based auth with local user table
-   auth runtime state persisted in storage via [auth_runtime.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/auth_runtime.py)
-   distributed rate limiting via [rate_limit_storage.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/rate_limit_storage.py)
-   token quotas via [token_quota.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/token_quota.py)

### Publicly visible API documentation

At code level today, `/docs`, `/openapi.json`, and `/redoc` are still public.

This is relevant for the auditor because:

-   it simplifies surface discovery
-   it exposes admin/debug routes in the OpenAPI document unless hidden elsewhere

## Known Unknowns

These could not be live-verified at the time of writing because the Azure CLI token had expired:

-   exact current region of every resource
-   exact current App Service app settings
-   current existence/state of the worker app
-   current applied autoscale values
-   exact current set of metric alerts
-   exact current document counts in each AI Search index
-   whether all secrets are Key Vault-backed or still present as raw app settings
-   whether staging slot currently exists
-   whether network restrictions are configured on SCM, app, storage, or vault

## Best Short Summary to Give Another Agent

If you need a compact briefing, use this:

`DBDE AI Assistant runs on Azure App Service in resource group rg-MS_Access_Chabot, centered on the web app millennium-ai-assistant and plan plan-dbde-v2. It persists conversations, uploads, jobs, quotas, auth runtime, and user-story curation state in Azure Table Storage and Blob Storage under storage account dbdeaccessstorage. It uses Azure OpenAI for chat and embeddings, Azure AI Search service dbdeacessrag for RAG, Azure DevOps for work items, and optional Azure Content Safety, PII, Speech, and Document Intelligence services. The repo also defines a dedicated worker app pattern named millennium-ai-assistant-worker for upload/export job processing, plus Key Vault dbde-ai-vault, monitor alerts, and autoscale. Public docs endpoints are currently auth-exempt in code. Live Azure properties should be verified in Portal because CLI verification was interrupted by expired auth during capture.`
