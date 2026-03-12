# DBDE AI Assistant — Worklog de Auditoria
## Data de arranque: 2026-03-10

## Objetivo
Auditar o snapshot local da aplicação que representa a `main` em produção, cruzando:
- código-fonte backend, frontend e workers;
- testes, CI e scripts operacionais;
- configuração e runtime efetivo no Azure;
- riscos técnicos, funcionais, operacionais e de segurança.

## Limitações conhecidas
- Este diretório não contém `.git`, por isso não é possível provar localmente o commit exacto da `main` nem fazer diff/histórico.
- O `deep health` em produção exige autenticação; a validação pública neste momento confirma apenas liveness.

## Evidência já recolhida
### Snapshot local
- Stack principal: FastAPI + Uvicorn + React/Vite.
- Ficheiros centrais: `app.py` (3629 linhas), `tools.py` (3306), `agent.py` (2414), `tools_devops.py` (1525), `llm_provider.py` (1145), `frontend/src/App.jsx` (1872).
- Suite de testes: 66 ficheiros.
- CI existente em `.github/workflows/ci.yml` com pytest em Python 3.11/3.12 e build frontend.

### Azure real
- Subscription activa: `Azure subscription 1`.
- Resource Group: `rg-MS_Access_Chabot` em `swedencentral`.
- App Service: `millennium-ai-assistant`, Linux, Python 3.12, `bash startup.sh`, `alwaysOn=true`, `httpsOnly=true`.
- Managed Identity: `SystemAssigned`.
- Key Vault references activas para segredos principais (`AZURE_OPENAI_KEY`, `DEVOPS_PAT`, `JWT_SECRET`, `SEARCH_KEY`, etc.).
- Basic health público responde `healthy`.

## Achados iniciais confirmados
1. Docs e scripts assumem slot `staging`, mas o App Service não tem deployment slots neste momento.
2. O script de rollback usa por omissão `https://dbdeai.pt`, mas o App Service expõe apenas `millennium-ai-assistant.azurewebsites.net` como hostname activo.
3. A estratégia de segredos está maioritariamente correta via Key Vault, mas existe pelo menos uma app setting com connection string em claro (`WEBSITE_DAAS_STORAGE_CONNECTIONSTRING`), o que exige revisão.
4. O `deep health` não é público; isto é aceitável do ponto de vista de segurança, mas obriga a ajustar runbooks/checklists se hoje estiver a ser assumido como validação anónima.
5. O snapshot local inclui `antenv/`, o que sugere risco de drift entre artefactos locais e build real se a equipa usar a pasta como referência sem limpar dependências vendorizadas.

## Frentes de auditoria
### 1. Provenance e release discipline
- Validar como a equipa garante que este snapshot corresponde à `main` produtiva.
- Rever scripts de deploy/rollback, pressupostos de slots, smoke tests e rollback paths.

### 2. Segurança e autenticação
- Rever JWT, gestão de cookies, invalidação de sessões, lockout, RBAC e superfícies admin.
- Procurar segredos hardcoded, exposição indevida de settings, CORS/cookies, fuga de dados e prompts externos.

### 3. Runtime e fiabilidade
- Rever startup, sidecars/workers, health checks, supervisão, concorrência, retries e failure modes.
- Cruzar com App Service, identidade, storage, observabilidade e alerting reais.

### 4. Dados e integrações
- Rever Azure Table/Blob auth, AI Search, Azure OpenAI, Anthropic via Foundry, Brave, DevOps, Figma e Miro.
- Verificar isolamento, quotas, saneamento de erros e tratamento de payloads sensíveis.

### 5. Backend funcional
- Auditar `app.py`, `agent.py`, `tools.py`, `tools_devops.py`, `tools_knowledge.py`, `storage.py`, `llm_provider.py`, `upload_worker.py`, `export_worker.py`.
- Procurar bugs, inconsistências de design, código duplicado, defaults perigosos e fragilidade sem testes.

