# Handoff para Claude — Debug de Uploads Presos/Lentos

## Objetivo
Perceber e corrigir, com foco prático, porque é que:

- uploads muito pequenos (`.csv` ~14 KB) ainda podem ficar presos em "A processar em background..."
- uploads maiores (`.xlsx`, `.csv`) continuam a parecer demasiado lentos ou a bloquear a conversa

O objetivo imediato nao e re-arquitetar tudo de novo. E:

1. garantir que uploads pequenos entram no caminho sincrono e ficam prontos rapidamente
2. garantir que uploads grandes nao ficam presos indefinidamente
3. manter a thread principal do projeto coerente:
   - pipeline tabular baseado em artefacto
   - menos dependencia de `RawBlobRef`
   - melhor seguranca, retencao e performance

## Estado atual resumido

### Repo / Git
- workspace: `/Users/pedromousinho/Downloads/dbde_ai_assistant-main`
- branch/HEAD atual: `6c18929`
- ultimos commits relevantes:
  - `6c18929` — `fix: unblock startup and small uploads`
  - `71d4851` — `fix: unblock small uploads and add async worker fallback`
  - `8dc1f2d` — `fix: unblock microphone headers and speech stop`
  - `349de08` — `docs: add queued roadmap to compliance assessment`

### Produção Azure confirmada
- Web App: `millennium-ai-assistant`
- RG: `rg-MS_Access_Chabot`
- runtime: `PYTHON|3.12`
- startup command atual:

