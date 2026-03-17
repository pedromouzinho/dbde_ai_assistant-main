# DBDE AI Assistant v7.3.0 — Analise SWOT Exaustiva (Revisao Completa)
## Data original: 6 de Marco de 2026
## Data desta revisao: 17 de Marco de 2026
## Autor: Auditoria linha a linha via Claude Code
## Owner: Pedro Mousinho, Product Owner — Millennium BCP

---

## Nota de Revisao

Esta revisao e baseada em analise **linha a linha** de todos os ficheiros Python e JavaScript/JSX
do repositorio em 2026-03-17. Substitui a analise de 2026-03-06 com achados actualizados.

**Estado do baseline de testes (2026-03-17)**:
- `pytest tests/ -q` -> **511 passed, 3 failed** (falhas pre-existentes: `test_pandas`,
  `test_mnt_data_path_remap_for_pandas` (sandbox pandas) e `test_chart_uploaded_table_generates_artifacts`).
- `npm run build` -> OK.
- `npm audit` -> 0 vulnerabilidades.
- `pip-audit -r requirements.txt` -> integrado no CI.

**Dimensao do codebase (17 Mar 2026)**:

| Ficheiro | Linhas |
|---|---|
| `app.py` | 4 005 |
| `tools.py` | 3 726 |
| `user_story_lane.py` | 3 304 |
| `agent.py` | 2 682 |
| `tools_devops.py` | 1 596 |
| `llm_provider.py` | 1 248 |
| `pptx_engine.py` | 1 127 |
| `routes_admin.py` | 1 078 |
| `xlsx_engine.py` | 1 019 |
| `tools_email.py` | 910 |
| `frontend/src/App.jsx` | 2 086 |
| **Total Python** | **~36 000** |

---

## Resumo Executivo (Revisado)

O DBDE AI Assistant e um produto interno maduro que evoluiu significativamente desde a analise
de 6 de Marco. A analise linha a linha de Marco 17 confirma:

1. **Todos os race conditions criticos foram corrigidos** -- ConversationStore, LLM client pool,
   upload locks, e meta store agora usam `asyncio.Lock()`.
2. **auth_runtime.py** foi criado e activa persistencia de blacklist/lockout no Azure Table Storage,
   eliminando a vulnerabilidade de revogacao in-memory.
3. **Code Interpreter hardening completo** -- PATH minimal, `resource.setrlimit()` CPU/memoria,
   validacao de symlinks, bloqueio de `getattr`/`setattr`/`delattr`.
4. **Secretos protegidos nos logs** -- `_sanitize_error_response()` com 4 regex patterns.
5. **Token quotas persistidas** no Azure Table Storage (distributed shards).
6. **Privacy service** implementado (DSR/GDPR user data export/delete).
7. **Provider governance** layer activo (data sensitivity classification, external model restrictions).
8. **Rate limiting persistido** no Azure Table Storage.
9. **Frontend cresceu de 1 872 para 2 086 linhas** -- refactoring ainda pendente e agora mais urgente.
10. **Risco residual principal**: exposicao publica sem VNet + auth custom sem Entra ID.

O risco global e **baixo a moderado (3.2/10)** -- uma melhoria significativa face ao 5.2/10 inicial.

---

## STRENGTHS (Forcas) -- Estado Actual

### S1. Arquitectura de Seguranca em Camadas (Melhorada)
- **5 shields activos**: PII masking (Azure AI Language), Prompt Shield (Content Safety),
  Code Interpreter sandboxed, Structured Outputs (JSON schemas validados), Document Intelligence.
- **PII por categoria** (`pii_shield.py:43-58`): thresholds diferenciados por tipo --
  NIF/IBAN/credito a 0.4, passaporte/carta a 0.5, Person/Address a 0.7.
  Financeiros recebem tratamento mais agressivo para minimizar falsos negativos.
- **DOMPurify 3.3.2** com `sanitizeHtmlOutput()` em `frontend/src/utils/sanitize.js:27-35`
  protege todos os `dangerouslySetInnerHTML`. `npm audit` = 0 vulnerabilidades.
- **Abuse Monitoring Opt-Out** activo (zero data retention nos modelos Azure OpenAI).
- **Prompt Shield fail-open por desenho** (`prompt_shield.py:78`) -- em falha do servico, passa o
  request em vez de bloquear o utilizador. Tradeoff explicitamente documentado no codigo.

