# DBDE AI Assistant — SWOT Tracker

**Criado**: 2026-03-07
**Ultima actualizacao**: 2026-03-17
**Baseado em**: [DBDE-SWOT-Analysis-Marco2026.md](./DBDE-SWOT-Analysis-Marco2026.md)
**Risk Score inicial**: 5.2/10 → Revisto para 4.4/10 (apos auditoria Azure) → **3.2/10 (Mar 17, linha a linha)**

---

## Progresso Global

| Metrica | Valor |
|---|---|
| Total de itens identificados | 47 (40 originais + 7 novos achados linha a linha) |
| Concluidos | 18 |
| Em progresso | 0 |
| Pendentes | 29 |
| **Progresso** | **38%** (base expandida) |
| **Risk Score actual estimado** | **~3.2/10** |

---

## Top 10 Recomendacoes — Estado

| # | Recomendacao | Esforco | Estado | Data | Notas |
|---|---|---|---|---|---|
| 1 | App Insights Ingestion + Health Check Path | Minutos | ✅ FEITO | 2026-03-07 | `ingestionMode=LogAnalytics`, workspace `dbde-ai-logs` criado. `healthCheckPath=/health`. |
| 2 | Locks de Concorrencia no Backend (W1) | 2-3 dias | ✅ FEITO | 2026-03-07 | **CRITICO** resolvido. 17 race conditions corrigidas. PR #5 merged. 12 tests novos. |
| 3 | VNet + Entra ID | Depende DSI | ❌ PENDENTE | — | Dependente da DSI do banco. SCM restringido como medida interina (2026-03-07). |
| 4 | Desactivar FTPS + Restringir SCM | Minutos | ✅ FEITO | 2026-03-07 | `ftpsState=Disabled`, SCM `DenyAll 0.0.0.0/0`. |
| 5 | Upgrade AI Search para Basic | 1 dia | ⏸️ ADIADO | — | Tier Free suficiente para uso actual. Reavaliar quando necessario. |
| 6 | Cleanup de Recursos Orfaos | Horas | ⚠️ PARCIAL | 2026-03-09 | Removidos 9 deployments órfãos do Foundry/OpenAI (`dbde_access_chatbot_41`, `gpt-4.1-mini`, `gpt-5-mini`, `gpt-5-chat`, `gpt-5.2-chat`, `gpt-4.1`, `gpt-5.1`, `o4-mini-dz`, `gpt-5.3-chat`) e limpo `ALLOWED_ORIGINS`. Mantidos: CosmosDB (`cosmosdbrgmsaccesschabot84949c`), deployment gpt-4o (`dbde_access_chatbot`) e `model-router` por referência/config operacional. |
| 7 | Dependency Scanning no CI | Horas | ✅ FEITO | 2026-03-07 | `pip-audit` + `npm audit --audit-level=high` no GitHub Actions CI. Commit `4677fc3`. |
| 8 | Proteger Secrets nos Logs (W7) | 1 dia | ✅ FEITO | 2026-03-08 | `_sanitize_error_response()` com 4 regex patterns. 14 pontos em 6 ficheiros. PR #6 merged. |
| 9 | Refactoring Frontend (Fase 1) | 1-2 semanas | ❌ PENDENTE | — | App.jsx 1,872 linhas. Nao bloqueante. |
| 10 | Testar Model Router + gpt-5.3-chat | 1-2 dias | ⏸️ ADIADO | — | Modelos nao certificados para dados confidenciais bancarios. Reavaliar quando houver compliance. |

---

## Weaknesses (W1-W12) — Estado Actual

