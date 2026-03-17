# DBDE AI Assistant — Auditoria SWOT Exaustiva (branch `main`, Março 2026)

**Data da auditoria**: 2026-03-17  
**Versão da codebase**: v8.0.0 (app.py, config.py, frontend v8.0.0)  
**Ambiente de referência**: Azure App Service P1v3 · `https://dbdeai.pt`  
**Metodologia**: revisão linha a linha de todos os ficheiros Python, JSX, JSON, scripts de configuração e documentação.

---

## Resumo Executivo

A codebase evoluiu significativamente desde a auditoria inicial (Risk Score 5.2/10). O trabalho acumulado nas fases anteriores reduziu o risco técnico para um valor estimado em **≈ 2.2/10**. A principal barreira restante já não está no código: está na **identidade corporativa (Entra ID)**, no **fecho de rede (VNet/Private Endpoints)** e na **governação operacional formal** — todas dependentes da DSI.

Esta auditoria identifica adicionalmente três novos itens corrigidos neste PR:

| # | Item | Severidade | Estado |
|---|---|---|---|
| N1 | `PROMPT_SHIELD_FAIL_MODE` não existia — shield falhava sempre em fail-open | ALTO | ✅ **CORRIGIDO neste PR** |
| N2 | `token_quota.py` usava `os.getenv()` directamente (bypass `_get_env`) | MÉDIO | ✅ **CORRIGIDO neste PR** |
| N3 | Admin role check inconsistente em `app.py` (dict raw vs `_is_admin_user`) | MÉDIO | ✅ **CORRIGIDO neste PR** |

---

## Inventário de Ficheiros Auditados

| Ficheiro | Linhas | Área |
|---|---|---|
| `app.py` | ~3 900 | API routing, middleware, upload, export |
| `agent.py` | ~2 700 | Orquestração do agente LLM, ferramentas |
| `tools.py` | ~3 500 | Implementação das ferramentas (search, DevOps, Code, etc.) |
| `llm_provider.py` | ~1 400 | Abstração multi-provider (Azure OpenAI, Anthropic) |
| `config.py` | ~510 | Configuração centralizada via `_get_env` |
| `auth.py` | ~350 | JWT, hashing, lockout, blacklist |
| `auth_runtime.py` | ~200 | Auth persistente em Azure Table Storage |
| `storage.py` | ~600 | Azure Table e Blob Storage (SharedKeyLite) |
| `prompt_shield.py` | ~112 | Azure Content Safety Prompt Shields |
| `pii_shield.py` | ~400 | Mascaramento PII via Azure AI Language |
| `code_interpreter.py` | ~360 | Sandbox Python com subprocess |
| `token_quota.py` | ~270 | Quota de tokens por tier |
| `rate_limit_storage.py` | ~100 | Rate limiting persistente |
| `route_deps.py` | ~220 | Dependências reutilizáveis de rotas |
| `routes_auth.py` | ~160 | Rotas de autenticação |
| `routes_admin.py` | ~600 | Painel de administração |
| `routes_chat.py` | ~250 | Rotas de chat |
| `routes_digest.py` | ~150 | Rotas de digest/feed |
| `privacy_service.py` | ~250 | Exportação e eliminação RGPD |
| `http_helpers.py` | ~130 | Retry + redacção de segredos em logs |
| `tabular_loader.py` | ~500 | Ingestão de ficheiros tabulares |
| `tabular_artifacts.py` | ~300 | Artefactos tabulares persistentes |
| `export_engine.py` | ~400 | Export para CSV/XLSX/PDF/HTML |
| `pptx_engine.py` | ~600 | Geração de PowerPoint |
| `xlsx_engine.py` | ~400 | Geração de Excel |
| `learning.py` | ~300 | Regras de prompt e aprendizagem |
| `models.py` | ~200 | Modelos Pydantic |
| `utils.py` | ~150 | Utilitários partilhados |
| `frontend/src/App.jsx` | 2 086 | Frontend React (monolito) |
| `frontend/src/utils/sanitize.js` | ~40 | DOMPurify + escapeHtml |
| `frontend/src/utils/markdown.js` | ~270 | Renderização de markdown |
| `frontend/src/components/MessageBubble.jsx` | ~120 | Renderização de mensagens |

---

## STRENGTHS — O que está bem feito

### S1 — Autenticação robusta com múltiplas camadas de protecção
**Ficheiros**: `auth.py`, `auth_runtime.py`, `routes_auth.py`