### S2. ConversationStore Completamente Thread-Safe (Novo)
- `agent.py:105`: `self._lock = asyncio.Lock()` adicionado ao ConversationStore.
- `agent.py:182-200`: `async_get()` e `async_set()` com lock explicito.
- `agent.py:261-265`: Locks separados para `_conversation_meta_lock`, `_uploaded_files_lock`,
  e `_conversation_locks` (per-conversation).
- `agent.py:529`: `_get_conversation_lock()` com lock guard para criacao lazy de locks
  por conversa.
- Write-through dirty tracking (`agent.py:117-128`): conversas marcadas como dirty persistem
  snapshot antes de eviction.
- **Race condition eliminada**: dois requests concorrentes na mesma conversa agora sao serializados.

### S3. auth_runtime.py -- Persistencia de Estado Auth (Novo)
- `auth_runtime.py`: modulo novo que persiste estado auth no Azure Table Storage.
- **Token blacklist persistida**: JTIs revogados sobrevivem a restart/recycle do App Service.
- **Invalidacao por utilizador**: `_user_invalidated_before` por username, persistida.
- **Lockout de login persistido**: tentativas falhadas persistem entre instancias.
- Cache local com TTL de 30s para reduzir round-trips ao storage.
- Tabela `AuthState` criada automaticamente no startup (`storage.py:51`).
- **Melhoria critica**: logout, force-logout e password reset agora efectivos apos restart.

### S4. Code Interpreter -- Hardening Completo (Melhorado)
- `code_interpreter.py:37`: `_MINIMAL_PATH = "/usr/local/bin:/usr/bin:/bin"` -- PATH do subprocess
  hardcoded para minimo.
- `code_interpreter.py:38-39`: `_CODE_CPU_LIMIT_SECONDS = 120` e
  `_CODE_MEMORY_LIMIT_BYTES = 512MB`.
- `code_interpreter.py:189-204`: `_set_resource_limits()` usa `resource.setrlimit()` para RLIMIT_CPU
  e RLIMIT_AS antes de executar codigo do utilizador.
- `code_interpreter.py:207-216`: `_path_within_root()` e `_is_safe_symlink_source()` validam
  symlinks -- impede que symlinks apontem para fora do tmpdir.
- `code_interpreter.py:72-75`: `_BLOCKED_CALLS` inclui `getattr`, `setattr`, `delattr` -- bloqueia
  refleccao/introspeccao dinamica.
- `code_interpreter.py:139-148`: bloqueio de snippets `open('/')` e `path('/')` no texto do codigo.
- `code_interpreter.py:56-66`: `io` e `pathlib` removidos do allowlist de imports.
- Runner script valida symlinks em runtime antes de montar dados.

### S5. Secretos Protegidos nos Logs (Novo)
- `http_helpers.py:15-22`: 4 regex patterns que redactam API keys, bearer tokens,
  base64 blobs e JWTs antes de qualquer log de erro HTTP.
- `http_helpers.py:29-36`: `_sanitize_error_response()` aplicado a **todos** os erros HTTP
  em `storage.py`, `llm_provider.py`, `tools_devops.py`, `prompt_shield.py`, `pii_shield.py`.
- DevOps PAT ja nao aparece em logs de erro de API.

### S6. Suite de Testes Abrangente (Melhorada)
- **514 testes** (511 passam, 3 falham por razoes pre-existentes de sandbox pandas).
- **87 ficheiros** de teste cobrindo 4 camadas: RAG, Tools, Arena, User Story.
- CI GitHub Actions com matrix Python 3.11/3.12 + build frontend.
- `pip-audit` e `npm audit --audit-level=high` no CI.
- Testes especificos para: `test_concurrency_locks.py`, `test_auth_runtime.py`,
  `test_privacy_service.py`, `test_pii_shield_hardening.py`, `test_security_hardening.py`.

### S7. Token Quotas Distribuidas e Persistidas (Novo)
- `token_quota.py`: quotas por tier persistidas em shards no Azure Table Storage.
- Particionamento por instancia (WEBSITE_INSTANCE_ID) -- fairness em cenario multi-instancia.
- Fast: 500K/hora, 5M/dia; Standard: 200K/h, 2M/dia; Pro: 100K/h, 1M/dia (configuravel).
- Totais calculados agregando todos os shards.

