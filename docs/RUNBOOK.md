# DBDE AI Assistant — Runbook Operacional
## Versão: 8.0.0 | Atualizado: 2026-03-17

## Fonte de verdade
Este documento foi revisto contra:
- `config.py`
- `startup.sh`
- `startup_worker.sh`
- `worker_entrypoint.py`
- `routes_admin.py`
- `route_deps.py`
- `routes_auth.py`
- `scripts/smoke_test.py`
- `scripts/deploy_swap.sh`
- `scripts/rollback.sh`
- `.github/workflows/ci.yml`

## 1. Arquitetura de runtime
- Azure App Service Linux para a app web.
- FastAPI/Uvicorn na porta `8000`.
- Frontend Vite servido a partir de `static/index.html`, com `/static` e `/dist` montados pela app.
- Worker dedicado de upload supervisionado por `startup.sh` quando `UPLOAD_DEDICATED_WORKER_ENABLED=true`.
- Worker dedicado de export supervisionado por `startup.sh` quando `EXPORT_DEDICATED_WORKER_ENABLED=true`.
- Worker app dedicada opcional com `startup_worker.sh` -> `worker_entrypoint.py`, usando `WORKER_MODE=upload|export|both`.
- Azure Table Storage para `ChatHistory`, `Users`, `feedback`, `UploadIndex`, `ExportJobs` e tabelas auxiliares.
- Azure Blob Storage para uploads, chunks, artefactos e ficheiros gerados.
- Azure OpenAI como provider Azure preferencial.
- Anthropic opcional via Azure AI Foundry ou API direta para tiers `standard` e `pro`.
- Azure AI Search para pesquisa/RAG.
- Brave Search opcional para pesquisa web.
- Azure Speech opcional para voz.
- Azure AI Language PII, Azure AI Content Safety e Azure AI Document Intelligence como integrações opcionais.

## 2. Startup e shutdown
### Web app (`startup.sh`)
1. Resolve `APP_ROOT`, com fallback para `/home/site/wwwroot`.
2. Ativa `antenv` se existir e define `PYTHONPATH`.
3. Cria `run/` e `/home/LogFiles`.
4. Arranca supervisão do upload worker se `UPLOAD_DEDICATED_WORKER_ENABLED=true`.
5. Arranca supervisão do export worker se `EXPORT_DEDICATED_WORKER_ENABLED=true`.
6. Arranca `uvicorn app:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-3}"`.

### Defaults relevantes no arranque web
- `UVICORN_WORKERS=3`
- upload worker sidecar: `--batch-size 4 --poll-seconds 2.5`
- export worker sidecar: `--batch-size 3 --poll-seconds 2.0`
- `UPLOAD_INLINE_WORKER_RUNTIME_ENABLED=true` por omissão

### Worker app dedicada (`startup_worker.sh`)
1. Resolve `APP_ROOT`.
2. Escolhe Python disponível.
3. Executa `worker_entrypoint.py`.
4. `worker_entrypoint.py` suporta `WORKER_MODE=upload|export|both` e supervisiona reinícios.
5. Se existir `antenv.tar.gz`, o entrypoint extrai o runtime virtualenv automaticamente.

### Shutdown
- SIGTERM termina o processo web.
- Workers supervisionados pelo processo pai são reciclados com a instância.
- A app tenta fazer shutdown limpo das tasks inline.

## 3. Logs, ficheiros e paths
- App logs: stdout/stderr no Log Stream do App Service.
- Upload worker log: `/home/LogFiles/upload-worker.log`
- Export worker log: `/home/LogFiles/export-worker.log`
- Worker app startup log: `/home/LogFiles/worker-startup.log`
- PID files por omissão:
  - `/home/site/wwwroot/run/upload-worker.pid`
  - `/home/site/wwwroot/run/upload-worker-supervisor.pid`
  - `/home/site/wwwroot/run/export-worker.pid`
  - `/home/site/wwwroot/run/export-worker-supervisor.pid`

## 4. Health check
### Básico
- `GET /health`
- Endpoint público e auth-exempt.
- Resposta esperada: `200` com `{"status":"healthy","mode":"basic","checks":{"app":"ok"}}`

### Deep
- `GET /health?deep=true`
- Requer token/cookie admin válido.
- Sem token válido devolve `401`.
- Com token válido mas role não admin devolve `403`.

### Checks de deep health
- `table_storage`
- `blob_storage`
- `llm_fast`
- `llm_vision`
- `ai_search`
- `rerank`
- `upload_worker`
- `export_worker`

### Semântica
- `200` com `status=healthy`: todos os checks estão `ok`, `configured` ou `disabled`.
- `503` com `status=degraded`: pelo menos um check está em erro.
- Nota: o check de `rerank` valida configuração do endpoint, não uma chamada live ao provider.

## 5. Smoke test
### Script oficial
- `python3 scripts/smoke_test.py [BASE_URL]`

### Checks sem autenticação
- `GET /health`
- `GET /api/info`
- `GET /`

