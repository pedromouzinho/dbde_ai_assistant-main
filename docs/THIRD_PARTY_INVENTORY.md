# DBDE AI Assistant — Inventário de Terceiros
## Versão: 8.0.0 | Atualizado: 2026-03-17

## Fonte de verdade
Inventário revisto contra:
- `config.py`
- `llm_provider.py`
- `provider_governance.py`
- `tools_figma.py`
- `tools_miro.py`
- `tools_knowledge.py`
- `routes_auth.py`
- `app.py`

## 1. Resumo
Inventário de integrações externas, com finalidade, dados trocados, risco de PII, jurisdição e dependência operacional.

## 2. Serviços externos

### 2.1 Azure OpenAI
- Finalidade: chat LLM, tool calling, embeddings e vision.
- Dados enviados: mensagens, contexto, payload de tools e imagens quando aplicável.
- Dados recebidos: respostas, tool calls e embeddings.
- PII potencial: média/alta, conforme conteúdo do utilizador.
- Jurisdição: região configurada no recurso Azure OpenAI.
- Env vars: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `CHAT_DEPLOYMENT`, `EMBEDDING_DEPLOYMENT`, `LLM_TIER_*`, `LLM_FALLBACK`.

### 2.2 Anthropic via Azure AI Foundry ou API direta
- Finalidade: tiers `standard` e `pro` quando configurados.
- Dados enviados/recebidos: mensagens e respostas.
- PII potencial: média/alta.
- Jurisdição: depende da configuração; via Foundry usa o recurso Azure configurado, via API direta depende do serviço Anthropic.
- Env vars: `ANTHROPIC_API_KEY`, `ANTHROPIC_FOUNDRY_RESOURCE`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MESSAGES_PATH`.
- Nota: o código marca providers externos como experimentais por omissão em modo de governance `advisory`.

### 2.3 Azure AI Search
- Finalidade: pesquisa semântica/vector e RAG.
- Dados enviados: queries e embeddings.
- Dados recebidos: documentos, snippets e scores.
- PII potencial: média, dependente do índice.
- Jurisdição: região do serviço Azure AI Search.
- Env vars: `SEARCH_SERVICE`, `SEARCH_KEY`, `DEVOPS_INDEX`, `OMNI_INDEX`, `EXAMPLES_INDEX`, `STORY_*_INDEX`.

### 2.4 Azure AI Language PII
- Finalidade: deteção e mascaramento de PII antes de certos fluxos LLM.
- Dados enviados: mensagens/prompts a analisar.
- Dados recebidos: entidades e texto mascarado.
- PII potencial: alta, porque o próprio serviço processa texto potencialmente sensível.
- Jurisdição: região do recurso configurado.
- Env vars: `PII_ENDPOINT`, `PII_API_KEY`, `PII_ENABLED`.

### 2.5 Azure AI Content Safety
- Finalidade: Prompt Shield e controlo de segurança de prompts.
- Dados enviados: prompts e conteúdo sujeito a avaliação.
- Dados recebidos: decisão/classificação.
- PII potencial: média/alta.
- Jurisdição: região do recurso configurado.
- Env vars: `CONTENT_SAFETY_ENDPOINT`, `CONTENT_SAFETY_KEY`.

### 2.6 Azure AI Document Intelligence
- Finalidade: extração estruturada de documentos.
- Dados enviados: ficheiros/documentos.
- Dados recebidos: layout e conteúdo extraído.
- PII potencial: média/alta, dependendo do documento.
- Jurisdição: região do recurso configurado.
- Env vars: `DOC_INTEL_ENDPOINT`, `DOC_INTEL_KEY`, `DOC_INTEL_ENABLED`, `DOC_INTEL_MODEL`.

### 2.7 Azure Speech
- Finalidade: speech token issuance, STT/TTS e voz no chat.
- Dados enviados: pedidos de token, áudio, texto para síntese.
- Dados recebidos: token e áudio sintetizado.
- PII potencial: média/alta.
- Jurisdição: região `AZURE_SPEECH_REGION`.
- Env vars: `AZURE_SPEECH_ENABLED`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_LANGUAGE`.

### 2.8 Brave Search API
- Finalidade: pesquisa web atual.
- Dados enviados: queries de pesquisa.
- Dados recebidos: snippets e links.
- PII potencial: baixo, desde que as queries não levem dados pessoais.
- Jurisdição: serviço Brave fora do tenant Azure.
- Env vars: `WEB_SEARCH_ENABLED`, `WEB_SEARCH_API_KEY`, `WEB_SEARCH_ENDPOINT`, `WEB_SEARCH_DAILY_QUOTA_PER_USER`.

