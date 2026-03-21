# DBDE AI Assistant — SWOT Analysis Corrigida
## Data
2026-03-18

## Escopo
Esta SWOT foi preparada contra o estado atual do `main` local que serviu de source of truth para o trabalho documental anterior e foi depois ramificada para `codex/correct-swot-analysis`.

Fontes primarias:
- [config.py](config.py)
- [app.py](app.py)
- [agent.py](agent.py)
- [tools.py](tools.py)
- [route_deps.py](route_deps.py)
- [routes_auth.py](routes_auth.py)
- [routes_chat.py](routes_chat.py)
- [routes_admin.py](routes_admin.py)
- [auth.py](auth.py)
- [auth_runtime.py](auth_runtime.py)
- [storage.py](storage.py)
- [llm_provider.py](llm_provider.py)
- [provider_governance.py](provider_governance.py)
- [prompt_shield.py](prompt_shield.py)
- [pii_shield.py](pii_shield.py)
- [code_interpreter.py](code_interpreter.py)
- [tabular_loader.py](tabular_loader.py)
- [tabular_artifacts.py](tabular_artifacts.py)
- [document_intelligence.py](document_intelligence.py)
- [privacy_service.py](privacy_service.py)
- [generated_files.py](generated_files.py)
- [rate_limit_storage.py](rate_limit_storage.py)
- [upload_worker.py](upload_worker.py)
- [export_worker.py](export_worker.py)
- [worker_entrypoint.py](worker_entrypoint.py)
- [startup.sh](startup.sh)
- [startup_worker.sh](startup_worker.sh)
- [scripts/setup_azure_infra.sh](scripts/setup_azure_infra.sh)
- [scripts/apply_p1v3_safe_profile.sh](scripts/apply_p1v3_safe_profile.sh)
- [scripts/deploy_swap.sh](scripts/deploy_swap.sh)
- [scripts/rollback.sh](scripts/rollback.sh)
- [.github/workflows/ci.yml](.github/workflows/ci.yml)
- [frontend/src/App.jsx](frontend/src/App.jsx)
- [frontend/src/utils/markdown.js](frontend/src/utils/markdown.js)
- [frontend/src/utils/sanitize.js](frontend/src/utils/sanitize.js)
- [tests/](tests/)

Fonte secundaria, apenas para referencias Azure nao demonstraveis no codigo:
- `docs/AZURE_INFRA_HANDOFF_FOR_AUDIT_20260316.md` local e nao live-verified

## Regras de confianca desta analise
- `Repo-confirmed`: suportado diretamente por codigo, config, scripts ou testes presentes no repo.
- `Repo-confirmed + Azure intent`: suportado pelo repo e tambem por scripts/notes de infraestrutura.
- `Azure handoff only`: suportado apenas pelo handoff local; nao deve ser tratado como prova de estado live no Azure.

## Correcoes face ao draft anterior
Esta versao evita erros factuais do draft do commit `aa42a9e`:
- Nao afirma que falta um audit log dedicado. O repo tem `AuditLog` em [storage.py](storage.py) e `log_audit()` em [route_deps.py](route_deps.py).
- Nao afirma que as camadas C e D estao vazias. O repo tem [tests/camada_c_arena/test_arena_comparison.py](tests/camada_c_arena/test_arena_comparison.py) e a suite [tests/camada_d_userstory/](tests/camada_d_userstory/).
- Nao recomenda remover `xlrd` nem converter tudo para `openpyxl`. O loader em [tabular_loader.py](tabular_loader.py) preserva fallback para `.xls`.
- Nao apresenta o risco de symlink escape como se estivesse totalmente por mitigar. [code_interpreter.py](code_interpreter.py) ja tem validacao de `realpath`, checagem de symlink e restricoes de imports/calls.
- Distingue afirmacoes confirmadas no repo de afirmacoes apenas inferidas do handoff Azure.

## Snapshot objetivo do codebase
- `Repo-confirmed`: 163 ficheiros Python, 35 ficheiros de frontend source e 74 ficheiros de teste no snapshot atual.
- `Repo-confirmed`: a pasta [tests/](tests/) contem 512 funcoes de teste detetadas por AST, cobrindo backend, frontend build, infra, seguranca, RAG, arena e user stories.
- `Repo-confirmed`: a aplicacao continua a ser uma FastAPI monolitica com modulos extraidos, mas com nucleos ainda muito grandes: [app.py](app.py) com 4005 linhas, [tools.py](tools.py) com 3726, [user_story_lane.py](user_story_lane.py) com 3304, [agent.py](agent.py) com 2682 e [frontend/src/App.jsx](frontend/src/App.jsx) com 2086.
- `Repo-confirmed`: nao existe `README`, Terraform, Bicep, Dockerfile nem outra IaC declarativa no repo atual.