### 6. Frontend e contrato API
- Rever autenticação, rendering, markdown, uploads, feedback, export, UX de erro e consistência com contratos do backend.
- Validar build output e dependências client-side.

### 7. Qualidade e testes
- Executar testes e builds relevantes.
- Identificar lacunas de cobertura e áreas críticas sem validação automatizada.

## Método de execução
1. Inventário e cruzamento código ↔ Azure.
2. Revisão backend por domínio funcional.
3. Revisão frontend e pipeline.
4. Validação dinâmica local/produção.
5. Relatório final com findings priorizados (`P0` a `P3`), impacto, evidência e remediação.

## Saídas esperadas
- Relatório executivo de riscos.
- Lista priorizada de findings técnicos.
- Mapa de inconsistências entre produção, docs e código.
- Plano de remediação por ondas: imediato, curto prazo, estrutural.

## Próximos passos imediatos
- Confirmar rotas/guardas do `deep health` e endpoints admin.
- Validar scripts de deploy/rollback contra os recursos Azure existentes.
- Correr a bateria de testes e build para estabelecer baseline.
- Entrar na revisão de `config.py`, `auth.py`, `storage.py`, `llm_provider.py`, `app.py` e `tools.py`.

## Checkpoint 1 — Estado confirmado
### Baseline local
- `python3 -m pytest tests/ -q` -> `299 passed in 3.88s`.
- `npm run build` -> build OK.
- `npm audit` -> 1 vulnerabilidade moderada (`dompurify`, fix disponível).
- O `antenv/` versionado não é reprodutível nesta máquina porque aponta para um `python3.12` inexistente.

### Runtime Azure
- `GET /health` público responde `200`.
- `GET /health?deep=true` sem autenticação responde `401`, logo o runbook/checklist deve assumir credenciais para deep checks.
- O App Service expõe apenas `millennium-ai-assistant.azurewebsites.net`; não há hostname `dbdeai.pt` configurado.
- Não existem deployment slots no App Service (`slot count = 0`).
- App Service Plan actual: `Basic B1`, capacidade `1`.
- Existe autoscale config `dbdeai-asp-autoscale`, mas está `enabled = false`.

### Key Vault / segredos
- A maioria dos segredos produtivos está corretamente referenciada via `@Microsoft.KeyVault(...)`.
- Há segredos aparentemente órfãos/duplicados no vault (`FIGMA-ACCESS-TOKEN`, `MIRO-ACCESS-TOKEN`, `STORAGE-CONNECTION-STRING`, `WEB-ANSWERS-API-KEY`, `dbde-devops-patoken`, `claude-opus-key`) sem evidência actual de utilização no código/app settings.
- O Key Vault usa RBAC e soft delete, mas mantém `publicNetworkAccess = Enabled`.

## Findings confirmados até agora
### P0
- `run_code` / `code_interpreter.py` tem bypass de sandbox: foi possível ler `/etc/hosts` fora do diretório temporário via `io.open` com path absoluto construído dinamicamente. O filtro estático por substring e o patch apenas a `builtins.open` não são suficientes.

### P1
- Logout, force logout, password reset e lockout dependem de estruturas in-memory (`auth.py`) e perdem efeito após recycle/restart. Isto invalida a premissa de revogação persistente de tokens.
- Processo de deploy/rollback documentado não corresponde ao Azure real: scripts e docs assumem slot `staging`, mas o App Service não tem slots.
- `rollback.sh` valida por defeito `https://dbdeai.pt`, domínio que não está configurado no Web App actual.

### P2
- Existe pelo menos uma app setting com connection string em claro (`WEBSITE_DAAS_STORAGE_CONNECTIONSTRING`), apesar da estratégia principal usar Key Vault.
- Dependência `dompurify` em versão com advisory conhecido de XSS; a app usa `dangerouslySetInnerHTML`, pelo que convém tratar isto como dívida de segurança real e não cosmética.
- Há state local relevante (`ConversationStore`, `feedback_memory`, caches de upload/conversation) que torna o sistema frágil a scale-out ou failover, mesmo que hoje esteja preso a 1 instância.