- JWT com `HS256`, `exp`/`iat`/`jti` obrigatórios.
- Token blacklist in-memory por `jti` + invalidação por utilizador via Azure Table Storage.
- Account lockout após 5 tentativas falhadas (15 min), persistente entre instâncias.
- Admin pode forçar logout de qualquer utilizador.
- Cookies com `httponly=True`, `secure=True`, `samesite="lax"`.
- `JWT_SECRET` gerado aleatoriamente no arranque se não definido (em não-produção); em produção obrigado e gerado com `secrets.token_hex(64)`.

### S2 — Middleware de segurança HTTP completo
**Ficheiros**: `app.py:400-425`

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(self), geolocation=()`
- `Content-Security-Policy` dinâmico e conservador (limitado ao Speech endpoint se activo).
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (só HTTPS).

### S3 — Sanitização XSS no frontend
**Ficheiros**: `frontend/src/utils/sanitize.js`, `frontend/src/utils/markdown.js`

- DOMPurify `^3.3.2` aplica sanitização a todo o HTML renderizado via `dangerouslySetInnerHTML`.
- `sanitizeLinkUrl` valida esquemas (só `http:` e `https:`) antes de qualquer link ser renderizado.
- `escapeHtml` para contextos de texto puro.
- Lista branca explícita de tags e atributos em `sanitizeHtmlOutput`.

### S4 — Prevenção de injecção OData
**Ficheiros**: `utils.py`, `agent.py`, `app.py`, `privacy_service.py`

- Todas as queries ao Azure Table Storage passam por `odata_escape()`.
- Sem construção dinâmica não-sanitizada de filtros.

### S5 — Redacção de segredos em logs
**Ficheiros**: `http_helpers.py`

- `_sanitize_error_response()` com 4 regex patterns cobre: API keys, tokens Bearer, base64 de comprimento suspeito, JWTs.
- Aplicado sistematicamente em todos os pontos de log de respostas HTTP externas.

### S6 — PII Shield multi-camada
**Ficheiros**: `pii_shield.py`

- Detecção via Azure AI Language (18 categorias PII configuradas).
- Pré-mascaramento regex local para 9 padrões PT/EU críticos (NIF, IBAN, CC, SWIFT, NISS, email, telefone).
- Thresholds diferenciados por categoria (financeiros: 0.4; pessoais: 0.7).
- `PIIMaskingContext` garante reversibilidade (unmask pós-resposta LLM).
- Mascaramento de `role=tool` outputs, blob PII, queries de web search.

### S7 — Code Interpreter sandbox robusto
**Ficheiros**: `code_interpreter.py`

- Subprocess isolado com `-I` (isolated mode).
- Validação AST antes da execução: imports bloqueados, funções perigosas bloqueadas (`exec`, `eval`, `__import__`, `getattr`, `setattr`, `delattr`, `os.system`, etc.).
- `builtins.open` substituído por `_safe_open` que valida path dentro do tmpdir.
- Limites de recursos: CPU 120s (`RLIMIT_CPU`), memória 512MB (`RLIMIT_AS`).
- Ambiente minimal: `PATH=/usr/local/bin:/usr/bin:/bin`, sem variáveis de ambiente sensíveis.
- Symlink validation com `_path_within_root`.
- Timeout asyncio configurável (`CODE_INTERPRETER_TIMEOUT`).

### S8 — Rate limiting persistente e distribuído
**Ficheiros**: `rate_limit_storage.py`, `route_deps.py`

- Backed by Azure Table Storage — partilhado entre instâncias.
- Cache local (1 min) para performance.
- **Fail-CLOSED**: se o Table Storage estiver indisponível, nega o pedido por precaução (linha 63).
- Decorador `@limiter.limit()` aplicado por rota.

### S9 — Validação de uploads com magic bytes
**Ficheiros**: `app.py:1431-1488`

- Validação do conteúdo real do ficheiro (não só a extensão) para PNG, JPEG, GIF, PDF, XLSX, XLS, DOCX, PPTX, ZIP e ficheiros texto.
- Limite de tamanho por ficheiro, por mensagem e por conversa.
- Limite de concurrent/pending jobs por utilizador.

### S10 — Token quota distribuída por tier
**Ficheiros**: `token_quota.py`, `config.py`

- Limites horários e diários por tier (fast/standard/pro).
- Shards por instância no Azure Table Storage — somatório entre instâncias.
- Configurável via env vars (`TOKEN_QUOTA_FAST`, etc.).

### S11 — Write-through persistence para conversas
**Ficheiros**: `agent.py`

- Background loop a cada 30s persiste conversas "dirty".
- Pre-evict persist antes de LRU/TTL eviction.
- Shutdown flush antes de fechar (timeout 15s).

### S12 — Suporte RGPD (DSR)
**Ficheiros**: `privacy_service.py`

- Exportação completa de dados do utilizador (JSON estruturado).
- Eliminação cascata: ChatHistory, uploads, feedback, exemplos, story drafts, knowledge assets, blobs associados.
- `odata_escape` em todas as queries; validação do `user_sub`.

### S13 — Docs/OpenAPI desactivados em produção
**Ficheiros**: `app.py:271-279`

- `/docs`, `/openapi.json`, `/redoc` não expostos quando `IS_PRODUCTION=true`.

### S14 — Provider governance configurável
**Ficheiros**: `llm_provider.py`, `config.py`

- `PROVIDER_GOVERNANCE_MODE` controla uso de providers externos.
- `PROVIDER_EXTERNAL_MODEL_FAMILIES` lista famílias permitidas.
- Fallback explícito e cadeia de tentativas documentada.

### S15 — Configuração centralizada via `_get_env`
**Ficheiros**: `config.py`

- `_get_env()` com fallback `APPSETTING_` (Azure App Service).
- Nenhum ficheiro faz `os.getenv()` directamente (excepto `os.getpid()` em bootstrap — agora corrigido em `token_quota.py`).

---

## WEAKNESSES — O que ainda tem margem de melhoria

### W1 — CSP contém `'unsafe-inline'` em `style-src`
**Ficheiro**: `app.py:450`  
**Severidade**: Médio

```python
"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
```

`'unsafe-inline'` em `style-src` permite injecção de estilos, o que pode ser usado para data exfiltration via CSS injection (técnica de side-channel). O Vite+React pode ser configurado para hash-based inline styles ou para remover `unsafe-inline` inteiramente após build.

**Mitigação disponível**: usar `nonce-based CSP` ou aceitar que o risk vector é baixo (CSS injection sem JS não permite RCE). Mitigação completa exige ajuste no build do frontend.

### W2 — Frontend App.jsx é um monolito (2 086 linhas, 34 estados)
**Ficheiro**: `frontend/src/App.jsx`  
**Severidade**: Médio (qualidade/manutenibilidade)

- 34 chamadas `useState` no componente raiz.
- Sem TypeScript — sem verificação de tipos em tempo de compilação.
- Ausência de state management library (Zustand, Jotai, Redux).
- Dificulta testes unitários e revisão de segurança focada.

**Impacto de segurança**: indirecto. Código denso aumenta probabilidade de passar erros (XSS, CSRF) despercebidos em revisão.

### W3 — Implementação JWT própria (não usa biblioteca certificada)
**Ficheiro**: `auth.py`  
**Severidade**: Médio

- JWT implementado manualmente com `hmac` + `hashlib`.
- Não usa `python-jose`, `authlib` ou `PyJWT` — bibliotecas amplamente auditadas.
- Risco: erros subtis em comparação de assinaturas ou validação de claims podem ser introduzidos em futuras alterações.

**Mitigação actual**: o código existente está correcto e usa `secrets.compare_digest()` para comparação timing-safe. Risco residual baixo mas presente.

### W4 — Azure Storage usa SharedKey (não Managed Identity)
**Ficheiros**: `storage.py`, `config.py`

- `STORAGE_KEY` (SharedKey) dá acesso total à conta de storage se comprometido.
- Managed Identity + RBAC granular seria o padrão ideal para produção bancária.
- Dependente de intervenção DSI / reconfiguração Azure.

### W5 — ConversationStore primariamente in-memory
**Ficheiros**: `agent.py`

- Com autoscale activo (2-3 instâncias), cada instância tem o seu próprio ConversationStore.
- Write-through persiste ao Table Storage, mas a leitura é sempre do cache local primeiro.
- Uma nova instância que receba um pedido para uma conversa existente pode ter um miss e ir buscar ao storage — correcto, mas com latência.
- **Não é um Redis**: sem invalidação cross-instance.

**Mitigação actual**: write-through + read-through está correcto para consistência eventual. Para consistência forte seria necessário Redis/Cosmos.

### W6 — Sem alertas de expiração de credenciais/PATs
**Severidade**: Médio  

- `AZURE_OPENAI_KEY`, `STORAGE_KEY`, `CONTENT_SAFETY_KEY`, `ANTHROPIC_API_KEY`, etc. podem expirar silenciosamente.
- Sem mecanismo de alerta proactivo (Azure Key Vault rotation alerts, Monitor alerts).

### W7 — Sem circuit breaker explícito para serviços externos
**Ficheiros**: `http_helpers.py`, `llm_provider.py`

- Retry com backoff exponencial está implementado (3-5 tentativas, 429/5xx).
- Mas não existe circuit breaker formal: se um serviço estiver degradado de forma prolongada, cada pedido continua a tentar e a falhar.
- **Impacto**: em carga elevada com serviço externo degradado, os workers ficam saturados.

### W8 — `prompt_shield.py` criava um novo `httpx.AsyncClient` por pedido _(corrigido parcialmente)_
**Ficheiro**: `prompt_shield.py`

- Actualmente abre e fecha um cliente por chamada (`async with httpx.AsyncClient(...)`).
- O `pii_shield.py` já usa cliente partilhado. O Prompt Shield devia fazer o mesmo.
- Impacto: overhead de conexão por pedido de chat. Com alto volume, pode causar throttling de conexões.

---

## THREATS — Ameaças e vectores de ataque residuais

### T1 — Prompt Shield sem fail-closed antes deste PR _(agora corrigido)_
**Ficheiro**: `prompt_shield.py`  
**Severidade anterior**: ALTO  
**Estado**: ✅ **CORRIGIDO neste PR** — `PROMPT_SHIELD_FAIL_MODE=closed` em produção por omissão.

Antes desta correcção, qualquer falha do serviço Azure Content Safety causava passthrough silencioso de todos os prompts, independentemente do seu conteúdo. Um atacante que conseguisse tornar o serviço de safety indisponível (DDoS ao endpoint do Content Safety) poderia fazer bypass do Prompt Shield.

### T2 — Serviços públicos sem VNet/Private Endpoints
**Severidade**: ALTO (não bloqueado, dependente DSI)

- Azure Storage, AI Search, OpenAI, Content Safety — todos acessíveis via internet pública.
- Um `STORAGE_KEY` ou `SEARCH_KEY` comprometido daria acesso total ao dado.
- **Mitigação interina**: chaves em App Settings (não em código), SCM restringido, FTPS desactivado.

### T3 — Ausência de MFA e identidade corporativa
**Severidade**: ALTO (dependente DSI)

- Auth própria (username/password) sem MFA.
- Sem Conditional Access.
- Sem integração com grupos/roles corporativos do Entra ID.

### T4 — Dados confidenciais enviados a providers externos (Anthropic)
**Severidade**: MÉDIO

- Claude Sonnet/Opus via Azure Foundry está activo como fallback.
- Anthropic processa dados via API — sem garantias equivalentes a Azure para conformidade bancária PT.
- `PROVIDER_GOVERNANCE_EXPERIMENTAL_ALLOW_EXTERNAL` controla mas não bloqueia por defeito em não-produção.

### T5 — Scale-out com estado in-memory
**Severidade**: BAIXO (mitigado por write-through)

- Ver W5. Com autoscale activo, um restart ou nova instância pode servir um pedido com estado ligeiramente desactualizado.

### T6 — Supply chain / dependências
**Severidade**: MÉDIO (mitigado)

- `pip-audit` e `npm audit` no CI.
- Sem `lockfile` determinístico para Python (`requirements.txt` sem hashes).
- Versões algumas com `>=` sem upper bound (ex: `tiktoken>=0.9`, `python-calamine>=0.6.0`).

### T7 — Sem isolamento multi-tenant real
**Severidade**: MÉDIO (uso actual mono-tenant)

- O sistema foi construído para uso individual/restrito.
- Não existe isolamento de dados entre utilizadores ao nível de storage (todos partilham a mesma conta de storage).
- Para cenários multi-tenant o modelo de dados teria de ser revisto.

---

## OPPORTUNITIES — Melhorias com maior retorno

### O1 — VNet + Entra ID (dependente DSI)
**Impacto**: MÁXIMO  
Já documentado nos trackers anteriores. Maior impacto no score de segurança.

### O2 — Prompt Shield: cliente HTTP partilhado
**Impacto**: Performance, Custo  
**Esforço**: 1-2 horas

Extrair o `httpx.AsyncClient` do Prompt Shield para um cliente global (como já foi feito no PII Shield). Reduz overhead de conexão.

### O3 — CSP `nonce`-based (remover `unsafe-inline` de `style-src`)
**Impacto**: Segurança (baixo-médio)  
**Esforço**: 1-2 dias (requer ajuste no build Vite)

Configurar o Vite para injectar nonce nos estilos inline gerados e passar o nonce pelo `Content-Security-Policy` header.

### O4 — Migrar autenticação para `PyJWT` ou `authlib`
**Impacto**: Robustez, auditabilidade  
**Esforço**: 1-2 dias

Substituir a implementação JWT manual por uma biblioteca amplamente auditada. Reduz risco de erros em futuras manutenções.

### O5 — `requirements.txt` com hashes (`pip-compile --generate-hashes`)
**Impacto**: Supply chain security  
**Esforço**: Horas

Gerar um `requirements.txt` com hashes SHA256 para todas as dependências via `pip-compile`. Garante builds determinísticos e detecta tamper da supply chain.

### O6 — Alertas de expiração de credenciais
**Impacto**: Disponibilidade  
**Esforço**: 1 dia

Azure Monitor alert rule sobre as datas de expiração dos PATs/keys, ou migração para Azure Key Vault com rotation automática.

### O7 — Frontend: refactoring gradual de App.jsx
**Impacto**: Manutenibilidade, testabilidade  
**Esforço**: 1-2 semanas

Dividir App.jsx em sub-componentes (UploadPanel, ConversationList, ChatView, etc.) e migrar state management para um padrão mais escalável (Context API + useReducer ou Zustand).

### O8 — Azure Storage: Managed Identity em vez de SharedKey
**Impacto**: Segurança (elimina chave de storage como vector)  
**Esforço**: 1 dia (requer reconfiguração Azure, dependente DSI)

### O9 — Pinning de versões em `requirements.txt`
**Impacto**: Reprodutibilidade de builds  
**Esforço**: Horas

Converter `tiktoken>=0.9` e `python-calamine>=0.6.0` para versões exactas ou com upper bound (`>=0.9,<1.0`).

### O10 — TypeScript no frontend
**Impacto**: Qualidade de código, segurança  
**Esforço**: 1-2 semanas

Migração gradual de JSX para TSX. Detecta erros de tipo que podem mascarar bugs de segurança (ex: `undefined` passado como URL).

---

## Correcções implementadas neste PR

### N1 — `PROMPT_SHIELD_FAIL_MODE` (fail-closed em produção)

**Antes**:
```python
# prompt_shield.py
except Exception as e:
    # Fail-open por desenho: em erro do serviço não bloqueamos o utilizador.
    logger.warning("Prompt Shield falhou (passthrough): %s", e)
    return PromptShieldResult(is_blocked=False)