### Checks com autenticação
Definir `SMOKE_USER` e `SMOKE_PASS`:
- `POST /api/auth/login`
- `GET /health?deep=true`
- `POST /chat/agent`
- `GET /api/upload/jobs`

## 6. Procedimentos de recuperação
### 6.1 Worker down
1. Validar `GET /health?deep=true`.
2. Verificar `upload_worker` e `export_worker`.
3. Consultar `/home/LogFiles/*-worker.log`.
4. Confirmar PID files e processo vivo.
5. Se necessário, reciclar a app web ou a worker app dedicada.

### 6.2 Storage indisponível
1. Confirmar erro em `table_storage` ou `blob_storage`.
2. Rever `STORAGE_CONNECTION_STRING` ou `STORAGE_ACCOUNT` + `STORAGE_KEY`.
3. Confirmar existência/estado da storage account e containers.
4. Voltar a testar `GET /health?deep=true`.

### 6.3 LLM indisponível
1. Confirmar `llm_fast` e `llm_vision`.
2. Rever `AZURE_OPENAI_*`, `CHAT_DEPLOYMENT`, `EMBEDDING_DEPLOYMENT`, `LLM_TIER_*`, `LLM_FALLBACK`.
3. Se Anthropic/Foundry estiver ativo, rever `ANTHROPIC_*`.
4. Verificar erros `429`, autenticação ou deployment inexistente.

### 6.4 Search/RAG indisponível
1. Confirmar `ai_search`.
2. Rever `SEARCH_SERVICE`, `SEARCH_KEY`, `API_VERSION_SEARCH`.
3. Validar índices `DEVOPS_INDEX`, `OMNI_INDEX`, `EXAMPLES_INDEX` e índices de user story.

### 6.5 PAT DevOps expirado
1. Sintoma típico: tools DevOps devolvem `401/403`.
2. Renovar `DEVOPS_PAT`.
3. Atualizar App Settings.
4. Validar operação de work items e novo smoke/auth flow.

### 6.6 Problemas de auth
1. Em produção, `JWT_SECRET` é obrigatório.
2. Rever `JWT_SECRET`, `JWT_SECRET_PREVIOUS`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_NAME`.
3. Validar `ALLOWED_ORIGINS` e cookies via browser/login.

## 7. Env vars críticas
### Core app
- `APP_ENV`
- `JWT_SECRET`
- `JWT_SECRET_PREVIOUS`
- `ALLOWED_ORIGINS`

### LLM
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_KEY`
- `CHAT_DEPLOYMENT`
- `EMBEDDING_DEPLOYMENT`
- `LLM_TIER_FAST`
- `LLM_TIER_STANDARD`
- `LLM_TIER_PRO`
- `LLM_TIER_VISION`
- `LLM_FALLBACK`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_FOUNDRY_RESOURCE`
- `ANTHROPIC_BASE_URL`

### Search e rerank
- `SEARCH_SERVICE`
- `SEARCH_KEY`
- `RERANK_ENABLED`
- `RERANK_ENDPOINT`
- `RERANK_API_KEY`

### Storage
- `STORAGE_CONNECTION_STRING`
- `STORAGE_ACCOUNT`
- `STORAGE_KEY`
- `UPLOAD_BLOB_CONTAINER_*`
- `GENERATED_FILES_BLOB_CONTAINER`

### Workers
- `UPLOAD_DEDICATED_WORKER_ENABLED`
- `EXPORT_DEDICATED_WORKER_ENABLED`
- `UPLOAD_INLINE_WORKER_ENABLED`
- `EXPORT_INLINE_WORKER_ENABLED`
- `UVICORN_WORKERS`
- `WORKER_MODE`

### Integrações opcionais
- `WEB_SEARCH_ENABLED`
- `WEB_SEARCH_API_KEY`
- `WEB_ANSWERS_ENABLED`
- `FIGMA_ACCESS_TOKEN`
- `MIRO_ACCESS_TOKEN`
- `AZURE_SPEECH_ENABLED`
- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`
- `PII_ENDPOINT`
- `PII_API_KEY`
- `CONTENT_SAFETY_ENDPOINT`
- `CONTENT_SAFETY_KEY`
- `DOC_INTEL_ENDPOINT`
- `DOC_INTEL_KEY`

## 8. Notas de deploy e rollback
- O repositório suporta dois modos: com slot `staging` ou deploy in-place.
- `scripts/deploy_swap.sh` e `scripts/rollback.sh` falham explicitamente quando o slot não existe.
- Sem slot, rollback é redeploy da versão anterior.
- O build frontend atual limpa `static/dist/assets` antes de gerar novos bundles.

## 9. Checklist operacional diária
1. `GET /health`
2. `GET /api/info`
3. `GET /health?deep=true` com conta admin
4. Confirmar logs sem erros repetidos de worker, storage ou llm
5. Rever expiração de PAT e outros segredos
6. Confirmar workers vivos quando dedicados estiverem ativos