## Executive Summary
O DBDE AI Assistant e um produto tecnicamente forte e com bastante profundidade funcional. O repo mostra uma plataforma real, nao um prototipo: multi-provider LLM, SSE streaming, uploads com pipeline assincrono, exports ricos, code interpreter sandboxed, persistence write-through, privacy export/delete, story lane especializada, integracoes DevOps/Search/Figma/Miro e uma suite de testes grande e segmentada.

Ao mesmo tempo, a plataforma paga um custo claro de complexidade: o core continua muito concentrado em poucos ficheiros grandes, a governance de providers externos ainda e sobretudo advisory, a postura infra depende de segredos raw e scripts shell mais do que de IaC declarativa, e continuam a existir superficies publicas de introspecao (`/docs`, `/redoc`, `/openapi.json`, `/api/info`) que simplificam reconnaissance. A principal conclusao nao e "o sistema esta fraco"; e "o sistema ja tem maturidade funcional suficiente para justificar um programa serio de simplificacao arquitetural e hardening operacional".

## Strengths
### 1. Amplitude funcional acima da media para um unico repo
- `Repo-confirmed`: a aplicacao agrega chat multi-modelo, SSE streaming, uploads, export de ficheiros, voice prompt normalization, privacy operations, user story lane, pesquisa semantica e tooling de design/devops no mesmo produto, visivel em [app.py](app.py), [agent.py](agent.py), [tools.py](tools.py), [routes_auth.py](routes_auth.py) e [routes_admin.py](routes_admin.py).
- `Repo-confirmed`: o frontend expõe essas capacidades de forma coerente em [frontend/src/App.jsx](frontend/src/App.jsx), [frontend/src/components/UserStoryWorkspace.jsx](frontend/src/components/UserStoryWorkspace.jsx), [frontend/src/components/UserStoryEvalPanel.jsx](frontend/src/components/UserStoryEvalPanel.jsx) e [frontend/src/hooks/useSpeechPrompt.js](frontend/src/hooks/useSpeechPrompt.js).

### 2. Boa profundidade de testes e avaliacoes
- `Repo-confirmed`: existe CI para backend e frontend em [.github/workflows/ci.yml](.github/workflows/ci.yml), incluindo Python 3.11/3.12, `pytest`, build Vite e auditorias de dependencias.
- `Repo-confirmed`: a suite de testes nao se limita a unit tests tradicionais; inclui camadas A-D em [tests/camada_a_rag/](tests/camada_a_rag/), [tests/camada_b_tools/](tests/camada_b_tools/), [tests/camada_c_arena/](tests/camada_c_arena/) e [tests/camada_d_userstory/](tests/camada_d_userstory/).
- `Repo-confirmed`: o runner de avaliacoes em [tests/runners/run_eval.py](tests/runners/run_eval.py) formaliza thresholds por camada definidos em [tests/eval_config.py](tests/eval_config.py), o que da ao produto uma base melhor para regressao controlada do que muitos repositórios aplicacionais.

### 3. Controlo de seguranca acima do basico
- `Repo-confirmed`: autenticacao e sessao usam JWT com cookie `HttpOnly`, `Secure` quando HTTPS e `SameSite=lax`, definidos em [routes_auth.py](routes_auth.py) e [config.py](config.py).
- `Repo-confirmed`: revogacoes, lockouts e invalidacao de tokens sobrevivem a recycle/deploy por persistirem em [auth_runtime.py](auth_runtime.py) na tabela `AuthState`.
- `Repo-confirmed`: o middleware em [app.py](app.py) aplica security headers, controlo de origins, limite de tamanho de request e rate limiting.
- `Repo-confirmed`: o rate limiter em [rate_limit_storage.py](rate_limit_storage.py) e fail-closed quando nao consegue ler o backend de storage.
- `Repo-confirmed`: o code interpreter em [code_interpreter.py](code_interpreter.py) restringe imports, calls, `PATH`, memoria, CPU, symlinks e acesso absoluto ao filesystem, com testes especificos em [tests/test_security_hardening.py](tests/test_security_hardening.py).