```text
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

- health:
  - [https://dbdeai.pt/health](https://dbdeai.pt/health) -> `200`
- `/api/info`:
  - `version = 8.0.0`
  - `frontend_async_threshold_bytes = 2097152` (`2 MB`)
  - limites tabulares em produção:
    - `.csv = 60 MB`
    - `.tsv = 60 MB`
    - `.xlsx = 60 MB`
    - `.xlsb = 60 MB`
    - `.xls = 60 MB`

### Flags Azure relevantes
- `UPLOAD_DEDICATED_WORKER_ENABLED = false`
- `EXPORT_DEDICATED_WORKER_ENABLED = false`
- `UPLOAD_INLINE_WORKER_RUNTIME_ENABLED = true`

Isto foi alterado de proposito para simplificar o runtime e evitar warmup/startup falhado.

## Sintomas observados

### 1. CSV pequeno ainda fica preso
Exemplo real do utilizador:
- ficheiro `.csv` com ~14 KB
- UI mostra:
  - `Upload iniciado para 1 ficheiro(s)`
  - `Vou continuar a processar em background...`
  - `A processar 1 anexo(s) em background...`

Isto **nao devia acontecer** para esse tamanho, porque o frontend devia escolher o caminho sincrono.

### 2. XLSX/CSV grandes continuam lentos ou presos
- casos anteriores com `.xlsx` ~41 MB
- houve tempoouts, depois mudancas no pipeline para reduzir ingestao pesada
- objetivo ainda em aberto: tornar o comportamento operacionalmente fiavel

## Hipóteses já testadas

### Hipótese A — Limites de upload demasiado baixos
**Confirmado e corrigido parcialmente**

Antes:
- havia limites mais baixos
- e chegou a existir um limite global de body de `15 MB`

Agora:
- limite global por rota ajustado
- limites tabulares aumentados para `60 MB`

Isto **já não explica** o caso de um CSV de `14 KB`.

### Hipótese B — O frontend live estava antigo
**Parcialmente confirmada no passado**

Houve momentos em que o bundle live não estava alinhado com o código local.

Agora:
- o site serve um bundle novo compatível com o `HEAD` atual
- o comportamento, no entanto, continua a parecer de caminho assíncrono para ficheiros pequenos segundo o utilizador

Logo:
- ainda pode haver cache/sessão antiga no browser
- mas ja nao é a explicacao principal que eu escolheria sem prova

### Hipótese C — Os workers dedicados estavam a bloquear o runtime
**Confirmado**

Antes:
- o App Service arrancava com `bash startup.sh`
- isso lançava sidecars dedicados (`upload_worker.py` / `export_worker.py`)
- os logs mostraram warmup a falhar durante `600s`
- o container ficava vivo, mas o site nao passava o startup probe

Consequência:
- produção instável
- uploads podiam ficar presos por runtime inconsistente

Mitigação já aplicada:
- `startup command` simplificado para uvicorn direto
- dedicated workers desligados
- inline worker mantido

### Hipótese D — O job store fica preso em `queued`/`processing`
**Ainda muito plausível**

Os logs de `upload-worker.log` mostravam polling contínuo de `UploadJobs` sem processamento real visível:

```text
GET .../UploadJobs()?filter=PartitionKey eq 'upload' and Status eq 'queued'
```

Mesmo com sidecars desligados, continua a ser plausível que:
- jobs sejam criados
- a UI fique a fazer polling
- mas o processamento inline não esteja a avançar como esperado

### Hipótese E — A UI mantém estado zombie de `pendingUploadJobs`
**Ainda plausível**

Mesmo quando o backend melhora, a UI pode:
- manter jobs antigos na conversa
- continuar a bloquear `send()`
- continuar a mostrar "A processar..." por estado local, nao por estado real

## O que já foi corrigido

### Uploads / runtime
- `frontend_async_threshold_bytes` exposto em `/api/info`
- frontend preparado para usar sync em ficheiros pequenos
- nudge/fallback do worker assíncrono
- limites tabulares aumentados para `60 MB`
- middleware de body size ajustado por rota
- startup Azure simplificado:
  - sem sidecars dedicados
  - com inline worker

### Pipeline tabular estrutural
Muito trabalho já foi feito e **nao deve ser perdido**:

- artefacto tabular persistente
- uso de `duckdb` sobre artefacto
- menos dependencia de `RawBlobRef`
- backfill de chunks tabulares
- retenção curta do raw quando já há artefacto/chunks

Isto significa que qualquer solução nova para upload deve respeitar essa direção, e nao regressar ao modelo antigo centrado no ficheiro raw.

## O que ainda falta provar

### A. Um CSV pequeno está mesmo a ir pelo caminho errado?
É preciso provar, idealmente com logs/estado real, se para um `.csv` de 14 KB:

- o frontend está a chamar `/upload`
ou
- está a chamar `/upload/async` ou `/upload/stream/async`

Sem isso, ainda estamos parcialmente às cegas.

### B. Se o frontend estiver correto, o backend inline está a processar o job?
É preciso provar, idealmente via logs ou estado do job:

- `queued -> processing -> completed`
ou
- `queued` para sempre

### C. A conversa fica presa por job real ou por estado local da UI?
É preciso distinguir:

- `pending_jobs > 0` no backend
de
- `pendingUploadJobs.length > 0` só no estado React

## Ficheiros críticos

### Backend
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/app.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/app.py)
  - `startup_event()`
  - `INLINE_WORKER_ENABLED_EFFECTIVE`
  - `/upload`
  - `/upload/async`
  - `/upload/stream/async`
  - `/upload/batch/async`
  - `/api/upload/status/{job_id}`
  - `/api/upload/status/batch`
  - `/api/upload/pending/{conversation_id}`
  - `_nudge_upload_worker()`
  - `_upload_worker_loop()`
  - `_count_pending_jobs_for_conversation()`
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/config.py)
  - limites de ficheiros
  - `UPLOAD_FRONTEND_ASYNC_THRESHOLD_BYTES`
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/upload_worker.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/upload_worker.py)
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/startup.sh](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/startup.sh)
  - já não deve ser o entrypoint de produção

### Frontend
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/App.jsx](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/App.jsx)
  - `loadRuntimeLimits()`
  - `handleFileUpload()`
  - `send()`
  - `getPendingUploads()`
  - render do banner `A processar ...`
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/utils/uploads.js](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/utils/uploads.js)
  - `uploadSingleFileSync()`
  - `queueUploadJob()`
  - `queueUploadJobStream()`
  - `queueUploadJobsBatch()`
  - `waitUploadJob()`
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/components/ChatComposer.jsx](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/frontend/src/components/ChatComposer.jsx)

### Artefacto tabular / direção estrutural
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/tabular_artifacts.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/tabular_artifacts.py)
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/tools.py](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/tools.py)

## Comandos úteis

### Ver o startup command atual
```bash
az webapp config show -g rg-MS_Access_Chabot -n millennium-ai-assistant --query '{appCommandLine:appCommandLine,healthCheckPath:healthCheckPath,alwaysOn:alwaysOn,linuxFxVersion:linuxFxVersion}' -o json
```

### Ver flags dos workers
```bash
az webapp config appsettings list -g rg-MS_Access_Chabot -n millennium-ai-assistant \
  --query "[?name=='UPLOAD_DEDICATED_WORKER_ENABLED' || name=='EXPORT_DEDICATED_WORKER_ENABLED' || name=='UPLOAD_INLINE_WORKER_RUNTIME_ENABLED'].{name:name,value:value}" -o table