### S8. Provider Governance Layer (Novo)
- `provider_governance.py`: classifica sensibilidade de dados por accao/modo/tools.
- Accoes elevadas: `speech_prompt`, `user_story_generate`, `chat_file`.
- Modo `userstory` = sempre `elevated`.
- Governa quais providers podem ser usados para dados sensiveis.

### S9. Privacy Service -- DSR/GDPR (Novo)
- `privacy_service.py`: export e delete de dados de utilizador.
- Cobre: conversas (`UserStoryDrafts`), feedback (`UserStoryFeedback`), curated corpus,
  knowledge assets, blobs de resultados de tools.
- Suporte a GDPR Right to Erasure para utilizadores internos.

### S10. Tabular Artifacts Pipeline com DuckDB + Parquet (Novo)
- `tabular_artifacts.py`: pipeline de ingestao tabular com DuckDB e Parquet.
- Performance: DataFrame+COPY vs executemany = ~100x mais rapido para ficheiros grandes
  (323K rows x 63 cols: 100s -> 3s).
- Cleanup com `finally: os.unlink(temp_path)` -- temp files sempre apagados.

### S11. Rate Limiting Persistido no Azure Table Storage (Novo)
- `rate_limit_storage.py`: sliding window rate limiter backed by Azure Table Storage.
- Cache local para reduzir round-trips -- sincroniza best-effort.
- Limites: 30/min em `/chat/agent`, 10/min em `/api/user-stories/publish`.

### S12. Pipeline LLM Multi-Provider com Fallback (Melhorado)
- `llm_provider.py:429,631`: `_client_lock = asyncio.Lock()` eliminou race condition
  na criacao de clientes HTTP.
- `llm_simple()` agora usa o mesmo pipeline protegido de `llm_with_fallback`.
- Structured output com routing correcto para Azure OpenAI (Anthropic nao suporta `response_format`).
- Retry com exponential backoff (3-5 tentativas, 1-30s wait).

### S13. config.py -- JWT Hard-Fail em Producao (Melhorado)
- `config.py:298-329`: `JWT_REQUIRE_EXPLICIT` defaul `true` em producao.
- Se `JWT_SECRET` nao definido em producao -> `RuntimeError` no startup (hard fail).
- Fallback inteligente em dev com aviso CRITICAL.
- `JWT_SECRET_PREVIOUS` suporta rotacao de secret sem invalidar tokens existentes.

### S14. Operacao e Documentacao Exemplar
- 5 documentos operacionais: CONTINUITY.md, RUNBOOK.md, DEPLOY_CHECKLIST.md,
  THIRD_PARTY_INVENTORY.md, DATA_POLICY.md.
- RUNBOOK e DEPLOY_CHECKLIST actualizados para reflectir ausencia de staging slot.
- Health check `/health?deep=true` restrito a admins.

### S15. HTTP Helpers Centralizados (Novo)
- `http_helpers.py`: `_request_with_retry()` centraliza logica de retry para todos os clientes.
- `devops_request_with_retry()` e `search_request_with_retry()` reutilizam o mesmo pipeline.
- Erros 5xx com backoff exponencial (1-30s); erros 4xx imediatos.

### S16. Seguranca de Uploads (Consolidada)
- Magic byte validation para PNG, JPEG, GIF, PDF, XLSX, XLS, DOCX, PPTX, ZIP, CSV, TSV, TXT.
- Limites por extensao (CSV/XLSX/XLSB/TSV ate 200MB, outros ate 100MB).
- Content-Length enforcement no middleware (`app.py:337-346`).
- Owner-based download authorization (so o dono pode fazer download).

### S17. DevOps Integration Hardened (Melhorado)
- `tools_devops.py`: `query_workitems` usa allowlist real de fields (`DEVOPS_FIELDS` em config).
- `create_workitem` exige token de confirmacao server-side consumivel uma vez.
- PAT nao aparece nos logs devido a `_sanitize_error_response()`.

---

## WEAKNESSES (Fraquezas) -- Estado Actual

### W1. Frontend App.jsx CRESCEU (PIOR QUE NA ANALISE ANTERIOR)
- **2 086 linhas** (era 1 872 em 2026-03-06) -- crescimento de 11% sem refactoring.
- `App.jsx` continua com 50+ variaveis de estado sem `useReducer`.
- `dangerouslySetInnerHTML` ainda usado em 3 lugares -- mitigado por `sanitizeHtmlOutput()`.
- Sem `React.memo`, `useCallback` ou `useMemo` -- rerenders desnecessarios.
- Sem virtualizacao de listas longas de mensagens.
- **Sem TypeScript** -- zero type safety no frontend.
- **Evidencia**: `wc -l frontend/src/App.jsx` = 2086 (2026-03-17).