| ID | Fraqueza | Severidade | Estado | Data | Notas |
|---|---|---|---|---|---|
| W1 | Concorrencia nao thread-safe | CRITICO | ✅ FEITO | 2026-03-07 | 17 race conditions corrigidas. asyncio.Lock em ConversationStore, meta, files, providers. PR #5. = Rec 2. |
| W2 | Frontend monolitico | MEDIO | ❌ PENDENTE | — | App.jsx cresceu para **2 086 linhas** (era 1 872 em Mar 6). Tendencia negativa. = Rec 5 nova. |
| W3 | App Insights ingestao desactivada | ALTO | ✅ FEITO | 2026-03-07 | `ingestionMode=LogAnalytics`, workspace `dbde-ai-logs`. = Rec 1. |
| W4 | Health Check Path null | ALTO | ✅ FEITO | 2026-03-07 | `healthCheckPath=/health`. = Rec 1. |
| W5 | AI Search no tier Free | MEDIO | ⏸️ ADIADO | — | Tier Free suficiente para uso actual. Reavaliar quando necessario. = Rec 5. |
| W6 | Sem token blacklist / refresh | MEDIO | ✅ FEITO | 2026-03-08 | auth_runtime.py criado: blacklist/lockout persistidos no Azure Table Storage. PR #7 merged. |
| W7 | Logging pode expor secrets | ALTO | ✅ FEITO | 2026-03-08 | `_sanitize_error_response()` com 4 regex patterns. 14 pontos em 6 ficheiros. PR #6 merged. = Rec 8. |
| W8 | PII Shield overlapping + HTTP client | ALTO | ✅ FEITO | 2026-03-07 | Phase 1: overlapping resolution, regex pre-mask. Phase 2: shared httpx client, audit logging. PR #3 + PR #4. |
| W9 | Recursos potencialmente orfaos | BAIXO | ⚠️ PARCIAL | 2026-03-07 | 3/5 apagados. Restam CosmosDB + deployment gpt-4o. = Rec 6. |
| W10 | Code Interpreter gaps hardening | MEDIO | ✅ FEITO | 2026-03-08 | PATH minimal, resource limits (CPU 120s, mem 512MB), symlink validation, AST import+getattr blocking. PR #6 merged. |
| W11 | FTPS deveria estar Disabled | BAIXO | ✅ FEITO | 2026-03-07 | `ftpsState=Disabled`. = Rec 4. |
| W12 | SCM site sem restricoes IP | MEDIO | ✅ FEITO | 2026-03-07 | `DenyAll 0.0.0.0/0` no SCM. = Rec 4. |
| W13 (NOVO) | PII threshold 0.7 para Person/PersonType | BAIXO | ❌ PENDENTE | — | Nomes compostos em PT podem ter confidence <0.7. Ajustar threshold ou adicionar regras regex adicionais. |
| W14 (NOVO) | Sem VNet + Sem Entra ID (dependente DSI) | ALTO | ❌ PENDENTE | — | App Service exposto publicamente. Key Vault publicNetworkAccess=Enabled. = Rec 3. |
| W15 (NOVO) | Storage Auth usa SharedKeyLite | MEDIO | ❌ PENDENTE | — | Managed Identity seria mais seguro. = Rec 4 nova. |

---

## Threats (T1-T9) — Mitigacoes Actuais

| ID | Ameaca | Severidade | Mitigacao | Estado | Notas |
|---|---|---|---|---|---|
| T1 | Dados bancarios confidenciais | ALTO | PII Shield Phase 1+2 | ✅ MITIGADO | Regex pre-mask, Azure AI Language, tool masking, blob PII, Brave query masking, audit logs. Risco residual: threshold 0.7, comportamento utilizadores. |
| T2 | Exposicao publica de servicos | ALTO | VNet + Private Endpoints | ❌ PENDENTE | Depende DSI. SCM restringido como interino. = Rec 3. |
| T3 | Dependencia servicos Azure | MEDIO | DR plan + fallback | ⚠️ PARCIAL | Fallback Claude Opus/Sonnet activo para LLM. AI Search e Storage sem fallback. |
| T4 | Supply chain / dependencias | MEDIO | CI scanning | ✅ MITIGADO | `pip-audit` + `npm audit` adicionados ao CI. = Rec 7. |
| T5 | Escalabilidade limitada | BAIXO | Scale-out architecture | ❌ PENDENTE | ConversationStore in-memory, 1 worker. Autoscale configurado mas sem externalizacao de estado. |
| T6 | Regulacao bancaria | MEDIO | Compliance docs | ⚠️ PARCIAL | Data Policy documentada. Sem DPIA/ROPA formal. = Rec 9 nova. |
| T7 | Expiracao credenciais | MEDIO | Alertas proactivos | ❌ PENDENTE | Sem alertas de expiracao de PATs/keys. = Rec 2 nova. |
| T8 | Prompt injection avancado | MEDIO | Prompt Shield + hardening | ⚠️ PARCIAL | Prompt Shield activo. AST checker melhorado. Risco residual: prompt injection via documentos. |
| T9 | Vendor lock-in | BAIXO | Multi-provider | ⚠️ PARCIAL | Claude via Foundry como fallback. Restante stack = Azure. |
| T10 (NOVO) | Key Vault publicNetworkAccess=Enabled | MEDIO | VNet (pendente) | ❌ PENDENTE | Key Vault acessivel da internet sem VNet restriction. Mitigado por RBAC. = Rec 3. |
| T11 (NOVO) | Deploys directos para producao | MEDIO | Staging slot | ❌ PENDENTE | Sem staging slot; rollback por redeploy. = Rec 1 nova. |