### 4. Persistencia e resiliência operacionais bem pensadas
- `Repo-confirmed`: o sistema usa write-through de conversas com dirty tracking, pre-evict persist e shutdown flush em [agent.py](agent.py), validado por [tests/test_writethrough.py](tests/test_writethrough.py).
- `Repo-confirmed`: existem jobs assincros para uploads e exports com stores persistentes, workers dedicados e health checks profundos, em [app.py](app.py), [upload_worker.py](upload_worker.py), [export_worker.py](export_worker.py), [startup.sh](startup.sh), [startup_worker.sh](startup_worker.sh) e [worker_entrypoint.py](worker_entrypoint.py).
- `Repo-confirmed`: o deep health em [routes_admin.py](routes_admin.py) verifica storage, LLM, search, rerank e workers, o que e util para operacao real.

### 5. Pipeline de ficheiros tabulares particularmente forte
- `Repo-confirmed`: os limites de upload por tipo, ingest profundo, concorrencia, retenção e thresholds assincros estao centralizados em [config.py](config.py) e aplicados em [app.py](app.py).
- `Repo-confirmed`: o pipeline preserva suporte a `.csv`, `.tsv`, `.xlsx`, `.xlsb` e `.xls`, com fallback explicito para casos edge `.xls` em [tabular_loader.py](tabular_loader.py).
- `Repo-confirmed`: artefactos tabulares sao materializados em Parquet/DuckDB em [tabular_artifacts.py](tabular_artifacts.py), o que melhora performance para profiling, metricas, series temporais e comparacoes.
- `Repo-confirmed`: a plataforma tambem tem retenção ativa de blobs e sweep de artefactos em [app.py](app.py) e [generated_files.py](generated_files.py), com validacao em [tests/test_upload_retention.py](tests/test_upload_retention.py).

### 6. Governação e privacidade ja fazem parte do desenho
- `Repo-confirmed`: existe `AuditLog` dedicado via [route_deps.py](route_deps.py) + [storage.py](storage.py), o que torna incorreta qualquer leitura que diga que nao ha trilho dedicado.
- `Repo-confirmed`: ha export e delete de dados pessoais em [privacy_service.py](privacy_service.py) e [routes_chat.py](routes_chat.py), cobrindo chats, uploads, drafts, feedback e referencias globais, com testes em [tests/test_privacy_service.py](tests/test_privacy_service.py).
- `Repo-confirmed`: o sistema mantem quotas por tier em [token_quota.py](token_quota.py), integradas no loop do agente em [agent.py](agent.py).

### 7. Integracoes ricas e pragmaticas
- `Repo-confirmed`: o produto integra Azure OpenAI, Anthropic/Foundry, Azure AI Search, rerank, DevOps, Brave web search, Figma, Miro, Document Intelligence, Speech, PII e Content Safety, conforme [config.py](config.py), [llm_provider.py](llm_provider.py), [tools_knowledge.py](tools_knowledge.py), [tools_figma.py](tools_figma.py), [tools_miro.py](tools_miro.py), [document_intelligence.py](document_intelligence.py) e [speech_prompt.py](speech_prompt.py).
- `Repo-confirmed`: esta amplitude cria real utilidade de negocio porque a app nao responde so com texto; consegue pesquisar, transformar, gerar artefactos e operar workflows.

### 8. Maturidade operacional melhor do que o normal para um app monolitico
- `Repo-confirmed + Azure intent`: o repo inclui scripts de setup e perfil App Service P1v3 com Key Vault, alertas e autoscale em [scripts/setup_azure_infra.sh](scripts/setup_azure_infra.sh) e [scripts/apply_p1v3_safe_profile.sh](scripts/apply_p1v3_safe_profile.sh).
- `Repo-confirmed`: o deploy tem scripts claros para swap e rollback por slot em [scripts/deploy_swap.sh](scripts/deploy_swap.sh) e [scripts/rollback.sh](scripts/rollback.sh), e esses scripts falham explicitamente quando o slot nao existe em vez de mascararem o risco.

## Weaknesses
### 1. Complexidade estrutural ainda demasiado concentrada
- `Repo-confirmed`: os ficheiros [app.py](app.py), [tools.py](tools.py), [user_story_lane.py](user_story_lane.py), [agent.py](agent.py), [frontend/src/App.jsx](frontend/src/App.jsx) e [frontend/src/styles/index.css](frontend/src/styles/index.css) continuam muito grandes, o que aumenta custo de onboarding, review e regressao.
- `Repo-confirmed`: a modularizacao A2 melhorou a situacao, mas a aplicacao ainda esta longe de uma arquitetura de servicos/coordenadores claramente separados.