### W2. ConversationStore Ainda In-Memory no Nucleo
- Ainda usa `dict` em memoria com LRU eviction (max 200 conversas, TTL 4h).
- Write-through dirty tracking adicionado, mas a persistencia de snapshots e best-effort.
- Scale-out para 2+ instancias exigiria externalizacao para Redis ou Table Storage.
- `agent.py:64`: `MAX_CONVERSATIONS = 200` -- conversas antigas sao evicted em carga elevada.

### W3. Rate Limiter -- Slow Path com I/O Async Dentro de Lock
- `rate_limit_storage.py:53-74`: slow path faz query async ao Table Storage DENTRO
  de `asyncio.Lock()`.
- Em cenario de storage lento (>100ms), o lock bloqueia requests concorrentes para o mesmo key.
- Mitigacao parcial: fast path via cache local e suficiente para a maioria dos requests.

### W4. Storage Auth usa SharedKeyLite (Nao Managed Identity)
- `storage.py:83-89`: autenticacao via SharedKeyLite com `STORAGE_KEY`.
- Key rotation e manual e implica downtime se nao gerida cuidadosamente.
- Managed Identity eliminaria a necessidade de gerir `STORAGE_KEY`.

### W5. Prompt Shield Sempre Fail-Open
- `prompt_shield.py:77-80`: em excepao, sempre retorna `is_blocked=False` (fail-open).
- Documentado no codigo como design decision, mas sem configuracao de fail-mode.
- **Nota**: a memoria anterior sobre `PROMPT_SHIELD_FAIL_MODE` esta desactualizada
  -- esta variavel ja nao existe no codigo actual.

### W6. auth_runtime.py -- Cache Local com TTL de 30s
- Cache local com TTL de 30s para reducao de round-trips.
- Janela de 30s onde um token revogado ainda pode ser aceite.
- Acceptable para a maioria dos casos de uso mas deve ser documentado como limitacao conhecida.

### W7. Key Vault com publicNetworkAccess=Enabled
- Confirmado na auditoria Azure: Key Vault nao tem accesso restrito a VNet.
- Potencialmente acessivel da internet publica com credenciais correctas.
- Mitigacao actual: RBAC + soft-delete activos.

### W8. Sem Staging Slot -- Deploys Directos para Producao
- Confirmado na auditoria Azure: App Service sem deployment slots.
- `rollback.sh` actualizado mas rollback real e por redeploy (nao swap atomico).

### W9. Document Intelligence -- Polling Fixo
- `tools.py` (Document Intelligence): polling cada 2s por 60s max.
- Documentos rapidos desperdicam tempo; documentos lentos (>60s) falham com timeout.
- Sem telemetria de performance de analise de documentos.

### W10. worker_entrypoint.py usa os.getenv() Directamente
- `worker_entrypoint.py:20-23`: `os.getenv()` directos para variaveis de runtime do worker.
- Minor: consistencia com a politica de usar `config._get_env()`.
- Severidade baixa -- variaveis de runtime nao sao segredos.

### W11. Sem Alertas Proactivos de Expiracao de Credenciais
- DevOps PAT expira periodicamente -- sem alerta de expiracao proxima.
- API keys (Search, Brave, Figma, Miro) sem rotacao automatica.

### W12. Sem DPIA / ROPA Formal
- `DATA_POLICY.md` documenta politica, mas sem DPIA formal nem ROPA.
- Processamento de dados de colaboradores internos exige base legal e notificacao ao DPO.

### W13. PII Shield -- Threshold 0.7 para Person/PersonType
- `pii_shield.py:53-57`: Person e PersonType com threshold 0.7.
- Nomes compostos em portugues podem ter confidence <0.7 e nao ser mascarados.

### W14. Sem VNet + Sem Entra ID (Pendente DSI)
- App Service ainda exposto publicamente -- sem VNet integration.
- Auth custom JWT em vez de Entra ID/SSO corporativo.
- Dependente de decisao da DSI do banco.

---

## OPPORTUNITIES (Oportunidades) -- Estado Actual

### O1. VNet + Entra ID (Maior Oportunidade, Pendente DSI)
- VNet integration eliminaria exposicao publica do App Service.
- Entra ID (Azure AD) substituiria JWT custom por SSO corporativo.
- Private Endpoints para Storage, Search, OpenAI -- zero exposicao publica.