### 2.9 Brave Answers API
- Finalidade: answers/chat grounded em Brave quando ativado.
- Dados enviados: prompts e contexto de pesquisa.
- Dados recebidos: respostas do provider Brave.
- PII potencial: baixo/médio.
- Jurisdição: serviço Brave fora do tenant Azure.
- Env vars: `WEB_ANSWERS_ENABLED`, `WEB_ANSWERS_API_KEY`, `WEB_ANSWERS_ENDPOINT`, `WEB_ANSWERS_MODEL`.

### 2.10 Azure DevOps REST API
- Finalidade: leitura, pesquisa, criação e refino de work items.
- Dados enviados: WIQL e payloads de work items.
- Dados recebidos: backlog metadata, work items e estados.
- PII potencial: média.
- Jurisdição: organização Azure DevOps configurada.
- Env vars: `DEVOPS_PAT`, `DEVOPS_ORG`, `DEVOPS_PROJECT`.

### 2.11 Azure Table Storage
- Finalidade: estado da app, histórico, feedback, rate limits, jobs e auth runtime.
- PII potencial: média.
- Jurisdição: região da storage account.
- Env vars: `STORAGE_CONNECTION_STRING`, `STORAGE_ACCOUNT`, `STORAGE_KEY`.

### 2.12 Azure Blob Storage
- Finalidade: uploads, chunks, artefactos, exports e ficheiros gerados.
- PII potencial: média/alta.
- Jurisdição: região da storage account.
- Env vars: `UPLOAD_BLOB_CONTAINER_*`, `CHAT_TOOLRESULT_BLOB_CONTAINER`, `GENERATED_FILES_BLOB_CONTAINER`.

### 2.13 Figma API
- Finalidade: pesquisa e análise read-only de ficheiros, nós e fluxos Figma.
- Dados enviados: queries, URLs e IDs de ficheiros/nodes.
- Dados recebidos: metadados e estrutura de frames.
- PII potencial: baixo/médio.
- Jurisdição: SaaS Figma.
- Env vars: `FIGMA_ACCESS_TOKEN`.

### 2.14 Miro API
- Finalidade: pesquisa read-only de boards e itens Miro.
- Dados enviados: query e IDs de board.
- Dados recebidos: metadados de boards e itens.
- PII potencial: baixo/médio.
- Jurisdição: SaaS Miro.
- Env vars: `MIRO_ACCESS_TOKEN`.

### 2.15 Rerank provider
- Finalidade: rerank pós-retrieval.
- Dados enviados: query e resultados candidatos.
- Dados recebidos: scoring/ranking.
- PII potencial: média.
- Jurisdição: depende do endpoint configurado.
- Env vars: `RERANK_ENABLED`, `RERANK_ENDPOINT`, `RERANK_API_KEY`, `RERANK_MODEL`, `RERANK_AUTH_MODE`.

### 2.16 Frontend CDNs
- Serviços observados no código: `cdn.plot.ly`, `fonts.googleapis.com`, `fonts.gstatic.com`.
- Finalidade: Plotly CDN e Google Fonts.
- Dados enviados: requests de browser para assets estáticos.
- Dados recebidos: scripts/fontes.
- Risco: supply chain e disponibilidade de CDN.
- Mitigação: fallback local para Plotly em `static/vendor/plotly.min.js`.

## 3. Matriz rápida de criticidade
- Alta: Azure OpenAI, Azure Storage, Azure DevOps.
- Média: Azure AI Search, Azure Speech, Azure AI Language PII, Azure AI Content Safety, Azure AI Document Intelligence, rerank, Anthropic.
- Baixa a média: Brave, Figma, Miro, CDNs.

## 4. Classificação de dados
- Dados operacionais internos: work items, conversas, métricas e anexos de trabalho.
- Dados potencialmente sensíveis: anexos, prompts, áudio, documentos e conteúdos com PII.
- Recomendação: mascarar PII e evitar queries externas com dados pessoais.

## 5. Controles recomendados
1. Rotação periódica de segredos.
2. Revisão de jurisdição por integração externa.
3. Minimização de dados enviados a providers externos.
4. Deep health e smoke test após alterações de infraestrutura.
5. Revisão periódica do modo de governance de provider e da lista de providers externos.