---

## Opportunities (O1-O10) — Estado Actual

| ID | Oportunidade | Estado | Notas |
|---|---|---|---|
| O1 | VNet + Entra ID | ❌ PENDENTE | Depende DSI. = Rec 3. |
| O2 | App Insights + telemetria custom | ⚠️ PARCIAL | Ingestao activada. Custom metrics (latencia, tokens) ainda por implementar. = Rec 1. |
| O3 | Refactoring frontend | ❌ PENDENTE | App.jsx cresceu para 2 086 linhas. Mais urgente que antes. = Rec 5 nova. |
| O4 | Upgrade AI Search | ⏸️ ADIADO | Tier Free suficiente. = Rec 5. |
| O5 | Optimizacao modelos (gpt-5.3, Router) | ⏸️ ADIADO | gpt-5.3-chat + Model Router adiados -- nao certificados para dados confidenciais. = Rec 10. |
| O6 | Code Interpreter hardening | ✅ FEITO | PATH minimal, resource limits, symlink validation, AST hardening. PR #6 merged. = W10. |
| O7 | Cleanup recursos orfaos | ❌ PENDENTE | = Rec 6. |
| O8 | Health Check Path | ✅ FEITO | `healthCheckPath=/health`. = Rec 1. |
| O9 | Export e reporting avancado | ❌ PENDENTE | Confluence/SharePoint export, templates por equipa. |
| O10 | Integracao com mais ferramentas | ❌ PENDENTE | Jira, Confluence, Teams, GitLab/GitHub. |
| O11 (NOVO) | Staging Slot | ❌ PENDENTE | Criar slot `staging`; scripts ja preparados. = Rec 1 nova. |
| O12 (NOVO) | Managed Identity para Storage | ❌ PENDENTE | Substituir SharedKeyLite por Managed Identity. = Rec 4 nova. |
| O13 (NOVO) | Alertas de expiracao de credenciais | ❌ PENDENTE | Azure Monitor + CI script. = Rec 2 nova. |
| O14 (NOVO) | DPIA e ROPA formal | ❌ PENDENTE | Colaboracao com DPO do banco. = Rec 9 nova. |

---

## Achados Novos da Auditoria Linha a Linha (2026-03-17)

| ID | Achado | Severidade | Estado | Notas |
|---|---|---|---|---|
| A1 | config.py -- ADMIN_USERNAME com nome real como default | BAIXO | ❌ PENDENTE | `ADMIN_USERNAME = _get_env("ADMIN_USERNAME", "pedro.mousinho")`. Configuravel via env var. |
| A2 | agent.py -- _conversation_locks sem limite de tamanho | BAIXO | ⚠️ MITIGADO | `_deferred_lock_cleanup()` limpa locks apos uso. Monitorizar em carga elevada. |
| A3 | storage.py -- xml.etree.ElementTree (XXE teorico) | NEGLIGIVEL | ❌ PENDENTE | Origem Azure API (confiada). Considerar migrar para `defusedxml`. = Rec 8 nova. |
| A4 | rate_limit_storage.py -- janela fixa (fixed window) | BAIXO | ❌ PENDENTE | Double-rate attack teorico. Sliding window recomendada. = Rec 7 nova. |
| A5 | tabular_artifacts.py -- SQL escaping manual com f-string | NEGLIGIVEL | ⚠️ ACEITE | Path interno de tempfile, zero risco pratico. Padrao de codigo questionavel. |
| A6 | pii_shield.py -- novo cliente httpx por chamada | BAIXO | ❌ PENDENTE | Connection pool melhoraria performance em PII frequente. = Rec 8. |
| A7 | App.jsx -- sem paginacao/virtualizacao de mensagens | BAIXO | ❌ PENDENTE | react-window recomendado para conversas longas. = Rec 10 nova. |

---

## Accoes Completadas Fora do SWOT (Bonus)