### O2. Refactoring Frontend (Urgente -- App.jsx Cresce)
- App.jsx cresceu de 1 872 para 2 086 linhas -- tendencia negativa.
- Decomposicao em componentes focados.
- `useReducer` para estado de conversacao.
- **TypeScript** migration para type safety.

### O3. Managed Identity para Storage
- Substituir SharedKeyLite auth por Managed Identity.
- Elimina necessidade de gerir `STORAGE_KEY` em Key Vault.
- SystemAssigned Managed Identity ja activa no App Service.

### O4. App Insights Custom Metrics (Parcialmente Implementado)
- Log Analytics workspace `dbde-ai-logs` criado.
- Custom metrics pendentes: latencia por tool, erros por provider, tokens por utilizador.
- Alertas pendentes: quota LLM >80%, PAT a expirar.

### O5. Staging Slot para Blue/Green Deployments
- Criar deployment slot `staging` no App Service.
- `deploy_swap.sh` e `rollback.sh` ja preparados para este cenario.

### O6. Alertas de Expiracao de Credenciais
- Azure Monitor Alert Rule para expiracao de Key Vault secrets.
- Script de verificacao de validade de PATs e API keys no CI.

### O7. Optimizacao de Modelos
- `gpt-4.1-mini` para operacoes de routing/classificacao (mais barato, mais rapido).
- `gpt-5.1` como tier pro para tarefas complexas (quando certificado para dados bancarios).

### O8. Export e Reporting Avancado
- Export para Confluence/SharePoint alem de DOCX/PDF.
- Templates personalizaveis por equipa.

### O9. Caching de Respostas LLM
- Cache de respostas para queries repetidas via Redis ou Azure Cache.
- Reduziria latencia e custos em queries identicas.

### O10. DPIA e ROPA Formal
- Elaborar DPIA formal em colaboracao com DPO do banco.
- Documentar ROPA para o processamento de dados de colaboradores.

---

## THREATS (Ameacas) -- Estado Actual

### T1. Dados Bancarios Confidenciais (Risco Residual)
- PII Shield activo mas confidence <threshold passa sem mascaramento.
- Nomes em portugues de clientes bancarios podem ter confidence 0.6-0.69.
- Mitigacao actual: Data Policy documentada, Abuse Monitoring Opt-Out.

### T2. Anthropic Foundry -- Dados Fora do Perimetro Azure
- Requests para Claude via Anthropic Foundry saem do perimetro Azure.
- Provider governance layer restringe dados `elevated` -- mas configuravel.
- Exige validacao DPO do banco.

### T3. ConversationStore Eviction sob Carga
- Max 200 conversas em memoria; LRU eviction ao atingir limite.
- Utilizador activo pode ter conversa evicted por outro utilizador.

### T4. Deploys Directos para Producao (Sem Staging Slot)
- Cada deploy vai directamente para producao.
- `rollback.sh` requer redeploy (nao e swap atomico).

### T5. Supply Chain e Dependencias
- 23 dependencias Python + dependencias npm.
- `pip-audit` e `npm audit` no CI -- mitigacao parcial.

### T6. Prompt Injection via Documentos (Document Intelligence)
- Documentos maliciosos podem injectar instrucoes via texto extraido.
- Prompt Shield activo para user prompt, mas sem verificacao de conteudo de documentos.

### T7. Expiracao de Credenciais Sem Alertas
- DevOps PAT expira -- interrupcao silenciosa das tools de DevOps.
- API keys sem rotacao automatica.

### T8. Regulacao Bancaria
- EBA/BCE guidelines sobre AI podem exigir auditorias adicionais.
- RGPD/GDPR: sem DPIA formal.

### T9. Scale-Out Bloqueado por Estado In-Memory
- ConversationStore in-memory, 1 worker Uvicorn.
- Scale-out exigiria Redis/Table Storage para estado, JWT secret partilhado.

### T10. Key Vault publicNetworkAccess=Enabled
- Key Vault acessivel da internet publica (protegido por RBAC, sem VNet restriction).

---

## Risk Score (0-10) -- Revisado 2026-03-17