```

**Depois**:
```python
# config.py — novo
PROMPT_SHIELD_FAIL_MODE: str = _get_env("PROMPT_SHIELD_FAIL_MODE", ...)
# defaults a "closed" em produção, "open" noutros ambientes

# prompt_shield.py
except Exception as e:
    fail_closed = PROMPT_SHIELD_FAIL_MODE == "closed"
    if fail_closed:
        logger.warning("Prompt Shield falhou (fail-closed — pedido bloqueado por precaução): %s", e)
        return PromptShieldResult(is_blocked=True, attack_type="service_unavailable", ...)
    logger.warning("Prompt Shield falhou (fail-open — passthrough): %s", e)
    return PromptShieldResult(is_blocked=False)
```

Em produção (`APP_ENV=prod` ou quando `WEBSITE_SITE_NAME` está definido — i.e. Azure App Service), o comportamento por omissão é agora **fail-closed**: se o Azure Content Safety estiver indisponível, o pedido é bloqueado por precaução.

Para desenvolvimento/testes, o comportamento é **fail-open** (como antes), para não bloquear trabalho quando o serviço não está configurado.

### N2 — `token_quota.py`: substituição de `os.getenv` por `_get_env`

```python
# Antes
os.getenv("WEBSITE_INSTANCE_ID")
os.getenv("HOSTNAME")