## Checkpoint 2 — Remediações aplicadas
### Segurança
- `code_interpreter.py` endurecido:
  - removidos imports de utilizador `io` e `pathlib` do allowlist;
  - `io.open` no runner também passa pelo mesmo guard de `_safe_path`;
  - adicionados testes para import bloqueado e path absoluto dinâmico.
- `dompurify` atualizado para `^3.3.2`; `npm audit` fica sem vulnerabilidades reportadas.

### Auth
- Criado `auth_runtime.py` para persistir:
  - tokens revogados;
  - cutoff de invalidação por utilizador;
  - lockout de login.
- Novo storage table: `AuthState`.
- Middleware HTTP passou a validar o token do request uma vez contra estado persistente e a propagar payload/erro validado para o resto da request.
- Endpoints de login/logout/password/deactivate/force-logout passaram a escrever estado persistente.

### Deploy / Operação
- `deploy_swap.sh` e `rollback.sh` agora:
  - resolvem o hostname real do App Service;
  - verificam explicitamente se o slot existe;
  - falham com erro claro quando não há slot, em vez de assumir swap impossível.
- `DEPLOY_CHECKLIST.md` e `RUNBOOK.md` atualizados para refletir:
  - deep health com autenticação;
  - cenário real sem `staging`;
  - rollback por redeploy quando não existe slot.

## Validação após remediação
- `python3 -m pytest tests/ -q` -> `304 passed`
- `npm run build` -> OK
- `npm audit` -> `0 vulnerabilities`

## Checkpoint 3 — Fecho quase total dos findings
### Backend / isolamento / retenção
- `generated_files.py` introduzido para centralizar ficheiros temporários com:
  - metadata persistida em Blob;
  - `user_sub` / `conversation_id` / `scope`;
  - purge local e remoto de artefactos expirados.
- `app.py` agora:
  - autoriza downloads temporários por owner;
  - purga `UploadIndex` e blobs associados ao apagar conversa;
  - revoga logout pelo token efetivo do request (cookie ou bearer);
  - valida retorno de `table_insert()` em `create-user`;
  - restringe `/api/learning/rules`, `/feedback/stats` e `GET /health?deep=true` a admins;
  - expõe `upload_limits` em `/api/info`;
  - recupera export jobs stale e limpa jobs persistentes expirados.
- `agent.py` agora vincula contexto de conversa e cache de anexos ao `user_sub`, evitando reutilização cross-user de `conversation_id`.
- `learning.py` deixou de reutilizar few-shot global; a recuperação fica scoped por utilizador e exemplos legados deixam de contaminar prompts de outros utilizadores.
- `data_dictionary.py` e `tools_learning.py` passaram a particionar dados por utilizador (`owner_sub`), fechando colisões globais em dicionários de dados e writer profiles.

### LLM / DevOps / quotas
- `llm_provider.py`:
  - `llm_simple()` passou a usar o mesmo pipeline protegido de `llm_with_fallback`;
  - pedidos com `response_format` deixam de ficar presos ao provider Anthropic quando este não suporta structured output.
- `tools_devops.py`:
  - `query_workitems` passou a usar allowlist real de fields;
  - `create_workitem` já não aceita apenas `confirmed=true`; exige token de confirmação server-side consumível uma vez.
- `token_quota.py` deixou de usar contadores puramente process-local:
  - quotas por tier passaram para shards persistidos em Table Storage por instância;
  - o snapshot admin passou a refletir uso distribuído entre instâncias;
  - criada tabela `TokenQuota`.

### Azure
- A app setting `WEBSITE_DAAS_STORAGE_CONNECTIONSTRING` foi alterada no App Service `millennium-ai-assistant` para deixar de estar em claro e passar a seguir a estratégia de Key Vault reference usada no resto da app.
- Health público após alteração Azure: `GET /health` -> `{"status":"healthy","mode":"basic","checks":{"app":"ok"}}`.
