# DBDE AI Assistant — Documentação de Continuidade
## Versão: 8.0.0 | Atualizado: 2026-03-17

## Fonte de verdade
Este documento foi alinhado com:
- `config.py`
- `app.py`
- `startup.sh`
- `startup_worker.sh`
- `worker_entrypoint.py`
- `.github/workflows/ci.yml`
- `docs/RUNBOOK.md`
- `docs/DEPLOY_CHECKLIST.md`

## 1. Objetivo
Garantir continuidade operacional por uma equipa backup sem depender de conhecimento tácito do autor original.

## 2. Componentes que têm de continuar acessíveis
- Repositório GitHub com histórico e workflow CI
- Web app FastAPI/App Service
- Frontend build Vite servido a partir de `static/`
- Azure Table Storage e Azure Blob Storage
- Azure OpenAI
- Azure AI Search
- Azure DevOps
- Secrets/App Settings do App Service
- Worker runtime de upload/export, seja sidecar na web app ou worker app dedicada

## 3. Invariantes operacionais atuais
- A versão de aplicação definida no código é `8.0.0`.
- O frontend é buildado em CI e em deploy local via `npm run build`.
- O web app pode operar com ou sem slot `staging`.
- Em produção, `JWT_SECRET` é obrigatório.
- `/health`, `/api/info`, `/docs`, `/openapi.json` e `/redoc` são auth-exempt por código.
- `/health?deep=true` requer conta admin válida.
- O runtime atual depende de `static/index.html` e de bundles em `static/dist/assets`.

## 4. Acessos mínimos necessários
- Azure subscription com permissões de operação sobre App Service, Storage, Search e recursos de IA
- GitHub repo com permissões para merge, tag e leitura de Actions
- Gestão de App Settings/secrets
- Azure DevOps PAT com scopes adequados
- Acesso a contas/admin para validar login e deep health

## 5. Operação diária
Ver [RUNBOOK.md](./RUNBOOK.md).

Ritual mínimo:
- validar `/health`
- validar `/api/info`
- validar `/health?deep=true`
- rever logs
- rever segredos com risco de expiração

## 6. Rotação de segredos
### Obrigatórios
- `JWT_SECRET`
- `DEVOPS_PAT`
- `AZURE_OPENAI_KEY`
- `SEARCH_KEY`
- `STORAGE_CONNECTION_STRING` ou `STORAGE_KEY`

### Opcionais mas sensíveis
- `ANTHROPIC_API_KEY`
- `WEB_SEARCH_API_KEY`
- `WEB_ANSWERS_API_KEY`
- `FIGMA_ACCESS_TOKEN`
- `MIRO_ACCESS_TOKEN`
- `AZURE_SPEECH_KEY`
- `PII_API_KEY`
- `CONTENT_SAFETY_KEY`
- `DOC_INTEL_KEY`

### Notas
- `JWT_SECRET_PREVIOUS` suporta rotação controlada sem invalidação imediata de todos os tokens.
- Mudança de `JWT_SECRET` invalida sessões existentes quando a secret anterior deixa de ser aceite.

## 7. Dependências humanas que o repositório não conhece
- owner de produto
- owner de operação
- owner de cloud/infra
- owner de segurança/compliance

Estas funções devem existir fora do repositório e precisam de backup explícito.

## 8. Riscos de continuidade
- Dependência forte de App Settings corretas
- Dependência de Azure OpenAI, Search e Storage
- Dependência de PAT de Azure DevOps
- Possível coexistência de worker sidecar e worker app dedicada em ambientes diferentes
- Parte da documentação histórica removida do repo já não deve ser usada como source of truth

## 9. Plano mínimo de handover
1. Partilhar acesso ao repositório e Azure.
2. Rever `RUNBOOK.md` e `DEPLOY_CHECKLIST.md`.
3. Executar smoke test num ambiente conhecido.
4. Validar login admin e `GET /health?deep=true`.
5. Confirmar localização dos logs e dos PID files.