```

### Ver limites e threshold publicados
```bash
curl -sS https://dbdeai.pt/api/info
```

### Ver saúde pública
```bash
curl -sS https://dbdeai.pt/health
```

### Descarregar logs
```bash
az webapp log download -g rg-MS_Access_Chabot -n millennium-ai-assistant --log-file /tmp/dbde-current-logs.zip
```

### Logs relevantes
- `docker.log`
- `upload-worker.log`
- `export-worker.log`

### Deploy limpo do HEAD
```bash
git archive --format=zip HEAD -o /tmp/dbde-head.zip
az webapp deploy -g rg-MS_Access_Chabot -n millennium-ai-assistant --src-path /tmp/dbde-head.zip --type zip --async false
```

## O que eu faria a seguir

### Passo 1 — provar o caminho real de um CSV pequeno
Instrumentar ou inspecionar para um `.csv` de 14 KB:
- que endpoint o frontend chama
- que resposta recebe
- que `job_id` nasce, se nascer

Se for possível, usar DevTools Network ou logs.

### Passo 2 — se estiver a ir async indevidamente
Corrigir no frontend:
- garantir que ficheiros pequenos usam sempre `/upload`
- endurecer a lógica do threshold
- impedir que o estado local fique com `pendingUploadJobs` para uploads síncronos

### Passo 3 — se estiver a ir sync mas o estado ficar preso
Corrigir UI:
- limpar `pendingUploadJobs` quando o backend já não reporta pendentes
- limpar jobs locais quando a conversa é apagada
- não bloquear `send()` por estado local zombie

### Passo 4 — se o job estiver mesmo pendente
Corrigir backend:
- dar visibilidade real a `queued / processing / failed / completed`
- marcar `failed` mais agressivamente quando o processamento não avançar
- eventualmente processar em linha ficheiros pequenos, independentemente do caminho escolhido

## O que nao deve ser perdido
Nao deitar fora o trabalho já feito nesta thread:
- pipeline tabular orientado a artefacto
- uso de `duckdb`
- retenção curta do raw
- backfill de chunks
- minimização de dados e melhorias de compliance

Esse trabalho já faz sentido e não é a causa principal deste bug específico.

## Nota de governação / compliance
O assessment consolidado continua em:
- [/Users/pedromousinho/Downloads/dbde_ai_assistant-main/docs/OVERALL_DEEP_SECURITY_AND_COMPLIANCE_ASSESSMENT.md](/Users/pedromousinho/Downloads/dbde_ai_assistant-main/docs/OVERALL_DEEP_SECURITY_AND_COMPLIANCE_ASSESSMENT.md)

Esse documento já deve manter explicitamente:
- que Anthropic continua como risco conhecido e conscientemente aceite nesta fase experimental

## Pedido explícito para Claude
Não recomeçar do zero. Partir deste estado:
- produção saudável
- startup simplificado
- bundle atual alinhado com `HEAD`
- problema ainda aberto: uploads pequenos e grandes continuam a dar sensação de bloqueio/lentidão

O foco deve ser:
- provar o caminho real do frontend
- provar o estado real dos jobs
- corrigir o bloqueio mais pequeno e mais certo primeiro
- sem rebentar a direção estrutural do pipeline tabular