### Seguranca Aplicacional: **2.5/10** (Risco Baixo -- Melhorado de 4.5/10)
- (+) Race conditions todas corrigidas com asyncio.Lock()
- (+) auth_runtime.py: blacklist/lockout persistidos no storage
- (+) Code Interpreter: PATH minimal, CPU/mem limits, symlink validation
- (+) Secretos sanitizados nos logs (_sanitize_error_response)
- (+) DOMPurify 3.3.2 sem vulnerabilidades (npm audit = 0)
- (+) JWT hard-fail em producao se JWT_SECRET nao definido
- (-) Prompt Shield fail-open (by design)
- (-) auth_runtime cache de 30s (janela de revogacao)
- (-) PII threshold 0.7 para Person/PersonType

### Seguranca de Dados/Rede: **4.0/10** (Risco Moderado -- Melhorado de 5.5/10)
- (+) PII masking com thresholds diferenciados por categoria
- (+) Provider governance layer activo
- (+) Privacy service (DSR/GDPR delete/export)
- (-) Sem VNet -- App Service exposto publicamente (dependente DSI)
- (-) Key Vault publicNetworkAccess=Enabled
- (-) Anthropic Foundry = dados saem do perimetro Azure

### Custo/Sustentabilidade: **2.0/10** (Risco Baixo -- Sem alteracao)
- (+) Custo actual 30-55 EUR/mes extremamente eficiente
- (+) Token quotas activas por tier (Fast/Standard/Pro)
- (-) Sem alertas de custo configurados

### Qualidade de Codigo: **4.0/10** (Risco Moderado -- Melhorado de 5.0/10)
- (+) 511 testes passam (514 total, 3 pre-existing failures)
- (+) Async patterns consistentes; locks correctos em todos os componentes
- (-) Frontend monolitico cresceu de 1872 para 2086 linhas (tendencia negativa)
- (-) Sem TypeScript no frontend

### Operacoes/Monitoring: **3.5/10** (Risco Baixo-Moderado -- Melhorado de 4.0/10)
- (+) Documentacao operacional actualizada e precisa
- (+) CI/CD com dependency scanning
- (-) Sem alertas proactivos de expiracao de credentials
- (-) Sem staging slot (deploys directos para producao)
- (-) Custom metrics ainda pendentes

### **Risk Score Global: 3.2/10 (Risco Baixo-Moderado)**
#### Evolucao: 5.2/10 (Mar 6) -> 4.4/10 (Mar 8) -> **3.2/10 (Mar 17)**

---

## Achados Novos -- Linha a Linha (nao cobertos na analise anterior)

### A1. config.py -- ADMIN_USERNAME Hardcoded com Nome Real
- `config.py:332`: `ADMIN_USERNAME = _get_env("ADMIN_USERNAME", "pedro.mousinho")`.
- Default inclui nome de pessoa real -- deve ser configuravel sem fallback pessoal.
- **Severidade**: Baixa -- e um default configuravel via env var.

### A2. agent.py -- _conversation_locks Sem Limite de Tamanho
- `agent.py:264`: `_conversation_locks: Dict[str, asyncio.Lock] = {}` sem limite.
- Com muitas conversas, este dict pode crescer indefinidamente.
- `_deferred_lock_cleanup()` (agent.py:278) limpa locks apos uso -- mitigacao activa.
- **Severidade**: Baixa -- cleanup deferred activo.

### A3. storage.py -- XML Parsing com ElementTree
- `storage.py`: usa `xml.etree.ElementTree` para parsear respostas XML do Azure.
- `ElementTree` e vulneravel a XXE se o conteudo nao e confiado.
- Mitigacao: o conteudo e sempre de respostas do Azure Table Storage API.
- Boas praticas sugerem `defusedxml` como alternativa mais segura.
- **Severidade**: Negligivel em contexto actual.

### A4. rate_limit_storage.py -- Janela Fixa (Fixed Window)
- `rate_limit_storage.py:37`: algoritmo de janela fixa.
- Susceptivel a burst attack na transicao de janela (double-rate no limite).
- Sliding window seria mais robusto para uso critico.
- **Severidade**: Baixa -- uso interno com ~20 utilizadores.

### A5. tabular_artifacts.py -- SQL Escaping Manual
- `tabular_artifacts.py:51`: escaping manual de apostrofes em path DuckDB com f-string.
- Path e gerado por `tempfile.NamedTemporaryFile` -- zero risco pratico.
- Padrao de codigo questionavel mesmo sendo low risk.
- **Severidade**: Negligivel -- path interno, nao input do utilizador.