### 2. Coupling entre web app e workers continua alto
- `Repo-confirmed`: [upload_worker.py](upload_worker.py) importa `process_upload_jobs_once` diretamente de [app.py](app.py) e [export_worker.py](export_worker.py) importa `process_export_jobs_once` do mesmo modulo.
- `Repo-confirmed`: isto reduz isolamento de runtime e significa que alteracoes no monolito web podem afetar workers assincros sem fronteiras claras de ownership.

### 3. Infra como codigo continua incompleta
- `Repo-confirmed`: o repo tem scripts shell e `.azure/config`, mas nao tem Terraform, Bicep, ARM, Helm, Dockerfile ou documentacao de bootstrap equivalente.
- `Repo-confirmed`: isso obriga a confiar em scripts imperativos e em conhecimento operacional difuso, em vez de estado declarativo versionado.

### 4. Governance de providers externos ainda nao e enforcement real
- `Repo-confirmed`: [provider_governance.py](provider_governance.py) calcula classificacao e metadados, mas nao impõe bloqueio.
- `Repo-confirmed`: [config.py](config.py) define `PROVIDER_GOVERNANCE_MODE=advisory` por omissao e `PROVIDER_GOVERNANCE_EXPERIMENTAL_ALLOW_EXTERNAL=true`.
- `Repo-confirmed`: [speech_prompt.py](speech_prompt.py) e o resto da stack tratam governance como metadata/audit, nao como policy engine hard-stop.

### 5. Alguns controlos de seguranca sao fail-open
- `Repo-confirmed`: [prompt_shield.py](prompt_shield.py) assume fail-open quando Azure Content Safety falha.
- `Repo-confirmed`: [pii_shield.py](pii_shield.py) preserva uma mascara regex local util, mas se a chamada Azure falhar o comportamento nao e equivalente a um bloqueio hard.
- `Repo-confirmed`: isto pode ser um tradeoff aceitavel para UX, mas do ponto de vista de risco continua a ser uma fraqueza e deve ser descrito como tal.

### 6. Existe superficie publica de introspecao maior do que a desejavel
- `Repo-confirmed`: [route_deps.py](route_deps.py) mantem `/health`, `/api/info`, `/api/client-error`, `/docs`, `/openapi.json` e `/redoc` como auth-exempt.
- `Repo-confirmed`: [routes_admin.py](routes_admin.py) faz com que `/api/info` exponha versao, limites e sinais de features.
- `Repo-confirmed`: isto nao e uma vulnerabilidade por si so, mas ajuda reconnaissance e expõe shape operacional desnecessariamente.

### 7. Postura de segredos e storage continua dependente de chaves
- `Repo-confirmed`: [storage.py](storage.py) usa SharedKeyLite e SharedKey para Azure Table/Blob.
- `Repo-confirmed`: [config.py](config.py) continua a esperar `STORAGE_KEY`, `SEARCH_KEY`, `AZURE_OPENAI_KEY`, `CONTENT_SAFETY_KEY`, `PII_API_KEY`, `DOC_INTEL_KEY`, `DEVOPS_PAT` e afins como app settings.
- `Repo-confirmed + Azure intent`: o handoff e os scripts falam em Key Vault, mas o repo nao mostra Managed Identity como caminho primario de auth runtime.

### 8. Modelo de dados e evolucao de schema estao implicitos no codigo
- `Repo-confirmed`: [storage.py](storage.py) cria tabelas programaticamente via `ensure_tables_exist()`, sem migracoes versionadas nem contrato formal de schema.
- `Repo-confirmed`: isto simplifica arranque inicial, mas aumenta risco de drift de entidades, campos opcionais proliferarem e comportamento historico ficar implícito no codigo.

### 9. A disciplina de qualidade automatizada ainda pode crescer bastante
- `Repo-confirmed`: [requirements-dev.txt](requirements-dev.txt) tem essencialmente `pytest` e `pytest-asyncio`.
- `Repo-confirmed`: [.github/workflows/ci.yml](.github/workflows/ci.yml) nao mostra linting Python, type-checking, ESLint, cobertura minima, contract tests nem secret scanning formal.
- `Repo-confirmed`: o projeto tem muitos testes, mas ainda sem algumas guardrails de engenharia que reduziriam regressao silenciosa.