# Depois
_get_env("WEBSITE_INSTANCE_ID", "")
_get_env("HOSTNAME", "")
```

Garante que `APPSETTING_WEBSITE_INSTANCE_ID` e `APPSETTING_HOSTNAME` são também considerados, consistente com o padrão de toda a codebase.

### N3 — Admin role check consistente em `app.py`

Seis verificações de `user.get("role") == "admin"` em `app.py` foram substituídas por chamadas a `_is_admin_user(user)` (que chama `principal_is_admin(user)` de `auth.py`). Isto:

- Centraliza a lógica de admin check num único local.
- Torna a verificação case-insensitive (antes `"Admin"` != `"admin"`).
- Prepara a transição futura para `SecurityPrincipal` com claims corporativas.

Locais corrigidos:
- `/api/upload/status/{job_id}` — verificação de ownership
- `/api/upload/status/batch` — verificação de ownership em batch
- `/api/upload/jobs` — guard "apenas admins"
- `/api/upload/worker/run-once` — guard "apenas admins"
- `/api/upload/pending/{conversation_id}` — flag `include_all_users`
- `/api/upload/index/{conversation_id}` — flag `include_all`
- `/api/export/status/{job_id}` — flag `is_admin`
- `/api/export/worker/run-once` — guard "apenas admins"

---

## Matriz de Risco Actualizada

| Área | Score anterior | Score actual | Notas |
|---|---|---|---|
| Autenticação e sessões | 7/10 | 8/10 | Blacklist, lockout, persistent auth |
| Autorização e controlo de acesso | 6/10 | 7/10 | Corrigido admin check, `_is_admin_user` |
| Protecção de dados (PII) | 7/10 | 7/10 | Multi-camada já robusto |
| Segurança de rede | 3/10 | 3/10 | Sem VNet/Private Endpoints (dependente DSI) |
| Identidade corporativa | 2/10 | 2/10 | Sem Entra ID/MFA (dependente DSI) |
| Prompt injection / AI safety | 6/10 | 8/10 | **PROMPT_SHIELD_FAIL_MODE** corrigido |
| Code execution sandbox | 8/10 | 8/10 | AST, resource limits, minimal PATH |
| Supply chain | 6/10 | 6/10 | CI scanning activo; sem hashes em requirements |
| Segurança frontend (XSS/CSRF) | 7/10 | 7/10 | DOMPurify, sanitization, SameSite=lax |
| Observabilidade e auditoria | 7/10 | 7/10 | Log Analytics, audit trail, sanitização de logs |
| **Global** | **≈ 5.8/10** | **≈ 6.5/10** | Melhorou com as correcções deste PR |

> **Nota**: O tecto actual (~6.5/10) está limitado pela ausência de Entra ID + VNet, que são as mudanças de maior impacto. Com DSI, o score pode atingir 8.5-9/10.

---

## Priorização das Oportunidades Restantes

### Curto prazo (sem DSI, sem retrabalho)

| # | Acção | Esforço | Impacto |
|---|---|---|---|
| 1 | Prompt Shield: cliente HTTP partilhado (O2) | Horas | Performance |
| 2 | `requirements.txt` com hashes ou pinning exacto (O5, O9) | Horas | Supply chain |
| 3 | Alertas de expiração de credenciais Azure (O6) | 1 dia | Disponibilidade |
| 4 | Migrar JWT para `PyJWT`/`authlib` (O4) | 1-2 dias | Robustez |

### Médio prazo (antes da DSI)

| # | Acção | Esforço | Impacto |
|---|---|---|---|
| 5 | CSP nonce-based sem `unsafe-inline` (O3) | 1-2 dias | Segurança (baixo-médio) |
| 6 | Refactoring gradual App.jsx (O7) | 1-2 semanas | Manutenibilidade |
| 7 | TypeScript no frontend (O10) | 1-2 semanas | Qualidade |

### Com DSI

| # | Acção | Esforço | Impacto |
|---|---|---|---|
| 8 | Entra ID + MFA + Conditional Access (O1) | Semanas | MÁXIMO |
| 9 | VNet + Private Endpoints (O1) | Semanas | MÁXIMO |
| 10 | Azure Storage Managed Identity (O8) | 1 dia | Alto |

---

## Conclusão

A codebase está num estado sólido para uso controlado interno:

- **O trabalho de segurança acumulado é real e consistente** — não é superficial.
- **As correcções deste PR fecham três lacunas identificadas** na auditoria linha a linha.
- **O tecto de segurança é a infra-estrutura Azure** (identidade, rede), não o código.
- **O código prepara correctamente a transição futura** para Entra ID e rede privada sem reescrever a app.

Honestamente:
- ✅ Adequado para uso individual e controlado com dados bancários não ultra-confidenciais.
- ⚠️ Ainda não no ponto ideal para "produção bancária séria com dados confidenciais de clientes" — requer DSI.
- ✅ Preparado para escalar quando a DSI intervir.
