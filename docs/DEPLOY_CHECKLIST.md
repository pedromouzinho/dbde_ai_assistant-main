# DBDE AI Assistant — Checklist de Deploy
## Versão: 8.0.0 | Atualizado: 2026-03-17

## Fonte de verdade
Checklist alinhado com:
- `.github/workflows/ci.yml`
- `package.json`
- `startup.sh`
- `startup_worker.sh`
- `scripts/smoke_test.py`
- `scripts/deploy_swap.sh`
- `scripts/rollback.sh`
- `routes_admin.py`

## 1. Pré-deploy local
- [ ] `python -m pytest tests/ -x --tb=short -q`
- [ ] `npm ci`
- [ ] `npm run build`
- [ ] Confirmar que existem `static/index.html` e `static/dist/assets/`
- [ ] Confirmar que não há secrets hardcoded nem `.env` acidentais no commit
- [ ] Confirmar que o commit/PR descreve a mudança
- [ ] Confirmar que a branch está atualizada com `main`

## 2. Preparação de runtime
- [ ] Rever App Settings críticas: `JWT_SECRET`, `AZURE_OPENAI_*`, `SEARCH_*`, `STORAGE_*`, `DEVOPS_PAT`
- [ ] Rever flags de workers: `UPLOAD_DEDICATED_WORKER_ENABLED`, `EXPORT_DEDICATED_WORKER_ENABLED`
- [ ] Rever `ALLOWED_ORIGINS`
- [ ] Rever se existe worker app dedicada e qual o `WORKER_MODE`

## 3. Deploy com slot `staging` quando existir
- [ ] Confirmar que o slot `staging` existe no App Service
- [ ] Fazer deploy para o slot `staging`
- [ ] Aguardar startup completo do web app
- [ ] Se existir worker app dedicada, aguardar startup dessa app também
- [ ] Correr `python3 scripts/smoke_test.py <staging_url>`
- [ ] Se houver credenciais de smoke, definir `SMOKE_USER` e `SMOKE_PASS` para cobrir `/health?deep=true`
- [ ] Verificar logs do App Service e dos workers

## 4. Swap staging -> production
- [ ] Confirmar smoke test de staging sem falhas
- [ ] Executar `bash scripts/deploy_swap.sh`
- [ ] Confirmar smoke test de production sem falhas
- [ ] Confirmar `GET /health?deep=true` com admin
- [ ] Confirmar `upload_worker` e `export_worker` como `ok` ou `disabled`, nunca em erro
- [ ] Monitorizar logs e erros durante pelo menos 5 minutos

## 5. Deploy in-place quando não existe slot
- [ ] Confirmar explicitamente que não existe slot `staging`
- [ ] Fazer deploy direto para production
- [ ] Correr `python3 scripts/smoke_test.py <production_url>`
- [ ] Se houver credenciais de smoke, repetir com `SMOKE_USER` e `SMOKE_PASS`
- [ ] Verificar `GET /health?deep=true` com admin
- [ ] Verificar logs e workers
- [ ] Preparar rollback por redeploy da versão anterior, não por swap

## 6. Pós-deploy
- [ ] `GET /health`
- [ ] `GET /api/info`
- [ ] `GET /`
- [ ] Login com utilizador válido
- [ ] Chat básico
- [ ] Upload simples
- [ ] Se export estiver no âmbito da release, validar um export
- [ ] Confirmar cookie auth, CORS e frontend bundle corretos

## 7. Rollback
### Com slot
- [ ] Executar `bash scripts/rollback.sh`
- [ ] Confirmar `/health`
- [ ] Confirmar `/health?deep=true`
- [ ] Repetir smoke test

### Sem slot
- [ ] Redeploy da versão anterior
- [ ] Confirmar `/health`
- [ ] Confirmar `/api/info`
- [ ] Repetir smoke test
- [ ] Registar motivo do rollback

## 8. Evidência mínima a guardar
- [ ] SHA/commit deployado
- [ ] URL alvo
- [ ] Resultado do smoke test
- [ ] Resultado do deep health
- [ ] Janela temporal de monitorização