### 10. Incerteza operacional real entre repo e Azure live
- `Repo-confirmed + Azure intent`: o repo mostra intencao clara de worker app, autoscale, Key Vault, alerts e slot deploy.
- `Azure handoff only`: o proprio handoff local diz explicitamente que o estado Azure nao foi live-verified na captura.
- Consequencia: algumas conclusoes infra devem ser lidas como "intencao/procedimento conhecido", nao como "estado confirmado hoje no tenant".

### 11. Onboarding e transmissao de contexto continuam fracos
- `Repo-confirmed`: a ausencia de `README` e de um mapa arquitetural curto obriga a reconstruir mentalmente a plataforma a partir de [app.py](app.py), [config.py](config.py), [tools.py](tools.py) e [tests/](tests/).
- `Repo-confirmed`: isto torna a qualidade do trabalho muito dependente de engenheiros que ja conhecem o sistema.

## Opportunities
### 1. Fechar o ciclo da modularizacao
- Extrair orquestracao de uploads, exports, retention, story lane e admin checks de [app.py](app.py) para services dedicados.
- Extrair fluxos de tool execution e prompt assembly de [agent.py](agent.py) e [tools.py](tools.py) para camadas menores com ownership mais claro.
- Partir [frontend/src/App.jsx](frontend/src/App.jsx) em modulos por dominio: chat, uploads, exports, speech, admin insight e story lane.

### 2. Transformar governance de providers em policy real
- Promover [provider_governance.py](provider_governance.py) de advisory para enforced mode, pelo menos para `speech_prompt`, `chat_file`, user story lane e queries com uploads.
- Criar uma policy simples: dados elevados ficam em Azure-only salvo override admin auditado.

### 3. Reduzir dependencia de secrets raw
- Trocar autenticacao por chaves onde possivel por Managed Identity e Key Vault references.
- Priorizar Storage, Search e, se suportado pela stack alvo, Azure OpenAI.

### 4. Formalizar a infraestrutura
- Materializar o estado Azure em IaC declarativa.
- Versionar App Service, worker app, autoscale, alerts, Key Vault bindings, slots e possivel networking privado.
- Eliminar a dependencia de "conhecimento oral" ou handoffs locais nao tracked.

### 5. Endurecer superficies publicas
- Fechar `/docs`, `/redoc`, `/openapi.json` e talvez reduzir o payload de `/api/info` para metadata estritamente necessaria ao frontend.
- Diferenciar explicitamente um `public info` minimal de um `diagnostic info` autenticado.

### 6. Subir o patamar de qualidade automatizada
- Adicionar `ruff` ou equivalente para Python, `eslint` para frontend, type-checking gradual e gate de cobertura minima.
- Acrescentar checks para bundle size e smoke tests de frontend mais proximos da UX real.

### 7. Tirar mais partido do suite de eval existente
- Integrar [tests/runners/run_eval.py](tests/runners/run_eval.py) em CI agendada ou em pipelines de release.
- Guardar historico de scores por camada para detetar queda de qualidade de RAG, Arena e User Story lane.

### 8. Fortalecer observabilidade de negocio e operacao
- Ligar o `AuditLog`, os token quotas, os tool metrics e o health profundo a dashboards persistentes.
- Separar melhor metricas de negocio, segurança e operacao.

### 9. Productizar a story lane como vantagem competitiva
- O conjunto [user_story_lane.py](user_story_lane.py), [story_curated_corpus.py](story_curated_corpus.py), [story_devops_index.py](story_devops_index.py), [story_knowledge_index.py](story_knowledge_index.py) e os componentes frontend de user stories ja mostram um produto especializado.
- A oportunidade e passar de "feature rica" para "sistema governado de geracao, validacao, curation e aprendizagem".

### 10. Melhorar onboarding e transmissao de contexto
- Criar um `README` curto com arquitetura, runtime, dependencias externas, principais comandos e mapa dos modulos.
- Criar um diagrama de componentes simples para novos maintainers.

## Threats
### 1. Risco de governance e residencia de dados por multi-provider
- `Repo-confirmed`: a stack multi-provider e uma forca de resiliencia, mas tambem aumenta superficie regulatoria.
- `Repo-confirmed`: se Anthropic/Foundry estiver ativo, dados podem sair do escopo Azure-preferred em alguns fluxos porque a governance atual e advisory.

