# Deploy + Smoke Test (10 Min)

Contexto atual:
- sem deployment slot `staging`
- deploy direto a produção
- foco principal desta release: lane de `userstory`

## 1. Pre-deploy

- Confirmar Azure subscription certa:
  - `az account show`
- Confirmar app target:
  - `millennium-ai-assistant`
- Confirmar health atual:
  - `curl -s https://millennium-ai-assistant.azurewebsites.net/health`
- Confirmar settings críticas:
  - `az webapp config appsettings list -g rg-MS_Access_Chabot -n millennium-ai-assistant --query "[?name=='SEARCH_SERVICE' || name=='DEVOPS_INDEX' || name=='STORY_EXAMPLES_INDEX' || name=='STORY_KNOWLEDGE_INDEX' || name=='LLM_TIER_STANDARD'].{name:name,value:value}" -o table`
- Confirmar índices existentes:
  - `millennium-devops-index`
  - `millennium-story-examples-index`
  - `millennium-story-knowledge-index`
- Guardar snapshot do artefacto a deployar fora desta pasta, porque este snapshot não tem `.git`.

## 2. Go/No-Go

Só avançar se:
- `python3 -m pytest tests -q` passou
- `npm run build` passou
- `/health` atual responde `200`
- settings críticas estão presentes

No estado validado desta release:
- `337 passed`
- frontend build `OK`

## 3. Deploy

Como não há slot, fazer deploy numa janela calma e assumir restart da app.

- Fazer deploy do artefacto atual
- Esperar o restart concluir
- Ver logs se necessário:
  - `az webapp log tail -g rg-MS_Access_Chabot -n millennium-ai-assistant`

## 4. Smoke Test 10 Min

### Min 0-2: saúde básica

- `GET /health`
  - esperado: `200`
- Abrir app no browser
  - esperado: login funciona
  - esperado: shell principal carrega sem erro JS visível

### Min 2-4: chat geral

- Enviar uma pergunta simples no chat normal
  - esperado: resposta sem erro
- Validar que não há timeout imediato nem erro de auth

### Min 4-8: lane de user stories

- Abrir a workspace de user stories em [frontend/src/components/UserStoryWorkspace.jsx](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/components/UserStoryWorkspace.jsx)
- Testar `Pré-visualizar contexto`
  - objetivo exemplo:
    - `Permitir ao cliente ativar Via Verde e rever resumo antes de confirmar`
  - equipa/área:
    - `IT.DIT\DIT\ADMChannels\DBKS\AM24\RevampFEE MVP2`
  - feature:
    - `994513`
- Esperado no preview:
  - `Placement provável` resolvido
  - `Pack da feature` presente
  - `Histórias irmãs da feature` presentes
  - `Refs DevOps de proveniência` ou `Corpus curado` com contexto útil

- Testar `Gerar draft estruturado`
  - esperado:
    - título começa por `MSE |`
    - draft estruturado aparece
    - `Publish ready` coerente
    - sem erro 500

- Testar `Validar`
  - esperado:
    - validação responde
    - quality score calculado

### Min 8-10: publish controlado

- Publicar um draft de teste no DevOps
  - esperado:
    - work item criado
    - URL devolvido
    - area path correta
- Confirmar no Azure DevOps:
  - título coerente
  - descrição e AC presentes
  - parent feature correta quando aplicável

## 5. Sinais de sucesso

- app responde normalmente
- chat geral continua operacional
- lane de user stories gera sem erro
- feature pack de `994513` aparece no preview
- publish para DevOps funciona

## 6. Blockers / Abortar release

Abortar ou corrigir imediatamente se:
- `/health` falhar
- login falhar
- frontend não carregar
- `context-preview` ou `generate` der `500`
- publish no DevOps falhar de forma sistemática
- placement vier vazio para `feature=994513`

## 7. Rollback pragmático

Como não há slot:
- voltar a deployar o artefacto anterior
- confirmar `/health`
- repetir apenas smoke básico:
  - login
  - chat
  - userstory preview

## 8. Pós-release imediato

Nos primeiros minutos, observar:
- logs da app
- falhas de auth
- falhas Azure Search
- falhas DevOps
- erros na lane em [user_story_lane.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/user_story_lane.py)

## 9. Nota operacional

Não usar workflow de slot swap enquanto o App Service continuar sem slots reais.