### A6. pii_shield.py -- Novo Cliente httpx por Chamada
- `pii_shield.py`: cada chamada ao PII service pode criar um cliente httpx novo.
- Connection pool seria mais eficiente para analises PII frequentes.
- **Severidade**: Baixa -- overhead de TCP handshake.

### A7. App.jsx -- Sem Paginacao de Mensagens
- Todas as mensagens de uma conversa carregadas e renderizadas de uma vez.
- Em conversas longas (>100 mensagens), performance do DOM pode degradar.
- **Severidade**: Baixa para uso actual; risco crescente com conversas longas.

---

## Recomendacoes Prioritarias (Top 10 -- Actualizado 2026-03-17)

Ordenadas por impacto / esforco:

### 1. Staging Slot -- Deploy Blue/Green
- **Impacto**: Alto | **Esforco**: Muito Baixo (<1 dia)
- Criar slot `staging` no App Service.
- `deploy_swap.sh` e `rollback.sh` ja estao preparados para este cenario.
- Elimina risco de downtime em cada deploy.

### 2. Alertas de Expiracao de Credenciais
- **Impacto**: Medio | **Esforco**: Muito Baixo (<1 dia)
- Azure Monitor Alert Rule para Key Vault secrets com expiracao proxima.
- Script de verificacao de PATs e API keys no CI.

### 3. VNet + Entra ID (Continuar pressao na DSI)
- **Impacto**: Muito Alto | **Esforco**: Medio (dependente DSI)
- VNet + Private Endpoints para App Service, Storage, Key Vault, OpenAI.
- Key Vault `publicNetworkAccess=Disabled` apos VNet activo.

### 4. Managed Identity para Storage
- **Impacto**: Medio | **Esforco**: Baixo (2-3 dias)
- Substituir SharedKeyLite por Azure AD auth via Managed Identity.
- Elimina `STORAGE_KEY` do Key Vault e rotacao manual.

### 5. Refactoring Frontend -- Fase 1
- **Impacto**: Alto | **Esforco**: Medio (1-2 semanas)
- Decomposicao de App.jsx (2 086 linhas) em componentes focados.
- Bloquear crescimento adicional (regra de CI: alertar se >2500 linhas).

### 6. App Insights Custom Metrics + Alertas
- **Impacto**: Medio | **Esforco**: Baixo (2-3 dias)
- Latencia por tool, erros por provider, tokens por utilizador.
- Alertas: quota LLM >80%, erros 5xx, PAT a expirar.

### 7. Sliding Window no Rate Limiter
- **Impacto**: Baixo | **Esforco**: Muito Baixo (1 dia)
- Substituir janela fixa por sliding window para prevenir double-rate bursts.

### 8. defusedxml para Parsing XML
- **Impacto**: Baixo | **Esforco**: Muito Baixo (horas)
- Substituir `xml.etree.ElementTree` por `defusedxml` em `storage.py`.
- Previne XXE por principio mesmo que o risco pratico seja negligivel.

### 9. DPIA e ROPA Formal
- **Impacto**: Medio (compliance) | **Esforco**: Baixo (1-2 dias tecnico)
- Elaborar DPIA em colaboracao com DPO do banco.

### 10. Virtualizar Mensagens no Frontend
- **Impacto**: Medio | **Esforco**: Baixo (1-2 dias)
- `react-window` para virtualizacao de listas longas de mensagens.

---

## Conclusao

O DBDE AI Assistant v7.3.0 evoluiu significativamente desde a analise inicial de 6 de Marco.
Todos os issues criticos de concorrencia foram resolvidos, o hardening de seguranca e robusto,
e a suite de testes cresceu para 514 testes.

A **principal preocupacao actual** e a exposicao publica sem VNet -- dependente da DSI --
e o crescimento continuo do frontend monolitico. Com as 10 recomendacoes implementadas,
o Risk Score global pode baixar de **3.2/10 para ~1.8/10**.

O produto esta num estado **adequado para o contexto actual de ~20 utilizadores internos**,
com controls de seguranca proporcionais ao risco, documentacao operacional actualizada,
e um pipeline de qualidade automatizado.

---
*Revisao exaustiva linha a linha em 2026-03-17 via Claude Code.*
*Revisao anterior: 2026-03-06 (analise inicial), 2026-03-08 (actualizacao pos-remediacao).*
*Projecto: DBDE AI Assistant v7.3.0 -- Millennium BCP (uso interno)*