### 2. Drift entre repo e ambiente Azure real
- `Repo-confirmed + Azure intent`: os scripts e docs descrevem uma topologia App Service + worker + autoscale + Key Vault.
- `Azure handoff only`: nao ha prova live no repo de que todas essas configuracoes continuam ativas exatamente assim hoje.
- Impacto: auditorias, incidentes e troubleshooting podem partir de premissas erradas se a equipa assumir que "o repo descreve exatamente o live".

### 3. Dependencia de servicos externos para fluxos criticos
- `Repo-confirmed`: Azure OpenAI, Search, Storage, DevOps, Content Safety, PII, Speech, rerank, Brave, Figma e Miro podem afetar UX ou resultados quando degradam.
- `Repo-confirmed`: o sistema tem fallbacks em varias areas, mas essa diversidade tambem multiplica pontos de falha e contratos externos.

### 4. Reconnaissance facilitada por endpoints publicos
- `Repo-confirmed`: `/docs`, `/openapi.json`, `/redoc`, `/health` e `/api/info` expõem shape, metadata e capacidade do sistema a qualquer cliente que alcance o host.
- Mesmo que a autenticacao esteja correta, isto reduz obscuridade operacional e simplifica enumeracao de superficie.

### 5. Escalabilidade e regressao ficam mais dificeis com o tamanho atual
- `Repo-confirmed`: ficheiros muito grandes e dependencias cruzadas tornam cada alteracao potencialmente transversal.
- Risco pratico: maior tempo de review, mais regressao acidental e maior dependencia de conhecimento tribal.

### 6. Worker e web podem falhar em conjunto por acoplamento excessivo
- `Repo-confirmed`: como os workers importam logica de [app.py](app.py), uma mudanca aparentemente "web only" pode introduzir regressao no runtime assincro.
- Isto e um threat operacional importante porque uploads e exports sao features de valor elevado para o produto.

### 7. Postura de credenciais baseada em chaves aumenta burden operacional
- `Repo-confirmed`: chaves de storage, search, AI e PATs continuam centrais.
- Threat: rotacao manual, erros de configuracao e maior blast radius em caso de fuga de segredos.

### 8. Rollback pode ser mais fraco quando nao existe slot
- `Repo-confirmed`: [scripts/deploy_swap.sh](scripts/deploy_swap.sh) e [scripts/rollback.sh](scripts/rollback.sh) deixam claro que o slot `staging` pode nao existir.
- Consequencia: em alguns cenarios o rollback efetivo deixa de ser `swap back` e passa a depender de redeploy da versao anterior, o que e menos robusto sob stress.

### 9. Bootstrap e estado administrativo merecem mais formalizacao
- `Repo-confirmed`: [storage.py](storage.py) cria user admin bootstrap se nao existir.
- Isto e funcional, mas sem runbooks fortes e controlos claros de secret bootstrap pode tornar administracao inicial mais opaca do que o desejavel.

## Conclusao estrategica
O retrato correto do repo nao e "um sistema fraco" nem "um sistema desgovernado". O retrato correto e: um produto já funcionalmente maduro, com muita engenharia util e um grau real de pensamento em seguranca, operacao e testes, mas que entrou numa fase em que a principal alavanca de melhoria deixou de ser adicionar features e passou a ser reduzir complexidade, endurecer governance e formalizar a infraestrutura.

Se eu tivesse de sintetizar a SWOT em tres frases:
- O maior `Strength` e a combinacao rara de profundidade funcional com cobertura de testes e controlos operacionais reais.
- O maior `Weakness` e a concentracao excessiva de logica e responsabilidade em poucos modulos nucleares e em policies ainda soft.
- A maior `Opportunity` e transformar o que hoje ja existe em arquitetura mais governada, observavel e auditavel sem perder a velocidade funcional.

## Prioridades recomendadas
### Prioridade 1
- Enforcement real de provider governance para dados elevados.
- Fecho de `/docs`, `/redoc`, `/openapi.json` e endurecimento de `/api/info`.
- Plano de extracao de servicos de upload/export/job orchestration para fora de [app.py](app.py).

### Prioridade 2
- IaC declarativa para App Service, worker app, autoscale, alerts e secrets binding.
- Migracao progressiva de auth por chaves para Managed Identity/Key Vault references onde aplicavel.
- Introducao de linting, typing e gates de cobertura.

### Prioridade 3
- Refactor do frontend central e decomposicao de [frontend/src/App.jsx](frontend/src/App.jsx).
- Evolucao da user story lane para produto governado com feedback loop medido.
- README e mapa arquitetural curto para reduzir dependencia de contexto tribal.