| Accao | Data | Notas |
|---|---|---|
| PII Shield Phase 2 — tool output masking | 2026-03-07 | Masking em `role=tool`, blob PII protection, Brave query masking, shared httpx client, audit logging. PR #4. |
| Feature activation — RERANK + WEB_SEARCH | 2026-03-07 | `RERANK_ENABLED=true`, `WEB_SEARCH_ENABLED=true`, `XDT_BaseExtensions=~1`. |
| Token quotas restauradas | 2026-03-07 | Fast 500K/5M, Standard 200K/2M, Pro 100K/1M (anteriormente 0,0 = ilimitado). |
| Model tiers configurados | 2026-03-07 | gpt-4.1 (fast), Claude Sonnet 4.6 via Azure Foundry (standard), Claude Opus 4.6 (pro). |
| Log Analytics workspace criado | 2026-03-07 | `dbde-ai-logs` em Sweden Central, 90 dias retencao. Workspace anterior (DefaultResourceGroup-SEC) estava orfao. |
| Dependency scanning CI | 2026-03-07 | `pip-audit` (Python) + `npm audit --audit-level=high` (frontend) adicionados ao GitHub Actions. Commit `4677fc3`. |
| Concurrency locks implementation | 2026-03-07 | 17 race conditions corrigidas em agent.py + llm_provider.py. 12 tests novos. PR #5 merged. |
| Security hardening — secrets in logs | 2026-03-08 | `_sanitize_error_response()` com 4 regex patterns. 14 pontos em 6 ficheiros. 15 tests novos. PR #6 merged. |
| Code Interpreter hardening | 2026-03-08 | PATH minimal, `resource.setrlimit()` CPU/mem, symlink validation, AST ImportFrom + getattr/setattr/delattr blocking. PR #6 merged. |
| Token blacklist + auth hardening | 2026-03-08 | JWT jti/iat claims, in-memory blacklist, user-level invalidation, account lockout (5/15min), force-logout endpoint. 13 tests. PR #7 merged. |
| Email tools + tabular loader + chart tool | 2026-03-08 | `prepare_outlook_draft`, `classify_uploaded_emails`, `tabular_loader.py`, `chart_uploaded_table`, XLSB support, per-extension upload limits, frontend UX. 245 tests. PR #8 merged. |
| auth_runtime.py -- blacklist/lockout persistidos | 2026-03-08 | Token blacklist, user invalidation, lockout persistidos no Azure Table Storage. Integrado em PR #7 e seguintes. |
| token_quota.py -- quotas distribuidas persistidas | 2026-03-08 | Shards por instancia no Azure Table Storage. Integrado em PR #8 e seguintes. |
| privacy_service.py -- DSR/GDPR | 2026-03-08 | User data export/delete. Integrado em PR #8 e seguintes. |
| provider_governance.py -- layer de governanca | 2026-03-08 | Classificacao de sensibilidade por accao/modo. Integrado em PR #8 e seguintes. |
| tabular_artifacts.py -- DuckDB + Parquet | 2026-03-08 | Pipeline ~100x mais rapido. Integrado em PR #8 e seguintes. |

---

## Proximos Passos Recomendados (por prioridade) -- Actualizado 2026-03-17

### Prioridade 1 -- Quick wins (horas)
- [ ] **Rec 1 (NOVO)**: Criar staging slot no App Service
- [ ] **Rec 2 (NOVO)**: Alertas de expiracao de credenciais (Azure Monitor + CI)
- [x] **Rec 7**: Adicionar `pip audit` + `npm audit` ao CI ✅

### Prioridade 2 -- Alto impacto (dias)
- [x] **Rec 2 / W1**: Locks de concorrencia -- **CRITICO** ✅ PR #5 merged
- [x] **Rec 8 / W7**: Filtrar secrets nos logs ✅ PR #6 merged
- [ ] **Rec 4 (NOVO)**: Managed Identity para Storage (substituir SharedKeyLite)
- [ ] **Rec 7 (NOVO)**: Sliding window no rate limiter

### Prioridade 3 -- Medio impacto (dias)
- [ ] ~~**Rec 5 / W5**: Upgrade AI Search para Basic~~ ⏸️ ADIADO -- Free suficiente
- [ ] ~~**Rec 10 / O5**: Testar gpt-5.3-chat + Model Router~~ ⏸️ ADIADO -- nao certificados para dados confidenciais
- [x] **W6**: Token blacklist + account lockout ✅ PR #7 merged
- [x] **W10**: Code Interpreter hardening (PATH, CPU/mem, symlinks) ✅ PR #6 merged
- [ ] **Rec 8 (NOVO)**: defusedxml para parsing XML em storage.py

### Prioridade 4 -- Esforco significativo (semanas)
- [ ] **Rec 5 (NOVO) / W2**: Refactoring frontend (App.jsx agora 2 086 linhas)
- [ ] **O2**: Custom metrics e dashboard operacional
- [ ] **Rec 9 (NOVO)**: DPIA e ROPA formal

### Dependente da DSI
- [ ] **Rec 3 / O1**: VNet + Private Endpoints + Entra ID + Key Vault sem accesso publico

---

*Tracker actualizado em 2026-03-17 via Claude Code (auditoria linha a linha).*
*Projecto: DBDE AI Assistant v7.3.0 — Millennium BCP (uso interno)*
